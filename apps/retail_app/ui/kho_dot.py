"""Kho đợt chỉ thêm file; Files API tách biệt với kết nối đọc DWH."""
from datetime import datetime, timezone
import io
import json
import os
from pathlib import Path
import re
from uuid import uuid4


class DaCo(FileExistsError):
    pass


class KhongCo(FileNotFoundError):
    pass


class TrangThaiDaDoi(ValueError):
    def __init__(self):
        super().__init__('Có người vừa thao tác cùng lúc; tải lại trang.')


def relative_path(path):
    if (not isinstance(path, str) or not re.fullmatch(r'[A-Za-z0-9_./-]+', path)
            or path.startswith('/') or '..' in path or any(p in ('', '.') for p in path.split('/'))):
        raise ValueError('Đường dẫn kho đợt không hợp lệ.')
    return path


def sequence_names(names):
    return sorted(n for n in names if re.fullmatch(r'[0-9]{6}\.json', n))


class Kho:
    def ghi_json_so_tiep(self, thu_muc, body, *, expected=None):
        """Một lần tranh số; kiểm mã cả khi SDK báo lỗi không liên quan ghi đè."""
        relative_path(thu_muc)
        record = dict(body, ma=uuid4().hex, luc=datetime.now(timezone.utc).isoformat())
        names = sequence_names(self.liet_ke(thu_muc))
        last = int(names[-1][:-5]) if names else 0
        if expected is not None and last != expected:
            raise TrangThaiDaDoi()
        number = last + 1
        if number > 999999:
            raise ValueError('Kho đợt đã hết số thứ tự.')
        path = f'{thu_muc}/{number:06d}.json'
        try:
            self.ghi_moi(path, json.dumps(record, ensure_ascii=False).encode('utf-8'))
        except Exception as error:
            try:
                saved = json.loads(self.doc(path))
            except KhongCo:
                raise error
            if saved.get('ma') != record['ma']:
                raise TrangThaiDaDoi() from error
        return number


def _comparison_path(path):
    # Windows có thể thêm tiền tố thiết bị khi thư mục vừa được tạo bởi writer khác.
    value = path.as_posix()
    if value.startswith('//?/UNC/'):
        value = '//' + value[8:]
    elif value.startswith('//?/'):
        value = value[4:]
    return Path(value)


class KhoDia(Kho):
    def __init__(self, root):
        self.root = Path(root).resolve()

    def _path(self, path):
        target = (self.root / relative_path(path)).resolve()
        if not _comparison_path(target).is_relative_to(_comparison_path(self.root)):
            raise ValueError('Đường dẫn vượt khỏi kho đợt.')
        return target

    def ghi_moi(self, path, data):
        target = self._path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name('.' + uuid4().hex + '.tmp')
        try:
            with temporary.open('xb') as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            try:
                if os.name == 'nt':
                    os.rename(temporary, target)  # Windows từ chối đích đã có, không ghi đè.
                else:
                    os.link(temporary, target)  # POSIX rename ghi đè: liên kết nguyên tử giữ luật ghi mới.
            except FileExistsError as error:
                raise DaCo(path) from error
        finally:
            temporary.unlink(missing_ok=True)

    def doc(self, path):
        try:
            return self._path(path).read_bytes()
        except FileNotFoundError as error:
            raise KhongCo(path) from error

    def liet_ke(self, thu_muc):
        try:
            return sorted(p.name for p in self._path(thu_muc).iterdir())
        except FileNotFoundError:
            return []


class KhoVolume(Kho):
    def __init__(self, root, client):
        self.root = root.rstrip('/')
        self.client = client

    def _path(self, path):
        return self.root + '/' + relative_path(path)

    def ghi_moi(self, path, data):
        from databricks.sdk.errors import AlreadyExists
        try:
            self.client.files.upload(self._path(path), io.BytesIO(data), overwrite=False)
        except AlreadyExists as error:
            raise DaCo(path) from error

    def doc(self, path):
        from databricks.sdk.errors import NotFound
        try:
            response = self.client.files.download(self._path(path))
            try:
                return response.contents.read()
            finally:
                response.contents.close()
        except NotFound as error:
            raise KhongCo(path) from error

    def liet_ke(self, thu_muc):
        from databricks.sdk.errors import NotFound
        try:
            prefix = self._path(thu_muc) + '/'
            return sorted({entry.path[len(prefix):].rstrip('/')
                           for entry in self.client.files.list_directory_contents(prefix.rstrip('/'))
                           if entry.path and entry.path.startswith(prefix)
                           and '/' not in entry.path[len(prefix):].rstrip('/')})
        except NotFound:
            return []


def mode():
    value = os.getenv('RETAIL_NHAP_DOT', 'tat')
    if value not in ('tat', 'dia', 'volume'):
        raise ValueError('RETAIL_NHAP_DOT chỉ nhận tat, dia hoặc volume.')
    return value


def configured_store():
    selected = mode()
    if selected == 'tat':
        return None
    if selected == 'dia':
        return KhoDia(os.getenv('RETAIL_NHAP_DIA', 'warehouse/ui_nhap_dot'))
    from dwh.connection import databricks_config
    values = [databricks_config().get('DATABRICKS_HOST'),
              os.getenv('RETAIL_NHAP_DBX_CLIENT_ID'), os.getenv('RETAIL_NHAP_DBX_CLIENT_SECRET')]
    if not all(values):
        raise ValueError('Chưa cấu hình kho đợt')
    from databricks.sdk import WorkspaceClient
    return KhoVolume(os.getenv('RETAIL_NHAP_VOLUME', '/Volumes/retail_lab/nhap_du_lieu/kho'),
                     WorkspaceClient(host=values[0], client_id=values[1], client_secret=values[2], auth_type='oauth-m2m'))
