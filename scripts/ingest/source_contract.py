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
