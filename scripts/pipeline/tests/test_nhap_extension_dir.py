"""Hợp đồng ngoài repo phải theo context đến tận các cổng kiểm sau prepare."""
import json
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from scripts.pipeline.tests.test_extensions_cli import cli_case, extension_case
from scripts.pipeline import cli, snapshot
from scripts.ingest import extension_contract as ec


@pytest.fixture
def external(cli_case, monkeypatch):
    c = cli_case
    c.doc['ten'] = 'ui_custom'
    (c.folder / 'ui_custom.yml').write_text(yaml.safe_dump(c.doc), encoding='utf-8')
    monkeypatch.setattr(ec, 'CONTRACT_DIR', c.folder / 'absent')
    return c


def test_external_dir_prepare_context_validate(external, monkeypatch):
    c = external
    with pytest.raises(FileNotFoundError):
        c.execute('missing', ['ui_custom'])
    context = c.execute('external', ['ui_custom'], extension_directory=c.folder)
    assert context['extension_dir'] == str(c.folder.resolve())
    assert c.execute('replay', ['ui_custom'], snapshot_id=context['snapshot_id'], extension_directory=c.folder)['stage'] == 'prepared'
    cols = [(f"r_{context['release_id']}_marts", 'dim_sales_employee', name)
            for name in ('sales_employee_id', 'sales_employee_name', 'years_experience')]
    assert cli.validate_extension_visibility(context, lambda sql: ([], cols)) == {
        'hidden_columns_checked': 3, 'mart_columns_checked': 3}
    with pytest.raises(FileNotFoundError):
        cli.validate_extension_visibility({k: v for k, v in context.items() if k != 'extension_dir'}, lambda sql: ([], cols))
    monkeypatch.setattr(cli, 'forecast_stage', lambda ctx: ('fake', {}))
    assert cli.execute('forecast', run_id='external', root=c.root)['stage'] == 'forecasted'
    with pytest.raises(ValueError, match='extension-dir'):
        c.execute('external', ['ui_custom'], extension_directory=c.folder / 'different')


@pytest.mark.parametrize('stage', ['forecast', 'build', 'validate', 'publish'])
def test_each_stage_validates_external_contract(external, monkeypatch, stage):
    c = external
    c.execute('check', ['ui_custom'], extension_directory=c.folder)
    seen = []
    def stop(path, **kwargs):
        seen.append(kwargs)
        raise ValueError('stop_before_stage')
    monkeypatch.setattr(snapshot, 'validate', stop)
    with pytest.raises(ValueError, match='stop_before_stage'):
        cli.execute(stage, run_id='check', root=c.root)
    assert seen == [{'extension_directory': str(c.folder.resolve())}]


@pytest.mark.parametrize('args', [[], ['--extension', 'ui_custom', '--stage-placeholder']])
def test_parser_rejects_dir_without_extension_or_late_stage(monkeypatch, args):
    argv = ['cli', 'validate' if args else 'prepare', '--run-id', 'r', '--extension-dir', 'somewhere']
    if args:
        argv += ['--extension', 'ui_custom']
    monkeypatch.setattr(sys, 'argv', argv)
    with pytest.raises(SystemExit) as error:
        cli.main()
    assert error.value.code == 2


def test_parser_forwards_dir(external, monkeypatch):
    c = external
    monkeypatch.setattr(sys, 'argv', ['cli', 'prepare', '--run-id', 'parser', '--root', str(c.root),
        '--data', str(c.data), '--extension', 'ui_custom', '--extension-dir', str(c.folder)])
    cli.main()
    assert json.loads((c.root / 'runs/parser/context.json').read_text(encoding='utf-8'))['extension_dir'] == str(c.folder.resolve())
