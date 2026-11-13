"""Tổng duyệt đợt 2023 (thiết kế §11): kiểm trước, xem trạng thái, kiểm kết quả, dọn thư mục thử.

Chạy trong container Airflow thử bằng `scripts/ops/tong_duyet.ps1`. Chỉ in mã, số đếm và kết quả,
không in client id hay dữ liệu từng dòng. Chỉ `xoa_kho` ghi lên cloud, và chỉ trong thư mục thử.
"""
import argparse
import csv
from decimal import Decimal
import json
import os
from pathlib import Path
import sys

from scripts.ops import nhap_do
from scripts.pipeline.runtime import Databricks, identifier
from scripts.pipeline.state import Registry

KHO_THU = '/Volumes/retail_lab/nhap_du_lieu/kho/tong_duyet'
ROOT = Path('warehouse/pipeline/docker')
MOC = Path('warehouse/pipeline/tong_duyet_truoc.json')
KIEM = Path('data_demo/dot_2023_kiem')
G_2023, R_2023 = Decimal('1108842415.88'), Decimal('826039488.68')  # D5 §11 bước 3, bộ sinh seed 2023
XU = Decimal('0.01')


def _kho():
    # Không bao giờ được chạy trên thư mục thật: đợt da_kiem ở đó sẽ chặn lượt demo bằng D2-7.
    if os.getenv('RETAIL_NHAP_VOLUME') != KHO_THU:
        raise SystemExit('RETAIL_NHAP_VOLUME khong phai thu muc tong duyet; dung lai.')
    return nhap_do._default_store()


def _trang_thai_cloud():
    cloud = Databricks()
    try:
        return Registry(ROOT, cloud.query).read()['payload']
    finally:
        cloud.close()


def _tien(value):
    return Decimal(str(value)).quantize(XU)


def _doc_sales(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as stream:
        return {int(row['Date'].replace('-', '')): (_tien(row['Revenue']), _tien(row['COGS']))
                for row in csv.DictReader(stream)}


def so_ngay(mong_doi, thuc_te):
    """Số ngày lệch, kể cả ngày thiếu hoặc thừa."""
    return sum(mong_doi.get(day) != thuc_te.get(day) for day in set(mong_doi) | set(thuc_te))


def truoc():
    kho, client = _kho()
    rows = nhap_do._requests(kho)
    count = sum(1 for schema in client.schemas.list(catalog_name='retail_lab')
                if schema.name != 'information_schema'
                for _ in client.tables.list(catalog_name='retail_lab', schema_name=schema.name))
    state = _trang_thai_cloud()
    moc = {'active': state['active'], 'dashboard': state.get('dashboard')}
    MOC.write_text(json.dumps(moc), encoding='utf-8')
    print(json.dumps({'import_nhap_do': 'dat', 'kho_thu': KHO_THU, 'so_yeu_cau_co_san': len(rows),
                      'so_bang_view_liet_ke': count, 'dat_nguong_do': count + 183 <= 500, **moc}, ensure_ascii=False, indent=2))


def trang_thai():
    kho, _ = _kho()
    rows = [{key: row.get(key) for key in ('id', 'loai', 'nhan', 'trang_thai', 'duong', 'ten_mo_rong', 'ma_loi',
                                            'thong_bao', 'release_id')}
            | {'so_file': len(row['files']) if 'files' in row else 1} for row in nhap_do._requests(kho).values()]
    print(json.dumps(rows, ensure_ascii=False, indent=2))


# Phần mở rộng → bảng mart chứng minh dữ liệu mới đã vào (nghiệm thu local 2026-11-05: 80 shipper, 200 nhân viên).
BANG_MO_RONG = {'shipments_realistic': 'dim_shipper', 'orders_enriched': 'dim_sales_employee'}


def kiem_t2():
    """T2 (phiếu giao_viec_t2_mot_file_cloud): yêu cầu một file, bản chỉ dashboard, active không đổi."""
    kho, client = _kho()
    rows = {k: v for k, v in nhap_do._requests(kho).items() if v.get('loai') == 'mot_file'}
    moc = json.loads(MOC.read_text(encoding='utf-8'))
    count = sum(1 for schema in client.schemas.list(catalog_name='retail_lab')
                if schema.name != 'information_schema'
                for _ in client.tables.list(catalog_name='retail_lab', schema_name=schema.name))
    lenh = []
    for name in nhap_do.sequence_names(kho.liet_ke('lenh')):
        body = nhap_do._json(kho, 'lenh/' + name)
        try:
            result = nhap_do._json(kho, 'lenh/' + name[:-5] + '.ket_qua.json').get('ket_qua')
        except FileNotFoundError:
            result = None
        lenh.append({'so': int(name[:-5]), 'loai': body.get('loai'), 'ai': body.get('ai'),
                     'release_id': body.get('release_id'), 'ket_qua': result})
    hop_dong = {}
    for ten in kho.liet_ke('hop_dong_da_duyet'):
        hop_dong[ten] = sorted(n for n in kho.liet_ke('hop_dong_da_duyet/' + ten) if n.endswith('.yml'))
    cloud = Databricks()
    try:
        state = Registry(ROOT, cloud.query).read()['payload']
        goc = _doc_sales('data/sales.csv')
        yeu_cau, ban = [], {}
        for rid_row in sorted(rows.values(), key=lambda r: r['id']):
            try:
                notice = json.loads(kho.doc(nhap_do.request_path(rid_row['id']) + '/thong_bao.json'))['thong_bao']
            except FileNotFoundError:
                notice = None
            yeu_cau.append({k: rid_row.get(k) for k in ('id', 'trang_thai', 'duong', 'ten_mo_rong', 'release_id',
                                                        'cot_moi', 'thong_bao')}
                           | {'ly_do': [r['ma'] for r in rid_row.get('ly_do', [])], 'thong_bao_dashboard': notice})
            rid = rid_row.get('release_id')
            if not rid or rid in ban:
                continue
            identifier(f'r_{rid}_marts')
            record = state['releases'].get(rid, {})
            item = {'status': record.get('status'), 'chi_dashboard': record.get('chi_dashboard'),
                    'nguon_moi': record.get('nguon_moi'), 'co_tong_hop': record.get('co_du_lieu_tong_hop')}
            if record.get('status') == 'ready':
                _, daily = cloud.query(f'select date_sk, revenue, cogs from r_{rid}_marts.fact_daily_sales where is_actual')
                item['sales_lech_ngay'] = so_ngay(goc, {int(d): (_tien(g), _tien(c)) for d, g, c in daily})
                bang = BANG_MO_RONG.get(rid_row.get('ten_mo_rong'))
                if bang:
                    _, n = cloud.query(f'select count(*) from r_{rid}_marts.{identifier(bang)}')
                    item[bang] = int(n[0][0])
            ban[rid] = item
    finally:
        cloud.close()
    dat = {'active_khong_doi': state['active'] == moc['active'],
           'khong_ban_mot_file_nao_la_active': state['active'] not in ban,
           'ban_mot_file_deu_chi_dashboard': all(b['chi_dashboard'] is True and b['co_tong_hop'] is not True
                                                 for b in ban.values() if b['status'] == 'ready'),
           'sales_khong_doi': all(b.get('sales_lech_ngay', 0) == 0 for b in ban.values()),
           'lenh_deu_co_ket_qua': all(l['ket_qua'] in ('dat', 'loi') for l in lenh)}
    print(json.dumps({'moc': moc, 'active': state['active'], 'dashboard': state.get('dashboard'),
                      'dich_rollback': (state.get('dich_rollback') or {}).get('release_id'),
                      'so_bang_view_liet_ke': count, 'du_cho_luot_moi': count + 183 <= 500,
                      'yeu_cau': yeu_cau, 'ban': ban, 'lenh': lenh, 'hop_dong_da_duyet': hop_dong, 'dat': dat,
                      'ket_luan': 'DAT' if all(dat.values()) else 'CHUA DAT'}, ensure_ascii=False, indent=2))
    return 0 if all(dat.values()) else 1


def _co_quyen(cloud, doi_tuong, principal):
    _, rows = cloud.query(f'show grants on {doi_tuong}')
    return any(principal in row for row in rows)


def kiem():
    kho, _ = _kho()
    rows = nhap_do._requests(kho)
    if not rows:
        raise SystemExit('Chua co yeu cau nao trong thu muc tong duyet.')
    row = rows[max(rows)]
    ket_qua = {'request_id': row['id'], 'trang_thai': row['trang_thai'], 'so_file': len(row['files']),
               'ma_loi': row.get('ma_loi'), 'thong_bao': row.get('thong_bao')}
    dat = {'da_kiem': row['trang_thai'] == 'da_kiem', 'khong_co_lenh_dashboard': not kho.liet_ke('lenh')}
    if not dat['da_kiem']:
        print(json.dumps({**ket_qua, 'dat': dat, 'ket_luan': 'CHUA DAT'}, ensure_ascii=False, indent=2))
        return 1
    rid = row['release_id']
    identifier(f'r_{rid}_reporting')
    run_id = next(e['pipeline_run_id'] for e in reversed(row['lich_su']) if e['toi'] == 'dang_chay')
    context = json.loads((ROOT / 'runs' / run_id / 'context.json').read_text(encoding='utf-8'))
    manifest = json.loads((ROOT / 'snapshots' / context['snapshot_id'] / 'manifest.json').read_text(encoding='utf-8'))
    cloud = Databricks()
    try:
        state = Registry(ROOT, cloud.query).read()['payload']
        record = state['releases'].get(rid, {})
        moc = json.loads(MOC.read_text(encoding='utf-8'))
        dat.update(active_khong_doi=state['active'] == moc['active'],
                   dashboard_khong_doi=state.get('dashboard') == moc['dashboard'],
                   ban_ready=record.get('status') == 'ready',
                   co_tong_hop=record.get('co_du_lieu_tong_hop') is True)

        _, daily = cloud.query(f'select date_sk, revenue, cogs from r_{rid}_marts.fact_daily_sales where is_actual')
        thuc_te = {int(d): (_tien(g), _tien(c)) for d, g, c in daily}
        goc = _doc_sales('data/sales.csv')
        moi = _doc_sales(KIEM / 'sales_doi_chung.csv')
        lech_goc = so_ngay(goc, {d: v for d, v in thuc_te.items() if d in goc})
        lech_moi = so_ngay(moi, {d: v for d, v in thuc_te.items() if d not in goc})
        dat.update(so_ngay_khop=len(thuc_te) == len(goc) + len(moi),
                   ngay_goc_khong_doi=lech_goc == 0, ngay_2023_khop_doi_chung=lech_moi == 0)

        _, year = cloud.query(f'select g, r from r_{rid}_reporting.rpt_revenue_yearly where year = 2023')
        g, r = (_tien(year[0][0]), _tien(year[0][1])) if len(year) == 1 else (None, None)
        dat.update(g_2023_khop=g == G_2023, r_2023_khop=r == R_2023)

        catalog = cloud.catalog
        web, ai = os.getenv('RETAIL_APP_DBX_CLIENT_ID'), os.getenv('RETAIL_AI_DBX_CLIENT_ID')
        bang = f'table {catalog}.r_{rid}_reporting.rpt_revenue_yearly'
        schema = f'schema {catalog}.r_{rid}_reporting'
        dat.update(co_bien_danh_tinh_reader=bool(web and ai),
                   web_doc_duoc=bool(web) and _co_quyen(cloud, bang, web) and _co_quyen(cloud, schema, web),
                   ai_khong_doc_duoc=bool(ai) and not _co_quyen(cloud, bang, ai) and not _co_quyen(cloud, schema, ai))

        _, tables = cloud.query(f'show tables in {catalog}.r_{rid}_raw')
        co_san = {name for table in tables for name in table if isinstance(name, str)}
        so_dong = {}
        for name, item in sorted(manifest['sources'].items()):
            if name in co_san and isinstance(item.get('rows'), int):
                _, count = cloud.query(f'select count(*) from r_{rid}_raw.{identifier(name)}')
                so_dong[name] = {'manifest': item['rows'], 'kho': int(count[0][0])}
    finally:
        cloud.close()
    bad = [key for key, value in dat.items() if not value]
    print(json.dumps({**ket_qua, 'release_id': rid, 'pipeline_run_id': run_id, 'dat': dat,
                      'so_ngay': len(thuc_te), 'ngay_goc_lech': lech_goc, 'ngay_2023_lech': lech_moi,
                      'g_2023': str(g), 'r_2023': str(r), 'so_dong_cach_ly': context.get('so_dong_cach_ly'),
                      'so_dong_thong_tin': so_dong, 'muc_chua_dat': bad,
                      'ket_luan': 'DAT' if not bad else 'CHUA DAT'}, ensure_ascii=False, indent=2))
    return 1 if bad else 0


def _xoa_cay(client, thu_muc):
    for entry in client.files.list_directory_contents(thu_muc):
        path = entry.path.rstrip('/')
        if not path.startswith(KHO_THU + '/'):
            raise SystemExit('Duong dan ngoai thu muc tong duyet; dung lai.')
        if entry.is_directory:
            _xoa_cay(client, path)
        else:
            client.files.delete(path)
    client.files.delete_directory(thu_muc)


def xoa_kho():
    from databricks.sdk.errors import NotFound
    _, client = _kho()
    try:
        _xoa_cay(client, KHO_THU)
    except NotFound:
        pass
    print('Da xoa thu muc tong duyet.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('buoc', choices=('truoc', 'trang_thai', 'kiem', 'kiem_t2', 'xoa_kho'))
    return {'truoc': truoc, 'trang_thai': trang_thai, 'kiem': kiem, 'kiem_t2': kiem_t2,
            'xoa_kho': xoa_kho}[parser.parse_args().buoc]()


if __name__ == '__main__':
    sys.exit(main())
