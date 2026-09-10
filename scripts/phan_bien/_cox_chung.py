# -*- coding: utf-8 -*-
"""Dung bang du lieu Cox dung chung cho B7, B11, B12, B14, B17.
Khong phai script tra loi — chi la ham dung san, moi script kia tu import."""
import pandas as pd, numpy as np, warnings
warnings.filterwarnings('ignore')

D = 'data/'
REF = pd.Timestamp('2022-12-31')

def nap():
    od = pd.read_csv(D+'orders.csv', parse_dates=['order_date'])
    oi = pd.read_csv(D+'order_items.csv', low_memory=False)
    p  = pd.read_csv(D+'products.csv', usecols=['product_id','category'])
    sh = pd.read_csv(D+'shipments.csv', parse_dates=['ship_date','delivery_date'])
    rt = pd.read_csv(D+'returns.csv', usecols=['order_id'])
    live = od[od.order_status != 'cancelled']
    oi['gross'] = oi.quantity * oi.unit_price
    return od, oi, p, sh, rt, live

def bang_cox():
    od, oi, p, sh, rt, live = nap()
    s = live.sort_values('order_date')
    first = s.groupby('customer_id').agg(oid1=('order_id','first'), d1=('order_date','first'))
    sec = s[s.duplicated('customer_id', keep='first')].groupby('customer_id').order_date.first()
    df = first.copy()
    df['d2'] = sec.reindex(df.index)
    df['su_kien'] = df.d2.notna().astype(int)
    df['thoi_gian'] = np.where(df.su_kien == 1, (df.d2-df.d1).dt.days, (REF-df.d1).dt.days)
    df = df[df.thoi_gian > 0]
    df['aov_first'] = df.oid1.map(oi.groupby('order_id').gross.sum())
    df['promo_first'] = df.oid1.map(
        oi.groupby('order_id').promo_id.apply(lambda x: x.notna().any())).fillna(False).astype(int)
    df['delivery_days'] = df.oid1.map(
        (sh.set_index('order_id').delivery_date - sh.set_index('order_id').ship_date).dt.days)
    df['returned_first'] = df.oid1.isin(set(rt.order_id)).astype(int)
    df['category_first'] = df.oid1.map(
        oi.merge(p, on='product_id').groupby(['order_id','category']).gross.sum()
          .reset_index().sort_values('gross').groupby('order_id').category.last())
    df['cohort_year'] = df.d1.dt.year
    df['thang_dau'] = df.d1.dt.month
    df['quy_dau'] = df.d1.dt.quarter
    return df

def ma_tran(df, them=None, bo=None):
    """Dung ma tran thiet ke giong btn4_survival.py, co the them/bo bien."""
    cot = ['thoi_gian','su_kien','promo_first','delivery_days','returned_first',
           'log_aov','category_first','cohort_year']
    m = df.dropna(subset=['delivery_days','aov_first','category_first']).copy()
    m['log_aov'] = np.log1p(m.aov_first)
    if them: cot = cot + them
    if bo: cot = [c for c in cot if c not in bo]
    phanloai = [c for c in ('category_first','thang_dau','quy_dau','cohort_cat') if c in cot]
    X = pd.get_dummies(m[cot], columns=phanloai, drop_first=True, dtype=float)
    if 'cohort_year' in X.columns:
        X['cohort_year'] = X.cohort_year - X.cohort_year.min()
    return X, m
