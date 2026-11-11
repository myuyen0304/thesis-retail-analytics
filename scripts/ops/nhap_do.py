"""Dò yêu cầu đợt qua Files API; chỉ mở SQL khi sắp trigger pipeline.

Quota được ước tính từ schemas.list/tables.list, gồm view. Số đếm không gồm
bảng đã xóa còn bị tính trễ khoảng 7 ngày; pipeline writer không đọc được
quota thật (S0). Nếu dbt vẫn vượt quota, yêu cầu ra lỗi để DE chạy lại sau khi dọn.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path('warehouse/pipeline/docker')
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'apps' / 'retail_app'))
from ui.kho_dot import DaCo, KhoVolume, TrangThaiDaDoi, sequence_names
from ui.trang_thai_dot import ID_PATTERN, phat_lai, request_path, loai_cua
from scripts.ingest import dot
from scripts.pipeline.state import Registry

REPO = Path(__file__).resolve().parents[2]

SAFE_NAME = re.compile(r'[A-Za-z0-9_.-]+')


def _json(kho, path):
    return json.loads(kho.doc(path))


def _log(code, error):
    print(f'{code}: {type(error).__name__}', file=sys.stderr)


def _requests(kho):
    result = {}
    for request_id in sorted(kho.liet_ke('yeu_cau')):
        if not ID_PATTERN.fullmatch(request_id):
            continue
        folder = request_path(request_id)
        try:
            names = sequence_names(kho.liet_ke(folder + '/su_kien'))
            events = [(int(name[:-5]), _json(kho, folder + '/su_kien/' + name)) for name in names]
            body = _json(kho, folder + '/yeu_cau.json')
            if not isinstance(body, dict) or body.get('id') != request_id or body.get('loai') != loai_cua(request_id):
                raise ValueError('Yêu cầu hỏng')
            if body['loai'] == 'mot_file':
                for key in ('nguoi_gui', 'vai_tro', 'mo_ta', 'ngay_gui'):
                    if not isinstance(body.get(key), str):
                        raise ValueError('Metadata một file hỏng')
                _mot_file(body)
            state = phat_lai(events, body['loai'])
            if state['trang_thai'] == 'hong':
                raise ValueError('Sự kiện hỏng')
            result[request_id] = {**body, **state}
        except Exception as error:
            _log(request_id, error)
    return result


def _ledger(kho):
    records = {}
    names = sequence_names(kho.liet_ke('so_dot'))
    for name in names:
        item = _json(kho, 'so_dot/' + name)
        if not isinstance(item, dict) or not isinstance(item.get('ma_dot'), str):
            raise ValueError('Sổ đợt hỏng')
        if item.get('loai') == 'vao_so':
            if not isinstance(item.get('files'), list):
                raise ValueError('Sổ đợt hỏng')
            records[item['ma_dot']] = item
        elif item.get('loai') == 'bo':
            records.pop(item['ma_dot'], None)
        else:
            raise ValueError('Sổ đợt hỏng')
    return list(records.values()), len(names)


def _event(kho, row, target, **extra):
    body = {'toi': target, 'ai': 'airflow', 'ghi_chu': '', **extra}
    return kho.ghi_json_so_tiep(request_path(row['id']) + '/su_kien', body,
                                expected=len(row['lich_su']))


def _ma_dot(row):
    return next((event['ma_dot'] for event in reversed(row['lich_su'])
                 if event.get('toi') in ('cho_chay', 'het_cho') and isinstance(event.get('ma_dot'), str)), None)

def _running(rows):
    for row in rows.values():
        if row['trang_thai'] != 'dang_chay':
            continue
        try:
            event = next(e for e in reversed(row['lich_su']) if e['toi'] == 'dang_chay')
            if (not isinstance(event.get('airflow_run_id'), str)
                    or not isinstance(event.get('pipeline_run_id'), str)
                    or not isinstance(event.get('conf'), dict)):
                raise ValueError('Sự kiện chạy hỏng')
            yield row, event
        except Exception as error:
            _log(row['id'], error)


def _files(row):
    files = row['files']
    if not isinstance(files, list) or not files:
        raise ValueError('Danh sách file hỏng')
    names = set()
    for item in files:
        name = item['ten']
        if (not isinstance(name, str) or not SAFE_NAME.fullmatch(name) or '..' in name
                or name in names or type(item['so_byte']) is not int or item['so_byte'] < 0
                or not isinstance(item['sha256'], str)
                or not re.fullmatch(r'[a-f0-9]{64}', item['sha256'])):
            raise ValueError('Tên file hoặc checksum hỏng')
        names.add(name)
    return files


def _download(kho, row, root):
    folder = root / 'nhap' / row['id'] / 'file'
    folder.mkdir(parents=True, exist_ok=True)
    temporary_folder = folder.parent / '.tam'
    for item in _files(row):
        target = folder / item['ten']
        if target.exists() and target.stat().st_size == item['so_byte']:
            with target.open('rb') as stream:
                if hashlib.file_digest(stream, 'sha256').hexdigest() == item['sha256']:
                    continue
        content = kho.doc(request_path(row['id']) + '/file/' + item['ten'])
        if len(content) != item['so_byte'] or hashlib.sha256(content).hexdigest() != item['sha256']:
            raise ValueError('File không khớp checksum')
        temporary_folder.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=temporary_folder, prefix='.tai_', delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(content)
        try:
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
    return folder


def _quota(client):
    """Ước tính quota catalog; bỏ schema hệ thống, tính view của dự án."""
    count = 0
    for schema in client.schemas.list(catalog_name='retail_lab'):
        if schema.name == 'information_schema':
            continue
        for _ in client.tables.list(catalog_name='retail_lab', schema_name=schema.name):
            count += 1
    return count + 183 <= 500


def _cli(args):
    return subprocess.run([sys.executable, '-m', 'scripts.pipeline.cli', *args],
                          cwd=Path(__file__).resolve().parents[2], capture_output=True, timeout=300)


def _command_result(kho, name, result, message=''):
    path = 'lenh/' + name[:-5] + '.ket_qua.json'
    try:
        kho.ghi_moi(path, json.dumps({'ket_qua': result, 'thong_bao': message},
                                    ensure_ascii=False).encode('utf-8'))
    except DaCo:
        pass


def _run_cli(call, stage, number, release_id=None, *, mot_file=False):
    args = [stage, '--run-id', 'lenh_' + str(number), '--target', 'databricks', '--root', str(ROOT)]
    if release_id:
        args += ['--release-id', release_id, '--xac-nhan-nguon-moi' if mot_file else '--xac-nhan-tong-hop']
    try:
        response = call(args)
        return response if isinstance(response, int) else response.returncode
    except subprocess.TimeoutExpired:
        return -1


def _process_command(kho, rows, call, ledger):
    names = sequence_names(kho.liet_ke('lenh'))
    if not names:
        return
    name = None
    for candidate in reversed(names):
        try:
            kho.doc('lenh/' + candidate[:-5] + '.ket_qua.json')
        except FileNotFoundError:
            name = candidate
            break
    if name is None:
        return
    try:
        command = _json(kho, 'lenh/' + name)
        kind = command['loai']
        if kind not in ('dat', 'tra'):
            raise ValueError('Lệnh hỏng')
    except Exception:
        _command_result(kho, name, 'loi', 'Dữ liệu lệnh hỏng; báo kỹ sư dữ liệu.')
        return
    number = int(name[:-5])
    if kind == 'dat':
        request_id, rid = command.get('request_id'), command.get('release_id')
        row = rows.get(request_id)
        if (not row or not isinstance(rid, str) or row.get('release_id') != rid or (row.get('loai') != 'mot_file' and not _ma_dot(row))
                or row['trang_thai'] not in ('da_kiem', 'da_tra', 'tren_dashboard')):
            _command_result(kho, name, 'loi', 'Bản không đạt điều kiện đưa lên dashboard.')
            return
        if ledger is None and row.get('loai') != 'mot_file':
            return
    try:
        code = _run_cli(call, 'dat-dashboard' if kind == 'dat' else 'tra-dashboard', number,
                        rid if kind == 'dat' else None, **({'mot_file': True} if kind == 'dat' and row.get('loai') == 'mot_file' else {}))
    except Exception as error:
        _log('lenh_' + str(number), error)
        code = -1
    if code == 75:
        return
    if code:
        message = ('Bản không đạt điều kiện đưa lên dashboard.' if code == 2
                   else 'Chưa đổi được dashboard; thử lại sau ít phút.')
        _command_result(kho, name, 'loi', message)
        return
    if kind == 'dat':
        if row.get('loai') != 'mot_file':
            entries, size = _ledger(kho)
            if not _ma_dot(row):
                raise ValueError('Yêu cầu thiếu mã đợt')
            if not any(entry['ma_dot'] == _ma_dot(row) for entry in entries):
                kho.ghi_json_so_tiep('so_dot', {'loai': 'vao_so', 'ma_dot': _ma_dot(row),
                    'request_id': request_id, 'release_id': rid, 'files': row['files']}, expected=size)
        for other in rows.values():
            if other['id'] != request_id and other['trang_thai'] == 'tren_dashboard':
                _event(kho, other, 'da_tra', ghi_chu='Thay bằng bản mới')
        if row['trang_thai'] in ('da_kiem', 'da_tra'):
            _event(kho, row, 'tren_dashboard')
    else:
        for row in rows.values():
            if row['trang_thai'] == 'tren_dashboard':
                _event(kho, row, 'da_tra')
    _command_result(kho, name, 'dat')


def quet(kho, client, *, root=ROOT, call=_cli, cloud_factory=None):
    """Đợt chỉ đọc Files API/metadata; một file đã duyệt đọc thêm registry để kiểm trùng."""
    root = Path(root)
    rows = _requests(kho)
    try:
        ledger, _ = _ledger(kho)
    except Exception as error:
        _log('so_dot', error)
        ledger = None
    try:
        _process_command(kho, rows, call, ledger)
    except Exception as error:
        _log('lenh', error)
    # Lệnh có thể vừa ghi sổ hoặc đổi trạng thái; phân loại theo dữ liệu mới nhất.
    rows = _requests(kho)
    if ledger is not None:
        try:
            ledger, _ = _ledger(kho)
        except Exception as error:
            _log('so_dot', error)
            ledger = None
    just_reserved = set()
    for row in rows.values():
        state = row['trang_thai']
        if row.get('loai') == 'mot_file':
            try:
                _quet_mot(kho, client, row, root, cloud_factory)
            except TrangThaiDaDoi:
                pass
            except Exception as error:
                _log(row['id'], error)
            continue
        if state not in ('da_gui', 'dang_kiem', 'het_cho'):
            continue
        if ledger is None:
            continue
        try:
            if state == 'da_gui':
                try:
                    _download(kho, row, root)
                except (ValueError, KeyError, TypeError, FileNotFoundError):
                    _event(kho, row, 'loi_file')
                    continue
                _event(kho, row, 'dang_kiem')
                row = _requests(kho)[row['id']]
                state = 'dang_kiem'
            if state == 'dang_kiem':
                try:
                    folder = _download(kho, row, root)
                except (ValueError, KeyError, TypeError, FileNotFoundError):
                    # dang_kiem chưa cho phép loi_file; để lần dò sau thử tải lại.
                    continue
                try:
                    batch, _ = dot.classify(folder, 'data')
                except dot.DotError as error:
                    code, _, text = str(error).partition(':')
                    _event(kho, row, 'sai_hop_dong', ma_loi=code, thong_bao=text.strip())
                    continue
                ma_dot = batch['ma_dot']
                duplicate = ma_dot in just_reserved or any(entry['ma_dot'] == ma_dot for entry in ledger)
                duplicate |= any(other['id'] != row['id'] and _ma_dot(other) == ma_dot
                                 and other['trang_thai'] in ('cho_chay', 'dang_chay', 'het_cho', 'da_kiem')
                                 for other in rows.values())
                if duplicate:
                    _event(kho, row, 'sai_hop_dong', ma_loi='D2-7', thong_bao='Đợt đã có hoặc đang chờ chạy.')
                    continue
            else:
                ma_dot = _ma_dot(row)
            enough = _quota(client)
            target = 'cho_chay' if enough else 'het_cho'
            if state != 'het_cho' or enough:
                _event(kho, row, target, ma_dot=ma_dot)
                just_reserved.add(ma_dot)
        except TrangThaiDaDoi:
            continue
        except Exception as error:
            _log(row['id'], error)
    return {'dang_chay': [{'request_id': row['id'], 'airflow_run_id': event['airflow_run_id'],
                           'pipeline_run_id': event['pipeline_run_id'], 'conf': event['conf']}
                          for row, event in _running(_requests(kho))]}


def _read_stage(root, run_id, name):
    if not re.fullmatch(r'[a-zA-Z0-9_-]{1,100}', run_id):
        raise ValueError('Mã lượt chạy hỏng')
    path = root / 'runs' / run_id / name
    return json.loads(path.read_text(encoding='utf-8'))


def ket_thuc(kho, states, *, root=ROOT, cloud_factory=None):
    """Theo dõi lượt đang chạy, rồi chuẩn bị tối đa một trigger."""
    if cloud_factory is None:
        from scripts.pipeline.runtime import Databricks
        cloud_factory = Databricks
    root = Path(root)
    rows = _requests(kho)
    trigger = []
    for row, event in _running(rows):
        run_id = event['airflow_run_id']
        state = states.get(run_id)
        if state is None:
            trigger.append({'airflow_run_id': run_id, 'conf': event['conf']})
            continue
        if state in ('queued', 'running'):
            continue
        try:
            if state == 'success':
                try:
                    context = _read_stage(root, event['pipeline_run_id'], 'context.json')
                except (OSError, ValueError):
                    context = {}
                marker = 'chi_dashboard' if row.get('loai') == 'mot_file' else 'co_du_lieu_tong_hop'
                if (context.get('stage') == 'validated' and context.get(marker) is True
                        and isinstance(context.get('release_id'), str)):
                    _event(kho, row, 'da_kiem', release_id=context['release_id'])
                    if row.get('loai') == 'mot_file' and row.get('duong') == 'tu_dong':
                        _auto_dashboard(kho, dict(row, release_id=context['release_id']), root, cloud_factory)
                else:
                    _event(kho, row, 'loi', thong_bao='Lượt chạy chưa đạt bước kiểm; kỹ sư dữ liệu xem nhật ký.')
            else:
                try:
                    failure = _read_stage(root, event['pipeline_run_id'], 'failure.json')
                except (OSError, ValueError):
                    failure = {}
                stage = failure.get('stage') if isinstance(failure.get('stage'), str) else 'không rõ'
                stage = stage if re.fullmatch(r'[a-z_]+', stage) else 'không rõ'
                extra = {'ma_loi': failure['ma_loi']} if isinstance(failure.get('ma_loi'), str) and re.fullmatch(r'D2-[A-Za-z0-9-]+', failure['ma_loi']) else {}
                _event(kho, row, 'loi', thong_bao=f'Lượt chạy lỗi ở bước {stage}; kỹ sư dữ liệu xem nhật ký.', **extra)
        except TrangThaiDaDoi:
            continue
        except Exception as error:
            _log(row['id'], error)
    rows = _requests(kho)
    if any(row['trang_thai'] == 'dang_chay' for row in rows.values()):
        return {'trigger': trigger}
    candidates = sorted((row for row in rows.values() if row['trang_thai'] == 'cho_chay'), key=lambda row: row['id'])
    if not candidates:
        return {'trigger': trigger}
    row = candidates[0]
    try:
        ledger = _ledger(kho)[0] if row.get('loai') != 'mot_file' else []
        cloud = cloud_factory()
        try:
            state = Registry(root, cloud.query).read()['payload']
            active = state['active']
            record = state['releases'][active]
        finally:
            cloud.close()
        manifest = json.loads((root / 'snapshots' / record['snapshot_id'] / 'manifest.json').read_text(encoding='utf-8'))
        extensions = sorted(name for name, item in manifest['sources'].items() if item.get('mo_rong'))
        lan = sum(e['toi'] == 'dang_chay' for e in row['lich_su']) + 1
        if row.get('loai') == 'mot_file':
            try:
                doc, raw = _mot_contract(kho, row)
                _download_mot(kho, row)
                own = row['ten_mo_rong']
                extensions = sorted(set(extensions) | {own})
                folder = root / 'nhap' / row['id'] / 'hop_dong'
                folder.mkdir(parents=True, exist_ok=True)
                for name in extensions:
                    content = raw if name == own else (REPO / 'scripts/ingest/extensions' / (name + '.yml')).read_bytes()
                    from ui.kho_hop_dong import load_raw
                    load_raw(name, content)
                    (folder / (name + '.yml')).write_bytes(content)
            except Exception as error:
                _log(row['id'], error)
                _event(kho, row, 'loi', thong_bao='Hợp đồng hoặc file không còn hợp lệ; cần đội dữ liệu kiểm tra.')
                return {'trigger': trigger}
            run_id = f"mot_{row['id']}_{lan}"
            conf = {'request_id': row['id'], 'target': 'databricks', 'dots': [],
                    'extension_dir': folder.resolve().as_posix(), 'chi_dashboard': True,
                    'du_bao_tu': active, 'extensions': extensions, 'pipeline_run_id': run_id}
        else:
            dots = []
            for entry in ledger:
                old = rows[entry['request_id']]
                path = _download(kho, {'id': old['id'], 'files': entry['files']}, root)
                dots.append(str(path.resolve()))
            path = _download(kho, row, root)
            dots.append(str(path.resolve()))
            run_id = f"dot_{row['id']}_{lan}"
            conf = {'request_id': row['id'], 'target': 'databricks', 'dots': dots,
                    'du_bao_tu': active, 'extensions': extensions, 'pipeline_run_id': run_id}
        _event(kho, row, 'dang_chay', lan=lan, airflow_run_id=run_id, pipeline_run_id=run_id, conf=conf)
        trigger.append({'airflow_run_id': run_id, 'conf': conf})
    except TrangThaiDaDoi:
        pass
    except Exception as error:
        _log(row['id'], error)
    return {'trigger': trigger}



def _mot_file(row):
    item = row.get('file')
    _files({'files': [item]})
    if not item['ten'].lower().endswith(('.csv', '.json')) or item['so_byte'] > 200 * 1024**2:
        raise ValueError('Một file chỉ nhận CSV/JSON tối đa 200 MB')
    return item


def _put(kho, path, raw):
    try:
        kho.ghi_moi(path, raw)
    except DaCo:
        if kho.doc(path) != raw:
            raise ValueError('Nội dung bất biến đã khác')


def _download_mot(kho, row):
    item = _mot_file(row)
    folder = REPO / 'data/ui_nhap_cloud' / row['id']
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / item['ten']
    if target.exists() and target.stat().st_size == item['so_byte']:
        with target.open('rb') as handle:
            if hashlib.file_digest(handle, 'sha256').hexdigest() == item['sha256']:
                return target
    raw = kho.doc(request_path(row['id']) + '/file/' + item['ten'])
    if len(raw) != item['so_byte'] or hashlib.sha256(raw).hexdigest() != item['sha256']:
        raise ValueError('File không khớp checksum')
    with tempfile.NamedTemporaryFile(dir=folder, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(raw)
    try:
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
    return target


def _mot_contract(kho, row):
    from ui.kho_hop_dong import KhoHopDong, load_raw, chu_ky_nghiep_vu
    from scripts.ingest import approval
    name = row.get('ten_mo_rong')
    registry = KhoHopDong(kho, REPO / 'scripts/ingest/extensions')
    registry.folder(name)  # Kiểm tên trước khi dựng đường dẫn.
    raw = kho.doc(request_path(row['id']) + '/hop_dong/' + name + '.yml')
    doc = load_raw(name, raw)
    expected_file = f"ui_nhap_cloud/{row['id']}/{_mot_file(row)['ten']}"
    if (doc['hop_dong_sha256'] != row.get('hop_dong_sha256') or doc['ten'] != name
            or doc['file'] != expected_file
            or not approval.has_dbt_model(name, REPO / 'retail_dbt/models')):
        raise ValueError('Hợp đồng không khớp yêu cầu hoặc thiếu model')
    signature = row.get('chu_ky_nghiep_vu')
    if signature is not None and signature != chu_ky_nghiep_vu(doc):
        raise ValueError('Chữ ký nghiệp vụ không khớp hợp đồng đã duyệt')
    registry.current(name)  # Có v mới hỏng thì dừng, không lùi về repo.
    return doc, raw


def _payload(root, cloud_factory=None):
    if cloud_factory is None:
        from scripts.pipeline.runtime import Databricks
        cloud_factory = Databricks
    cloud = cloud_factory()
    try:
        return Registry(root, cloud.query).read()['payload']
    finally:
        cloud.close()


def _mot_duplicate(kho, row, doc, root, cloud_factory):
    state = _payload(root, cloud_factory)
    releases = state['releases']
    if not isinstance(releases, dict):
        raise ValueError('Registry hỏng')
    dashboard = state.get('dashboard')
    manifests = {}

    def read_manifest(record):
        manifest = _read_stage_manifest(root, record)
        if (not isinstance(manifest, dict) or not isinstance(manifest.get('sources'), dict)
                or any(not isinstance(item, dict) for item in manifest['sources'].values())):
            raise ValueError('Manifest hỏng')
        return manifest

    # Con trỏ đang phục vụ không được âm thầm bỏ qua khi hỏng.
    if dashboard is not None:
        if (not isinstance(dashboard, str) or not re.fullmatch(r'[a-f0-9]{24}', dashboard)
                or not isinstance(releases.get(dashboard), dict)
                or releases[dashboard].get('status') != 'ready'):
            raise ValueError('Con trỏ dashboard hỏng')
        manifests[dashboard] = read_manifest(releases[dashboard])

    signature = row.get('chu_ky_nghiep_vu')
    if not isinstance(signature, str) or not signature:
        return False  # Yêu cầu từ phiên bản cũ chưa có chữ ký: không đoán là trùng.
    for other in _requests(kho).values():
        if (other['id'] == row['id'] or other.get('loai') != 'mot_file'
                or other['trang_thai'] not in ('da_kiem', 'tren_dashboard', 'da_tra')
                or other.get('ten_mo_rong') != row['ten_mo_rong']
                or other.get('chu_ky_nghiep_vu') != signature):
            continue
        rid = other.get('release_id')
        record = releases.get(rid)
        if (not isinstance(record, dict) or record.get('status') != 'ready'
                or record.get('co_du_lieu_tong_hop') is True):
            continue  # Bản đợt không phải bản hợp đồng một file.
        try:
            manifest = manifests[rid] if rid in manifests else read_manifest(record)
            item = manifest['sources'].get(row['ten_mo_rong'], {})
            if not isinstance(item, dict):
                raise ValueError('Nguồn trong manifest hỏng')
        except Exception:
            if rid == dashboard:
                raise
            continue  # Bản cũ không đang phục vụ, mất manifest thì cho phép dựng lại.
        if item.get('csv_sha256') == row['file']['sha256']:
            return True
    return False


def _read_stage_manifest(root, record):
    sid = record.get('snapshot_id')
    if not isinstance(sid, str) or not re.fullmatch(r'[a-f0-9]{12}', sid):
        raise ValueError('Mã snapshot hỏng')
    return json.loads((root / 'snapshots' / sid / 'manifest.json').read_text(encoding='utf-8'))


def _safe_proposal(value):
    # Giữ thống kê và tên cột; không đưa giá trị ô hoặc ánh xạ ID lên đề xuất cloud.
    if isinstance(value, dict):
        return {key: ([] if key in ('mau', 'anh_xa') else _safe_proposal(item))
                for key, item in value.items()}
    if isinstance(value, list):
        return [_safe_proposal(item) for item in value]
    return value


def _quet_mot(kho, client, row, root, cloud_factory):
    from datetime import datetime, timezone
    from ui.kho_hop_dong import KhoHopDong, load_raw, chu_ky_nghiep_vu
    from scripts.ingest import approval, auto_mapping, tu_dong
    import yaml
    folder = request_path(row['id'])
    state = row['trang_thai']
    if state == 'da_gui':
        try:
            _download_mot(kho, row)
        except Exception as error:
            _log(row['id'], error)
            _event(kho, row, 'loi_file')
            return
        _event(kho, row, 'dang_doc')
        row = _requests(kho)[row['id']]
        state = 'dang_doc'
    if state == 'dang_doc':
        try:
            proposal = auto_mapping.propose(_download_mot(kho, row), REPO / 'data')
            proposal = _safe_proposal(proposal)
            with tempfile.TemporaryDirectory() as temporary:
                files = auto_mapping.write_proposal(proposal, Path(temporary) / 'de_xuat')
                for file in files:
                    _put(kho, folder + '/de_xuat/' + file.name, file.read_bytes())
        except Exception as error:
            _log(row['id'], error)
            _event(kho, row, 'loi_de_xuat', thong_bao='Chưa đọc được file; cần đội dữ liệu kiểm tra.')
            return
        try:
            registry = KhoHopDong(kho, REPO / 'scripts/ingest/extensions')
            candidates = registry.ung_vien(proposal)
            complete = [c for c in candidates if not c[3]]
            model = len(complete) == 1 and approval.has_dbt_model(complete[0][0], REPO / 'retail_dbt/models')
            result = tu_dong.phan_loai(proposal, candidates, model)
            if result['ket_qua'] != 'tu_dong':
                _event(kho, row, 'cho_duyet', duong='tay', ly_do=result['ly_do'])
                return
            name = result['ten']
            meta, approved = registry.current(name)
            if meta['phien_ban'] != result['phien_ban']:
                raise ValueError('Hợp đồng đã đổi')
            doc = tu_dong.hop_dong_cua_luot(approved, [c['ten_trong_file'] for c in proposal['cot']],
                f"ui_nhap_cloud/{row['id']}/{row['file']['ten']}", meta['phien_ban'],
                datetime.now(timezone.utc).isoformat())
            raw = yaml.safe_dump(doc, allow_unicode=True, sort_keys=False).encode('utf-8')
            checked = load_raw(name, raw)
            _put(kho, folder + '/hop_dong/' + name + '.yml', raw)
            _event(kho, row, 'da_duyet', duong='tu_dong', ten_mo_rong=name,
                   hop_dong_sha256=checked['hop_dong_sha256'], cot_moi=result['cot_moi'],
                   chu_ky_nghiep_vu=chu_ky_nghiep_vu(checked))
        except TrangThaiDaDoi:
            raise
        except Exception as error:
            _log(row['id'], error)
            reason = {'ma': 'hop_dong_khong_hop_le', 'nghiep_vu': 'Hợp đồng cần đội dữ liệu kiểm tra.',
                      'ky_thuat': 'Hợp đồng chưa qua kiểm tra.'}
            _event(kho, row, 'cho_duyet', duong='tay', ly_do=[reason])
            return
        row = _requests(kho)[row['id']]
        state = 'da_duyet'
    if state in ('da_duyet', 'het_cho'):
        try:
            _download_mot(kho, row)
            doc, _ = _mot_contract(kho, row)
            if _mot_duplicate(kho, row, doc, root, cloud_factory):
                _event(kho, row, 'khong_moi')
                return
        except Exception as error:
            _log(row['id'], error)
            _event(kho, row, 'loi', thong_bao='Hợp đồng hoặc file không còn hợp lệ; cần đội dữ liệu kiểm tra.')
            return
        enough = _quota(client)
        if enough or state != 'het_cho':
            _event(kho, row, 'cho_chay' if enough else 'het_cho')


def _auto_dashboard(kho, row, root, cloud_factory):
    try:
        state = _payload(root, cloud_factory)
        record = state['releases'].get(row['release_id'], {})
        names = sequence_names(kho.liet_ke('lenh'))
        pending = False
        for name in names:
            result = _json(kho, 'lenh/' + name[:-5] + '.ket_qua.json')
            if not isinstance(result, dict) or result.get('ket_qua') not in ('dat', 'loi'):
                pending = True
                break
        if state.get('dashboard') is not None or pending or record.get('status') != 'ready' or record.get('chi_dashboard') is not True:
            raise ValueError('Dashboard cần Admin kiểm tra')
        kho.ghi_json_so_tiep('lenh', {'loai': 'dat', 'request_id': row['id'],
            'release_id': row['release_id'], 'ai': 'airflow'}, expected=int(names[-1][:-5]) if names else 0)
        return
    except Exception as error:
        _log(row['id'], error)
    try:
        kho.ghi_moi(request_path(row['id']) + '/thong_bao.json',
            json.dumps({'thong_bao': 'Dashboard đang có bản khác; chờ Admin đưa lên.'}, ensure_ascii=False).encode('utf-8'))
    except DaCo:
        pass

def _default_store():
    from databricks.sdk import WorkspaceClient
    required = ('DATABRICKS_HOST', 'RETAIL_PIPELINE_CLIENT_ID', 'RETAIL_PIPELINE_CLIENT_SECRET')
    if any(not os.getenv(key) for key in required):
        raise ValueError('Thiếu cấu hình kho đợt')
    client = WorkspaceClient(host=os.environ['DATABRICKS_HOST'], client_id=os.environ['RETAIL_PIPELINE_CLIENT_ID'],
                             client_secret=os.environ['RETAIL_PIPELINE_CLIENT_SECRET'], auth_type='oauth-m2m')
    return KhoVolume(os.getenv('RETAIL_NHAP_VOLUME', '/Volumes/retail_lab/nhap_du_lieu/kho'), client), client


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=('quet', 'ket_thuc'))
    parser.add_argument('--trang-thai', default='{}')
    args = parser.parse_args()
    kho, client = _default_store()
    result = quet(kho, client) if args.stage == 'quet' else ket_thuc(kho, json.loads(args.trang_thai))
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
