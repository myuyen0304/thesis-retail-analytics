"""H1–H5, G1–G5: kiểm log và quyền mở rộng bằng hàm thật, không kết nối cloud."""
import pytest

from dwh import guarded
from scripts.ingest.source_contract import SOURCES
from scripts.pipeline import cli
from tests.test_ai_databricks import _g, _t, CAT, SP
from tests.test_databricks import assert_ingest_sources


@pytest.mark.parametrize('extra', [[], ['orders_enriched']], ids=['H1-core', 'H2-extension'])
def test_h1_h2_valid_sources(extra):
    names = list(SOURCES) + extra
    assert_ingest_sources(names, len(names))


def test_h3_missing_core():
    names = [n for n in SOURCES if n != 'orders']
    with pytest.raises(AssertionError, match='orders'):
        assert_ingest_sources(names, len(names))


def test_h4_unknown_extension():
    names = list(SOURCES) + ['unknown_extension']
    with pytest.raises(AssertionError, match='unknown_extension'):
        assert_ingest_sources(names, len(names))


@pytest.mark.parametrize('duplicate', [False, True], ids=['H5-count', 'duplicate'])
def test_h5_count_and_unique(duplicate):
    names = list(SOURCES) + (['orders'] if duplicate else [])
    with pytest.raises(AssertionError, match='Số nguồn'):
        assert_ingest_sources(names, len(names) if duplicate else len(names) + 1)


@pytest.fixture(params=[0, 1], ids=['app', 'chat'])
def reader(request):
    # Cùng danh sách và registry như verify_consumers; mọi bảng tùy chọn đều hiện diện.
    qualified, _ = cli.reader_grants(CAT, SP, 'r_x_reporting', cli.consumers()[request.param])
    allowed = frozenset(qualified)
    grants = [_g('catalog', CAT, None, None, SP, 'USE_CATALOG')]
    grants += [_g('schema', CAT, s, None, SP, 'USE_SCHEMA') for s in sorted({r.split('.')[0] for r in allowed})]
    grants += [_g('table', CAT, *r.split('.'), SP, 'SELECT') for r in sorted(allowed)]
    objects = [_t(CAT, *r.split('.')) for r in sorted(allowed)]
    return allowed, grants, objects


def violations(reader, extra_grants=(), extra_objects=()):
    allowed, grants, objects = reader
    return guarded._dbx_violations(SP, SP, grants + list(extra_grants), objects + list(extra_objects),
                                   allowed, CAT, allowed)


def test_g1_staging_select(reader):
    why = violations(reader, [_g('table', CAT, 'r_x_staging', 'stg_orders_enriched', SP, 'SELECT')])
    assert any('r_x_staging.stg_orders_enriched' in message for message in why)


def test_g2_staging_schema(reader):
    why = violations(reader, [_g('schema', CAT, 'r_x_staging', None, SP, 'USE_SCHEMA')])
    assert any('USE_SCHEMA' in message and 'r_x_staging' in message for message in why)


def test_g3_seen_raw(reader):
    why = violations(reader, extra_objects=[_t(CAT, 'r_x_raw', 'orders_enriched')])
    assert any('nhìn thấy' in message and 'r_x_raw.orders_enriched' in message for message in why)


def test_g4_exact_reader_permissions(reader):
    assert violations(reader) == []


def test_g5_consumers_reporting_only():
    for logical in cli.consumers():
        assert all(r.startswith('reporting.') for r in logical)
        assert not {'stg_orders_enriched', 'orders_enriched', 'dim_sales_employee'} & {r.split('.')[1] for r in logical}
