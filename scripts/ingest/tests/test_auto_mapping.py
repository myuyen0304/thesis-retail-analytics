"""U9–U15 và I1–I3: bằng chứng đề xuất, CLI và dữ liệu giảng viên."""
import hashlib
from copy import deepcopy
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


def matched_column(name, kind):
    return {'ten_trong_file': name, 'cot_hop_dong': name, 'loai': 'khop', 'kieu_hop_dong': kind}


def test_review_a1_new_id_is_not_conflicting_id(tmp_path):
    write_csv(tmp_path / 'products.csv', ['product_id', 'product_name'], [['1', 'A']])
    path = write_csv(tmp_path / 'input.csv', ['product_id', 'product_name'], [['99', 'B']])
    with read_file(path) as data:
        result = mapping.key_conflicts(data, 'products', tmp_path)
    assert result['id_trung_khac_noi_dung'] == 0


def test_review_a2_integer_child_with_leading_zero(tmp_path):
    path, refs, conflict = extension_fixture(tmp_path, 'products')
    write_csv(path, ['product_id'], [['099']])
    write_csv(refs / 'inventory.csv', ['product_id'], [['99']])
    with read_file(path) as data:
        assert mapping.extension_candidate(data, 'products', conflict, refs) == (None, [])


def test_review_a2_child_missing_column(tmp_path):
    path, refs, conflict = extension_fixture(tmp_path, 'products')
    write_csv(refs / 'inventory.csv', ['other_id'], [['1']])
    with read_file(path) as data:
        assert mapping.extension_candidate(data, 'products', conflict, refs) == (None, ['inventory'])


def test_review_a3_empty_reference_domain(tmp_path):
    write_csv(tmp_path / 'products.csv', ['price'], [[''], [' ']])
    path = write_csv(tmp_path / 'input.csv', ['price'], [['10']])
    with read_file(path) as data:
        assert mapping.unusual_values(data, [matched_column('price', 'double')], 'products', tmp_path) == [
            {'cot': 'price', 'chua_kiem_mien': True}]


def test_review_a4_unicode_suffix(tmp_path):
    write_csv(tmp_path / 'web_traffic.csv', ['traffic_source'], [['Search']])
    path = write_csv(tmp_path / 'input.csv', ['traffic_source'], [['Search Bản 1'], ['Search Bản 2']])
    with read_file(path) as data:
        assert mapping.suffix_candidates(data, [matched_column('traffic_source', 'string')], 'web_traffic', tmp_path) == [
            {'cot': 'traffic_source', 'mau': r'\s+Bản\s+[0-9]+$', 'so_dong': 2,
             'tong_khac_rong': 2, 'khop_sau_khi_bo': 2, 'trang_thai': 'de_xuat', 'da_ap_dung': False}]


def test_review_a4_reference_missing_column(tmp_path):
    write_csv(tmp_path / 'web_traffic.csv', ['other'], [['Search']])
    path = write_csv(tmp_path / 'input.csv', ['traffic_source'], [['Search Edition 1']])
    with read_file(path) as data:
        assert mapping.suffix_candidates(data, [matched_column('traffic_source', 'string')], 'web_traffic', tmp_path) == []


@pytest.mark.parametrize('kind,count', [('so_am', 3), ('vuot_nguong', 4)])
def test_review_a5_summary_counts_domain_evidence(enriched, kind, count):
    from scripts.ingest import approval
    path, refs, _, _ = enriched
    proposal = mapping.propose(path, refs)
    proposal['gia_tri_la'] = [{'cot': 'price', 'khong_ep_duoc': {'so_dong': 1}, kind: {'so_dong': count}}]
    expected = 'Có 4 giá trị' if kind == 'so_am' else 'Có 5 giá trị'
    assert any(line.startswith(expected) for line in approval.tom_tat_nghiep_vu(proposal))


def test_a1_mapping_null_duplicate_ambiguous_and_order(tmp_path):
    refs = tmp_path / 'refs'
    refs.mkdir()
    write_csv(refs / 'products.csv', ['product_id', 'product_name', 'price'],
              [['1', 'A', '10'], ['2', 'B', '20'], ['3', 'C', '30'], ['4', 'C', '30']])
    path = write_csv(tmp_path / 'input.csv', ['product_id', 'product_name', 'price'],
                     [['9', 'B', '20'], ['', 'A', '10'], ['9', 'A', '10.0000001'],
                      ['1', 'A', '10'], ['8', 'C', '30'], ['7', 'X', '40']])
    with read_file(path) as data:
        result = mapping.key_conflicts(data, 'products', refs)
    assert result['id_rong'] == result['id_trung_trong_file'] == 1
    assert result['khop_dung_1'] == 4 and result['khong_khop'] == 2
    assert result['danh_lai_khoa'] == 2
    assert result['anh_xa'] == [{'id_trong_file': '9', 'id_nguon': '1'},
        {'id_trong_file': None, 'id_nguon': '1'}, {'id_trong_file': '9', 'id_nguon': '2'}]
    with read_file(refs / 'products.csv') as data:
        assert mapping.key_conflicts(data, 'products', refs)['anh_xa'] == []


CHILDREN = [('promotions', 'order_items', 'promo_id'), ('promotions', 'order_items', 'promo_id_2'),
            ('products', 'order_items', 'product_id'), ('products', 'inventory', 'product_id'),
            ('customers', 'orders', 'customer_id')]


def extension_fixture(tmp_path, source):
    refs = tmp_path / 'refs'
    refs.mkdir()
    key = {'promotions': 'promo_id', 'products': 'product_id', 'customers': 'customer_id'}[source]
    path = write_csv(tmp_path / 'input.csv', [key], [['99'], ['99'], ['']])
    write_csv(refs / 'order_items.csv', ['promo_id', 'promo_id_2', 'product_id'], [['old', '', '1']])
    write_csv(refs / 'inventory.csv', ['product_id'], [['1']])
    write_csv(refs / 'orders.csv', ['customer_id'], [['1']])
    return path, refs, {'da_kiem': True, 'id_trung_nguon': 0, 'danh_lai_khoa': 2}


@pytest.mark.parametrize('source', ['promotions', 'products', 'customers'])
def test_a2_extension_zero_references(tmp_path, source):
    path, refs, conflict = extension_fixture(tmp_path, source)
    with read_file(path) as data:
        result, absent = mapping.extension_candidate(data, source, conflict, refs)
    assert not absent
    assert result == {'ten': source + '_ext', 'hien_thi': 'silver', 'id_chung_nguon': 0,
                      'dong_con_tham_chieu': 0, 'ban_ghi_giong_nguon': 2, 'trang_thai': 'de_xuat'}


@pytest.mark.parametrize('source,child,column', CHILDREN)
@pytest.mark.parametrize('damage', ['referenced', 'missing'])
def test_a2_every_child_blocks_or_is_missing(tmp_path, source, child, column, damage):
    path, refs, conflict = extension_fixture(tmp_path, source)
    if damage == 'missing':
        (refs / (child + '.csv')).unlink()
    else:
        header = ['promo_id', 'promo_id_2', 'product_id'] if child == 'order_items' else [column]
        write_csv(refs / (child + '.csv'), header, [['99' if c == column else '' for c in header]])
    with read_file(path) as data:
        result, absent = mapping.extension_candidate(data, source, conflict, refs)
    assert result is None
    assert absent == ([child] if damage == 'missing' else [])


@pytest.mark.parametrize('mode', ['overlap', 'unchecked', 'empty', 'other_source'])
def test_a2_ineligible(tmp_path, mode):
    path, refs, conflict = extension_fixture(tmp_path, 'products')
    source = 'products'
    if mode == 'overlap':
        conflict['id_trung_nguon'] = 1
    elif mode == 'unchecked':
        conflict['da_kiem'] = False
    elif mode == 'empty':
        write_csv(path, ['product_id'], [[''], [' ']])
    else:
        source = 'web_traffic'
    with read_file(path) as data:
        assert mapping.extension_candidate(data, source, conflict, refs) == (None, [])


def test_a2_missing_child_propagates_to_proposal(tmp_path):
    refs = tmp_path / 'refs'
    refs.mkdir()
    header = SOURCES['products'][0]
    row = ['1', 'A', 'C', 'S', 'M', 'red', '10', '5']
    write_csv(refs / 'products.csv', header, [row])
    path = write_csv(tmp_path / 'products.csv', header, [['99', *row[1:]]])
    result = mapping.propose(path, refs)
    assert result['nguon_mo_rong_de_xuat'] is None
    assert result['tham_chieu_thieu'] == ['inventory', 'order_items']


@pytest.mark.parametrize('kind', ['integer', 'double', 'decimal(14,2)'])
@pytest.mark.parametrize('reference', ['positive', 'negative', 'absent'])
def test_a3_domain_bounds_and_samples(tmp_path, kind, reference):
    refs = tmp_path / 'refs'
    refs.mkdir()
    if reference != 'absent':
        write_csv(refs / 'products.csv', ['price'], [['-2' if reference == 'negative' else '0'], ['10']])
    path = write_csv(tmp_path / 'input.csv', ['price', 'extra'],
        [[v, '-999'] for v in ['badB', 'badA', 'badB', '-1', '100', '101', '', 'badC', 'badD', 'badE', 'badF']])
    columns = [matched_column('price', kind), {'ten_trong_file': 'extra', 'loai': 'thuoc_tinh_le'}]
    with read_file(path) as data:
        result, = mapping.unusual_values(data, columns, 'products', refs)
    assert result['cot'] == 'price'
    assert result['khong_ep_duoc'] == {'so_dong': 7, 'mau': ['badB', 'badA', 'badC', 'badD', 'badE']}
    if reference == 'absent':
        assert result['chua_kiem_mien'] is True
        assert 'so_am' not in result and 'vuot_nguong' not in result
    else:
        assert result['vuot_nguong']['so_dong'] == 1
        assert result['vuot_nguong']['mau'] == ['101']
        assert float(result['vuot_nguong']['nguong']) == 100
        assert ('so_am' in result) == (reference == 'positive')
        if reference == 'positive':
            assert result['so_am'] == {'so_dong': 1, 'mau': ['-1']}


def test_a3_clean_is_empty_and_date_invalid(tmp_path):
    path = write_csv(tmp_path / 'web_traffic.csv', ['date', 'sessions'], [['2023-01-01', '10']])
    columns = [matched_column('date', 'date'), matched_column('sessions', 'integer')]
    with read_file(path) as data:
        assert mapping.unusual_values(data, columns, 'web_traffic', tmp_path) == []
    path = write_csv(tmp_path / 'input.csv', ['date'], [['not-a-date'], ['']])
    with read_file(path) as data:
        assert mapping.unusual_values(data, columns[:1], 'web_traffic', tmp_path) == [
            {'cot': 'date', 'khong_ep_duoc': {'so_dong': 1, 'mau': ['not-a-date']}}]


@pytest.mark.parametrize('ratio,matching,expected', [(89, 89, False), (90, 90, True),
    (100, 98, False), (100, 99, True), (100, 0, False)])
def test_a4_suffix_thresholds_and_no_mutation(tmp_path, ratio, matching, expected):
    refs = tmp_path / 'refs'
    refs.mkdir()
    write_csv(refs / 'web_traffic.csv', ['traffic_source'], [['Search'], ['Event Edition 2023']])
    values = ['  Search Edition 1  ' if i < matching else 'Event Edition 2023' for i in range(ratio)]
    values += ['plain'] * (100 - ratio) + [' ', '']
    path = write_csv(tmp_path / 'input.csv', ['traffic_source'], [[v] for v in values])
    before = path.read_bytes()
    with read_file(path) as data:
        result = mapping.suffix_candidates(data, [matched_column('traffic_source', 'string')], 'web_traffic', refs)
        assert data.n_rows == 102
    assert bool(result) == expected
    if expected:
        assert result == [{'cot': 'traffic_source', 'mau': r'\s+Edition\s+[0-9]+$', 'so_dong': ratio,
            'tong_khac_rong': 100, 'khop_sau_khi_bo': matching, 'trang_thai': 'de_xuat', 'da_ap_dung': False}]
    assert path.read_bytes() == before


def test_a4_no_reference_or_unmatched_column(tmp_path):
    path = write_csv(tmp_path / 'input.csv', ['traffic_source'], [['Search Edition 1']])
    with read_file(path) as data:
        assert mapping.suffix_candidates(data, [matched_column('traffic_source', 'string')], 'web_traffic', tmp_path) == []
    write_csv(tmp_path / 'web_traffic.csv', ['traffic_source'], [['Search']])
    col = matched_column('traffic_source', 'string')
    col['loai'] = 'thuoc_tinh_le'
    with read_file(path) as data:
        assert mapping.suffix_candidates(data, [col], 'web_traffic', tmp_path) == []


@pytest.mark.parametrize('mode', ['split_words', 'no_letters', 'empty', 'numeric_column'])
def test_a4_requires_one_word_group_and_string_column(tmp_path, mode):
    write_csv(tmp_path / 'web_traffic.csv', ['traffic_source'], [['Search']])
    values = {'split_words': ['Search Edition 1'] * 5 + ['Search Copy 2'] * 5,
              'no_letters': ['Search 123 4'] * 10, 'empty': ['', ' '],
              'numeric_column': ['Search Edition 1'] * 10}[mode]
    path = write_csv(tmp_path / 'input.csv', ['traffic_source'], [[v] for v in values])
    col = matched_column('traffic_source', 'integer' if mode == 'numeric_column' else 'string')
    with read_file(path) as data:
        assert mapping.suffix_candidates(data, [col], 'web_traffic', tmp_path) == []


def test_a_new_evidence_defaults_empty(tmp_path):
    path = write_csv(tmp_path / 'unknown.csv', ['alien'], [['value']])
    proposal = mapping.propose(path, tmp_path)
    assert proposal['phien_ban'] == 1
    assert proposal['gia_tri_la'] == proposal['luat_sua_ung_vien'] == []
    assert proposal['nguon_mo_rong_de_xuat'] is None


def test_a5_old_proposal_decisions_and_safe_reports(enriched):
    from scripts.ingest import approval, tu_dong
    path, refs, _, _ = enriched
    proposal = mapping.propose(path, refs)
    old = deepcopy(proposal)
    for key in ('nguon_mo_rong_de_xuat', 'gia_tri_la', 'luat_sua_ung_vien'):
        old.pop(key)
    for key in ('id_rong', 'id_trung_trong_file', 'khong_khop', 'anh_xa'):
        old['xung_dot_khoa'].pop(key, None)
    assert mapping.render_report(old)
    poison = '<evil>|\n# injected'
    proposal['gia_tri_la'] = [{'cot': poison, 'khong_ep_duoc': {'so_dong': 2, 'mau': [poison]}}]
    proposal['luat_sua_ung_vien'] = [{'cot': poison, 'mau': poison, 'so_dong': 9,
        'tong_khac_rong': 10, 'khop_sau_khi_bo': 9, 'trang_thai': 'de_xuat', 'da_ap_dung': False}]
    proposal['nguon_mo_rong_de_xuat'] = {'ten': poison, 'trang_thai': 'de_xuat'}
    proposal['xung_dot_khoa']['anh_xa'] = [{'id_trong_file': poison, 'id_nguon': str(i)} for i in range(7)]
    decisions = approval.default_decisions(old)
    assert approval.default_decisions(proposal) == decisions
    args = (decisions, 'demo', 'student_data/demo.csv', 'PM', '2026-11-05')
    assert approval.hop_dong_tu_de_xuat(proposal, *args) == approval.hop_dong_tu_de_xuat(old, *args)
    assert tu_dong.phan_loai(proposal, [], False) == tu_dong.phan_loai(old, [], False)
    summary = approval.tom_tat_nghiep_vu(proposal)
    assert len(summary) == len(approval.tom_tat_nghiep_vu(old)) + 2
    assert not any(poison in line or '<evil>' in line for line in summary)
    report = mapping.render_report(proposal)
    assert '<evil>' not in report and '\n# injected' not in report
    assert '&lt;evil&gt;&#124; # injected' in report
    assert '7 dòng ánh xạ' in report
    assert '| 5 |' not in report and '| 6 |' not in report


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


@pytest.mark.parametrize('filename', ['tf.json', 'epd.json', 'eprom.json',
                                     'orders_enriched.csv', 'shipments_realistic.csv'])
def test_a6_real_acceptance(filename):
    from scripts.ingest import approval, extension_contract, tu_dong
    if not (REAL / filename).is_file() or not all((ROOT / 'data' / (n + '.csv')).is_file() for n in SOURCES):
        pytest.skip('Thiếu data/student_data hoặc bảng tham chiếu A6')
    path = REAL / filename
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    p = mapping.propose(path, ROOT / 'data')
    conflict = p['xung_dot_khoa']
    unusual = {item['cot']: item for item in p['gia_tri_la']}
    if filename == 'tf.json':
        rule, = p['luat_sua_ung_vien']
        assert rule['cot'] == 'traffic_source'
        assert (rule['so_dong'], rule['tong_khac_rong'], rule['khop_sau_khi_bo']) == (998, 999, 998)
        assert rule['da_ap_dung'] is False and rule['trang_thai'] == 'de_xuat'
        assert unusual['date']['khong_ep_duoc'] == {'so_dong': 2, 'mau': ['2026-99-99', 'not_a_date']}
        assert unusual['sessions']['khong_ep_duoc'] == {'so_dong': 1, 'mau': ['N/A']}
        assert unusual['sessions']['so_am']['so_dong'] == 1
        assert unusual['sessions']['vuot_nguong']['so_dong'] == 1
        assert unusual['sessions']['vuot_nguong']['mau'] == ['999999999']
        assert unusual['unique_visitors']['khong_ep_duoc'] == {'so_dong': 1, 'mau': ['unknown']}
        assert unusual['unique_visitors']['so_am']['so_dong'] == 1
    elif filename == 'epd.json':
        assert [conflict[k] for k in ('id_rong', 'id_trung_trong_file', 'khop_dung_1', 'khong_khop', 'id_trung_nguon')] == [2, 1, 995, 5, 998]
        assert len(conflict['anh_xa']) == 995
        assert unusual['price']['khong_ep_duoc'] == {'so_dong': 1, 'mau': ['N/A']}
        assert unusual['price']['so_am']['so_dong'] == unusual['price']['vuot_nguong']['so_dong'] == 1
    elif filename == 'eprom.json':
        assert p['nguon']['de_xuat'] == 'promotions'
        assert p['nguon_mo_rong_de_xuat'] == {'ten': 'promotions_ext', 'hien_thi': 'silver',
            'id_chung_nguon': 0, 'dong_con_tham_chieu': 0, 'ban_ghi_giong_nguon': 217, 'trang_thai': 'de_xuat'}
        assert unusual['discount_value']['khong_ep_duoc'] == {'so_dong': 2, 'mau': ['30%%', 'twenty percent']}
        assert unusual['discount_value']['so_am']['so_dong'] == 1
    else:
        assert conflict['anh_xa'] == []
    if filename != 'eprom.json':
        assert p['nguon_mo_rong_de_xuat'] is None
    candidates = [('orders_enriched', 1, extension_contract.load('orders_enriched'), [])] if filename == 'orders_enriched.csv' else []
    route = tu_dong.phan_loai(p, candidates, filename == 'orders_enriched.csv')
    assert route['ket_qua'] == ('tu_dong' if filename == 'orders_enriched.csv' else 'can_nguoi')
    if filename == 'shipments_realistic.csv':
        assert 'chua_co_hop_dong' in [r['ma'] for r in route['ly_do']]
    summary = '\n'.join(approval.tom_tat_nghiep_vu(p))
    assert not any(value in summary for item in unusual.values() for key in ('khong_ep_duoc', 'so_am', 'vuot_nguong')
                   for value in item.get(key, {}).get('mau', []))
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before


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
