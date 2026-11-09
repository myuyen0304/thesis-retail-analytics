"""B3: chạy SQL model/test trên DuckDB nhỏ, render Jinja cục bộ; không chạy pipeline."""
from pathlib import Path
import subprocess
from types import SimpleNamespace

import duckdb
from jinja2 import Environment, StrictUndefined
import pytest

from scripts.ingest import extension_contract

ROOT = Path(__file__).resolve().parents[3]
MART = ['shipper_id', 'shipper_company', 'shipper_vehicle', 'shipper_experience_years',
        'shipper_rating', 'delivery_success_rate', 'average_delivery_time', 'working_shift',
        'join_date', 'shipper_name', 'shipper_phone', 'city', 'region', 'district']
HIDDEN = ['shipper_gender', 'shipper_age', 'shipper_marital_status', 'shipper_education']


def render(text, extensions=('orders_enriched', 'shipments_realistic'), target='duckdb', sources=None):
    def source(schema, name):
        if sources is not None:
            sources.append(name)
        return 'raw_' + name
    return Environment(undefined=StrictUndefined).from_string(text).render(
        config=lambda **kw: '', extension_enabled=lambda n: n in extensions,
        ref=lambda n: n, source=source, clean=lambda c: f"nullif(trim({c}), '')",
        date_sk=lambda c: f"cast(strftime({c}, '%Y%m%d') as integer)",
        dbt=SimpleNamespace(datediff=lambda a, b, unit: f"datediff('{unit}', {a}, {b})"),
        target=SimpleNamespace(type=target), var=lambda key, default=None: extensions if key == 'extensions' else default)


def sql(relative):
    return render((ROOT / 'retail_dbt' / relative).read_text(encoding='utf-8'))


def build_fixture(con):
    doc = extension_contract.load('shipments_realistic')
    selected = extension_contract.loaded_columns(doc)
    con.execute('create table raw_shipments_realistic (' + ', '.join(c + ' varchar' for c in selected)
                + ', _src_row integer, _dong_goc integer)')
    types = {c['ten']: c.get('kieu') for c in doc['cot']}
    for i, key in enumerate(['B', 'B', 'A'], 1):
        values = [str(i) if c == 'order_id' else key if c == 'shipper_id'
                  else '2023-01-01' if types[c] == 'date'
                  else '2' if types[c] != 'string' else 'fixture_' + c for c in selected]
        con.execute('insert into raw_shipments_realistic values (' + ','.join('?' for _ in values) + ',?,?)',
                    [*values, i, i])
    con.execute('create table stg_shipments_realistic as ' + sql('models/staging/stg_shipments_realistic.sql'))
    con.execute('create table dim_shipper as ' + sql('models/marts/dim_shipper.sql'))
    con.execute("create table int_orders as select i as order_id, date '2022-01-01' as order_date, "
                "date '2022-01-02' as ship_date, date '2022-01-03' as delivery_date, 1 as customer_id, "
                "'ok' as order_status, 'cash' as payment_method, 'web' as device_type, 'shop' as order_source, "
                "1 as installments, 2 as shipping_fee from range(1,5) t(i)")
    con.execute('create table stg_orders as select * from int_orders')
    con.execute('create table fact_order_item as select order_id, 10 as net_amount from int_orders')
    con.execute('create table dim_customer as select 1 as customer_id, 9 as customer_sk')
    con.execute("create table dim_order_junk as select 8 as order_junk_sk, 'ok' as order_status, "
                "'cash' as payment_method, 'web' as device_type, 'shop' as order_source")
    con.execute("create table stg_orders_enriched as select order_id, 'E' as sales_employee_id, "
                "'fixture' as sales_employee_name, 2 as years_experience from int_orders")
    con.execute('create table dim_sales_employee as ' + sql('models/marts/dim_sales_employee.sql'))
    con.execute('create table fact_order as ' + sql('models/marts/fact_order.sql'))


@pytest.fixture
def warehouse():
    with duckdb.connect() as con:
        build_fixture(con)
        yield con


@pytest.mark.parametrize('name', ['shipments_realistic', 'shipper', 'order_shipper'])
def test_b3_dbt_sql_passes(warehouse, name):
    assert warehouse.execute(sql(f'tests/assert_{name}.sql')).fetchall() == []


def test_b3_mart_columns_and_orders(warehouse):
    columns = [r[0] for r in warehouse.execute('describe dim_shipper').fetchall()]
    assert set(columns) == {'shipper_sk', *MART}
    assert not set(HIDDEN) & set(columns)
    assert warehouse.execute('select count(*) from dim_shipper').fetchone()[0] == 2
    assert warehouse.execute('select order_id, shipper_id from fact_order left join dim_shipper using (shipper_sk) '
                             'order by order_id').fetchall() == [(1, 'B'), (2, 'B'), (3, 'A'), (4, None)]
    assert warehouse.execute('select count(*), sum(payment_value), count(sales_employee_sk) from fact_order').fetchone() == (4, 40, 4)
    # Đổi cách đánh số vẫn phải đạt đối soát khóa tự nhiên.
    warehouse.execute('update dim_shipper set shipper_sk = shipper_sk + 20')
    warehouse.execute('update fact_order set shipper_sk = shipper_sk + 20')
    assert warehouse.execute(sql('tests/assert_order_shipper.sql')).fetchall() == []


@pytest.mark.parametrize('column', [c for c in MART + HIDDEN if c != 'shipper_id'])
def test_b3_fd_all_17_attributes(warehouse, column):
    kind = next(c['kieu'] for c in extension_contract.load('shipments_realistic')['cot'] if c['ten'] == column)
    value = "'changed'" if kind == 'string' else "date '2024-01-01'" if kind == 'date' else '3'
    warehouse.execute(f'update stg_shipments_realistic set {column} = {value} where order_id = 1')
    assert ('phu_thuoc_ham',) in warehouse.execute(sql('tests/assert_shipper.sql')).fetchall()


@pytest.mark.parametrize('column', ['city', 'region', 'district'])
def test_b3_requires_columns_on_shipper_itself(warehouse, column):
    warehouse.execute(f'create table dim_geography as select {column} from dim_shipper')
    warehouse.execute(f'alter table dim_shipper drop column {column}')
    with pytest.raises(duckdb.BinderException):
        warehouse.execute(sql('tests/assert_shipper.sql'))


@pytest.mark.parametrize('statement,test,rule', [
    ('update fact_order set shipper_sk = 999 where order_id = 1', 'order_shipper', 'gan_shipper'),
    ('update fact_order set shipper_sk = null where order_id = 1', 'order_shipper', 'gan_shipper'),
    ('update fact_order set shipper_sk = 1 where order_id = 1', 'order_shipper', 'gan_shipper'),
    ('delete from fact_order where order_id = 4', 'order_shipper', 'so_don'),
    ('insert into fact_order select * from fact_order where order_id = 1', 'order_shipper', 'khoa_don'),
    ('update dim_shipper set shipper_sk = 1', 'shipper', 'khoa_thay_the'),
    ("update dim_shipper set shipper_id = 'A'", 'shipper', 'khoa_tu_nhien'),
    ('delete from dim_shipper where shipper_sk = 1', 'shipper', 'so_shipper'),
    ('insert into stg_shipments_realistic select * from stg_shipments_realistic where order_id = 1',
     'shipments_realistic', 'khoa_don'),
])
def test_b3_sql_rejects_damage(warehouse, statement, test, rule):
    warehouse.execute(statement)
    assert (rule,) in warehouse.execute(sql(f'tests/assert_{test}.sql')).fetchall()


@pytest.mark.parametrize('statement,test,rule', [
    ('delete from stg_shipments_realistic where order_id = 3', 'shipments_realistic', 'so_dong'),
    ('update stg_shipments_realistic set order_id = 999 where order_id = 3', 'shipments_realistic', 'don_mo_coi'),
    ('update stg_shipments_realistic set _src_row = null where order_id = 2', 'shipments_realistic', 'so_thu_tu'),
    ('update stg_shipments_realistic set _src_row = 1 where order_id = 2', 'shipments_realistic', 'so_thu_tu'),
    ('update stg_shipments_realistic set _src_row = _src_row + 1', 'shipments_realistic', 'so_thu_tu'),
    ('update stg_shipments_realistic set _src_row = 4 where order_id = 3', 'shipments_realistic', 'so_thu_tu'),
    ("delete from dim_shipper where shipper_id = 'A'", 'shipper', 'thuoc_tinh'),
    ("delete from stg_shipments_realistic where shipper_id = 'A'", 'shipper', 'thuoc_tinh'),
])
def test_b3_missing_rows_and_sequence(warehouse, statement, test, rule):
    warehouse.execute(statement)
    assert (rule,) in warehouse.execute(sql(f'tests/assert_{test}.sql')).fetchall()


@pytest.mark.parametrize('column', MART[1:])
def test_b3_mart_attribute_value_must_match(warehouse, column):
    kind = next(c['kieu'] for c in extension_contract.load('shipments_realistic')['cot'] if c['ten'] == column)
    value = "'changed'" if kind == 'string' else "date '2024-01-01'" if kind == 'date' else '3'
    warehouse.execute(f"update dim_shipper set {column} = {value} where shipper_id = 'A'")
    assert ('thuoc_tinh',) in warehouse.execute(sql('tests/assert_shipper.sql')).fetchall()


@pytest.mark.parametrize('table', ['stg_shipments_realistic', 'dim_shipper'])
def test_b3_numeric_and_date_types(warehouse, table):
    types = {row[0]: row[1] for row in warehouse.execute('describe ' + table).fetchall()}
    assert {name: types[name] for name in ['shipper_rating', 'delivery_success_rate', 'join_date',
            'shipper_experience_years', 'average_delivery_time']} == {
        'shipper_rating': 'DOUBLE', 'delivery_success_rate': 'DOUBLE', 'join_date': 'DATE',
        'shipper_experience_years': 'INTEGER', 'average_delivery_time': 'INTEGER'}


def test_b3_shipper_key_order(warehouse):
    assert warehouse.execute('select shipper_id, shipper_sk from dim_shipper order by shipper_id').fetchall() == [('A', 1), ('B', 2)]


@pytest.mark.parametrize('extensions', [[], ['orders_enriched']])
def test_b3_disabled_fact_sql_unchanged(extensions):
    path = 'retail_dbt/models/marts/fact_order.sql'
    try:
        before = subprocess.check_output(['git', 'show', 'fe1f65c:' + path], cwd=ROOT,
                                         stderr=subprocess.PIPE).decode('utf-8')
    except (subprocess.CalledProcessError, OSError):
        pytest.skip('Không đọc được commit fe1f65c trong bản sao này')
    after = (ROOT / path).read_text(encoding='utf-8')
    assert render(after, extensions) == render(before, extensions)


@pytest.mark.parametrize('target', ['postgres', 'databricks'])
@pytest.mark.parametrize('extensions,expected', [([], 14), (['orders_enriched'], 15),
    (['shipments_realistic'], 15), (['orders_enriched', 'shipments_realistic'], 16)])
def test_b3_health_source_count_expression(target, extensions, expected):
    import re
    sources = []
    text = render((ROOT / 'retail_dbt/tests/assert_rpt_health.sql').read_text(encoding='utf-8'),
                  extensions, target, sources)
    assert f'ingest: du {expected} nguon' in text
    assert all(name in sources for name in extensions)
    query = re.search(r"select 'ingest: du .*?(?=union all)", text, re.S).group(0)
    with duckdb.connect() as con:
        con.execute('create table rpt_health_ingest as select 1 as loaded_at_utc from range(?)', [expected])
        assert con.execute(query).fetchone()[1] == 0
        con.execute('insert into rpt_health_ingest values (1)')
        assert con.execute(query).fetchone()[1] == 1
