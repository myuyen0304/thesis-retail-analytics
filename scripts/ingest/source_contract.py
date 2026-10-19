"""Hợp đồng bộ CSV chuẩn; số dòng cố định chỉ áp dụng snapshot Datathon."""

SOURCES = {
    'geography': (['zip', 'city', 'region', 'district'], 39948),
    'customers': (['customer_id', 'zip', 'city', 'signup_date', 'gender', 'age_group', 'acquisition_channel'], 121930),
    'products': (['product_id', 'product_name', 'category', 'segment', 'size', 'color', 'price', 'cogs'], 2412),
    'promotions': (['promo_id', 'promo_name', 'promo_type', 'discount_value', 'start_date', 'end_date',
                    'applicable_category', 'promo_channel', 'stackable_flag', 'min_order_value'], 50),
    'orders': (['order_id', 'order_date', 'customer_id', 'zip', 'order_status', 'payment_method',
                'device_type', 'order_source'], 646945),
    'order_items': (['order_id', 'product_id', 'quantity', 'unit_price', 'discount_amount', 'promo_id', 'promo_id_2'], 714669),
    'payments': (['order_id', 'payment_method', 'payment_value', 'installments'], 646945),
    'shipments': (['order_id', 'ship_date', 'delivery_date', 'shipping_fee'], 566067),
    'returns': (['return_id', 'order_id', 'product_id', 'return_date', 'return_reason', 'return_quantity', 'refund_amount'], 39939),
    'reviews': (['review_id', 'order_id', 'product_id', 'customer_id', 'review_date', 'rating', 'review_title'], 113551),
    'inventory': (['snapshot_date', 'product_id', 'stock_on_hand', 'units_received', 'units_sold', 'stockout_days',
                   'days_of_supply', 'fill_rate', 'stockout_flag', 'overstock_flag', 'reorder_flag',
                   'sell_through_rate', 'product_name', 'category', 'segment', 'year', 'month'], 60247),
    'web_traffic': (['date', 'sessions', 'unique_visitors', 'page_views', 'bounce_rate',
                     'avg_session_duration_sec', 'traffic_source'], 3652),
    'sales': (['Date', 'Revenue', 'COGS'], 3833),
    'sample_submission': (['Date', 'Revenue', 'COGS'], 548),
}

# Hợp đồng bản gọn (A3, bước S4, 2026-10-19), kiểm ở stage prepare trên snapshot, trước build (scripts/pipeline/contract.py).
# SOURCES giữ nguyên cấu trúc (header, số dòng): snapshot.validate / prepare đang unpack nó, và snapshot_id không đổi.
#
# COLUMNS: mỗi cột (kiểu, được rỗng). Kiểu là đúng kiểu model staging cast (retail_dbt/models/staging/stg_<nguồn>.sql,
# `cast({{ clean(col) }} as <kiểu>)`, clean = nullif(trim(x), ''), type_double() = double); cột staging không cast là 'string'.
# Được rỗng chỉ ba cột: applicable_category (rỗng = mọi ngành hàng), promo_id và promo_id_2 của order_items.
_S, _I, _D, _F = 'string', 'integer', 'date', 'double'
COLUMNS = {
    'geography': {'zip': (_I, False), 'city': (_S, False), 'region': (_S, False), 'district': (_S, False)},
    'customers': {'customer_id': (_I, False), 'zip': (_I, False), 'city': (_S, False), 'signup_date': (_D, False),
                  'gender': (_S, False), 'age_group': (_S, False), 'acquisition_channel': (_S, False)},
    'products': {'product_id': (_I, False), 'product_name': (_S, False), 'category': (_S, False), 'segment': (_S, False),
                 'size': (_S, False), 'color': (_S, False), 'price': (_F, False), 'cogs': (_F, False)},
    'promotions': {'promo_id': (_S, False), 'promo_name': (_S, False), 'promo_type': (_S, False),
                   'discount_value': ('decimal(10,2)', False), 'start_date': (_D, False), 'end_date': (_D, False),
                   'applicable_category': (_S, True), 'promo_channel': (_S, False), 'stackable_flag': (_S, False),
                   'min_order_value': (_I, False)},
    'orders': {'order_id': (_I, False), 'order_date': (_D, False), 'customer_id': (_I, False), 'zip': (_I, False),
               'order_status': (_S, False), 'payment_method': (_S, False), 'device_type': (_S, False),
               'order_source': (_S, False)},
    'order_items': {'order_id': (_I, False), 'product_id': (_I, False), 'quantity': (_I, False),
                    'unit_price': ('decimal(14,2)', False), 'discount_amount': ('decimal(16,2)', False),
                    'promo_id': (_S, True), 'promo_id_2': (_S, True)},
    'payments': {'order_id': (_I, False), 'payment_method': (_S, False), 'payment_value': (_F, False),
                 'installments': (_I, False)},
    'shipments': {'order_id': (_I, False), 'ship_date': (_D, False), 'delivery_date': (_D, False),
                  'shipping_fee': ('decimal(10,2)', False)},
    'returns': {'return_id': (_S, False), 'order_id': (_I, False), 'product_id': (_I, False), 'return_date': (_D, False),
                'return_reason': (_S, False), 'return_quantity': (_I, False), 'refund_amount': ('decimal(16,2)', False)},
    'reviews': {'review_id': (_S, False), 'order_id': (_I, False), 'product_id': (_I, False), 'customer_id': (_I, False),
                'review_date': (_D, False), 'rating': (_I, False), 'review_title': (_S, False)},
    'inventory': {'snapshot_date': (_D, False), 'product_id': (_I, False), 'stock_on_hand': (_I, False),
                  'units_received': (_I, False), 'units_sold': (_I, False), 'stockout_days': (_I, False),
                  'days_of_supply': (_F, False), 'fill_rate': (_F, False), 'stockout_flag': (_I, False),
                  'overstock_flag': (_I, False), 'reorder_flag': (_I, False), 'sell_through_rate': (_F, False),
                  'product_name': (_S, False), 'category': (_S, False), 'segment': (_S, False), 'year': (_I, False),
                  'month': (_I, False)},
    'web_traffic': {'date': (_D, False), 'sessions': (_I, False), 'unique_visitors': (_I, False), 'page_views': (_I, False),
                    'bounce_rate': ('decimal(8,5)', False), 'avg_session_duration_sec': ('decimal(8,1)', False),
                    'traffic_source': (_S, False)},
    'sales': {'Date': (_D, False), 'Revenue': ('decimal(18,2)', False), 'COGS': ('decimal(18,2)', False)},
    'sample_submission': {'Date': (_D, False), 'Revenue': ('decimal(18,2)', False), 'COGS': ('decimal(18,2)', False)},
}

# KEYS: khóa chính của từng nguồn (không trùng, kiểm sau trim). order_items KHÔNG có khóa tự nhiên: một đơn có thể có hai dòng
# cùng sản phẩm (16 nhóm trùng (order_id, product_id) trong snapshot 5bd9a84aaf73), staging không dedup và lấy thứ tự dòng
# theo _src_row (star_schema.md §5.1). Khóa ngoại không kiểm ở đây: dbt test lo như hiện nay.
KEYS = {
    'geography': ['zip'], 'customers': ['customer_id'], 'products': ['product_id'], 'promotions': ['promo_id'],
    'orders': ['order_id'], 'order_items': None, 'payments': ['order_id'], 'shipments': ['order_id'],
    'returns': ['return_id'], 'reviews': ['review_id'], 'inventory': ['snapshot_date', 'product_id'],
    'web_traffic': ['date'], 'sales': ['Date'], 'sample_submission': ['Date'],
}
