"""Kiểm hành vi đồng bộ trên thư mục tạm, không chạm skill đang dùng."""
import importlib.util
import json
from pathlib import Path

import pytest


SPEC = importlib.util.spec_from_file_location('sync_skills', Path(__file__).parents[1] / 'sync_skills.py')
sync_skills = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sync_skills)


@pytest.fixture
def repo(tmp_path):
    for name in sync_skills.SKILLS:
        folder = tmp_path / '.agents' / 'skills' / name
        folder.mkdir(parents=True)
        (folder / 'SKILL.md').write_text(f'---\nname: {name}\n---\nNội dung\n', encoding='utf-8')
    return tmp_path


def source(repo):
    return repo / '.agents/skills' / sync_skills.SKILLS[0] / 'SKILL.md'


def target(repo):
    return repo / '.claude/skills' / sync_skills.SKILLS[0] / 'SKILL.md'


def snapshot(folder):
    return {p.relative_to(folder).as_posix(): p.read_bytes() for p in folder.rglob('*') if p.is_file()}


def test_check_does_not_write_and_initial_sync_is_idempotent(repo):
    assert sync_skills.sync(repo)
    assert not (repo / '.claude').exists()
    sync_skills.sync(repo, write=True)
    before = snapshot(repo)
    mtimes = {p: p.stat().st_mtime_ns for p in repo.rglob('*') if p.is_file()}
    assert sync_skills.sync(repo) == []
    assert sync_skills.sync(repo, write=True) == []
    assert snapshot(repo) == before
    assert all(p.stat().st_mtime_ns == t for p, t in mtimes.items())


def test_source_update_propagates(repo):
    sync_skills.sync(repo, write=True)
    source(repo).write_text('Nội dung mới\n', encoding='utf-8')
    assert sync_skills.sync(repo)
    sync_skills.sync(repo, write=True)
    assert sync_skills.read_text_bytes(target(repo)) == sync_skills.read_text_bytes(source(repo))
    assert sync_skills.sync(repo) == []


@pytest.mark.parametrize('write', [False, True])
def test_manual_edit_blocks_every_mutation(repo, write):
    sync_skills.sync(repo, write=True)
    target(repo).write_text('Sửa thủ công\n', encoding='utf-8')
    source(repo).write_text('Thay nguồn\n', encoding='utf-8')
    before = snapshot(repo)
    with pytest.raises(sync_skills.SyncError, match='ngoài quy trình'):
        sync_skills.sync(repo, write=write)
    assert snapshot(repo) == before


def test_preserves_unmanaged_skill_and_removes_only_retired_owned_file(repo):
    old = source(repo).parent / 'references' / 'old.md'
    old.parent.mkdir()
    old.write_text('cũ', encoding='utf-8')
    sync_skills.sync(repo, write=True)
    unrelated = repo / '.claude/skills/some-other-skill/SKILL.md'
    unrelated.parent.mkdir()
    unrelated.write_text('không thay đổi', encoding='utf-8')
    old.unlink()
    sync_skills.sync(repo, write=True)
    assert unrelated.read_text(encoding='utf-8') == 'không thay đổi'
    assert not (target(repo).parent / 'references/old.md').exists()


def test_unknown_file_in_managed_skill_blocks_write(repo):
    sync_skills.sync(repo, write=True)
    (target(repo).parent / 'notes.md').write_text('của người dùng', encoding='utf-8')
    before = snapshot(repo)
    with pytest.raises(sync_skills.SyncError):
        sync_skills.sync(repo, write=True)
    assert snapshot(repo) == before


def test_conflict_before_first_sync_preserved(repo):
    target(repo).parent.mkdir(parents=True)
    target(repo).write_text('file đã tồn tại', encoding='utf-8')
    before = snapshot(repo)
    with pytest.raises(sync_skills.SyncError):
        sync_skills.sync(repo, write=True)
    assert snapshot(repo) == before


def test_missing_source_never_removes_destination(repo):
    sync_skills.sync(repo, write=True)
    source(repo).unlink()
    before = snapshot(repo)
    with pytest.raises(sync_skills.SyncError, match='Thiếu source'):
        sync_skills.sync(repo, write=True)
    assert snapshot(repo) == before


def test_crlf_checkout_does_not_create_conflict(repo):
    sync_skills.sync(repo, write=True)
    target(repo).write_bytes(target(repo).read_bytes().replace(b'\n', b'\r\n'))
    assert sync_skills.sync(repo) == []


@pytest.mark.parametrize('bad_key', ['', '.', '../outside.md', 'retail-metric-design/../../outside.md',
                                     'retail-metric-design/../../../outside.md', 'other-skill/SKILL.md'])
def test_manifest_path_escape_blocked(repo, bad_key):
    sync_skills.sync(repo, write=True)
    manifest = repo / '.claude/skills' / sync_skills.MANIFEST
    doc = json.loads(manifest.read_text(encoding='utf-8'))
    doc['files'][bad_key] = 'a' * 64
    manifest.write_text(json.dumps(doc), encoding='utf-8')
    before = snapshot(repo)
    with pytest.raises(sync_skills.SyncError):
        sync_skills.sync(repo, write=True)
    assert snapshot(repo) == before


def test_symlink_refused(repo):
    outside = repo / 'outside.md'
    outside.write_text('không sửa', encoding='utf-8')
    link = source(repo).parent / 'linked.md'
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip('Tài khoản Windows không có quyền tạo symlink.')
    with pytest.raises(sync_skills.SyncError, match='liên kết'):
        sync_skills.sync(repo, write=True)
    assert outside.read_text(encoding='utf-8') == 'không sửa'


def test_file_directory_conflict_blocks_before_write(repo):
    sync_skills.sync(repo, write=True)
    (source(repo).parent / 'new.md').write_text('mới', encoding='utf-8')
    (target(repo).parent / 'new.md').mkdir()
    source(repo).write_text('đổi nguồn', encoding='utf-8')
    before = snapshot(repo)
    with pytest.raises(sync_skills.SyncError, match='thư mục thay vì file'):
        sync_skills.sync(repo, write=True)
    assert snapshot(repo) == before
