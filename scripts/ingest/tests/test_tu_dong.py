"""Kiểm phân loại và kho hợp đồng bằng dữ liệu giả, không chạy pipeline."""
from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from scripts.ingest.contract_registry import ContractRegistry
from scripts.ingest.extension_contract import load
from scripts.ingest.tu_dong import phan_loai, hop_dong_cua_luot


@pytest.fixture
def registry(tmp_path):
    repo = tmp_path / 'scripts/ingest/extensions'
    repo.mkdir(parents=True)
    (repo / 'orders_enriched.yml').write_bytes((ROOT / 'scripts/ingest/extensions/orders_enriched.yml').read_bytes())
    return ContractRegistry(tmp_path)


def proposal(header, source='orders'):
    return {'nguon': {'de_xuat': source},
            'cot': [{'ten_trong_file': col, 'loai': 'khop', 'khong_ep_duoc': 0} for col in header],
            'xung_dot_khoa': {'da_kiem': True, 'id_trung_khac_noi_dung': 0},
            'tham_chieu_thieu': [], 'file': {'ten': 'whatever.csv'}}


def test_registry_seed_immutable_and_header_not_filename(registry):
    repo_file = registry.repo / 'orders_enriched.yml'
    before = repo_file.read_bytes()
    meta, doc = registry.current('orders_enriched')
    assert meta['phien_ban'] == 1 and meta['nguon_goc'].startswith('repo:')
    path = registry.folder('orders_enriched') / 'v1.yml'
    first = path.read_bytes()
    candidates = registry.candidates(proposal(doc['header']))
    assert [(item[0], item[1], item[3]) for item in candidates] == [('orders_enriched', 1, [])]
    newer = deepcopy(doc)
    newer.pop('hop_dong_sha256')
    newer['header'].append('bonus')
    newer['cot'].append({'ten': 'bonus', 'xu_ly': 'nap', 'kieu': 'integer', 'duoc_rong': False,
                        'hien_thi': 'silver', 'trang_thai': 'da_duyet'})
    meta2, _ = registry.write('orders_enriched', newer, 'de1', 'nang_hop_dong:test', expected=1)
    assert meta2['phien_ban'] == 2 and (registry.folder('orders_enriched') / 'v2.yml').exists()
    assert path.read_bytes() == first and repo_file.read_bytes() == before
    assert json.loads((registry.folder('orders_enriched') / 'hien_hanh.json').read_text())['phien_ban'] == 2
    with pytest.raises(ValueError, match='đã đổi'):
        registry.write('orders_enriched', newer, 'de1', 'nang_hop_dong:test', expected=1)


@pytest.mark.parametrize('code,mutate', [
    ('chua_ro_nguon', lambda p: p['nguon'].update(de_xuat='chua_ro')),
    ('doi_kieu', lambda p: p['cot'][0].update(khong_ep_duoc=1)),
    ('xung_dot_khoa', lambda p: p['xung_dot_khoa'].update(id_trung_khac_noi_dung=1)),
    ('tham_chieu_thieu', lambda p: p['tham_chieu_thieu'].append('products')),
])
def test_classification_reasons(registry, code, mutate):
    _, doc = registry.current('orders_enriched')
    body = proposal(doc['header'])
    mutate(body)
    result = phan_loai(body, registry.candidates(body), True)
    assert result['ket_qua'] == 'can_nguoi'
    assert code in {reason['ma'] for reason in result['ly_do']}


def test_classification_cardinality_and_new_columns(registry):
    _, doc = registry.current('orders_enriched')
    full = proposal(doc['header'])
    one = registry.candidates(full)
    assert phan_loai(full, one, True)['ket_qua'] == 'tu_dong'
    extra = proposal([*doc['header'], 'bonus'])
    assert phan_loai(extra, registry.candidates(extra), True)['cot_moi'] == ['bonus']
    missing = proposal(doc['header'][:-1])
    result = phan_loai(missing, registry.candidates(missing), True)
    assert result['ket_qua'] == 'can_nguoi' and 'thieu_cot' in {r['ma'] for r in result['ly_do']}
    assert doc['header'][-1] in next(r['ky_thuat'] for r in result['ly_do'] if r['ma'] == 'thieu_cot')
    assert 'chua_co_hop_dong' in {r['ma'] for r in phan_loai(full, [], True)['ly_do']}
    assert 'nhieu_hop_dong' in {r['ma'] for r in phan_loai(full, one + one, True)['ly_do']}
    assert 'chua_co_model' in {r['ma'] for r in phan_loai(full, one, False)['ly_do']}
    uncertain = proposal(doc['header'], 'chua_ro')
    assert 'chua_ro_nguon' in {r['ma'] for r in phan_loai(uncertain, [], False)['ly_do']}
    unknown = proposal(['alien'], 'chua_ro')
    unknown['xung_dot_khoa']['da_kiem'] = False
    assert phan_loai(unknown, [], False)['ket_qua'] == 'can_nguoi'


def test_run_contract_preserves_decisions_and_ignores_new_columns(registry, tmp_path):
    meta, doc = registry.current('orders_enriched')
    reversed_header = list(reversed(doc['header']))
    run = hop_dong_cua_luot(doc, reversed_header, 'ui_nhap/id/file.csv', 1, '2026-11-02')
    assert run['header'] == reversed_header
    assert [col['ten'] for col in run['cot']] == reversed_header
    assert {col['ten']: col['xu_ly'] for col in run['cot']} == {col['ten']: col['xu_ly'] for col in doc['cot']}
    run = hop_dong_cua_luot(doc, [*doc['header'], 'bonus'], 'ui_nhap/id/file.csv', 1, '2026-11-02')
    assert run['cot'][-1]['xu_ly'] == 'bo'
    candidate = tmp_path / 'orders_enriched.yml'
    candidate.write_text(yaml.safe_dump(run, allow_unicode=True), encoding='utf-8')
    assert load('orders_enriched', tmp_path)['cot'][-1]['xu_ly'] == 'bo'


@pytest.mark.parametrize('checked', [False, None, 'true'])
def test_unchecked_keys_require_review_even_without_conflicts(registry, checked):
    _, doc = registry.current('orders_enriched')
    body = proposal(doc['header'])
    body['xung_dot_khoa']['da_kiem'] = checked
    result = phan_loai(body, registry.candidates(body), True)
    assert result['ket_qua'] == 'can_nguoi'
    assert [reason['ma'] for reason in result['ly_do']] == ['xung_dot_khoa']


def test_missing_columns_reports_closest_contract_without_model_reason():
    body = proposal(['id'])
    candidates = [('far', 1, {}, ['bonus', 'comment']), ('near', 2, {}, ['comment'])]
    result = phan_loai(body, candidates, False)
    assert result['ket_qua'] == 'can_nguoi'
    assert [reason['ma'] for reason in result['ly_do']] == ['thieu_cot']
    assert 'near v2' in result['ly_do'][0]['ky_thuat']
    assert 'comment' in result['ly_do'][0]['nghiep_vu']
    assert 'bonus' not in result['ly_do'][0]['nghiep_vu']
    assert [r['ma'] for r in phan_loai(body, [], False)['ly_do']] == ['chua_co_hop_dong']


@pytest.mark.parametrize('variant', ['original', 'reordered', 'extra'])
def test_run_contract_equivalence_all_fields(registry, tmp_path, variant):
    meta, doc = registry.current('orders_enriched')
    before = deepcopy(doc)
    header = list(reversed(doc['header'])) if variant == 'reordered' else list(doc['header'])
    if variant == 'extra':
        header.append('bonus')
    run = hop_dong_cua_luot(doc, header, 'ui_nhap/new/fresh.csv', 1, '2026-11-02T12:00:00Z')
    assert run['file'] == 'ui_nhap/new/fresh.csv' != doc['file']
    assert run['duyet_boi'] == f"he_thong (hợp đồng orders_enriched v1, sha256 {meta['sha256'][:8]})"
    assert run['ngay_duyet'] == '2026-11-02T12:00:00Z'
    for field in ('thuc_the', 'khoa_noi', 'nguong_cach_ly'):
        assert run[field] == doc[field]
    original = {c['ten']: c for c in doc['cot']}
    assert [c for c in run['cot'] if c['ten'] in original] == [original[n] for n in header if n in original]
    assert doc == before
    (tmp_path / 'orders_enriched.yml').write_text(yaml.safe_dump(run), encoding='utf-8')
    assert load('orders_enriched', tmp_path)['header'] == header


def test_registry_refuses_overwriting_orphan_version(registry):
    _, doc = registry.current('orders_enriched')
    folder = registry.folder('orders_enriched')
    # Mô phỏng máy dừng sau ghi v2, trước đổi con trỏ; không được ghi đè v2 đó.
    orphan = folder / 'v2.yml'
    orphan.write_bytes((folder / 'v1.yml').read_bytes())
    before = orphan.read_bytes()
    pointer = (folder / 'hien_hanh.json').read_bytes()
    with pytest.raises(FileExistsError):
        registry.write('orders_enriched', doc, 'de1', 'nang_hop_dong:test', expected=1)
    assert orphan.read_bytes() == before
    assert (folder / 'hien_hanh.json').read_bytes() == pointer


def test_registry_rejects_valid_yaml_tampered_after_approval(registry):
    _, doc = registry.current('orders_enriched')
    doc['duyet_boi'] = 'changed'
    (registry.folder('orders_enriched') / 'v1.yml').write_text(yaml.safe_dump(doc), encoding='utf-8')
    with pytest.raises(ValueError, match='bị đổi'):
        registry.current('orders_enriched')


def test_candidates_filter_source_even_with_matching_filename_and_header(registry):
    _, doc = registry.current('orders_enriched')
    body = proposal(doc['header'], source='payments')
    body['file']['ten'] = 'orders_enriched.csv'
    assert registry.candidates(body) == []


def test_pii_integer_without_leading_zero_stays_string(tmp_path):
    from scripts.ingest import auto_mapping
    from scripts.ingest.adapters import read_file
    path = tmp_path / 'pii.csv'
    path.write_text('age,years_experience\n23,23\n41,41\n', encoding='utf-8')
    with read_file(path) as data:
        assert auto_mapping.column_profile(data, 'age')['kieu_goi_y'] == 'string'
        assert auto_mapping.column_profile(data, 'years_experience')['kieu_goi_y'] == 'integer'


def test_default_decisions_uses_integer_suggestion():
    from scripts.ingest.approval import default_decisions
    body = proposal(['years_experience'])
    body['cot'][0].update(loai='thuoc_tinh_le', thong_ke={'kieu_goi_y': 'integer', 'so_rong': 0})
    body['thuc_the_moi'] = []
    assert default_decisions(body)['cot'][0]['kieu'] == 'integer'


@pytest.mark.parametrize('column,expected', [
    ('sales_employee_id', True), ('sales_employee_name', True), ('sales_employee_sk', True),
    ('years_experience', True), ('bonus', False), ('source', False), ('raw', False),
    ('id', False), ('clean', False), ('select', False), ('integer', False), ('comment', False),
    ('marital_status', False), ('education_level', False),
])
def test_mart_output_columns_in_real_models(column, expected):
    from scripts.ingest.approval import has_dbt_column
    assert has_dbt_column('orders_enriched', column, ROOT / 'retail_dbt/models') is expected


@pytest.mark.parametrize('sql,folder,expected', [
    ('select bonus from raw', 'marts', False),
    ("{{ config(enabled=extension_enabled('other')) }} select bonus from raw", 'marts', False),
    ("{{ config(enabled=extension_enabled('orders_enriched')) }} select bonus from raw", 'staging', False),
    ("-- extension_enabled('orders_enriched')\nselect bonus from raw", 'marts', False),
    ("{{ config(enabled=extension_enabled('orders_enriched')) }} select id from raw -- bonus", 'marts', False),
    ("{{ config(enabled=extension_enabled('orders_enriched')) }} with c as (select bonus from raw) select id from c", 'marts', False),
    ("{{ config(enabled=extension_enabled('orders_enriched')) }} select 'bonus' as note from raw", 'marts', False),
    ("{{ config(enabled=extension_enabled('orders_enriched')) }} select {{ bonus }} as note from raw", 'marts', False),
    ("{{ config(enabled=extension_enabled('orders_enriched')) }} select cast(id as integer) as bonus from raw", 'marts', True),
    ("{{ config(enabled=extension_enabled('orders_enriched')) }} select r.bonus from raw r", 'marts', True),
])
def test_mart_column_requires_marker_and_outer_output(tmp_path, sql, folder, expected):
    from scripts.ingest.approval import has_dbt_column
    models = tmp_path / 'models'
    (models / folder).mkdir(parents=True)
    (models / folder / 'example.sql').write_text(sql, encoding='utf-8')
    assert has_dbt_column('orders_enriched', 'bonus', models) is expected


def test_optional_columns_missing_return_and_rename_prepare_real_parquet(tmp_path):
    """Chỉ chạy prepare phần mở rộng trên một dòng giả, không chạy pipeline."""
    import duckdb
    from scripts.ingest.extension_prepare import prepare
    registry = ContractRegistry(tmp_path)
    doc = {'ten': 'orders_extra', 'phien_ban': 1, 'trang_thai': 'da_duyet',
           'file': 'old.csv', 'duyet_boi': 'de1', 'ngay_duyet': '2026-11-02',
           'header': ['order_id', 'comment', 'bonus', 'ignored', 'mart_col'],
           'cot': [
               {'ten': 'order_id', 'xu_ly': 'khoa_noi', 'kieu': 'integer', 'duoc_rong': False},
               {'ten': 'comment', 'xu_ly': 'nap', 'kieu': 'string', 'duoc_rong': False, 'hien_thi': 'silver'},
               {'ten': 'bonus', 'xu_ly': 'nap', 'kieu': 'integer', 'duoc_rong': False, 'hien_thi': 'silver', 'tuy_chon': True},
               {'ten': 'ignored', 'xu_ly': 'bo', 'ly_do': 'Không cần', 'tuy_chon': True},
               {'ten': 'mart_col', 'xu_ly': 'nap', 'kieu': 'integer', 'duoc_rong': False, 'hien_thi': 'mart'}],
           'thuc_the': [], 'khoa_noi': {'nguon': 'orders', 'cot': 'order_id', 'cot_nguon': 'order_id'},
           'nguong_cach_ly': 0.01}
    for col in doc['cot']:
        col['trang_thai'] = 'da_duyet'
    registry.write('orders_extra', doc, 'de1', 'yeu_cau:test')
    _, approved = registry.current('orders_extra')
    for required in ('comment', 'mart_col', 'order_id'):
        body = proposal([n for n in doc['header'] if n != required])
        classified = phan_loai(body, registry.candidates(body), True)
        assert classified['ket_qua'] == 'can_nguoi'
        assert [r['ma'] for r in classified['ly_do']] == ['thieu_cot']
        assert required in classified['ly_do'][0]['ky_thuat']
    data = tmp_path / 'data'
    data.mkdir()
    prior = []
    for index, header in enumerate([
        doc['header'], ['order_id', 'comment', 'mart_col'], doc['header'],
        ['order_id', 'comment', 'mart_col', 'renamed_bonus'],
    ]):
        body = proposal(header)
        result = phan_loai(body, registry.candidates(body), True)
        assert result['ket_qua'] == 'tu_dong'
        missing = [name for name in ('bonus', 'ignored') if name not in header]
        assert result['cot_tuy_chon_thieu'] == missing
        assert result['cot_moi'] == (['renamed_bonus'] if index == 3 else [])
        filename = f'file{index}.csv'
        (data / filename).write_text(','.join(header) + '\n' + ','.join('1' for _ in header) + '\n', encoding='utf-8')
        run = hop_dong_cua_luot(approved, header, filename, 2, '2026-11-02')
        (tmp_path / 'orders_extra.yml').write_text(yaml.safe_dump(run), encoding='utf-8')
        run = load('orders_extra', tmp_path)
        ready = tmp_path / f'snapshot{index}'
        ready.mkdir()
        with duckdb.connect() as con:
            con.execute("copy (select '1' as order_id) to ? (format parquet)", [str(ready / 'orders.parquet')])
        entry = prepare(run, data, ready)
        assert entry['rows'] == 1 and entry['so_dong_cach_ly'] == 0
        parquet = ready / 'orders_extra.parquet'
        with duckdb.connect() as con:
            columns = [d[0] for d in con.execute('select * from read_parquet(?)', [str(parquet)]).description]
        assert ('bonus' in columns) == ('bonus' in header)
        assert 'ignored' not in columns and 'renamed_bonus' not in columns
        for old, raw in prior:
            assert old.read_bytes() == raw
        prior.append((parquet, parquet.read_bytes()))
