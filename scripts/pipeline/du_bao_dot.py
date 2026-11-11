"""Bản có đợt (D3): dự báo đứng yên và biến dbt của kỳ.

Không train: chép nguyên kết quả của một bản gốc đã kiểm, ghi rõ nguồn. File này cố ý nằm ngoài
scripts/forecast, vì model_version() băm mọi file trong thư mục đó và kiểm code dự báo.
"""
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile

import duckdb

from scripts.pipeline import snapshot
from scripts.pipeline.state import Registry

DUCKDB_CONFIG = {'threads': 2, 'memory_limit': '2GB'}
LICH_CUOI = dt.date(2024, 7, 1)  # dim_date phủ tới ngày này (retail_dbt/models/marts/dim_date.sql)
NHOM_NOI = ('khop_loi', 'loi_kem_cot_them')  # nhóm file được nối vào nguồn lõi (scripts/ingest/dot.py)


def _digest(path):
    with Path(path).open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def _quoted(path):
    return "'" + Path(path).as_posix().replace("'", "''") + "'"


def ngay_thuc_te_cuoi(snapshot_path):
    with duckdb.connect(config=DUCKDB_CONFIG) as con:
        return con.execute('select max(cast("Date" as date)) from read_parquet('
                           + _quoted(Path(snapshot_path) / 'sales.parquet') + ')').fetchone()[0]


def ky_cua_ban(snapshot_path):
    """Kỳ suy ra từ dữ liệu của bản. Đợt chưa đủ năm tạm chặn (phiếu D3 §10 mục 2)."""
    last = ngay_thuc_te_cuoi(snapshot_path)
    if (last.month, last.day) != (12, 31):
        raise ValueError(f'Đợt kết thúc {last}, chưa đủ năm: chưa hỗ trợ ở D3')
    if last >= LICH_CUOI:
        raise ValueError(f'Đợt kết thúc {last}, vượt lịch dim_date và vùng dự báo tới {LICH_CUOI}')
    return {'analysis_end_year': last.year, 'last_actual_date': str(last)}


def so_dong_dot(batches):
    """Số dòng đã nối theo nguồn, lấy từ manifest. File master và file chỉ đề xuất không được nối."""
    total = {}
    for batch in batches:
        for item in batch['files']:
            if item.get('nhom') in NHOM_NOI:
                total[item['nguon']] = total.get(item['nguon'], 0) + item['so_dong']
    return total


def bien_dbt(context, manifest):
    meta = json.loads((Path(context['forecast_path']) / 'forecast_meta.json').read_text(encoding='utf-8'))
    source = meta.get('nguon_du_bao')
    if not source:
        raise ValueError('Dự báo của bản có đợt thiếu nguon_du_bao; chạy lại stage forecast')
    return {'co_dot': True, **ky_cua_ban(context['snapshot_path']),
            'forecast_trained_through': source['trained_through'],
            'dot_so_dong': so_dong_dot(manifest['dot'])}


def _kiem_hash(folder, meta, files):
    for name in files:
        if not (folder / name).exists() or _digest(folder / name) != meta['sha256'][name]:
            raise ValueError(f'Dự báo nguồn hỏng hoặc thiếu {name}')


def _kiem_nguon(root, release_id, target='duckdb', registry=None):
    """Trả (thư mục dự báo, meta, thư mục snapshot, bản ghi) của bản nguồn; sai điều kiện thì ValueError."""
    from scripts.forecast import stage
    state = (registry or Registry(root)).read()['payload']
    record = state['releases'].get(release_id)
    if not record or record.get('status') != 'ready':
        raise ValueError(f'Bản nguồn {release_id} không có trong registry hoặc chưa sẵn sàng')
    run = root / 'runs' / record['run_id']
    context = json.loads((run / 'context.json').read_text(encoding='utf-8'))
    if context.get('target') != target or context.get('release_id') != release_id:
        raise ValueError('Bản nguồn phải cùng target và đúng lượt chạy đó')
    source = root / 'snapshots' / record['snapshot_id']
    options = {'extension_directory': context['extension_dir']} if context.get('extension_dir') else {}
    if snapshot.validate(source, **options).get('dot'):
        raise ValueError('Bản nguồn có đợt; dự báo phải lấy từ bản gốc')
    folder = run / 'forecast'
    meta_path = folder / 'forecast_meta.json'
    if not meta_path.exists():
        raise ValueError('Bản nguồn chưa có kết quả dự báo')
    meta = json.loads(meta_path.read_text(encoding='utf-8'))
    _kiem_hash(folder, meta, stage.FILES)
    if meta.get('model_version') != stage.model_version():
        raise ValueError('Dự báo nguồn được tạo bởi code dự báo khác')
    return folder, meta, source, record


def _kiem_khop(folder, source, target):
    """Trả trained_through. Lịch sử của bản đợt phải trùng từng dòng với bản gốc, và đợt nối liền ngay sau đó."""
    with duckdb.connect(config=DUCKDB_CONFIG) as con:
        daily = _quoted(folder / 'forecast_daily.parquet')
        base = 'read_parquet(' + _quoted(source / 'sales.parquet') + ')'
        ours = 'read_parquet(' + _quoted(target / 'sales.parquet') + ')'
        moc = con.execute(f'select count(distinct trained_through), min(trained_through), min(forecast_date), '
                          f'max(forecast_date) from read_parquet({daily})').fetchone()
        if moc[0] != 1:
            raise ValueError('Dự báo nguồn phải có đúng một trained_through')
        trained, first, last = moc[1:]
        old = con.execute(f'select max(cast("Date" as date)) from {base}').fetchone()[0]
        if old != trained or first != trained + dt.timedelta(days=1):
            raise ValueError('Bản nguồn không kết thúc đúng ở trained_through của dự báo')
        columns = '"Date", "Revenue", "COGS"'
        same = f'select {columns} from {ours} where cast("Date" as date) <= date \'{trained}\''
        diff = con.execute(f'select count(*) from ((select {columns} from {base} except all {same}) '
                           f'union all ({same} except all select {columns} from {base}))').fetchone()[0]
        if diff:
            raise ValueError('sales của bản đợt khác bản nguồn ở kỳ gốc')
        low, high = con.execute(f'select min(cast("Date" as date)), max(cast("Date" as date)) from {ours} '
                                f'where cast("Date" as date) > date \'{trained}\'').fetchone()
    if low != trained + dt.timedelta(days=1):
        raise ValueError('Đợt không nối liền ngay sau trained_through của dự báo')
    if high >= last:
        raise ValueError('Không còn ngày dự báo nào sau ngày thực tế cuối')
    return trained


def _dung_lai(context, root, release_id, *, registry=None, same_sales=False):
    """Chép dự báo bản gốc vào lượt này. Chạy lại khi đã đúng thì không chép lại."""
    from scripts.forecast import stage
    root = Path(root)
    out = Path(context['directory']) / 'forecast'
    if not same_sales:
        ky_cua_ban(context['snapshot_path'])
    folder, meta, source, record = _kiem_nguon(root, release_id, context['target'], registry)
    check = _kiem_cung_sales if same_sales else _kiem_khop
    trained = check(folder, source, Path(context['snapshot_path']))
    nguon = {'release_id': release_id, 'snapshot_id': record['snapshot_id'], 'run_id': record['run_id'],
             'trained_through': str(trained)}
    keys = ('model_version', 'primary', 'selection_step', 'fits', 'seconds')
    existing = out / 'forecast_meta.json'
    if existing.exists():
        current = json.loads(existing.read_text(encoding='utf-8'))
        if current.get('snapshot_id') == context['snapshot_id'] and current.get('nguon_du_bao') == nguon:
            _kiem_hash(out, current, stage.FILES)
            return out.as_posix(), {**{k: current[k] for k in keys}, 'nguon_du_bao': nguon}
    new = {**meta, 'snapshot_id': context['snapshot_id'], 'run_id': context['run_id'], 'seconds': 0,
           'finished_at': dt.datetime.now(dt.timezone.utc).isoformat(), 'nguon_du_bao': nguon}
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix='forecast-', dir=out.parent))
    try:
        for name in stage.FILES:
            shutil.copyfile(folder / name, tmp / name)
        (tmp / 'forecast_meta.json').write_text(json.dumps(new, ensure_ascii=False, indent=2), encoding='utf-8')
        if out.exists():
            shutil.rmtree(out)
        os.replace(tmp, out)
    except BaseException:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    return out.as_posix(), {**{k: new[k] for k in keys}, 'nguon_du_bao': nguon}


def _kiem_cung_sales(folder, source, target):
    with duckdb.connect(config=DUCKDB_CONFIG) as con:
        columns = '"Date", "Revenue", "COGS"'
        base = 'select ' + columns + ' from read_parquet(' + _quoted(source / 'sales.parquet') + ')'
        ours = 'select ' + columns + ' from read_parquet(' + _quoted(target / 'sales.parquet') + ')'
        diff = con.execute(f'select count(*) from (({base} except all {ours}) union all '
                           f'({ours} except all {base}))').fetchone()[0]
        if diff:
            raise ValueError('sales khác bản nguồn; không dùng lại dự báo')
        count, trained = con.execute('select count(distinct trained_through), min(trained_through) '
            'from read_parquet(' + _quoted(folder / 'forecast_daily.parquet') + ')').fetchone()
        if count != 1:
            raise ValueError('Dự báo nguồn phải có đúng một trained_through')
        last = con.execute('select max(cast("Date" as date)) from read_parquet('
                           + _quoted(source / 'sales.parquet') + ')').fetchone()[0]
        if trained != last:
            raise ValueError('Dự báo nguồn không khớp ngày cuối của sales')
    return trained


def dung_lai(context, root, release_id, *, registry=None):
    return _dung_lai(context, root, release_id, registry=registry)


def dung_lai_cung_sales(context, root, release_id, *, registry=None):
    """Bản một file chỉ dùng lại dự báo khi toàn bộ sales giống hệt bản nguồn."""
    return _dung_lai(context, root, release_id, registry=registry, same_sales=True)
