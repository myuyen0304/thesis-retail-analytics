"""Retry thay file chỉ áp dụng lỗi chia sẻ file Windows, không đổi Linux."""
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from scripts.pipeline import state


def permission(winerror):
    error = PermissionError(13, 'File đang mở')
    if winerror is not None:
        error.winerror = winerror
    return error


@pytest.mark.parametrize('platform,code,retry', [
    ('nt', 5, True), ('nt', 32, True), ('nt', 33, False), ('nt', None, False),
    ('posix', 5, False), ('posix', 32, False), ('posix', None, False),
])
def test_atomic_json_retries_only_windows_sharing_errors(tmp_path, monkeypatch, platform, code, retry):
    target = tmp_path / 'state.json'
    state.atomic_json(target, {'old': True})
    calls, sleeps = [], []
    replace = os.replace

    def fail_once(source, destination):
        calls.append(source)
        assert json.loads(target.read_text()) == {'old': True}
        if len(calls) == 1:
            raise permission(code)
        replace(source, destination)

    monkeypatch.setattr(state, 'os', SimpleNamespace(name=platform, fsync=os.fsync, replace=fail_once))
    monkeypatch.setattr(state, 'time', SimpleNamespace(sleep=sleeps.append))
    if retry:
        state.atomic_json(target, {'new': True})
        assert json.loads(target.read_text()) == {'new': True}
        assert len(calls) == 2 and sleeps == [0.1] and calls[0] == calls[1]
    else:
        with pytest.raises(PermissionError):
            state.atomic_json(target, {'new': True})
        assert len(calls) == 1 and not sleeps
        assert json.loads(target.read_text()) == {'old': True}
    assert list(tmp_path.iterdir()) == [target]


def test_atomic_json_retry_has_limit_and_keeps_old_file(tmp_path, monkeypatch):
    target = tmp_path / 'state.json'
    state.atomic_json(target, {'old': True})
    calls, sleeps = [], []

    def fail(source, destination):
        calls.append(source)
        raise permission(32)

    monkeypatch.setattr(state, 'os', SimpleNamespace(name='nt', fsync=os.fsync, replace=fail))
    monkeypatch.setattr(state, 'time', SimpleNamespace(sleep=sleeps.append))
    with pytest.raises(PermissionError):
        state.atomic_json(target, {'new': True})
    assert len(calls) == 100 and sleeps == [0.1] * 99
    assert json.loads(target.read_text()) == {'old': True}
    assert list(tmp_path.iterdir()) == [target]


def test_atomic_json_does_not_retry_other_oserror(tmp_path, monkeypatch):
    calls = []

    def fail(*args):
        calls.append(args)
        error = OSError('Không còn chỗ trên đĩa')
        error.winerror = 5
        raise error

    monkeypatch.setattr(state, 'os', SimpleNamespace(name='nt', fsync=os.fsync, replace=fail))
    monkeypatch.setattr(state, 'time', SimpleNamespace(sleep=lambda _: pytest.fail('Không được retry lỗi đĩa')))
    with pytest.raises(OSError, match='Không còn chỗ'):
        state.atomic_json(tmp_path / 'state.json', {})
    assert len(calls) == 1 and not list(tmp_path.iterdir())
