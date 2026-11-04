"""Kho hợp đồng local: phiên bản bất biến, con trỏ hiện hành ghi nguyên tử."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import tempfile

from scripts.ingest import extension_contract
from scripts.ingest.tu_dong import normalize
from scripts.pipeline.state import atomic_json, writer_lock


def _now():
    return datetime.now(timezone.utc).isoformat()


def _validate(name, raw, parent):
    with tempfile.TemporaryDirectory(dir=parent) as temporary:
        path = Path(temporary) / f'{name}.yml'
        path.write_bytes(raw)
        return extension_contract.load(name, temporary)


class ContractRegistry:
    def __init__(self, base):
        self.base = Path(base).resolve()
        self.root = self.base / 'warehouse/ui_nhap/hop_dong_da_duyet'
        self.repo = self.base / 'scripts/ingest/extensions'

    def folder(self, name):
        if not re.fullmatch(r'[a-z][a-z0-9_]*', name):
            raise ValueError('Tên hợp đồng không hợp lệ.')
        return self.root / name

    def current(self, name):
        folder = self.folder(name)
        pointer = folder / 'hien_hanh.json'
        if not pointer.exists():
            seed = self.repo / f'{name}.yml'
            if not seed.exists():
                return None
            folder.mkdir(parents=True, exist_ok=True)
            with writer_lock(folder):
                if not pointer.exists():
                    raw = seed.read_bytes()
                    _validate(name, raw, folder)
                    self._write_locked(folder, 1, raw, 'he_thong', f'repo:{seed.relative_to(self.base).as_posix()}')
        meta = json.loads(pointer.read_text(encoding='utf-8'))
        raw = (folder / f"v{meta['phien_ban']}.yml").read_bytes()
        doc = _validate(name, raw, folder)
        if doc['hop_dong_sha256'] != meta['sha256']:
            raise ValueError(f'Hợp đồng {name} bị đổi sau khi duyệt.')
        return meta, doc

    def _write_locked(self, folder, version, raw, actor, origin):
        name = folder.name
        doc = _validate(name, raw, folder)
        destination = folder / f'v{version}.yml'
        with destination.open('xb') as output:
            output.write(raw)
            output.flush()
            os.fsync(output.fileno())
        meta = {'phien_ban': version, 'sha256': doc['hop_dong_sha256'], 'duyet_boi': actor,
                'ngay_duyet': _now(), 'nguon_goc': origin}
        atomic_json(folder / 'hien_hanh.json', meta)
        return meta, doc

    def write(self, name, doc, actor, origin, expected=None):
        import yaml
        folder = self.folder(name)
        folder.mkdir(parents=True, exist_ok=True)
        raw = yaml.safe_dump(doc, allow_unicode=True, sort_keys=False).encode('utf-8')
        with writer_lock(folder):
            pointer = folder / 'hien_hanh.json'
            previous = json.loads(pointer.read_text(encoding='utf-8')) if pointer.exists() else None
            if expected is not None and (not previous or previous['phien_ban'] != expected):
                raise ValueError('Phiên bản hợp đồng đã đổi; tải lại trang.')
            version = previous['phien_ban'] + 1 if previous else 1
            return self._write_locked(folder, version, raw, actor, origin)

    def ung_vien(self, proposal):
        source = (proposal.get('nguon') or {}).get('de_xuat')
        if not source or source == 'chua_ro':
            return []
        names = {path.stem for path in self.repo.glob('*.yml')}
        if self.root.exists():
            names.update(path.name for path in self.root.iterdir() if path.is_dir())
        header = {normalize(col['ten_trong_file']) for col in proposal.get('cot', [])}
        result = []
        for name in sorted(names):
            current = self.current(name)
            if not current:
                continue
            meta, doc = current
            if doc['khoa_noi']['nguon'] == source:
                optional = {normalize(col['ten']) for col in doc['cot'] if col.get('tuy_chon') is True}
                missing = [col for col in doc['header']
                           if normalize(col) not in header and normalize(col) not in optional]
                result.append((name, meta['phien_ban'], doc, missing))
        return result

    candidates = ung_vien

    def rejected(self, name, columns):
        path = self.folder(name) / 'tu_choi.json'
        if not path.exists():
            return False
        key = sorted(normalize(col) for col in columns)
        return any(row['cot'] == key for row in json.loads(path.read_text(encoding='utf-8')))

    def reject(self, name, columns, reason, actor):
        if not reason.strip():
            raise ValueError('Từ chối nâng hợp đồng phải ghi lý do.')
        folder = self.folder(name)
        folder.mkdir(parents=True, exist_ok=True)
        with writer_lock(folder):
            path = folder / 'tu_choi.json'
            rows = json.loads(path.read_text(encoding='utf-8')) if path.exists() else []
            key = sorted(normalize(col) for col in columns)
            if not any(row['cot'] == key for row in rows):
                rows.append({'cot': key, 'ly_do': reason.strip(), 'ai': actor, 'luc': _now()})
            atomic_json(path, rows)

    def upgrade_notice(self, name, version, message=None):
        path = self.folder(name) / f'thong_bao_v{version}.json'
        if message is not None:
            with writer_lock(self.folder(name)):
                atomic_json(path, {'noi_dung': message})
        return json.loads(path.read_text(encoding='utf-8'))['noi_dung'] if path.exists() else None
