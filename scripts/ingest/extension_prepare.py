"""Kiểm nguồn mở rộng bằng SQL, giữ bằng chứng và đánh lại số dòng phần nhận."""
import hashlib
from pathlib import Path

import duckdb

from scripts.ingest.adapters import quote, read_file
from scripts.ingest.extension_contract import load, loaded_columns
from scripts.ingest.source_contract import COLUMNS
from scripts.pipeline.contract import SAMPLE

R1 = 'R1_khoa_sai'
R2 = 'R2_trung_khoa'
R3 = 'R3_mo_coi'
R4 = 'R4_lech_loi'
R5 = 'R5_gia_tri_sai'
R6 = 'R6_mau_thuan_thuc_the'


def digest(path, kind='sha256'):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, kind).hexdigest()


class QuarantineError(ValueError):
    """Mang bằng chứng tới đường ghi quarantine hiện có của CLI."""

    def __init__(self, name, rejected, total, tolerance, summary, evidence):
        super().__init__(f'{name}: cách ly {rejected}/{total} dòng, vượt ngưỡng {tolerance}')
        self.summary = {name: summary}
        self.evidence = {name: evidence}


def _value(col, alias=None):
    expr = (alias + '.' if alias else '') + quote(col)
    return f"nullif(trim({expr}), '')"


def _typed(col, kind, alias=None):
    expr = _value(col, alias)
    return expr if kind == 'string' else f'try_cast({expr} as {kind})'


def prepare(doc, data, ready):
    """Chỉ ghi parquet sau khi kiểm header, các lý do R1–R6 và ngưỡng."""
    name = doc['ten']
    source = Path(data) / doc['file']
    ready = Path(ready)
    with read_file(source) as table:
        con = table.con
        if table.columns != doc['header']:
            added = sorted(set(table.columns) - set(doc['header']))
            missing = sorted(set(doc['header']) - set(table.columns))
            raise ValueError(f'{name}: header sai (thêm {added}, thiếu {missing}, kiểm cả thứ tự); '
                             'chạy lại scripts.ingest.auto_mapping rồi duyệt lại')
        if not table.n_rows:
            raise ValueError(f'{name}: file 0 dòng')
        con.execute(f'create temp table original as select row_number() over () as _dong_goc, * '
                    f'from {quote(table.table)}')
        con.execute('create temp table normalized as select _dong_goc, '
                    + ', '.join(f'{_value(c)} as {quote(c)}' for c in table.columns) + ' from original')
        link = doc['khoa_noi']
        key, core_key = link['cot'], link['cot_nguon']
        kind = COLUMNS[link['nguon']][core_key][0]
        con.execute('create temp table core as select * from read_parquet(?)',
                    [str(ready / (link['nguon'] + '.parquet'))])
        con.execute('create temp table bad (_dong_goc bigint, ly_do varchar, cot varchar)')

        def add(condition, reason, col, relation='normalized'):
            con.execute(f'insert into bad select _dong_goc, ?, ? from '
                        f'(select *, {condition} as invalid from {relation}) where invalid', [reason, col])

        typed_key = _typed(key, kind)
        add(f'{typed_key} is null', R1, key)
        add(f'{typed_key} is not null and count(*) over (partition by {typed_key}) > 1', R2, key)
        nkey, ckey = _typed(key, kind, 'n'), _typed(core_key, kind, 'c')
        con.execute(f'insert into bad select n._dong_goc, ?, ? from normalized n '
                    f'where {nkey} is not null and not exists (select 1 from core c where {ckey} = {nkey})',
                    [R3, key])
        for col in doc['cot']:
            column = col['ten']
            if col['xu_ly'] == 'doi_chieu_loi':
                core_kind = COLUMNS[link['nguon']][column][0]
                con.execute(f'insert into bad select n._dong_goc, ?, ? from normalized n join core c '
                            f'on {nkey} = {ckey} where {_typed(column, core_kind, "n")} '
                            f'is distinct from {_typed(column, core_kind, "c")}', [R4, column])
            elif col['xu_ly'] == 'nap':
                value = quote(column)
                invalid = f'{value} is null' if not col['duoc_rong'] else 'false'
                if col['kieu'] != 'string':
                    invalid += f' or ({value} is not null and {_typed(column, col["kieu"])} is null)'
                add(invalid, R5, column)
        con.execute('create temp table eligible as select * from normalized '
                    'where _dong_goc not in (select _dong_goc from bad)')
        for entity in doc['thuc_the']:
            ek = quote(entity['khoa'])
            conflicts = ' or '.join(f'count(distinct {quote(c)}) + '
                                   f'cast(count(*) > count({quote(c)}) as integer) > 1'
                                   for c in entity['thuoc_tinh'])
            con.execute(f'insert into bad select _dong_goc, ?, ? from eligible where {ek} in '
                        f'(select {ek} from eligible group by {ek} having {conflicts})',
                        [R6, entity['khoa']])
        rejected = con.execute('select count(distinct _dong_goc) from bad').fetchone()[0]
        summary = dict(con.execute('select ly_do, count(distinct _dong_goc) from bad '
                                   'group by ly_do order by ly_do').fetchall())
        con.execute(f'create temp table samples as select * exclude (rn) from '
                    f'(select *, row_number() over (partition by ly_do order by _dong_goc, cot) rn from bad) '
                    f'where rn <= {SAMPLE}')
        if digest(source) != table.sha256:
            raise ValueError(f'{name}: nguồn đổi trong lúc đọc')
        tolerance = doc['nguong_cach_ly']
        if rejected / table.n_rows > tolerance:
            cur = con.execute('select b.ly_do, b.cot, o._dong_goc as _src_row, o.* '
                              'from samples b join original o using (_dong_goc) order by b.ly_do, b._dong_goc, b.cot')
            header = [d[0] for d in cur.description][2:]
            evidence = (header, [(r[0], r[1], r[2:]) for r in cur.fetchall()])
            raise QuarantineError(name, rejected, table.n_rows, tolerance, summary, evidence)
        selected = loaded_columns(doc)
        parquet = ready / f'{name}.parquet'
        con.execute('copy (select ' + ', '.join(f"nullif({quote(c)}, '') as {quote(c)}" for c in selected)
                    + ', row_number() over (order by _dong_goc) as _src_row, _dong_goc from original '
                    'where _dong_goc not in (select _dong_goc from bad) order by _dong_goc) '
                    'to ? (format parquet)', [str(parquet)])
        quarantine = ready / 'cach_ly' / f'{name}.csv'
        quarantine.parent.mkdir(exist_ok=True)
        con.execute('copy (select b._dong_goc, b.ly_do, b.cot, o.* exclude (_dong_goc) '
                    'from samples b join original o using (_dong_goc) order by b.ly_do, b._dong_goc, b.cot) '
                    'to ? (format csv, header true)', [str(quarantine)])
        return {'header': selected, 'rows': table.n_rows - rejected, 'csv_sha256': table.sha256,
                'csv_md5': digest(source, 'md5'), 'parquet_sha256': digest(parquet),
                'mo_rong': True, 'file': doc['file'], 'hop_dong_sha256': doc['hop_dong_sha256'],
                'so_dong_file': table.n_rows, 'so_dong_cach_ly': rejected, 'cach_ly': summary,
                'cach_ly_sha256': digest(quarantine)}


def validate(path, name, entry, directory=None):
    """Kiểm lại hợp đồng, hash và thứ tự dòng bằng DuckDB, không tải toàn bảng vào Python."""
    doc = load(name, directory)
    selected = loaded_columns(doc)
    path = Path(path)
    parquet, quarantine = path / f'{name}.parquet', path / 'cach_ly' / f'{name}.csv'
    if (entry['hop_dong_sha256'] != doc['hop_dong_sha256'] or entry['header'] != selected
            or entry['file'] != doc['file']
            or digest(parquet) != entry['parquet_sha256']
            or not quarantine.is_file() or digest(quarantine) != entry['cach_ly_sha256']):
        raise ValueError(f'{name}: hợp đồng/header/hash/cach_ly không khớp')
    total, rejected, rows = entry['so_dong_file'], entry['so_dong_cach_ly'], entry['rows']
    if (any(type(n) is not int for n in (total, rejected, rows)) or total <= 0 or rejected < 0
            or rows + rejected != total or rejected / total > doc['nguong_cach_ly']):
        raise ValueError(f'{name}: số dòng/ngưỡng không khớp')
    with duckdb.connect(config={'threads': 4}) as con:
        con.execute('create temp table accepted as select * from read_parquet(?)', [str(parquet)])
        header = [r[0] for r in con.execute('describe accepted').fetchall()]
        stats = con.execute('select count(*), count(distinct _src_row), min(_src_row), max(_src_row) '
                            'from accepted').fetchone()
        invalid = con.execute('select count(*) from (select *, lag(_dong_goc) over (order by _src_row) prev '
                              'from accepted) where _dong_goc is null or _dong_goc < 1 or _dong_goc > ? '
                              'or _dong_goc <= prev', [total]).fetchone()[0]
    if header != selected + ['_src_row', '_dong_goc'] or stats != (rows, rows, 1, rows) or invalid:
        raise ValueError(f'{name}: cột hoặc định danh dòng không khớp')
