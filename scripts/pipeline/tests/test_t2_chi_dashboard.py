"""T2a: cờ CLI, con trỏ, DAG và dự báo dùng lại; không train/build/cloud."""
import json
from pathlib import Path
import shutil
import sys

import duckdb
import pytest
import yaml

from scripts.pipeline import cli, du_bao_dot
from scripts.pipeline.state import Registry, atomic_json
from test_d3_du_bao import base, RID, forecast_stage
from test_d5_con_tro import load_dag, record

ROOT = Path(__file__).resolve().parents[3]
A, B = 'a'*24, 'b'*24
MOT = '20261111T000000Z_abcdef_mot'


def invoke(monkeypatch, *args):
    monkeypatch.setattr(sys,'argv',['cli',*map(str,args)])
    return cli.main()


@pytest.fixture
def registry(tmp_path):
    reg = Registry(tmp_path)
    reg.initialize()
    reg.register(record(A))
    reg.register(dict(record(B),chi_dashboard=True,nguon_moi=['orders_enriched']))
    reg.publish(A,None)
    return reg


@pytest.mark.parametrize('args', [
    ['prepare','--chi-dashboard'],
    ['prepare','--chi-dashboard','--extension-dir','unused','--extension','orders_enriched','--dot','batch'],
    ['run','--chi-dashboard','--extension-dir','unused','--extension','orders_enriched'],
    ['build','--chi-dashboard','--extension-dir','unused','--extension','orders_enriched']])
def test_cli_bad_options_before_any_work(monkeypatch, args):
    monkeypatch.setattr(cli,'execute',lambda *a,**k: pytest.fail('Không được chạy stage'))
    with pytest.raises(SystemExit) as error:
        invoke(monkeypatch,*args,'--run-id','r')
    assert error.value.code == 2


def test_prepare_marks_source_and_retry_type(tmp_path,monkeypatch):
    directory = tmp_path/'contracts'
    directory.mkdir()
    raw = (ROOT/'scripts/ingest/extensions/orders_enriched.yml').read_bytes()+b'\n# run contract\n'
    (directory/'orders_enriched.yml').write_bytes(raw)
    monkeypatch.setattr(cli,'code_version',lambda:'same')
    monkeypatch.setattr(cli.snapshot,'prepare',lambda *a,**k: tmp_path/'snapshot')
    monkeypatch.setattr(cli.snapshot,'validate',lambda *a,**k: {
        'snapshot_id':'c'*12,'sources':{'orders_enriched':{'mo_rong':True,'so_dong_cach_ly':0}}})
    monkeypatch.setattr(cli.contract,'check',lambda *a:{})
    options=dict(run_id='mot_run',root=tmp_path/'root',extensions=['orders_enriched'],extension_directory=directory)
    ctx=cli._execute('prepare',chi_dashboard=True,**options)
    assert ctx['chi_dashboard'] is True and ctx['nguon_moi'] == ['orders_enriched']
    assert cli._execute('prepare',chi_dashboard=True,**options) == ctx
    with pytest.raises(ValueError):
        cli._execute('prepare',**options)


@pytest.mark.parametrize('stage',['validated','published','skipped'])
def test_publish_never_changes_active_even_on_retry(registry,stage):
    context=dict(record(B),chi_dashboard=True,target='duckdb',stage=stage)
    atomic_json(registry.path.parent/'runs/r/context.json',context)
    before=registry.path.read_bytes()
    with pytest.raises(ValueError,match='chỉ được đưa lên dashboard'):
        cli._execute('publish',run_id='r',root=registry.path.parent)
    assert registry.path.read_bytes() == before
    with pytest.raises(ValueError):
        registry.publish(B,A)
    assert registry.read()['payload']['active'] == A


@pytest.mark.parametrize('flag',[None,'--xac-nhan-tong-hop','both','--xac-nhan-nguon-moi'])
def test_cli_dashboard_requires_exact_confirmation(registry,monkeypatch,flag):
    monkeypatch.setattr(cli,'verify_consumers',lambda *a:None)
    monkeypatch.setattr(cli,'record_history',lambda *a:None)
    args=['dat-dashboard','--run-id','r','--root',registry.path.parent,'--release-id',B]
    if flag == 'both':
        args += ['--xac-nhan-tong-hop','--xac-nhan-nguon-moi']
    elif flag:
        args += [flag]
    before=registry.path.read_bytes()
    if flag != '--xac-nhan-nguon-moi':
        with pytest.raises(SystemExit) as error:
            invoke(monkeypatch,*args)
        assert error.value.code == 2 and registry.path.read_bytes() == before
    else:
        invoke(monkeypatch,*args)
        assert registry.read()['payload']['dashboard'] == B
    assert registry.read()['payload']['active'] == A


def test_validate_copies_chi_dashboard_metadata(tmp_path,monkeypatch):
    reg=Registry(tmp_path)
    reg.initialize()
    ctx={**record(B),'chi_dashboard':True,'nguon_moi':['orders_enriched'],
         'target':'duckdb','stage':'built','snapshot_path':'unused','code_version':'same'}
    atomic_json(tmp_path/'runs/r/context.json',ctx)
    monkeypatch.setattr(cli,'code_version',lambda:'same')
    monkeypatch.setattr(cli.snapshot,'validate',lambda *a,**kw:{})
    monkeypatch.setattr(cli,'validate_data',lambda *a:{'ok':True})
    monkeypatch.setattr(cli,'verify_consumers',lambda *a:None)
    cli._execute('validate',run_id='r',root=tmp_path)
    saved=reg.read()['payload']['releases'][B]
    assert saved['chi_dashboard'] is True and saved['nguon_moi'] == ['orders_enriched']
    assert reg.read()['payload']['active'] is None


@pytest.mark.parametrize('target',['duckdb','databricks'])
def test_forecast_routes_to_same_sales_and_requires_source(tmp_path,monkeypatch,target):
    context={**record(B),'target':target,'stage':'prepared','chi_dashboard':True,
             'snapshot_path':'unused','code_version':'same','directory':str(tmp_path/'runs/r')}
    atomic_json(tmp_path/'runs/r/context.json',context)
    monkeypatch.setattr(cli,'code_version',lambda:'same')
    monkeypatch.setattr(cli.snapshot,'validate',lambda *a,**k:{})
    monkeypatch.setattr(cli,'forecast_stage',lambda *a:pytest.fail('Không được train'))
    cloud=type('Cloud',(),{'query':lambda *a:None,'close':lambda *a:None})()
    monkeypatch.setattr(cli,'Databricks',lambda:cloud)
    captured=[]
    monkeypatch.setattr(du_bao_dot,'dung_lai_cung_sales',lambda ctx,root,rid,*,registry:
        captured.append((rid,registry.sql if registry else None)) or ('out',{}))
    with pytest.raises(ValueError):
        cli._execute('forecast',run_id='r',root=tmp_path,target=target)
    result=cli._execute('forecast',run_id='r',root=tmp_path,target=target,du_bao_tu=A)
    assert result['stage'] == 'forecasted'
    assert captured == [(A,cloud.query if target=='databricks' else None)]


@pytest.mark.parametrize('change',['same','value','duplicate','reordered'])
def test_reuse_forecast_only_for_equal_sales(base,change,monkeypatch):
    shutil.copyfile(base.source/'sales.parquet',base.target/'sales.parquet')
    if change in ('value','duplicate','reordered'):
        source=(base.target/'sales.parquet').as_posix()
        if change == 'value':
            query=f"""select "Date", case when "Date"='2022-12-31' then '999' else "Revenue" end as "Revenue", "COGS", _src_row from read_parquet('{source}')"""
        elif change == 'duplicate':
            query=f"select * from read_parquet('{source}') union all select * from read_parquet('{source}') limit 100000"
        else:
            query=f'select * from read_parquet(\'{source}\') order by "Date" desc'
        data=duckdb.sql(query).to_arrow_table()
        import pyarrow.parquet as pq
        pq.write_table(data,source)
    monkeypatch.setattr(forecast_stage,'run',lambda *a,**k:pytest.fail('Không được train'))
    if change in ('value','duplicate'):
        with pytest.raises(ValueError,match='sales khác bản nguồn; không dùng lại dự báo'):
            du_bao_dot.dung_lai_cung_sales(base.context,base.root,RID)
    else:
        out,summary=du_bao_dot.dung_lai_cung_sales(base.context,base.root,RID)
        assert summary['nguon_du_bao']['release_id'] == RID
        for name in forecast_stage.FILES:
            assert (Path(out)/name).read_bytes() == (base.folder/name).read_bytes()


def params():
    return {'run_id':'airflow_run','params':{
        'dots':[],'du_bao_tu':A,'request_id':MOT,'target':'databricks',
        'chi_dashboard':True,'extension_dir':f'/opt/retail/warehouse/pipeline/docker/nhap/{MOT}/hop_dong',
        'extensions':['orders_enriched']}}


def test_dag_empty_dots_with_bound_extension_dir(monkeypatch):
    dag,tasks,config=load_dag(monkeypatch,'retail_dot_pipeline.py')
    ctx=params()
    assert tasks == ['prepare','forecast','build','validate']
    command=dag.command('prepare',ctx)
    assert '--chi-dashboard' in command and '--extension-dir' in command and '--dot' not in command
    assert config['max_active_runs'] == 1
    for stage in ('forecast','build','validate'):
        assert '--chi-dashboard' not in dag.command(stage,ctx)


@pytest.mark.parametrize('patch', [
    {'chi_dashboard':False},{'extension_dir':None},{'extension_dir':'/tmp/other'},
    {'extension_dir':f'/opt/retail/warehouse/pipeline/docker/nhap/{MOT}/../hop_dong'},
    {'request_id':MOT.replace('abcdef','abcdee')},{'chi_dashboard':'true'},
    {'dots':['/opt/retail/data_demo/batch']},
])
def test_dag_rejects_unsafe_or_mixed_requests(monkeypatch,patch):
    dag,_,_=load_dag(monkeypatch,'retail_dot_pipeline.py')
    ctx=params()
    ctx['params'].update(patch)
    with pytest.raises(ValueError):
        dag.command('prepare',ctx)


def test_mount_keeps_core_readonly_and_ui_directory_writable():
    doc=yaml.safe_load((ROOT/'docker-compose.airflow.yml').read_text(encoding='utf-8'))
    mounts=doc['x-airflow']['volumes']
    assert './data:/opt/retail/data:ro' in mounts
    assert './data/ui_nhap_cloud:/opt/retail/data/ui_nhap_cloud' in mounts
    assert 'data/' in (ROOT/'.gitignore').read_text(encoding='utf-8')


@pytest.mark.parametrize('kind',['chi_dashboard','dot'])
def test_run_after_validate_prints_correct_next_step(monkeypatch,capsys,kind):
    calls=[]
    def execute(stage,**kwargs):
        calls.append(stage)
        return {'run_id':'r','release_id':B,'snapshot_id':'c'*12,'stage':stage,kind:True}
    monkeypatch.setattr(cli,'execute',execute)
    invoke(monkeypatch,'run','--run-id','r','--extension-dir','unused',
           '--extension','orders_enriched','--chi-dashboard','--du-bao-tu',A)
    text=capsys.readouterr().out
    assert calls==['prepare','forecast','build','validate']
    if kind=='chi_dashboard':
        assert 'dat-dashboard --xac-nhan-nguon-moi' in text
        assert 'publish --xac-nhan-tong-hop' not in text
    else:
        assert 'publish --xac-nhan-tong-hop' in text
