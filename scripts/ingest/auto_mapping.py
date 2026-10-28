"""Sinh đề xuất ánh xạ có bằng chứng, không đọc phê duyệt và không nạp dữ liệu."""
import argparse
from collections import Counter
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
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
    return {'so_gia_tri': distinct, 'so_rong': empty,
            'ty_le_rong': round(empty / data.n_rows, 4) if data.n_rows else 0.0,
            'mau': samples, 'so_giong_dien_thoai': phone, 'so_khac_rong': nonempty}


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
        return {'phien_ban': 1, 'sinh_luc_utc': datetime.now(timezone.utc).isoformat(timespec='microseconds').replace('+00:00', 'Z'),
                'file': {'ten': data.name, 'sha256': data.sha256, 'dinh_dang': data.format, 'encoding': data.encoding,
                         'co_bom': data.has_bom, 'so_dong': data.n_rows, 'so_cot': len(data.columns)},
                'nguon': source,
                'schema_diff': {'loai': diff['kind'], 'doi_thu_tu': diff['order_changed'], 'cot_khop': diff['matched'],
                                'cot_them': diff['added'], 'cot_thieu': diff['missing'], 'ung_vien_doi_ten': diff['rename_candidates']},
                'cot': columns, 'thuc_the_moi': entities, 'tham_chieu_thieu': absent}


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
            lines.append('- Thiếu file tham chiếu, chưa kiểm được các đường tương ứng: ' + ', '.join(body['tham_chieu_thieu']) + '.')
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
