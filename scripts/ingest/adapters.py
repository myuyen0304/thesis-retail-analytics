"""Đọc file ngoài thành bảng chuỗi; giữ nguyên giá trị, không nạp vào pipeline."""
import codecs
import csv
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import uuid

import duckdb


def quote(name):
    """Tên cột bên ngoài chỉ được dùng như định danh SQL đã escape."""
    return '"' + name.replace('"', '""') + '"'


def normalize(name):
    return name.replace('\ufeff', '').strip().lower()


def _scan(path):
    """Kiểm UTF-8 và băm theo khối, kể cả lỗi nằm ngoài mẫu đọc của DuckDB."""
    digest = hashlib.sha256()
    decoder = codecs.getincrementaldecoder('utf-8')('strict')
    offset = 0
    with path.open('rb') as stream:
        has_bom = stream.read(3) == codecs.BOM_UTF8
        stream.seek(0)
        while block := stream.read(1024 * 1024):
            pending = len(decoder.getstate()[0])
            try:
                decoder.decode(block)
            except UnicodeDecodeError as exc:
                raise ValueError(f'{path.name}: không phải UTF-8 tại byte {offset - pending + exc.start}') from exc
            digest.update(block)
            offset += len(block)
        try:
            decoder.decode(b'', final=True)
        except UnicodeDecodeError as exc:
            raise ValueError(f'{path.name}: UTF-8 chưa đủ byte tại byte {offset - len(decoder.getstate()[0])}') from exc
    return has_bom, digest.hexdigest()


def _check_columns(columns):
    names = [normalize(c) for c in columns]
    if any(not c for c in names) or len(set(names)) != len(names):
        raise ValueError('Tên cột rỗng hoặc trùng sau chuẩn hóa; không tự đổi tên cột')


@dataclass
class FileTable:
    name: str
    path: Path
    format: str
    encoding: str
    has_bom: bool
    sha256: str
    n_rows: int
    columns: list
    con: object
    table: str
    owns_connection: bool

    def close(self):
        self.con.execute(f'drop table if exists {quote(self.table)}')
        if self.owns_connection:
            self.con.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def read_file(path, con=None):
    """CSV/JSON → bảng tạm DuckDB toàn VARCHAR; người gọi đóng FileTable sau khi dùng."""
    path = Path(path)
    kind = path.suffix.lower().lstrip('.')
    if kind not in ('csv', 'json'):
        raise ValueError(f'{path.name}: chỉ hỗ trợ CSV hoặc JSON')
    has_bom, sha256 = _scan(path)
    encoding = 'utf-8-sig' if has_bom else 'utf-8'
    owns = con is None
    con = con if con is not None else duckdb.connect(config={'threads': 4})
    table = 'input_' + uuid.uuid4().hex
    raw = table + '_json'
    try:
        if kind == 'csv':
            with path.open(encoding=encoding, newline='') as stream:
                columns = next(csv.reader(stream), [])
            _check_columns(columns)
            if not columns:
                raise ValueError(f'{path.name}: CSV không có header')
            con.execute(f'create temp table {quote(table)} as select * from read_csv(?, '
                        'header=true, all_varchar=true, delim=\',\', names=?, strict_mode=true)',
                        [str(path), columns])
        else:
            # json chỉ giải mã/kiểm cấu trúc. Chuyển giá trị và hợp khóa chạy bằng SQL.
            content = path.read_text(encoding=encoding)
            def unique_object(pairs):
                result = {}
                for key, value in pairs:
                    if key in result:
                        raise ValueError(f'{path.name}: Khóa JSON trùng {key!r}; không tự chọn giá trị')
                    result[key] = value
                return result

            parsed = json.loads(content, object_pairs_hook=unique_object)
            if not isinstance(parsed, list) or not all(isinstance(r, dict) for r in parsed):
                raise ValueError(f'{path.name}: JSON phải là mảng đối tượng ở cấp ngoài cùng')
            del parsed
            con.execute(f'create temp table {quote(raw)} as '
                        'select cast(key as bigint) as ordinal, value as obj from json_each(?)', [content])
            columns = [r[0] for r in con.execute(
                f'select j.key from {quote(raw)} r, lateral json_each(r.obj) j group by j.key '
                'order by min(struct_pack(rownum := r.ordinal, fieldnum := j.id))').fetchall()]
            _check_columns(columns)
            if columns:
                expressions = []
                for col in columns:
                    expressions.append('max(case when j.key = ? then case '
                                       "when j.type = 'NULL' then null when j.type = 'VARCHAR' "
                                       "then json_extract_string(j.value, '$') else cast(j.value as varchar) end end) as "
                                       + quote(col))
                con.execute(f'create temp table {quote(table)} as select ' + ', '.join(expressions)
                            + f' from {quote(raw)} r left join lateral json_each(r.obj) j on true '
                            'group by r.ordinal order by r.ordinal', columns)
            else:
                # DuckDB không có bảng không cột; cột nội bộ không xuất vào siêu dữ liệu.
                con.execute(f'create temp table {quote(table)} as select cast(null as varchar) as _empty '
                            f'from {quote(raw)}')
            con.execute(f'drop table {quote(raw)}')
        n_rows = con.execute(f'select count(*) from {quote(table)}').fetchone()[0]
        return FileTable(path.name, path, kind, encoding, has_bom, sha256, n_rows, columns, con, table, owns)
    except Exception:
        con.execute(f'drop table if exists {quote(raw)}')
        con.execute(f'drop table if exists {quote(table)}')
        if owns:
            con.close()
        raise
