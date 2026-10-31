"""Đối chiếu notebook, mặc định phê duyệt và hợp đồng mẫu PM đã chốt."""
from copy import deepcopy
from pathlib import Path
import sys

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from scripts.ingest import auto_mapping, approval, extension_contract as ec


@pytest.fixture(scope='module')
def demo():
    return auto_mapping.propose('data/student_data/orders_enriched.csv')


def test_epd_notebook():
    p = auto_mapping.propose('data/student_data/epd.json')
    c = p['xung_dot_khoa']
    assert p['nguon']['de_xuat'] == 'products'
    assert [c[k] for k in ('khop_dung_1', 'khop_va_cung_id', 'id_trung_nguon', 'id_trung_khac_noi_dung')] == [995, 0, 998, 998]
    assert c['danh_lai_khoa'] > 0
    assert 'Xung đột khóa' in auto_mapping.render_report(p)
    summary = ' '.join(approval.tom_tat_nghiep_vu(p))
    assert '998 mã trùng với sản phẩm đã có nhưng khác nội dung' in summary
    assert '993 bản ghi giống sản phẩm cũ nhưng mang mã khác' in summary
    assert 'Khớp khóa với 998' not in summary
    assert 'xung đột khóa' in summary


def test_orders_no_conflict(demo):
    c = demo['xung_dot_khoa']
    assert c['id_trung_nguon'] == 646945
    assert c['id_trung_khac_noi_dung'] == c['danh_lai_khoa'] == 0


def test_pii_defaults(demo):
    d = approval.default_decisions(demo)
    by = {c['ten']: c for c in d['cot']}
    assert by['order_id']['xu_ly'] == 'khoa_noi'
    assert by['order_date']['xu_ly'] == 'doi_chieu_loi'
    assert by['city']['xu_ly'] == 'bo'
    assert by['sales_employee_id']['xu_ly'] == 'nap'
    for c in demo['cot']:
        if c.get('nghi_pii'):
            assert by[c['ten_trong_file']]['hien_thi'] == 'silver'
    text = ' '.join(approval.tom_tat_nghiep_vu(demo))
    assert 'Đơn hàng' in text and '646.945' in text
    assert 'Khớp khóa với 646.945 đơn hàng đã có' in text
    assert 'phụ thuộc hàm' not in text and 'điểm' not in text
    assert set(approval.SOURCE_LABELS) == set(auto_mapping.SOURCES)


def test_contract_equivalent(demo, tmp_path):
    expected = ec.load('orders_enriched')
    d = approval.default_decisions(demo)
    # Những lựa chọn DE phải chủ động sửa theo hợp đồng đã được PM duyệt.
    by = {c['ten']: c for c in d['cot']}
    by['sales_employee_name']['hien_thi'] = 'mart'
    by['years_experience']['kieu'] = 'integer'
    by['comment']['hien_thi'] = 'silver'
    by['comment']['duoc_rong'] = True
    for col in ('city', 'region', 'district'):
        by[col]['ly_do'] = 'thừa, suy từ geography qua zip'
    doc = approval.hop_dong_tu_de_xuat(demo, d, 'orders_enriched', 'ui_nhap/demo/orders.csv', 'de1', '2026-10-30')
    (tmp_path / 'orders_enriched.yml').write_text(yaml.safe_dump(doc, allow_unicode=True), encoding='utf-8')
    actual = ec.load('orders_enriched', tmp_path)
    for key in ('thuc_the', 'khoa_noi', 'nguong_cach_ly'):
        assert actual[key] == expected[key]
    assert sorted(actual['cot'], key=lambda c: c['ten']) == sorted(expected['cot'], key=lambda c: c['ten'])
    assert actual['file'] != expected['file']
    assert all('trang_thai' not in c for c in d['cot'])


@pytest.mark.parametrize('bad,match', [('missing', 'header/cot'), ('kind', 'khoa_noi.kieu'), ('core', 'ten')])
def test_load_rejects_decisions(demo, tmp_path, bad, match):
    d = approval.default_decisions(demo)
    name = 'orders' if bad == 'core' else 'test_upload'
    if bad == 'missing':
        d['cot'].pop()
    if bad == 'kind':
        d['cot'][0]['kieu'] = 'string'
    doc = approval.hop_dong_tu_de_xuat(demo, d, name, 'ui_nhap/a.csv', 'de', '2026-10-30')
    (tmp_path / f'{name}.yml').write_text(yaml.safe_dump(doc), encoding='utf-8')
    with pytest.raises(ValueError, match=match):
        ec.load(name, tmp_path)


def test_model_detection():
    assert approval.has_dbt_model('orders_enriched', 'retail_dbt/models')
    assert not approval.has_dbt_model('other_upload', 'retail_dbt/models')


@pytest.mark.parametrize('source', ['sales', 'sample_submission'])
@pytest.mark.parametrize('header', ['Date', 'date'])
def test_date_key_default(source, header, tmp_path):
    # Hợp đồng lõi dùng Date, còn auto_mapping nhận cả header khác hoa/thường.
    proposal = {'nguon': {'de_xuat': source}, 'thuc_the_moi': [],
                'cot': [{'ten_trong_file': header, 'loai': 'khop'},
                        {'ten_trong_file': 'note', 'loai': 'thuoc_tinh_le'}]}
    decisions = approval.default_decisions(proposal)
    assert decisions['khoa_noi'] == {'nguon': source, 'cot': header, 'cot_nguon': 'Date'}
    assert decisions['cot'][0] == {'ten': header, 'xu_ly': 'khoa_noi', 'kieu': 'date', 'duoc_rong': False}
    doc = approval.hop_dong_tu_de_xuat(proposal, decisions, 'daily_extra', 'ui_nhap/demo/daily.csv', 'de', '2026-10-31')
    (tmp_path / 'daily_extra.yml').write_text(yaml.safe_dump(doc), encoding='utf-8')
    assert ec.load('daily_extra', tmp_path)['khoa_noi'] == decisions['khoa_noi']
