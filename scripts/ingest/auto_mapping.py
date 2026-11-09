"""Sinh đề xuất ánh xạ có bằng chứng, không đọc phê duyệt và không nạp dữ liệu."""
import argparse
from collections import Counter
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
import re
import sys

import duckdb
import yaml

from scripts.ingest.adapters import normalize, quote, read_file
from scripts.ingest.schema_diff import compare_columns, infer_types
from scripts.ingest.source_contract import COLUMNS, KEYS, SOURCES

# Độ phủ hợp đồng là tín hiệu chính; độ chính xác và khóa phân biệt bảng rộng/bảng con.
SOURCE_WEIGHTS = {'coverage': 0.55, 'precision': 0.25, 'unique_key': 0.15, 'filename': 0.05}
SOURCE_MIN_SCORE = 0.55       # Một vài tên trùng không đủ để đề xuất nguồn.
SOURCE_MIN_MARGIN = 0.08     # Điểm gần nhau thì đưa BA quyết, không phá hòa bằng thứ tự.
REDUNDANT_MIN_RATIO = 0.999  # Chấp nhận tối đa 0,1% lệch, vẫn ghi tử số/mẫu số cho BA.
PHONE_MIN_RATIO = 0.5       # Phải quá nửa số giá trị không rỗng giống điện thoại.
SAMPLE_LIMIT = 5
GIA_TRI_LA_HE_SO = 10
LUAT_SUA_TY_LE = 0.9
LUAT_SUA_KHOP = 0.99
THAM_CHIEU_CON = {'promotions': [('order_items', 'promo_id'), ('order_items', 'promo_id_2')],
                 'products': [('order_items', 'product_id'), ('inventory', 'product_id')],
                 'customers': [('orders', 'customer_id')]}
PII_ID_WORDS = frozenset({'name', 'phone', 'email', 'address', 'birth', 'age', 'gender', 'ten', 'sdt'})
PII_SENSITIVE_WORDS = frozenset({'marital', 'education'})
PHONE_PATTERN = r'[+0-9 ()-]+'
ENTITY_NOTE = 'BA quyết: bảng 3NF mới, dim mới hay dừng ở silver'


def _value(col, alias=None):
    ref = (alias + '.' if alias else '') + quote(col)
    return f"nullif(trim({ref}), '')"


def key_evidence(data, columns):
    """Khóa đơn/ghép chỉ được thưởng điểm khi đầy đủ, không rỗng, không trùng."""
    names = {normalize(c): c for c in data.columns}
    if not columns or any(normalize(k) not in names for k in columns):
        return {'co_mat': False, 'khong_trung': False}
    values = [_value(names[normalize(k)]) for k in columns]
    nulls = data.con.execute(f'select count(*) from {quote(data.table)} where '
                             + ' or '.join(f'{v} is null' for v in values)).fetchone()[0]
    distinct = data.con.execute('select count(*) from (select distinct ' + ', '.join(values)
                                + f' from {quote(data.table)})').fetchone()[0]
    return {'co_mat': True, 'so_khoa': distinct, 'khoa_rong': nulls,
            'khong_trung': bool(data.n_rows and not nulls and distinct == data.n_rows)}


def score_sources(data):
    """Ghi mọi nguồn có cột trùng; tên file chỉ có trọng số nhỏ."""
    present = {normalize(c) for c in data.columns}
    scores = []
    for name, (columns, _) in SOURCES.items():
        overlap = len(present & {normalize(c) for c in columns})
        if not overlap:
            continue
        key = key_evidence(data, KEYS.get(name))
        signals = {'coverage': overlap / len(columns), 'precision': overlap / len(present),
                   'unique_key': float(key['khong_trung']),
                   'filename': SequenceMatcher(None, normalize(data.path.stem), name).ratio()}
        score = sum(SOURCE_WEIGHTS[k] * v for k, v in signals.items())
        scores.append({'nguon': name, 'diem': round(score, 4), 'so_cot_trung': overlap,
                       'tin_hieu': {k: round(v, 4) for k, v in signals.items()}, 'khoa': key})
    scores.sort(key=lambda r: (-r['diem'], r['nguon']))
    chosen = 'chua_ro'
    if scores and scores[0]['diem'] >= SOURCE_MIN_SCORE:
        second = scores[1]['diem'] if len(scores) > 1 else 0
        if scores[0]['diem'] - second >= SOURCE_MIN_MARGIN:
            chosen = scores[0]['nguon']
    return {'de_xuat': chosen, 'trang_thai': 'de_xuat', 'diem': scores}


def column_profile(data, col):
    value = _value(col)
    distinct, empty, phone, nonempty = data.con.execute(
        f'select count(distinct {value}), count(*) filter(where {value} is null), '
        f'count(*) filter(where regexp_full_match({value}, ?) '
        f"and length(regexp_replace({value}, '[^0-9]', '', 'g')) between 9 and 12 "
        f"and (regexp_matches({value}, '[+ -]') or starts_with({value}, '0'))), "
        f'count({value}) from {quote(data.table)}', [PHONE_PATTERN]).fetchone()
    samples = [r[0] for r in data.con.execute(
        f'select {value} as v from {quote(data.table)} where {value} is not null '
        f'group by 1 order by count(*) desc, v limit {SAMPLE_LIMIT}').fetchall()]
    integer_count = data.con.execute(
        f'select count(*) from {quote(data.table)} where {value} is not null '
        f"and try_cast({value} as integer) is not null and regexp_full_match({value}, '-?(0|[1-9][0-9]*)')"
    ).fetchone()[0]
    profile = {'so_gia_tri': distinct, 'so_rong': empty,
            'ty_le_rong': round(empty / data.n_rows, 4) if data.n_rows else 0.0,
            'mau': samples, 'so_giong_dien_thoai': phone, 'so_khac_rong': nonempty}
    profile['kieu_goi_y'] = ('integer' if nonempty and integer_count == nonempty
                            and not pii_reasons(col, profile) else 'string')
    return profile


def pii_reasons(col, profile):
    words = set(normalize(col).split('_'))
    reasons = []
    for label, vocabulary in [('định danh', PII_ID_WORDS), ('thuộc tính cá nhân nhạy cảm', PII_SENSITIVE_WORDS)]:
        matched = sorted(words & vocabulary)
        if matched:
            reasons.append(f"{label}: từ {', '.join(matched)}")
    n = profile['so_khac_rong']
    if n and profile['so_giong_dien_thoai'] / n > PHONE_MIN_RATIO:
        reasons.append(f"định danh: mẫu số điện thoại ({profile['so_giong_dien_thoai']}/{n})")
    return '; '.join(reasons)


def redundant_paths(data, added, data_dir):
    """Chỉ nối trực tiếp qua khóa đơn, duy nhất; không suy đường nối nhiều chặng."""
    names = {normalize(c): c for c in data.columns}
    paths = {c: [] for c in added}
    absent = []
    for source in sorted(SOURCES):
        key = KEYS.get(source)
        if not key or len(key) != 1 or normalize(key[0]) not in names:
            continue
        contract = {normalize(c) for c in SOURCES[source][0]}
        candidates = [c for c in added if normalize(c) in contract and normalize(c) != normalize(key[0])]
        if not candidates:
            continue
        path = Path(data_dir) / f'{source}.csv'
        if not path.exists():
            absent.append(source)
            continue
        with read_file(path, con=data.con) as ref:
            ref_names = {normalize(c): c for c in ref.columns}
            if not key_evidence(ref, key)['khong_trung']:
                continue
            left_key = _value(names[normalize(key[0])], 'f')
            right_key = _value(ref_names[normalize(key[0])], 'r')
            candidates = [c for c in candidates if normalize(c) in ref_names]
            if not candidates:
                continue
            exprs = [f'count(*) filter(where {right_key} is not null and '
                     f'{_value(c, "f")} is not distinct from {_value(ref_names[normalize(c)], "r")})'
                     for c in candidates]
            counts = data.con.execute('select ' + ', '.join(exprs)
                                      + f' from {quote(data.table)} f left join {quote(ref.table)} r '
                                      + f'on {left_key} = {right_key}').fetchone()
            for col, count in zip(candidates, counts):
                if data.n_rows and count / data.n_rows >= REDUNDANT_MIN_RATIO:
                    paths[col].append({'nguon': source, 'khoa_noi': key[0], 'khop': count, 'tong': data.n_rows})
    for evidence in paths.values():
        evidence.sort(key=lambda r: (-r['khop'], r['nguon'], r['khoa_noi']))
    return paths, absent


def entity_candidates(data, remaining):
    """Kiểm FD trên khóa không rỗng; NULL của thuộc tính vẫn là một giá trị cần kiểm."""
    entities = []
    for key in remaining:
        if not normalize(key).endswith('_id'):
            continue
        attrs = [c for c in remaining if c != key and not normalize(c).endswith('_id')]
        if not attrs:
            continue
        value = _value(key)
        n_keys, empty = data.con.execute(f'select count(distinct {value}), '
                                        f'count(*) filter(where {value} is null) from {quote(data.table)}').fetchone()
        counts = [f'count(distinct {_value(c)}) + cast(bool_or({_value(c)} is null) as integer) as {quote("v" + str(i))}'
                  for i, c in enumerate(attrs)]
        sums = ', '.join(f'count(*) filter(where {quote("v" + str(i))} > 1)' for i in range(len(attrs)))
        violations = data.con.execute(f'select {sums} from (select ' + ', '.join(counts)
                                     + f' from {quote(data.table)} where {value} is not null group by {value})').fetchone()
        bad = dict(zip(attrs, violations))
        good = [c for c in attrs if bad[c] == 0]
        if n_keys and good:
            entities.append({'ten_de_xuat': normalize(key)[:-3], 'khoa': key, 'thuoc_tinh': good,
                             'so_khoa': n_keys, 'khoa_rong': empty, 'vi_pham': bad,
                             'ghi_chu': ENTITY_NOTE, 'trang_thai': 'de_xuat'})
    # Nhiều id cùng giải thích một cột: chọn id ít giá trị nhất (ít nguy cơ FD tầm thường), rồi tên.
    entities.sort(key=lambda e: (e['so_khoa'], e['khoa']))
    assigned = set()
    result = []
    for entity in entities:
        attrs = [c for c in entity['thuoc_tinh'] if c not in assigned]
        if attrs:
            entity['thuoc_tinh'] = attrs
            assigned.update(attrs)
            result.append(entity)
    return result


def key_conflicts(data, source, data_dir):
    """So thuộc tính theo schema_evolution §5, cell 20–21 (0-based).

    Chuỗi trim/rỗng; số thực so sai số < 1e-6, khóa số ép theo hợp đồng.
    """
    keys = KEYS.get(source) or ()
    names = {normalize(c): c for c in data.columns}
    if len(keys) != 1 or normalize(keys[0]) not in names:
        return {'da_kiem': False, 'ly_do': 'Nguồn chưa rõ hoặc không có khóa đơn trong file'}
    path = Path(data_dir) / f'{source}.csv'
    if not path.exists():
        return {'da_kiem': False, 'ly_do': 'Thiếu file tham chiếu'}
    key = keys[0]
    with read_file(path, con=data.con) as ref:
        attrs = [c for c in COLUMNS[source] if c != key and normalize(c) in names]
        if not attrs:
            return {'da_kiem': False, 'ly_do': 'Không có thuộc tính chung ngoài khóa'}
        def value(col, alias):
            return _value(names[normalize(col)] if alias == 'f' else col, alias)
        def key_value(alias):
            return f'try_cast({value(key, alias)} as {COLUMNS[source][key][0]})'
        comparisons = []
        for col in attrs:
            left, right = value(col, 'f'), value(col, 'r')
            kind = COLUMNS[source][col][0]
            if kind == 'double' or kind.startswith('decimal'):
                comparisons.append(f'abs(try_cast({left} as double) - try_cast({right} as double)) < 1e-6')
            else:
                comparisons.append(f'{left} = {right}')
        same = ' and '.join(comparisons)
        fk, rk = key_value('f'), key_value('r')
        # LATERAL giữ đúng một dòng cho mỗi bản ghi gửi lên.
        matched = quote(data.table + '_matches')
        data.con.execute(f"""create temp table {matched} as
            select {value(key, 'f')} file_id, a.pid source_id, a.n matches,
                   b.n overlap_count, b.identical identical
            from {quote(data.table)} f,
            lateral (select count(*) n, min({value(key, 'r')}) pid from {quote(ref.table)} r where {same}) a,
            lateral (select count(*) n, count(*) filter(where {same}) identical
                     from {quote(ref.table)} r where {fk} = {rk}) b
        """)
        try:
            rows = data.con.execute(f"""select
                count(*) filter(where matches = 1),
                count(*) filter(where matches = 1 and file_id = source_id),
                count(*) filter(where overlap_count > 0),
                count(*) filter(where overlap_count > 0 and identical = 0),
                count(*) filter(where matches = 1 and file_id <> source_id),
                count(*) filter(where file_id is null),
                count(file_id) - count(distinct file_id),
                count(*) filter(where matches <> 1) from {matched}""").fetchone()
            mappings = data.con.execute(f'''select file_id, source_id from {matched}
                where matches = 1 and file_id is distinct from source_id
                order by source_id, file_id''').fetchall()
            return dict(zip(('khop_dung_1', 'khop_va_cung_id', 'id_trung_nguon',
                             'id_trung_khac_noi_dung', 'danh_lai_khoa', 'id_rong',
                             'id_trung_trong_file', 'khong_khop'), rows),
                        da_kiem=True, khoa=key, thuoc_tinh=attrs,
                        anh_xa=[{'id_trong_file': f, 'id_nguon': r} for f, r in mappings])
        finally:
            data.con.execute(f'drop table {matched}')


def extension_candidate(data, source, conflict, data_dir):
    """Chỉ đề xuất master tách riêng khi đã kiểm đủ bảng con và không có tham chiếu."""
    if (source not in THAM_CHIEU_CON or conflict.get('da_kiem') is not True
            or conflict.get('id_trung_nguon') != 0):
        return None, []
    key = KEYS[source][0]
    names = {normalize(c): c for c in data.columns}
    raw = _value(names[normalize(key)], 'f')
    if not data.con.execute(f'select count({raw}) from {quote(data.table)} f').fetchone()[0]:
        return None, []
    missing = sorted({name for name, _ in THAM_CHIEU_CON[source]
                      if not (Path(data_dir) / f'{name}.csv').is_file()})
    if missing:
        return None, missing
    kind = COLUMNS[source][key][0]
    # Gộp các khóa cùng bảng để một dòng con chỉ đếm một lần.
    children = {}
    for name, column in THAM_CHIEU_CON[source]:
        children.setdefault(name, []).append(column)
    count = 0
    for name, columns in children.items():
        with read_file(Path(data_dir) / f'{name}.csv', con=data.con) as child:
            child_names = {normalize(c): c for c in child.columns}
            if any(normalize(col) not in child_names for col in columns):
                return None, [name]
            matches = ' or '.join(f'try_cast({_value(child_names[normalize(col)], "c")} as {kind}) '
                                 f'= try_cast({raw} as {kind})' for col in columns)
            count += data.con.execute(f'''select count(*) from {quote(child.table)} c where exists
                (select 1 from {quote(data.table)} f where {matches})''').fetchone()[0]
    if count:
        return None, []
    return {'ten': source + '_ext', 'hien_thi': 'silver', 'id_chung_nguon': 0,
            'dong_con_tham_chieu': count, 'ban_ghi_giong_nguon': conflict['danh_lai_khoa'],
            'trang_thai': 'de_xuat'}, []


def unusual_values(data, columns, source, data_dir):
    """Chỉ ghi bằng chứng trên cột khớp, không sửa hoặc loại dòng."""
    path = Path(data_dir) / f'{source}.csv'
    reference = read_file(path, con=data.con) if path.is_file() else None
    result = []
    try:
        names = {normalize(c): c for c in reference.columns} if reference else {}
        for col in columns:
            if col['loai'] != 'khop':
                continue
            name, kind = col['ten_trong_file'], col['kieu_hop_dong']
            raw = _value(name)
            typed = f'try_cast({raw} as {kind})'
            item = {'cot': name}

            def evidence(condition):
                count = data.con.execute(f'select count(*) from {quote(data.table)} where {condition}').fetchone()[0]
                samples = data.con.execute(f'select {raw} v from {quote(data.table)} where {condition} '
                    f'group by 1 order by count(*) desc, v limit {SAMPLE_LIMIT}').fetchall() if count else []
                return {'so_dong': count, 'mau': [r[0] for r in samples]}

            invalid = evidence(f'{raw} is not null and {typed} is null')
            if invalid['so_dong']:
                item['khong_ep_duoc'] = invalid
            if kind in ('integer', 'double') or kind.startswith('decimal('):
                ref_col = names.get(normalize(col['cot_hop_dong']))
                if ref_col is None:
                    item['chua_kiem_mien'] = True
                else:
                    expr = f'try_cast({_value(ref_col)} as {kind})'
                    low, high = data.con.execute(f'select min({expr}), max({expr}) from {quote(reference.table)}').fetchone()
                    if low is None or high is None:
                        item['chua_kiem_mien'] = True
                    else:
                        negative = evidence(f'{typed} < 0') if low >= 0 else None
                        if negative and negative['so_dong']:
                            item['so_am'] = negative
                        threshold = high * GIA_TRI_LA_HE_SO
                        # Tham số SQL tránh chuyển DECIMAL sang float khi so ngưỡng.
                        count = data.con.execute(f'select count(*) from {quote(data.table)} where {typed} > ?', [threshold]).fetchone()[0]
                        if count:
                            samples = data.con.execute(f'select {raw} v from {quote(data.table)} where {typed} > ? '
                                f'group by 1 order by count(*) desc, v limit {SAMPLE_LIMIT}', [threshold]).fetchall()
                            item['vuot_nguong'] = {'so_dong': count, 'mau': [r[0] for r in samples],
                                                  'nguong': str(threshold)}
            if len(item) > 1:
                result.append(item)
    finally:
        if reference:
            reference.close()
    return result


def suffix_candidates(data, columns, source, data_dir):
    """Luật ứng viên có đối chứng; không áp dụng vào bảng đầu vào."""
    path = Path(data_dir) / f'{source}.csv'
    if not path.is_file():
        return []
    candidates = []
    pattern = r'\s+(\p{L}+)\s+[0-9]+$'
    with read_file(path, con=data.con) as ref:
        names = {normalize(c): c for c in ref.columns}
        for col in columns:
            if col['loai'] != 'khop' or col['kieu_hop_dong'] != 'string':
                continue
            ref_col = names.get(normalize(col['cot_hop_dong']))
            if ref_col is None:
                continue
            raw = _value(col['ten_trong_file'], 'f')
            total = data.con.execute(f'select count({raw}) from {quote(data.table)} f').fetchone()[0]
            groups = data.con.execute(f'''select regexp_extract({raw}, ?, 1) word, count(*) n
                from {quote(data.table)} f where regexp_matches({raw}, ?) group by 1 order by 1''',
                [pattern, pattern]).fetchall()
            for word, count in groups:
                if count < LUAT_SUA_TY_LE * total:
                    continue
                specific = r'\s+' + re.escape(word) + r'\s+[0-9]+$'
                matches = data.con.execute(f'''select count(*) from {quote(data.table)} f
                    where regexp_matches({raw}, ?) and exists (select 1 from {quote(ref.table)} r
                    where regexp_replace({raw}, ?, '') = {_value(ref_col, 'r')})''', [specific, specific]).fetchone()[0]
                if matches >= LUAT_SUA_KHOP * count:
                    candidates.append({'cot': col['ten_trong_file'], 'mau': specific, 'so_dong': count,
                        'tong_khac_rong': total, 'khop_sau_khi_bo': matches,
                        'trang_thai': 'de_xuat', 'da_ap_dung': False})
    return candidates


def propose(path, data_dir='data'):
    """Một cấu trúc bằng chứng duy nhất cho cả YAML và Markdown."""
    with read_file(path) as data:
        source = score_sources(data)
        name = source['de_xuat']
        expected = SOURCES[name][0] if name in SOURCES else []
        types = COLUMNS.get(name, {})
        diff = compare_columns(data.columns, expected)
        if diff['missing']:
            diff = compare_columns(data.columns, expected, infer_types(data, diff['added']), types)
        if name == 'chua_ro':
            diff['kind'] = 'chua_ro'
        paths, absent = redundant_paths(data, diff['added'], data_dir)
        remaining = [c for c in diff['added'] if not paths[c]]
        entities = entity_candidates(data, remaining)
        memberships = {c: e['ten_de_xuat'] for e in entities for c in [e['khoa'], *e['thuoc_tinh']]}
        expected_names = {normalize(c): c for c in expected}
        columns = []
        for col in data.columns:
            record = {'ten_trong_file': col}
            if col in diff['matched']:
                canonical = expected_names[normalize(col)]
                kind = types[canonical][0]
                value = _value(col)
                invalid = data.con.execute(f'select count(*) from {quote(data.table)} '
                                          f'where {value} is not null and try_cast({value} as {kind}) is null').fetchone()[0]
                record.update(loai='khop', cot_hop_dong=canonical, kieu_hop_dong=kind, khong_ep_duoc=invalid)
                if invalid:
                    record['trang_thai'] = 'de_xuat'
            else:
                profile = column_profile(data, col)
                reason = pii_reasons(col, profile)
                record.update(trang_thai='de_xuat', nghi_pii=bool(reason), ly_do_pii=reason, thong_ke=profile)
                if paths[col]:
                    record.update(loai='thua', de_xuat='bo', bang_chung=paths[col])
                elif col in memberships:
                    record.update(loai='thuc_the_moi', thuc_the=memberships[col])
                else:
                    record['loai'] = 'thuoc_tinh_le'
            columns.append(record)
        conflict = key_conflicts(data, name, data_dir)
        extension, missing_children = extension_candidate(data, name, conflict, data_dir)
        absent = sorted(set(absent) | set(missing_children))
        return {'phien_ban': 1, 'sinh_luc_utc': datetime.now(timezone.utc).isoformat(timespec='microseconds').replace('+00:00', 'Z'),
                'file': {'ten': data.name, 'sha256': data.sha256, 'dinh_dang': data.format, 'encoding': data.encoding,
                         'co_bom': data.has_bom, 'so_dong': data.n_rows, 'so_cot': len(data.columns)},
                'nguon': source,
                'schema_diff': {'loai': diff['kind'], 'doi_thu_tu': diff['order_changed'], 'cot_khop': diff['matched'],
                                'cot_them': diff['added'], 'cot_thieu': diff['missing'], 'ung_vien_doi_ten': diff['rename_candidates']},
                'cot': columns, 'thuc_the_moi': entities, 'tham_chieu_thieu': absent,
                'xung_dot_khoa': conflict,
                'nguon_mo_rong_de_xuat': extension,
                'gia_tri_la': unusual_values(data, columns, name, data_dir),
                'luat_sua_ung_vien': suffix_candidates(data, columns, name, data_dir)}


def _md(value):
    """Giữ nội dung file ngoài trong ô bảng, không cho chèn HTML hoặc thêm dòng Markdown."""
    return str(value).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('|', '&#124;').replace('`', '&#96;').replace('\r', ' ').replace('\n', ' ')


def render_report(body):
    file, source, diff = body['file'], body['nguon'], body['schema_diff']
    cols = body['cot']
    lines = ['# Báo cáo đề xuất ánh xạ', '', '## 1. Tóm tắt', '',
             f"- File: {_md(file['ten'])}; {file['so_dong']} dòng, {file['so_cot']} cột.",
             f"- Nguồn đề xuất: {source['de_xuat']}.",
             '- Hai nguồn đầu: ' + '; '.join(f"{s['nguon']} = {s['diem']:.4f}" for s in source['diem'][:2]) + '.',
             f"- Schema: {diff['loai']}; đổi thứ tự tương đối: {'có' if diff['doi_thu_tu'] else 'không'}.",
             f"- BOM UTF-8: {'có' if file['co_bom'] else 'không'}; encoding: {file['encoding']}.",
             f"- Cột khớp: {len(diff['cot_khop'])}; cột thêm: {len(diff['cot_them'])}; cột thiếu: {len(diff['cot_thieu'])}."]
    if source['de_xuat'] == 'chua_ro' or diff['cot_thieu'] or diff['ung_vien_doi_ten'] or body['tham_chieu_thieu']:
        lines += ['', '## 2. Cần làm rõ', '']
        if source['de_xuat'] == 'chua_ro':
            lines.append('- Chưa đủ bằng chứng chọn nguồn; BA quyết nguồn logic.')
        if diff['cot_thieu']:
            lines.append('- Cột thiếu: ' + ', '.join(map(_md, diff['cot_thieu'])) + '.')
        for c in diff['ung_vien_doi_ten']:
            lines.append(f"- Ứng viên {_md(c['ung_vien'])} → {_md(c['cot_thieu'])}: {c['diem']:.4f}; kiểu {c['kieu_suy_duoc']}. Chưa áp dụng.")
        if body['tham_chieu_thieu']:
            lines.append('- Thiếu file tham chiếu, chưa kiểm được các đường tương ứng: ' + ', '.join(map(_md, body['tham_chieu_thieu'])) + '.')
    lines += ['', '## 3. Nghi PII', '']
    pii = [c for c in cols if c.get('nghi_pii')]
    lines += [f"- {_md(c['ten_trong_file'])}: {_md(c['ly_do_pii'])}." for c in pii] or ['Không phát hiện theo các luật hiện có.']
    lines += ['', '## 4. Thực thể mới', '']
    for e in body['thuc_the_moi']:
        lines += [f"- {_md(e['ten_de_xuat'])}: khóa {_md(e['khoa'])}, {e['so_khoa']} giá trị phân biệt, {e['khoa_rong']} dòng rỗng.",
                  '- Thuộc tính: ' + ', '.join(map(_md, e['thuoc_tinh'])) + '.',
                  '- Số khóa vi phạm từng phụ thuộc hàm: ' + '; '.join(f'{_md(k)} = {v}' for k, v in e['vi_pham'].items()) + '.',
                  '- ' + e['ghi_chu'] + '.']
    if not body['thuc_the_moi']:
        lines.append('Không có đề xuất thực thể mới.')
    lines += ['', '## 5. Cột thừa', '']
    redundant = [c for c in cols if c['loai'] == 'thua']
    for c in redundant:
        evidence = '; '.join(f"{p['nguon']} qua {p['khoa_noi']}: {p['khop']}/{p['tong']} dòng khớp" for p in c['bang_chung'])
        lines.append(f"- {_md(c['ten_trong_file'])}: {evidence}. Đề xuất bỏ.")
    if not redundant:
        lines.append('Không có cột đủ bằng chứng thừa.')
    lines += ['', '## 6. Thuộc tính lẻ', '']
    singles = [c for c in cols if c['loai'] == 'thuoc_tinh_le']
    for c in singles:
        p = c['thong_ke']
        lines += [f"- {_md(c['ten_trong_file'])}: {p['so_gia_tri']} giá trị phân biệt, {p['so_rong']} dòng rỗng ({p['ty_le_rong']:.2%}).",
                  '- Mẫu (tần suất giảm dần, rồi giá trị): ' + '; '.join(map(_md, p['mau'])) + '.']
    if not singles:
        lines.append('Không có thuộc tính lẻ.')
    lines += ['', '## 7. Cột khớp', '', '| Cột trong file | Cột hợp đồng | Kiểu | Không ép được |', '|---|---|---|---:|']
    for c in cols:
        if c['loai'] == 'khop':
            lines.append(f"| {_md(c['ten_trong_file'])} | {_md(c['cot_hop_dong'])} | {c['kieu_hop_dong']} | {c['khong_ep_duoc']} |")
    suggestions = [c for c in cols if c.get('thong_ke', {}).get('kieu_goi_y') == 'integer']
    if suggestions:
        lines += ['', '## 7a. Gợi ý kiểu', '']
        lines += [f"- {_md(c['ten_trong_file'])}: gợi ý kiểu integer vì 100% giá trị khác rỗng là số nguyên."
                  for c in suggestions]
    conflict = body.get('xung_dot_khoa', {})
    lines += ['', '## 8. Xung đột khóa', '']
    if conflict.get('da_kiem'):
        lines += [f'- {key}: {conflict[key]}.' for key in
                  ('khop_dung_1', 'khop_va_cung_id', 'id_trung_nguon', 'id_trung_khac_noi_dung', 'danh_lai_khoa')]
    else:
        lines.append(_md(conflict.get('ly_do', 'Chưa kiểm.')))
    lines += ['', '## 9. Ánh xạ khóa đề xuất', '']
    mappings = conflict.get('anh_xa', [])
    for key in ('id_rong', 'id_trung_trong_file', 'khong_khop'):
        if key in conflict:
            lines.append(f'- {key}: {_md(conflict[key])}.')
    lines.append(f'- {len(mappings)} dòng ánh xạ đề xuất; tối đa 5 dòng đầu bên dưới, bản đầy đủ trong YAML.')
    if mappings:
        lines += ['', '| Mã trong file | Mã nguồn |', '|---|---|']
        lines += [f"| {_md(r['id_trong_file'])} | {_md(r['id_nguon'])} |" for r in mappings[:5]]
    lines += ['', '## 10. Nguồn mở rộng đề xuất', '']
    extension = body.get('nguon_mo_rong_de_xuat')
    if extension:
        lines += [f'- {_md(key)}: {_md(value)}.' for key, value in extension.items()]
    else:
        lines.append('Không có đề xuất nguồn mở rộng.')
    lines += ['', '## 11. Giá trị lạ', '']
    for item in body.get('gia_tri_la', []):
        lines.append(f"- Cột {_md(item['cot'])}:")
        if item.get('chua_kiem_mien'):
            lines.append('  - Chưa kiểm miền: không có giá trị tham chiếu dùng được.')
        for key in ('khong_ep_duoc', 'so_am', 'vuot_nguong'):
            if key in item:
                evidence = item[key]
                threshold = f"; ngưỡng {_md(evidence['nguong'])}" if 'nguong' in evidence else ''
                lines.append(f"  - {key}: {_md(evidence['so_dong'])} dòng{threshold}; mẫu: "
                             + '; '.join(map(_md, evidence.get('mau', []))) + '.')
    if not body.get('gia_tri_la'):
        lines.append('Không có giá trị lạ theo các phép kiểm đã chạy.')
    lines += ['', '## 12. Luật sửa ứng viên, chưa áp dụng', '']
    for rule in body.get('luat_sua_ung_vien', []):
        lines.append(f"- Cột {_md(rule['cot'])}; mẫu {_md(rule['mau'])}: {_md(rule['so_dong'])}/"
                     f"{_md(rule['tong_khac_rong'])} dòng khác rỗng; {_md(rule['khop_sau_khi_bo'])} dòng khớp sau khi bỏ đuôi. Chỉ đề xuất.")
    if not body.get('luat_sua_ung_vien'):
        lines.append('Không có luật sửa ứng viên đủ bằng chứng.')
    lines += ['', 'Máy chỉ đề xuất; chưa có gì được nạp. Sửa `trang_thai` trong `mapping_de_xuat.yml`.', '']
    return '\n'.join(lines)


def write_proposal(body, folder):
    """Không ghi đè cả khi thư mục chứa file ngoài hai tên đầu ra."""
    folder = Path(folder)
    if folder.exists() and (not folder.is_dir() or any(folder.iterdir())):
        raise FileExistsError(f'Đầu ra đã tồn tại: {folder}')
    folder.mkdir(parents=True, exist_ok=True)
    yml = folder / 'mapping_de_xuat.yml'
    md = folder / 'bao_cao_mapping.md'
    with yml.open('x', encoding='utf-8') as stream:
        yaml.safe_dump(body, stream, allow_unicode=True, sort_keys=False)
    with md.open('x', encoding='utf-8') as stream:
        stream.write(render_report(body))
    return yml, md


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('file', type=Path)
    parser.add_argument('--data', type=Path, default=Path('data'))
    parser.add_argument('--out', type=Path)
    args = parser.parse_args(argv)
    folder = args.out or Path('warehouse/schema_review') / (args.file.stem + '_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    try:
        if folder.exists() and (not folder.is_dir() or any(folder.iterdir())):
            raise FileExistsError(f'Đầu ra đã tồn tại: {folder}')
        body = propose(args.file, args.data)
        yml, md = write_proposal(body, folder)
    except (OSError, ValueError, duckdb.Error) as exc:
        print(f'Lỗi: {exc}', file=sys.stderr)
        return 1
    print(yml)
    print(md)
    counts = Counter(c['loai'] for c in body['cot'])
    print(f"Nguồn đề xuất: {body['nguon']['de_xuat']}; " + ', '.join(f'{k}: {counts[k]}' for k in sorted(counts)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
