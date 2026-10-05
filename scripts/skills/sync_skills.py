"""Đồng bộ sáu skill chuẩn sang Claude Code; --check không ghi file."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import sys


SKILLS = (
    'retail-metric-design',
    'retail-data-analysis',
    'retail-analytics-engineering',
    'retail-bi-product',
    'retail-ai-explain',
    'retail-platform-validation',
)
MANIFEST = '.retail-sync.json'
TEXT_SUFFIXES = {'.md', '.yaml', '.yml', '.json', '.py', '.sql', '.txt'}


class SyncError(Exception):
    """Xung đột phải giải quyết trước khi đồng bộ."""


def safe_path(root: Path, relative: str) -> Path:
    """Không đi theo symlink/junction hoặc thoát khỏi thư mục đã chọn."""
    pure = PurePosixPath(relative)
    if (not relative or pure.is_absolute() or '\\' in relative or ':' in relative
            or '..' in pure.parts or pure.as_posix() != relative):
        raise SyncError(f'Đường dẫn không hợp lệ: {relative}')
    path = root.joinpath(*pure.parts)
    for part in (path, *path.parents):
        if part.is_symlink() or getattr(part, 'is_junction', lambda: False)():
            raise SyncError(f'Không đồng bộ qua liên kết: {part}')
    if not path.resolve().is_relative_to(root.resolve()):
        raise SyncError(f'Đường dẫn ngoài phạm vi: {relative}')
    return path


def read_text_bytes(path: Path) -> bytes:
    # Git/Windows có thể đổi LF thành CRLF; so nội dung văn bản sau chuẩn hóa.
    data = path.read_bytes()
    data.decode('utf-8')
    return data.replace(b'\r\n', b'\n')


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def collect(root: Path, *, required: bool) -> dict[str, bytes]:
    files = {}
    for name in SKILLS:
        directory = safe_path(root, name)
        if required and not safe_path(root, f'{name}/SKILL.md').is_file():
            raise SyncError(f'Thiếu source: {name}/SKILL.md')
        if directory.exists() and not directory.is_dir():
            raise SyncError(f'Cần thư mục: {directory}')
        if not directory.exists():
            continue
        # Kiểm liên kết trước khi đi xuống cây; không dùng rglob qua junction.
        pending = [directory]
        while pending:
            current = pending.pop()
            for child in sorted(current.iterdir()):
                key = child.relative_to(root).as_posix()
                safe_path(root, key)
                if child.is_dir():
                    pending.append(child)
                elif child.suffix in TEXT_SUFFIXES and child.is_file():
                    files[key] = read_text_bytes(child)
                else:
                    raise SyncError(f'File không hỗ trợ trong skill được quản lý: {key}')
    return files


def read_manifest(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    doc = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(doc, dict) or doc.get('version') != 1 or doc.get('skills') != list(SKILLS):
        raise SyncError('Manifest không đúng phiên bản/danh sách skill.')
    files = doc.get('files')
    if not isinstance(files, dict):
        raise SyncError('Manifest thiếu bảng hash.')
    for key, value in files.items():
        if (not isinstance(key, str) or not isinstance(value, str)
                or len(value) != 64 or any(c not in '0123456789abcdef' for c in value)):
            raise SyncError('Manifest có entry/hash không hợp lệ.')
        if not PurePosixPath(key).parts or PurePosixPath(key).parts[0] not in SKILLS:
            raise SyncError(f'Manifest vượt phạm vi: {key}')
        safe_path(path.parent, key)
    return files


def sync(root: Path, *, write: bool = False) -> list[str]:
    root = root.absolute()
    source_root = safe_path(root, '.agents/skills')
    target_root = safe_path(root, '.claude/skills')
    manifest_path = safe_path(target_root, MANIFEST)
    source = collect(source_root, required=True)
    target = collect(target_root, required=False)
    previous = read_manifest(manifest_path)
    source_hashes = {k: digest(v) for k, v in sorted(source.items())}

    for key in source:
        if safe_path(target_root, key).is_dir():
            raise SyncError(f'Đích là thư mục thay vì file: {key}')

    # Preflight toàn bộ trước mọi ghi/xóa; không tự chấp nhận sửa ngoài quy trình.
    conflicts = []
    for key, data in target.items():
        actual = digest(data)
        if key in previous:
            if actual != previous[key]:
                conflicts.append(key)
        elif key not in source or actual != source_hashes[key]:
            conflicts.append(key)
    if conflicts:
        raise SyncError('Bản Claude có thay đổi ngoài quy trình: ' + ', '.join(conflicts))

    changed = [k for k, v in source.items() if target.get(k) != v]
    retired = [k for k in target if k not in source]
    manifest_changed = previous != source_hashes or not manifest_path.exists()
    differences = [f'WRITE {k}' for k in sorted(changed)]
    differences += [f'REMOVE {k}' for k in sorted(retired)]
    if manifest_changed:
        differences.append(f'WRITE {MANIFEST}')
    if not write:
        return differences

    # Chỉ xóa file trước đây được manifest quản lý và vẫn khớp hash; không recursive delete.
    for key in retired:
        safe_path(target_root, key).unlink()
    for key in changed:
        path = safe_path(target_root, key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(source[key])
    if manifest_changed:
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps({
            'version': 1, 'skills': list(SKILLS), 'files': source_hashes,
        }, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    return differences


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--check', action='store_true')
    mode.add_argument('--write', action='store_true')
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    try:
        differences = sync(args.root, write=args.write)
    except (SyncError, OSError, ValueError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 2
    if differences:
        print('\n'.join(differences))
    else:
        print('PASS: sáu skill đồng bộ.')
    return 1 if differences and args.check else 0


if __name__ == '__main__':
    raise SystemExit(main())
