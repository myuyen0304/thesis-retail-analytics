"""Thử V1–V6 và dọn bằng Files API giả, tuyệt đối không mở cloud."""
import io
import json
import logging
from pathlib import Path
import re
import subprocess
import sys
from threading import Barrier, BrokenBarrierError, Lock
from types import SimpleNamespace

from databricks.sdk.errors import AlreadyExists, NotFound, PermissionDenied, Unauthenticated
import pytest

from scripts.ops import thu_kho_volume as probe


ROOT = probe.DEFAULT_ROOT
OTHER = ROOT + '/thu_ket_noi/20260101T000000Z_abcdef'
SECRET = 'secret-mau-khong-duoc-in'
HOST = 'https://workspace-mau.invalid'
CLIENT_ID = 'client-id-mau'


class FakeFiles:
    """Xóa file và xóa thư mục tách biệt đúng giao diện SDK."""
    def __init__(self, fault=None, cleanup_fault=None, directory_slash=False):
        self.data = {}
        self.directories = {ROOT}
        self.calls = []
        self.upload_sizes = {}
        self.lock = Lock()
        self.barriers = {}
        self.fault = fault
        self.cleanup_fault = cleanup_fault
        self.directory_slash = directory_slash
        self.cleaning = False
        self.foreign_entries = []

    def upload(self, path, contents, *, overwrite=False):
        assert overwrite is False
        data = contents.read()
        if '/v5/' in path:
            with self.lock:
                barrier = self.barriers.setdefault(path, Barrier(2, timeout=5))
            barrier.wait()
        with self.lock:
            self.calls.append(('upload', path))
            self.upload_sizes[path] = len(data)
            if self.fault == 'auth':
                raise Unauthenticated(SECRET)
            if self.fault == 'permission' and '/v1/' in path:
                raise PermissionDenied(SECRET)
            if self.fault == 'write' and '/v4/' in path:
                raise RuntimeError(SECRET)
            if path in self.data:
                if self.fault == 'duplicate_no_error' and '/v1/' in path:
                    return
                if self.fault == 'duplicate_changed' and '/v1/' in path:
                    self.data[path] = data
                if self.fault != 'race_overwrite' or '/v5/' not in path:
                    raise AlreadyExists(SECRET)
            self.data[path] = data
            parent = path.rsplit('/', 1)[0]
            while parent.startswith(ROOT):
                self.directories.add(parent)
                parent = parent.rsplit('/', 1)[0]

    def download(self, path):
        with self.lock:
            self.calls.append(('download', path))
            if path not in self.data:
                raise NotFound(SECRET)
            data = self.data[path]
        if self.fault == 'byte' and '/v1/' in path:
            data = b'sai'
        if self.fault in ('ma', 'ma_different') and '/v4/' in path:
            record = json.loads(data)
            record['ma'] = ('1' if self.fault == 'ma_different' and path.endswith('000002.json') else '0') * 32
            data = json.dumps(record).encode()
        if self.fault == 'wrong_winner' and '/v5/' in path:
            record = json.loads(data)
            record['luong'] = 1 - record['luong']
            data = json.dumps(record).encode()
        if self.fault == 'megabyte' and '/v6/' in path:
            data = data[:-1] + b'x'
        return SimpleNamespace(contents=io.BytesIO(data))

    def list_directory_contents(self, path):
        with self.lock:
            self.calls.append(('list', path))
            if re.fullmatch(re.escape(ROOT) + r'/thu_ket_noi/[0-9TZ]+_[a-f0-9]{6}', path):
                self.cleaning = True
            if self.cleaning and self.cleanup_fault == 'list':
                raise RuntimeError(SECRET)
            if self.fault == 'missing_not_empty' and path.endswith('/khong_co'):
                return [SimpleNamespace(path=path + '/file', is_directory=False)]
            if path not in self.directories:
                raise NotFound(SECRET)
            entries = [SimpleNamespace(path=name, is_directory=False) for name in self.data
                       if name.rsplit('/', 1)[0] == path]
            entries += [SimpleNamespace(path=name + ('/' if self.directory_slash else ''), is_directory=True)
                        for name in self.directories if name.rsplit('/', 1)[0] == path]
            if self.fault == 'extra_event' and re.search(r'/v5/[0-4]$', path) and not self.cleaning:
                entries.append(SimpleNamespace(path=path + '/extra.bin', is_directory=False))
            if self.fault == 'list_empty' and not self.cleaning and path.endswith('/v1'):
                return []
            if self.cleaning:
                entries += self.foreign_entries
            return entries

    def delete(self, path):
        self.calls.append(('delete', path))
        if self.cleanup_fault == 'delete':
            raise RuntimeError(SECRET)
        if path in self.directories:
            raise IsADirectoryError(SECRET)
        if path not in self.data:
            raise NotFound(SECRET)
        del self.data[path]

    def delete_directory(self, path):
        self.calls.append(('delete_directory', path))
        if self.cleanup_fault == 'directory':
            raise RuntimeError(SECRET)
        if path in self.data:
            raise NotADirectoryError(SECRET)
        if any(name.startswith(path + '/') for name in self.data.keys() | self.directories):
            raise OSError(SECRET)
        if path not in self.directories:
            raise NotFound(SECRET)
        self.directories.remove(path)


@pytest.fixture
def env_file(tmp_path):
    path = tmp_path / 'credentials.env'
    path.write_text(f'RETAIL_NHAP_DBX_CLIENT_ID={CLIENT_ID}\n'
                    f'RETAIL_NHAP_DBX_CLIENT_SECRET="{SECRET}"\n'
                    f'RETAIL_PIPELINE_CLIENT_ID=pipeline-id\n'
                    f'RETAIL_PIPELINE_CLIENT_SECRET=pipeline-secret\n'
                    f'DATABRICKS_HOST={HOST}\n'
                    'IGNORED="unterminated\n', encoding='utf-8')
    return path


def invoke(env_file, files, capsys, identity='writer', extra=()):
    options = []

    def factory(**kwargs):
        options.append(kwargs)
        # Ngay cả khi SDK in hoặc log cấu hình, đầu ra chỉ còn thông báo kiểm soát.
        print(SECRET)
        print(HOST, file=sys.stderr)
        logging.getLogger('databricks.sdk').warning(CLIENT_ID)
        return SimpleNamespace(files=files, config=SimpleNamespace(authenticate=lambda: {}))

    status = probe.main(['--env-file', str(env_file), '--danh-tinh', identity, *extra], client_factory=factory)
    captured = capsys.readouterr()
    for value in (SECRET, HOST, CLIENT_ID, 'pipeline-secret', 'pipeline-id'):
        assert value not in captured.out + captured.err
    assert not captured.err
    return status, captured.out, options


@pytest.mark.parametrize('identity', ['writer', 'pipeline'])
@pytest.mark.parametrize('directory_slash', [False, True])
def test_all_checks_and_cleanup(env_file, capsys, identity, directory_slash):
    files = FakeFiles(directory_slash=directory_slash)
    status, output, options = invoke(env_file, files, capsys, identity)
    assert status == 0
    assert output.splitlines() == [f'V{i}: ĐẠT' for i in range(1, 7)]
    assert options == [dict(host=HOST, client_id=CLIENT_ID if identity == 'writer' else 'pipeline-id',
                            client_secret=SECRET if identity == 'writer' else 'pipeline-secret', auth_type='oauth-m2m')]
    assert files.data == {}
    assert files.directories == {ROOT, ROOT + '/thu_ket_noi'}
    uploads = [path for operation, path in files.calls if operation == 'upload']
    assert all(re.fullmatch(re.escape(ROOT) + r'/thu_ket_noi/[0-9]{8}T[0-9]{6}Z_[a-f0-9]{6}/.+', path) for path in uploads)
    assert len([p for p in uploads if '/v5/' in p]) == 10
    assert len(files.barriers) == 5
    assert [n for p, n in files.upload_sizes.items() if '/v6/' in p] == [1024 * 1024]
    assert all(op in ('upload', 'download', 'list', 'delete', 'delete_directory') for op, _ in files.calls)


@pytest.mark.parametrize('fault,failed', [('byte', 'V1'), ('duplicate_no_error', 'V2'),
    ('duplicate_changed', 'V2'), ('list_empty', 'V3'), ('missing_not_empty', 'V3'),
    ('ma', 'V4'), ('ma_different', 'V4'), ('write', 'V4'),
    ('race_overwrite', 'V5'), ('wrong_winner', 'V5'), ('extra_event', 'V5'),
    ('megabyte', 'V6')])
@pytest.mark.parametrize('directory_slash', [False, True])
def test_failed_check_still_cleans_everything(env_file, capsys, fault, failed, directory_slash):
    files = FakeFiles(fault=fault, directory_slash=directory_slash)
    status, output, _ = invoke(env_file, files, capsys)
    assert status == 1 and failed + ': TRƯỢT' in output
    assert len([line for line in output.splitlines() if line.startswith('V')]) == 6
    assert files.data == {}
    assert files.directories == {ROOT, ROOT + '/thu_ket_noi'}


@pytest.mark.parametrize('failure', ['list', 'delete', 'directory'])
@pytest.mark.parametrize('fault,expected', [(None, 0), ('megabyte', 1)])
@pytest.mark.parametrize('directory_slash', [False, True])
def test_cleanup_error_does_not_change_exit(env_file, capsys, failure, fault, expected, directory_slash):
    files = FakeFiles(fault=fault, cleanup_fault=failure, directory_slash=directory_slash)
    status, output, _ = invoke(env_file, files, capsys)
    assert status == expected
    assert 'Cảnh báo dọn: ' + ROOT + '/thu_ket_noi/' in output
    assert '(RuntimeError)' in output


@pytest.mark.parametrize('directory_slash', [False, True])
def test_cleanup_preserves_other_run_and_rejects_foreign_paths(env_file, capsys, directory_slash):
    files = FakeFiles(directory_slash=directory_slash)
    files.data[OTHER + '/keep.bin'] = b'giu-nguyen'
    files.directories.update({ROOT + '/thu_ket_noi', OTHER})
    files.foreign_entries = [SimpleNamespace(path=OTHER, is_directory=True),
                             SimpleNamespace(path=ROOT + '/yeu_cau/keep.bin', is_directory=False)]
    status, output, _ = invoke(env_file, files, capsys)
    assert status == 0 and '(ValueError)' in output
    assert files.data == {OTHER + '/keep.bin': b'giu-nguyen'}
    assert OTHER in files.directories
    deleted = [p for op, p in files.calls if op.startswith('delete')]
    assert not any(p.startswith(OTHER) or '/yeu_cau/' in p for p in deleted)


@pytest.mark.parametrize('suffix', ['/../other/file', '/./file', '//file'])
def test_cleanup_rejects_noncanonical_path(suffix):
    files = FakeFiles()
    run_root = ROOT + '/thu_ket_noi/20261109T000000Z_123abc'
    files.directories.add(run_root)
    files.foreign_entries = [SimpleNamespace(path=run_root + suffix, is_directory=False)]
    messages = []
    probe.cleanup(files, run_root, messages)
    assert any('(ValueError)' in m for m in messages)
    assert ('delete', run_root + suffix) not in files.calls


def test_fake_enforces_sdk_delete_contract():
    files = FakeFiles()
    path = ROOT + '/folder/file'
    files.upload(path, io.BytesIO(b'x'))
    with pytest.raises(IsADirectoryError):
        files.delete(ROOT + '/folder')
    with pytest.raises(OSError):
        files.delete_directory(ROOT + '/folder')
    files.delete(path)
    files.delete_directory(ROOT + '/folder')


@pytest.mark.parametrize('error', [ValueError, RuntimeError, Unauthenticated])
def test_login_failure_is_sanitized(env_file, capsys, error):
    def fail(**kwargs):
        print(SECRET, file=sys.stderr)
        raise error(SECRET + HOST + CLIENT_ID)
    assert probe.main(['--env-file', str(env_file), '--danh-tinh', 'writer'], client_factory=fail) == 3
    result = capsys.readouterr()
    assert result.out == f'Không đăng nhập được ({error.__name__}).\n'
    assert result.err == ''


def test_lazy_auth_failure(env_file, capsys):
    status, output, _ = invoke(env_file, FakeFiles(fault='auth'), capsys)
    assert status == 3 and 'Không đăng nhập được (Unauthenticated).' in output


@pytest.mark.parametrize('content', ['', 'RETAIL_NHAP_DBX_CLIENT_SECRET="unclosed', 'DATABRICKS_HOST=x'])
def test_invalid_credentials_never_construct_client(tmp_path, capsys, content):
    path = tmp_path / 'bad.env'
    path.write_text(content, encoding='utf-8')
    calls = []
    assert probe.main(['--env-file', str(path), '--danh-tinh', 'writer'],
                      client_factory=lambda **kw: calls.append(kw)) == 3
    assert not calls
    assert capsys.readouterr().out == 'Không đăng nhập được (ValueError).\n'


def test_host_fallback_and_allowlist(tmp_path, monkeypatch):
    monkeypatch.setenv('DATABRICKS_HOST', 'must-not-use-environment')
    path = tmp_path / 'fake.env'
    path.write_text("export RETAIL_PIPELINE_CLIENT_ID='id' # chú thích\n"
                    'RETAIL_PIPELINE_CLIENT_SECRET="a#b=c"\n'
                    'RETAIL_NHAP_DBX_CLIENT_SECRET="unclosed\n', encoding='utf-8-sig')
    result = probe.read_credentials(path, 'pipeline', HOST)
    assert result == dict(host=HOST, client_id='id', client_secret='a#b=c', auth_type='oauth-m2m')
    with pytest.raises(ValueError):
        probe.read_credentials(path, 'pipeline')


def test_missing_env_file(capsys, tmp_path):
    assert probe.main(['--env-file', str(tmp_path / 'missing.env'), '--danh-tinh', 'writer']) == 3
    assert capsys.readouterr().out == 'Không đăng nhập được (FileNotFoundError).\n'


@pytest.mark.parametrize('root', ['/Volumes/a/b/c/../x', '/Volumes/a/b', '/tmp/abc'])
def test_invalid_root_never_calls_files(env_file, capsys, root):
    files = FakeFiles()
    status, output, _ = invoke(env_file, files, capsys, extra=['--goc', root])
    assert status == 1 and not files.calls
    assert 'Không thử được kho Volume (ValueError).' in output


def test_direct_script_help_without_heavy_imports():
    script = Path(probe.__file__).resolve()
    code = "import sys,runpy; sys.modules.update({n:None for n in ['streamlit','duckdb','scripts.ingest.dot','scripts.ingest.auto_mapping']}); sys.argv=[sys.argv[1],'--help']; runpy.run_path(sys.argv[0],run_name='__main__')"
    result = subprocess.run([sys.executable, '-B', '-X', 'utf8', '-c', code, str(script)],
                            capture_output=True, text=True, encoding='utf-8')
    assert result.returncode == 0, result.stderr
    assert '--danh-tinh' in result.stdout


def test_token_acquisition_failure_is_login_error(env_file, capsys):
    files = FakeFiles()

    def authenticate():
        raise ValueError(SECRET)

    def factory(**kwargs):
        return SimpleNamespace(files=files, config=SimpleNamespace(authenticate=authenticate))

    assert probe.main(['--env-file', str(env_file), '--danh-tinh', 'writer'], client_factory=factory) == 3
    assert not files.calls
    assert capsys.readouterr().out == 'Không đăng nhập được (ValueError).\n'


def test_wrong_sequence_number_fails_v4(env_file, capsys, monkeypatch):
    original = probe.KhoVolume.ghi_json_so_tiep

    def wrong_number(self, folder, body, **kwargs):
        number = original(self, folder, body, **kwargs)
        return number + 1 if folder.endswith('/v4') else number

    monkeypatch.setattr(probe.KhoVolume, 'ghi_json_so_tiep', wrong_number)
    files = FakeFiles()
    status, output, _ = invoke(env_file, files, capsys)
    assert status == 1 and 'V4: TRƯỢT' in output
    assert not files.data


def test_permission_error_reports_type_and_cleans(env_file, capsys):
    files = FakeFiles(fault='permission', directory_slash=True)
    status, output, _ = invoke(env_file, files, capsys)
    assert status == 1
    assert 'V1: TRƯỢT (PermissionDenied)' in output
    assert SECRET not in output
    assert not files.data
    assert files.directories == {ROOT, ROOT + '/thu_ket_noi'}


@pytest.mark.parametrize('exists', [False, True])
def test_observed_files_barrier_applies_after_list_or_not_found(exists):
    files = FakeFiles()
    folder = ROOT + '/thu_ket_noi/20261109T000000Z_123abc/v5/0'
    if exists:
        files.directories.add(folder)
    observed = probe.ObservedFiles(files)
    observed.race_folder = folder
    observed.race_barrier = Barrier(2, timeout=0.1)
    with pytest.raises(BrokenBarrierError):
        observed.list_directory_contents(folder)
    assert ('list', folder) in files.calls


def test_host_from_file_has_priority_over_flag(env_file):
    result = probe.read_credentials(env_file, 'writer', 'https://other-host.invalid')
    assert result['host'] == HOST
