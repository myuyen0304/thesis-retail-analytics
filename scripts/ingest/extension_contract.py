"""Đọc ánh xạ đã duyệt; không suy đoán hay bổ sung quyết định của BA."""
import hashlib
from pathlib import Path
import re

import yaml

from scripts.ingest.source_contract import COLUMNS, SOURCES

CONTRACT_DIR = Path(__file__).with_name('extensions')
APPROVED = 'da_duyet'
ACTIONS = {'khoa_noi', 'doi_chieu_loi', 'bo', 'nap'}
DEFAULT_TOLERANCE = 0.01


def load(name, directory=None):
    """Kiểm hợp đồng và trả nội dung cùng hash độc lập CRLF/LF."""
    if not isinstance(name, str) or not re.fullmatch(r'[a-z][a-z0-9_]*', name):
        raise ValueError(f'{name}.yml: ten không hợp lệ')
    path = Path(directory or CONTRACT_DIR) / f'{name}.yml'

    def require(condition, field):
        if not condition:
            raise ValueError(f'{path.name}: {field} không hợp lệ')

    raw = path.read_bytes()
    try:
        doc = yaml.safe_load(raw)
    except yaml.YAMLError as error:
        raise ValueError(f'{path.name}: YAML không hợp lệ') from error
    require(isinstance(doc, dict), 'file')
    require(doc.get('ten') == name and name not in SOURCES, 'ten')
    require(doc.get('trang_thai') == APPROVED, 'trang_thai')
    for field in ('duyet_boi', 'ngay_duyet'):
        require(bool(doc.get(field)), field)
    file = doc.get('file')
    require(isinstance(file, str) and bool(file) and not Path(file).is_absolute()
            and '..' not in Path(file).parts and ':' not in file, 'file')
    tolerance = doc.get('nguong_cach_ly')
    require(type(tolerance) in (int, float) and 0 <= tolerance < 1, 'nguong_cach_ly')
    header, cols = doc.get('header'), doc.get('cot')
    require(isinstance(header, list) and bool(header)
            and all(isinstance(c, str) and c and not c.startswith('_') for c in header)
            and len(set(c.lower() for c in header)) == len(header), 'header')
    require(isinstance(cols, list) and all(isinstance(c, dict) for c in cols), 'cot')
    require(len(cols) == len(header) and {c.get('ten') for c in cols} == set(header), 'header/cot')
    link = doc.get('khoa_noi')
    require(isinstance(link, dict) and link.get('nguon') in SOURCES, 'khoa_noi.nguon')
    core = COLUMNS[link['nguon']]
    require(link.get('cot') in header and link.get('cot_nguon') in core, 'khoa_noi.cot')
    by_name = {c['ten']: c for c in cols}
    require([c['ten'] for c in cols if c.get('xu_ly') == 'khoa_noi'] == [link['cot']], 'khoa_noi')
    for col in cols:
        field = 'cot.' + col['ten']
        require(col.get('trang_thai') == APPROVED, field + '.trang_thai')
        require(col.get('xu_ly') in ACTIONS, field + '.xu_ly')
        if col['xu_ly'] == 'doi_chieu_loi':
            require(col['ten'] in core, field + '.doi_chieu_loi')
        elif col['xu_ly'] in ('nap', 'khoa_noi'):
            kind = col.get('kieu', '')
            valid = kind in ('string', 'integer', 'date', 'double')
            match = re.fullmatch(r'decimal\((\d+),(\d+)\)', kind) if isinstance(kind, str) else None
            valid = valid or bool(match and 1 <= int(match[1]) <= 38 and 0 <= int(match[2]) <= int(match[1]))
            require(valid, field + '.kieu')
            require(type(col.get('duoc_rong')) is bool, field + '.duoc_rong')
    require(by_name[link['cot']]['kieu'] == core[link['cot_nguon']][0], 'khoa_noi.kieu')
    entities = doc.get('thuc_the', [])
    require(isinstance(entities, list), 'thuc_the')
    for entity in entities:
        require(isinstance(entity, dict), 'thuc_the')
        field = 'thuc_the.' + str(entity.get('ten'))
        require(entity.get('trang_thai') == APPROVED, field + '.trang_thai')
        attrs = entity.get('thuoc_tinh')
        require(isinstance(attrs, list) and bool(attrs), field + '.thuoc_tinh')
        require(all(c in by_name and by_name[c]['xu_ly'] == 'nap'
                    for c in [entity.get('khoa'), *attrs]), field + '.khoa/thuoc_tinh')
    doc['hop_dong_sha256'] = hashlib.sha256(raw.replace(b'\r\n', b'\n')).hexdigest()
    return doc


def loaded_columns(doc):
    """Thứ tự cột nạp theo header đã duyệt."""
    selected = {c['ten'] for c in doc['cot'] if c['xu_ly'] in ('khoa_noi', 'nap')}
    return [c for c in doc['header'] if c in selected]


def identity_suffix(entries):
    return ''.join(f"ext:{n}:{e['csv_sha256']}:{e['hop_dong_sha256']};"
                   for n, e in sorted(entries.items()))
