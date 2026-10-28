"""U9–U15 và I1–I3: bằng chứng đề xuất, CLI và dữ liệu giảng viên."""
import hashlib
from pathlib import Path
import sys

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from scripts.ingest import auto_mapping as mapping
from scripts.ingest.adapters import read_file, quote
from scripts.ingest.source_contract import SOURCES
from conftest import write_csv


def by_column(body):
    return {c['ten_trong_file']: c for c in body['cot']}


def test_u9_classification_and_all_paths(enriched):
    path, refs, columns, rows = enriched
    result = mapping.propose(path, refs)
    assert result['nguon']['de_xuat'] == 'orders'
    assert result['schema_diff']['loai'] == 'additive'
    assert result['schema_diff']['doi_thu_tu'] is False
    cols = by_column(result)
    assert [c['ten_trong_file'] for c in result['cot']] == columns
    assert cols['city']['bang_chung'] == [
        {'nguon': 'customers', 'khoa_noi': 'customer_id', 'khop': 30, 'tong': 30},
        {'nguon': 'geography', 'khoa_noi': 'zip', 'khop': 30, 'tong': 30}]
    assert cols['city']['loai'] == cols['region']['loai'] == cols['district']['loai'] == 'thua'
    assert cols['city']['de_xuat'] == 'bo'
    entity, = result['thuc_the_moi']
    assert entity['khoa'] == 'employee_id' and entity['so_khoa'] == 3 and entity['khoa_rong'] == 0
    assert entity['thuoc_tinh'] == ['employee_name', 'level', 'marital_status', 'education_level', 'years_experience']
    assert entity['vi_pham']['comment'] == 3
    assert all(entity['vi_pham'][c] == 0 for c in entity['thuoc_tinh'])
    assert cols['comment']['loai'] == 'thuoc_tinh_le'
    assert cols['comment']['thong_ke']['mau'] == ['note 0', 'note 1', 'note 2', 'note 3', 'note 4']
    assert {c['ten_trong_file'] for c in result['cot'] if c.get('nghi_pii')} == {'employee_name', 'marital_status', 'education_level'}
    assert all(cols[c]['loai'] == 'thuc_the_moi' for c in ['employee_id', *entity['thuoc_tinh']])
    assert all(c['trang_thai'] == 'de_xuat' for c in result['cot'] if c['loai'] != 'khop')
    assert entity['trang_thai'] == result['nguon']['trang_thai'] == 'de_xuat'
    assert entity['ghi_chu'] == 'BA quyết: bảng 3NF mới, dim mới hay dừng ở silver'
    scores = {s['nguon']: s for s in result['nguon']['diem']}
    assert scores['orders']['khoa']['khong_trung'] is True
    assert scores['geography']['khoa']['khong_trung'] is False
    assert scores['geography']['khoa']['so_khoa'] == 2
    with read_file(path) as data:
        assert set(scores) == {name for name, (header, _) in SOURCES.items() if set(header) & set(columns)}


def test_u10_mismatch_below_threshold(enriched):
    path, refs, columns, rows = enriched
    rows[0][columns.index('city')] = 'khác'
    write_csv(path, columns, rows)
    result = mapping.propose(path, refs)
    assert by_column(result)['city']['loai'] != 'thua'
    assert by_column(result)['region']['loai'] == 'thua'


def test_u11_no_join_key_no_redundancy(tmp_path):
    refs = tmp_path / 'refs'
    refs.mkdir()
    write_csv(refs / 'geography.csv', ['zip', 'city', 'region', 'district'], [['1', 'A', 'B', 'C']])
    path = write_csv(tmp_path / 'unknown.csv', ['city', 'region', 'district'], [['A', 'B', 'C']])
    with read_file(path) as data:
        paths, _ = mapping.redundant_paths(data, data.columns, refs)
        assert paths == {'city': [], 'region': [], 'district': []}


def test_u12_geography(tmp_path):
    path = write_csv(tmp_path / 'anonymous.csv', SOURCES['geography'][0], [['1', 'A', 'B', 'C'], ['2', 'D', 'E', 'F']])
    with read_file(path) as data:
        source = mapping.score_sources(data)
    assert source['de_xuat'] == 'geography'
    assert source['diem'][0]['khoa']['khong_trung'] is True


def test_u13_unknown_and_tied_sources(tmp_path):
    path = write_csv(tmp_path / 'unknown.csv', ['alien'], [['a']])
    result = mapping.propose(path, tmp_path)
    assert result['nguon']['de_xuat'] == 'chua_ro' and result['nguon']['diem'] == []
    assert result['schema_diff']['loai'] == 'chua_ro'
    path = write_csv(tmp_path / 'x.csv', ['Date', 'Revenue', 'COGS'], [['2022-01-01', '1', '2']])
    with read_file(path) as data:
        assert mapping.score_sources(data)['de_xuat'] == 'chua_ro'


def test_u14_cli_no_overwrite(enriched, tmp_path, capsys):
    path, refs, _, _ = enriched
    out = tmp_path / 'output'
    args = [str(path), '--data', str(refs), '--out', str(out)]
    assert mapping.main(args) == 0
    assert 'Nguồn đề xuất: orders' in capsys.readouterr().out
    proposal = out / 'mapping_de_xuat.yml'
    # Mô phỏng BA đã sửa file; lần chạy sau tuyệt đối không ghi đè.
    proposal.write_text(proposal.read_text(encoding='utf-8').replace('de_xuat', 'da_duyet'), encoding='utf-8')
    before = {p.name: p.read_bytes() for p in out.iterdir()}
    assert mapping.main(args) != 0
    assert 'Đầu ra đã tồn tại' in capsys.readouterr().err
    assert {p.name: p.read_bytes() for p in out.iterdir()} == before


def test_u14_existing_other_file_is_preserved(tmp_path):
    out = tmp_path / 'out'
    out.mkdir()
    note = out / 'ba.txt'
    note.write_text('đã duyệt', encoding='utf-8')
    assert mapping.main(['missing.csv', '--out', str(out)]) != 0
    assert list(out.iterdir()) == [note] and note.read_text(encoding='utf-8') == 'đã duyệt'


def test_u15_deterministic_yaml_and_report(enriched, tmp_path):
    path, refs, _, _ = enriched
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    bodies = [mapping.propose(path, refs) for _ in range(2)]
    texts = []
    for i, body in enumerate(bodies):
        yml, md = mapping.write_proposal(body, tmp_path / str(i))
        text = yml.read_text(encoding='utf-8')
        assert yaml.safe_load(text) == body
        assert md.read_text(encoding='utf-8') == mapping.render_report(body)
        assert str(tmp_path) not in text
        texts.append([line for line in text.splitlines() if not line.startswith('sinh_luc_utc:')])
    assert texts[0] == texts[1]
    assert mapping.render_report(bodies[0]) == mapping.render_report(bodies[1])
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before


def test_cast_errors_are_reported_not_blocked(tmp_path):
    path = write_csv(tmp_path / 'orders.csv', SOURCES['orders'][0],
                     [['1', 'wrong date', 'not int', '10', 'ok', 'cash', 'mobile', 'web']])
    result = mapping.propose(path, tmp_path)
    assert result['nguon']['de_xuat'] == 'orders'
    cols = by_column(result)
    assert cols['order_date']['khong_ep_duoc'] == cols['customer_id']['khong_ep_duoc'] == 1
    assert cols['order_date']['trang_thai'] == 'de_xuat'
    assert cols['order_id']['khong_ep_duoc'] == 0 and 'trang_thai' not in cols['order_id']
    assert 'nghi_pii' not in cols['order_source']


def test_pii_whole_words_and_phone_values(tmp_path):
    names = ['average_delivery_time', 'page_views', 'content', 'years_experience', 'reference', 'digits', 'zip',
             'marital_status', 'education_level', 'person_name']
    path = write_csv(tmp_path / 'pii.csv', names, [
        ['5', '10', 'nội dung', '9', '+84 912 345 678', '1234567890', '12345', 'single', 'college', 'An'],
        ['7', '12', 'nội dung', '8', '0912-345-678', '1234567891', '12346', 'single', 'college', 'Bình']])
    result = mapping.propose(path, tmp_path)
    cols = by_column(result)
    assert {c['ten_trong_file'] for c in result['cot'] if c.get('nghi_pii')} == {
        'reference', 'marital_status', 'education_level', 'person_name'}
    assert 'thuộc tính cá nhân nhạy cảm: từ marital' in cols['marital_status']['ly_do_pii']
    assert 'mẫu số điện thoại (2/2)' in cols['reference']['ly_do_pii']


def test_composite_key_and_no_key(tmp_path):
    path = write_csv(tmp_path / 'inventory.csv', ['snapshot_date', 'product_id', 'category'],
                     [['2022-01-01', '1', 'A'], ['2022-01-02', '1', 'A']])
    with read_file(path) as data:
        scores = {s['nguon']: s for s in mapping.score_sources(data)['diem']}
        assert scores['inventory']['khoa']['khong_trung'] is True
        assert scores['order_items']['khoa']['khong_trung'] is False
        assert mapping.redundant_paths(data, ['category'], tmp_path)[0] == {'category': []}


def test_duplicate_reference_key_cannot_multiply_evidence(enriched):
    path, refs, _, _ = enriched
    write_csv(refs / 'geography.csv', ['zip', 'city', 'region', 'district'],
              [['10', 'A', 'R1', 'D1'], ['10', 'A', 'R1', 'D1'], ['20', 'B', 'R2', 'D2']])
    cols = by_column(mapping.propose(path, refs))
    assert cols['region']['loai'] != 'thua'
    assert [p['nguon'] for p in cols['city']['bang_chung']] == ['customers']


def test_fd_null_attribute_counts_as_value(tmp_path):
    path = write_csv(tmp_path / 'fd.csv', ['employee_id', 'attribute', 'good'], [['1', 'A', 'x'], ['1', '', 'x']])
    with read_file(path) as data:
        entity, = mapping.entity_candidates(data, data.columns)
    assert entity['vi_pham'] == {'attribute': 1, 'good': 0}
    assert entity['thuoc_tinh'] == ['good']


def test_untrusted_column_names_and_markdown(tmp_path):
    name = 'x"; drop table anything; --'
    path = write_csv(tmp_path / 'outside.csv', [name, 'markup'], [['1', '<script>|\n# text']])
    result = mapping.propose(path, tmp_path)
    assert result['file']['so_dong'] == 1
    report = mapping.render_report(result)
    assert '<script>' not in report and '\n# text' not in report
    assert '&lt;script&gt;&#124; # text' in report


REAL = ROOT / 'data/student_data'


@pytest.fixture(scope='module')
def real_orders():
    if not (REAL / 'orders_enriched.csv').exists() or not (ROOT / 'data/geography.csv').exists():
        pytest.skip('Thiếu data/student_data/ hoặc bảng tham chiếu')
    return mapping.propose(REAL / 'orders_enriched.csv', ROOT / 'data')


def test_i1_real_orders_all_numbers(real_orders):
    result = real_orders
    assert result['file']['so_dong'] == 646945 and result['file']['so_cot'] == 17
    assert result['file']['co_bom'] is True and result['file']['encoding'] == 'utf-8-sig'
    assert result['nguon']['de_xuat'] == 'orders'
    diff = result['schema_diff']
    assert diff['loai'] == 'additive' and diff['doi_thu_tu'] is False
    assert diff['cot_khop'] == SOURCES['orders'][0] and len(diff['cot_them']) == 9 and not diff['cot_thieu']
    cols = by_column(result)
    assert all(cols[c]['khong_ep_duoc'] == 0 for c in SOURCES['orders'][0])
    for name in ['city', 'region', 'district']:
        assert cols[name]['loai'] == 'thua'
        assert {'nguon': 'geography', 'khoa_noi': 'zip', 'khop': 646945, 'tong': 646945} in cols[name]['bang_chung']
    assert {'nguon': 'customers', 'khoa_noi': 'customer_id', 'khop': 646945, 'tong': 646945} in cols['city']['bang_chung']
    entity, = result['thuc_the_moi']
    attrs = ['sales_employee_name', 'marital_status', 'education_level', 'years_experience']
    assert entity['ten_de_xuat'] == 'sales_employee' and entity['khoa'] == 'sales_employee_id'
    assert entity['thuoc_tinh'] == attrs and entity['so_khoa'] == 200 and entity['khoa_rong'] == 0
    assert all(entity['vi_pham'][c] == 0 for c in attrs) and entity['vi_pham']['comment'] == 200
    assert [cols[c]['thong_ke']['so_gia_tri'] for c in attrs] == [192, 2, 4, 20]
    assert cols['comment']['loai'] == 'thuoc_tinh_le'
    assert cols['comment']['thong_ke']['so_gia_tri'] == 18 and cols['comment']['thong_ke']['so_rong'] == 0
    assert {c['ten_trong_file'] for c in result['cot'] if c.get('nghi_pii')} == {
        'sales_employee_name', 'marital_status', 'education_level'}
    assert all(cols[c]['loai'] == 'thuc_the_moi' for c in attrs)
    scores = {s['nguon']: s for s in result['nguon']['diem']}
    assert scores['orders']['khoa']['so_khoa'] == 646945
    assert scores['geography']['khoa']['so_khoa'] == 29932
    assert not result['tham_chieu_thieu']


REAL_SOURCES = {**{n + '.csv': n for n in ['customers', 'geography', 'inventory', 'order_items', 'payments',
                 'products', 'promotions', 'returns', 'reviews', 'web_traffic']},
                'orders_enriched.csv': 'orders', 'shipments_realistic.csv': 'shipments',
                'epd.json': 'products', 'tf.json': 'web_traffic', 'eprom.json': 'promotions'}


@pytest.mark.parametrize('filename,expected', sorted(REAL_SOURCES.items()))
def test_i2_source_all_15(filename, expected):
    if not (REAL / filename).exists():
        pytest.skip('Thiếu data/student_data/')
    with read_file(REAL / filename) as data:
        scores = mapping.score_sources(data)
    assert scores['de_xuat'] == expected, scores
    if filename == expected + '.csv':
        assert hashlib.sha256((REAL / filename).read_bytes()).digest() == hashlib.sha256((ROOT / 'data' / filename).read_bytes()).digest()


def test_i3_shipments_without_zip():
    if not (REAL / 'shipments_realistic.csv').exists():
        pytest.skip('Thiếu data/student_data/')
    with read_file(REAL / 'shipments_realistic.csv') as data:
        assert 'zip' not in data.columns
        assert mapping.score_sources(data)['de_xuat'] == 'shipments'
        paths, _ = mapping.redundant_paths(data, ['city', 'region', 'district'], ROOT / 'data')
    assert paths == {'city': [], 'region': [], 'district': []}


def test_report_known_evidence_and_section_order(enriched):
    path, refs, _, _ = enriched
    report = mapping.render_report(mapping.propose(path, refs))
    assert '30 dòng, 18 cột' in report
    assert 'Schema: additive; đổi thứ tự tương đối: không' in report
    assert 'customers qua customer_id: 30/30 dòng khớp; geography qua zip: 30/30 dòng khớp' in report
    assert 'employee_id, 3 giá trị phân biệt, 0 dòng rỗng' in report
    assert 'comment = 3' in report and 'comment: 5 giá trị phân biệt, 0 dòng rỗng (0.00%)' in report
    assert '| order_id | order_id | integer | 0 |' in report
    headings = ['## 1. Tóm tắt', '## 3. Nghi PII', '## 4. Thực thể mới', '## 5. Cột thừa',
                '## 6. Thuộc tính lẻ', '## 7. Cột khớp']
    assert [report.index(h) for h in headings] == sorted(report.index(h) for h in headings)
    assert report.endswith('Máy chỉ đề xuất; chưa có gì được nạp. Sửa `trang_thai` trong `mapping_de_xuat.yml`.\n')


def test_sparse_source_below_threshold(tmp_path):
    path = write_csv(tmp_path / 'x.csv', ['order_date'], [['2022-01-01'], ['2022-01-02']])
    with read_file(path) as data:
        source = mapping.score_sources(data)
    assert source['diem'] and source['de_xuat'] == 'chua_ro'


def test_cli_unknown_and_breaking_succeed(tmp_path):
    for name, columns, rows, expected_kind in [
        ('alien', ['something'], [['a']], 'chua_ro'),
        ('orders', [c for c in SOURCES['orders'][0] if c != 'order_date'],
         [['1', '2', '10', 'ok', 'card', 'mobile', 'web']], 'breaking'),
    ]:
        path = write_csv(tmp_path / (name + '.csv'), columns, rows)
        out = tmp_path / ('out_' + name)
        assert mapping.main([str(path), '--data', str(tmp_path / 'no_refs'), '--out', str(out)]) == 0
        body = yaml.safe_load((out / 'mapping_de_xuat.yml').read_text(encoding='utf-8'))
        assert body['schema_diff']['loai'] == expected_kind
