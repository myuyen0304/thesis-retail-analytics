"""Hợp đồng trên Volume: phiên bản chỉ thêm, không con trỏ ghi đè hay khóa đĩa."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import tempfile

from ui.kho_dot import DaCo, sequence_names
from scripts.ingest.tu_dong import normalize

REPO = Path(__file__).resolve().parents[3] / 'scripts/ingest/extensions'



def chu_ky_nghiep_vu(doc):
    """Chữ ký quyết định nghiệp vụ, giữ phiên bản và bỏ metadata riêng của lượt."""
    ignored = {'file', 'ngay_duyet', 'duyet_boi', 'hop_dong_sha256'}
    business = {key: value for key, value in doc.items() if key not in ignored}
    raw = json.dumps(business, sort_keys=True, ensure_ascii=False).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()


def load_raw(name, raw):
    if not isinstance(name, str) or not re.fullmatch(r'[a-z][a-z0-9_]*', name):
        raise ValueError('Tên hợp đồng không hợp lệ.')
    from scripts.ingest import extension_contract
    with tempfile.TemporaryDirectory() as temporary:
        (Path(temporary) / (name + '.yml')).write_bytes(raw)
        return extension_contract.load(name, temporary)


class KhoHopDong:
    def __init__(self, kho, repo=None):
        self.kho = kho
        self.repo = Path(repo) if repo is not None else REPO

    def folder(self, name):
        if not isinstance(name, str) or not re.fullmatch(r'[a-z][a-z0-9_]*', name):
            raise ValueError('Tên hợp đồng không hợp lệ.')
        return 'hop_dong_da_duyet/' + name

    def current(self, name):
        folder = self.folder(name)
        versions = [int(m[1]) for item in self.kho.liet_ke(folder)
                    if (m := re.fullmatch(r'v([1-9][0-9]*)\.yml', item))]
        if versions:
            version = max(versions)
            raw = self.kho.doc(folder + f'/v{version}.yml')
        else:
            seed = self.repo / (name + '.yml')
            if not seed.exists():
                return None
            version, raw = 1, seed.read_bytes()
        doc = load_raw(name, raw)  # Bản mới nhất hỏng thì dừng, không lùi bản cũ.
        return {'phien_ban': version, 'sha256': doc['hop_dong_sha256'],
                'duyet_boi': doc['duyet_boi'], 'ngay_duyet': doc['ngay_duyet']}, doc

    def write(self, name, doc, actor, origin, expected=None):
        import yaml
        folder = self.folder(name)
        current = self.current(name)
        previous = current[0]['phien_ban'] if current else 0
        if expected is not None and previous != expected:
            raise DaCo('Phiên bản hợp đồng đã đổi; tải lại trang.')
        version = previous + 1
        candidate = dict(doc)
        candidate.pop('hop_dong_sha256', None)
        candidate.update(phien_ban=version, duyet_boi=actor,
                         ngay_duyet=datetime.now(timezone.utc).isoformat(), nguon_goc=origin)
        raw = yaml.safe_dump(candidate, allow_unicode=True, sort_keys=False).encode('utf-8')
        checked = load_raw(name, raw)
        self.kho.ghi_moi(folder + f'/v{version}.yml', raw)
        return {'phien_ban': version, 'sha256': checked['hop_dong_sha256'],
                'duyet_boi': actor, 'ngay_duyet': candidate['ngay_duyet']}, checked

    def ung_vien(self, proposal):
        source = (proposal.get('nguon') or {}).get('de_xuat')
        if not source or source == 'chua_ro':
            return []
        names = {p.stem for p in self.repo.glob('*.yml')}
        names.update(self.kho.liet_ke('hop_dong_da_duyet'))
        header = {normalize(c['ten_trong_file']) for c in proposal.get('cot', [])}
        result = []
        for name in sorted(names):
            current = self.current(name)
            if current and current[1]['khoa_noi']['nguon'] == source:
                meta, doc = current
                optional = {normalize(c['ten']) for c in doc['cot'] if c.get('tuy_chon') is True}
                missing = [c for c in doc['header'] if normalize(c) not in header | optional]
                result.append((name, meta['phien_ban'], doc, missing))
        return result

    candidates = ung_vien

    def rejected(self, name, columns):
        import json
        folder = self.folder(name) + '/tu_choi'
        key = sorted(normalize(c) for c in columns)
        return any(json.loads(self.kho.doc(folder + '/' + n))['cot'] == key
                   for n in sequence_names(self.kho.liet_ke(folder)))

    def reject(self, name, columns, reason, actor):
        if not reason.strip():
            raise ValueError('Từ chối nâng hợp đồng phải ghi lý do.')
        self.kho.ghi_json_so_tiep(self.folder(name) + '/tu_choi',
            {'cot': sorted(normalize(c) for c in columns), 'ly_do': reason.strip(),
             'ai': actor, 'luc': datetime.now(timezone.utc).isoformat()})
