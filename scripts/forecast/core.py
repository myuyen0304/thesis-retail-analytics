"""Dự báo G và COGS theo ngày: biến lịch, mốc, model, backtest và luật chọn (B2).

Một đường code cho notebook chứng minh (`notebooks/04_forecasting/so_sanh_model.ipynb`) và stage dự báo của pipeline
(`scripts/forecast/stage.py`), nên hai nơi ra cùng số trên cùng snapshot.

Tham số, danh sách ứng viên và luật chọn được đăng ký ngày 2026-10-14, trước khi có điểm backtest
(`docs/hop_dong_du_bao.md` §0, §4, §5). Đổi các hằng số dưới đây là đổi hợp đồng: phải được PM chốt lại.
"""
import time

import holidays
import lightgbm as lgb
import numpy as np
import pandas as pd
from statsmodels.tsa.statespace.sarimax import SARIMAX

# ---------------------------------------------------------------- đăng ký trước (hợp đồng §0, §4, §5)
SEED = 42
H = 548                                   # số ngày dự báo, như vùng 2023-01-01 → 2024-07-01
K_FOURIER = 5                             # số cặp Fourier cho mùa vụ năm
REGIME_START = pd.Timestamp('2019-01-01')  # mốc chế độ sau đứt gãy (Q4); Calendar kiểm lại trên dữ liệu
EVIDENCE_MIN_RESID = 0.05                 # luật đưa biến Tết / đầu tháng vào model (notebook §2.3)
EVIDENCE_MIN_SHARE = 0.75

FOLDS = {'F1': pd.Timestamp('2020-06-30'), 'F2': pd.Timestamp('2020-12-31'), 'F3': pd.Timestamp('2021-06-30')}
TIE = 0.01                                # ngưỡng hòa: trong vòng 1% điểm thấp nhất thì chọn ứng viên đơn giản hơn
BLEND_GRID = [0.0, 0.25, 0.5, 0.75, 1.0]  # trọng số LightGBM trong bản gộp
INNER_DAYS = 365                          # năm cuối của phần train dùng để chọn trọng số gộp

SARIMAX_ORDER = (1, 0, 1)                 # phần sai số ARMA bậc thấp, d = 0
ARIMA_ORDER = (1, 1, 1)                   # ARIMA thuần trên log, không biến lịch
MAXITER = 1000                            # số vòng tối đa của bộ tối ưu (sửa 2026-10-14, notebook §5)
LGB_PARAMS = dict(objective='regression', learning_rate=0.03, num_leaves=15, min_data_in_leaf=20,
                  feature_fraction=0.9, lambda_l2=1.0, num_threads=4, seed=SEED, deterministic=True,
                  force_col_wise=True, verbose=-1)
LGB_ROUNDS = 800

BASELINES = ['naive1y', 'naive2y', 'baseline_cu']
FLOOR = 'naive2y'
MODELS = ['arima_2019', 'sarimax_2019', 'sarimax_full', 'lgbm_2019', 'lgbm_full', 'blend_full']
COGS_METHODS = ['ratio', 'direct']
CANDIDATES = [(m, c) for m in MODELS for c in COGS_METHODS]
RANK = {cand: i for i, cand in enumerate(CANDIDATES)}   # nhỏ hơn = đơn giản hơn (thứ tự hợp đồng §0)


# ---------------------------------------------------------------- nạp dữ liệu
def load_sales(frame):
    """`frame`: cột Date, Revenue, COGS dạng chuỗi (CSV đọc với dtype=str, hoặc parquet của snapshot).
    Notebook và stage cùng đi qua hàm này, để số thực giống nhau tới từng bit."""
    out = pd.DataFrame({'Revenue': pd.to_numeric(frame['Revenue']).to_numpy(dtype=float),
                        'COGS': pd.to_numeric(frame['COGS']).to_numpy(dtype=float)},
                       index=pd.DatetimeIndex(pd.to_datetime(frame['Date']), name='Date'))
    return out.sort_index()


def load_promotions(frame):
    out = pd.DataFrame({'promo_name': frame['promo_name'].astype(str),
                        'start_date': pd.to_datetime(frame['start_date']),
                        'end_date': pd.to_datetime(frame['end_date'])})
    out['family'] = out['promo_name'].str.replace(r'\s+\d{4}$', '', regex=True)
    out['year'] = out['start_date'].dt.year
    return out


def check_prerequisites(sales):
    """Hợp đồng §5: đủ ngày liên tục, G > 0 và COGS > 0 mọi ngày (cần cho phép log)."""
    full_days = pd.date_range(sales.index.min(), sales.index.max(), freq='D')
    info = {'so_ngay': len(sales), 'tu': sales.index.min().date(), 'den': sales.index.max().date(),
            'lien_tuc': bool(sales.index.equals(full_days)),
            'g_duong': bool((sales['Revenue'] > 0).all()), 'cogs_duong': bool((sales['COGS'] > 0).all())}
    if not (info['lien_tuc'] and info['g_duong'] and info['cogs_duong']):
        raise ValueError(f'Điều kiện tiên quyết của dự báo không đạt: {info}')
    return info


# ---------------------------------------------------------------- biến lịch
def tet_dates(years):
    """Mồng 1 Tết theo năm. language cố định: không truyền thì holidays đặt tên theo biến LANG (Windows en_US →
    'Lunar New Year', Docker C.UTF-8 → 'Tết Nguyên Đán') và lần chạy Docker 2026-10-15 không tìm thấy Tết."""
    vn = holidays.country_holidays('VN', years=years, language='en_US')
    return {d.year: pd.Timestamp(d) for d, name in vn.items() if name == 'Lunar New Year'}


class Calendar:
    """Biến suy từ lịch, cùng bằng chứng cho từng nhóm biến (notebook §2)."""

    def __init__(self, sales, promotions):
        self.sales = sales
        yr = sales.groupby(sales.index.year).agg(so_ngay=('Revenue', 'size'), G_tb_ngay=('Revenue', 'mean'),
                                                 COGS_tb_ngay=('COGS', 'mean'))
        yr['G_doi_so_nam_truoc_%'] = (yr['G_tb_ngay'].pct_change() * 100).round(1)
        self.regime_table = yr
        self.biggest_drop_year = int(yr['G_doi_so_nam_truoc_%'].idxmin())
        if self.biggest_drop_year != REGIME_START.year:
            raise ValueError(f'Năm giảm mạnh nhất là {self.biggest_drop_year}, khác mốc chế độ {REGIME_START.date()} (Q4): báo PM')

        mode_md = lambda s: s.dt.strftime('%m-%d').mode().iloc[0]
        rules = promotions.groupby('family').agg(start_md=('start_date', mode_md), end_md=('end_date', mode_md),
                                                 first_year=('year', 'min'), years=('year', lambda v: sorted(v)))
        rules['odd_only'] = rules['years'].apply(lambda v: all(y % 2 == 1 for y in v))
        rules['slug'] = rules.index.str.lower().str.replace(r'[^a-z]+', '_', regex=True).str.strip('_')
        self.rules = rules
        self.rule_check = self._rule_check(promotions)

        self.tet = tet_dates(range(2011, 2026))
        # đối chiếu với hai ngày lời giải tham khảo ghi (Mục XIV.3)
        if self.tet.get(2023) != pd.Timestamp('2023-01-22') or self.tet.get(2024) != pd.Timestamp('2024-02-10'):
            raise ValueError('Ngày Tết từ thư viện holidays lệch với 22/01/2023, 10/02/2024')

        d_all = sales.index
        Xb = self.base_linear(d_all).assign(const=1.0)
        y = np.log(sales['Revenue'].values)
        beta, *_ = np.linalg.lstsq(Xb.values, y, rcond=None)
        self._resid = pd.Series(y - Xb.values @ beta, index=d_all)
        td = self.tet_diff(d_all)
        tet_bin = pd.Series(np.where(np.abs(td) <= 35, (np.floor(td / 7) * 7).astype(int), np.nan), index=d_all)
        self.tet_evidence = self._evidence(tet_bin)
        first = pd.Series(np.where(d_all.day <= 3, d_all.day, np.nan), index=d_all)
        self.first_evidence = self._evidence(first)
        self.use_tet = bool(self.tet_evidence['dat_luat'].any())
        self.use_first = bool(self.first_evidence['dat_luat'].any())

    def rule_window(self, fam, year):
        r = self.rules.loc[fam]
        start = pd.Timestamp(f'{year}-{r.start_md}')
        end = pd.Timestamp(f'{year}-{r.end_md}')
        if end < start:
            end = pd.Timestamp(f'{year + 1}-{r.end_md}')
        return start, end

    def _rule_check(self, promotions):
        rows = []
        for _, p in promotions.iterrows():
            s, e = self.rule_window(p.family, p.year)
            actual = set(pd.date_range(p.start_date, p.end_date)); rule = set(pd.date_range(s, e))
            rows.append(dict(family=p.family, year=p.year, lech_ngay_dau=(p.start_date - s).days,
                             lech_ngay_cuoi=(p.end_date - e).days, so_ngay_that=len(actual), so_ngay_lech=len(actual ^ rule)))
        chk = pd.DataFrame(rows)
        tom_tat = chk.groupby('family').agg(so_nam=('year', 'size'), lech_dau_toi_da=('lech_ngay_dau', lambda v: v.abs().max()),
                                            lech_cuoi_toi_da=('lech_ngay_cuoi', lambda v: v.abs().max()),
                                            so_ngay_that=('so_ngay_that', 'sum'), so_ngay_lech=('so_ngay_lech', 'sum'))
        tom_tat['ty_le_ngay_lech_%'] = (tom_tat['so_ngay_lech'] / tom_tat['so_ngay_that'] * 100).round(2)
        return self.rules[['start_md', 'end_md', 'first_year', 'odd_only']].join(tom_tat)

    def tet_diff(self, d):
        """Số ngày từ mồng 1 Tết gần nhất (âm: trước Tết)."""
        out = np.empty(len(d), dtype=int)
        for i, x in enumerate(d):
            diffs = [(x - self.tet[y]).days for y in (x.year - 1, x.year, x.year + 1)]
            out[i] = min(diffs, key=abs)
        return out

    def promo_flags(self, d):
        X = pd.DataFrame(index=d)
        for fam, r in self.rules.iterrows():
            flag = np.zeros(len(d)); since = np.full(len(d), -1.0)
            for y in range(d.year.min() - 1, d.year.max() + 1):
                if y < r.first_year or (r.odd_only and y % 2 == 0):
                    continue
                s, e = self.rule_window(fam, y)
                m = (d >= s) & (d <= e)
                flag[m] = 1; since[m] = (d[m] - s).days
            X[f'promo_{r.slug}'] = flag; X[f'promo_{r.slug}_since'] = since
        return X

    def base_linear(self, d):
        d = pd.DatetimeIndex(d); X = pd.DataFrame(index=d)
        doy = d.dayofyear.values
        for k in range(1, K_FOURIER + 1):
            X[f'sin{k}'] = np.sin(2 * np.pi * k * doy / 365.25); X[f'cos{k}'] = np.cos(2 * np.pi * k * doy / 365.25)
        dim, dom = d.days_in_month.values, d.day.values
        X['days_to_eom'] = dim - dom
        for k in (1, 2, 3):
            X[f'is_last{k}'] = (dim - dom <= k - 1).astype(float)
        pf = self.promo_flags(d)
        X = X.join(pf[[c for c in pf if not c.endswith('_since')]])
        X['post2019'] = (d >= REGIME_START).astype(float)
        return X

    def _evidence(self, groups):
        d_all = self.sales.index
        df = pd.DataFrame({'resid': self._resid, 'nhom': groups, 'nam': d_all.year}).dropna()
        by_year = df.groupby(['nhom', 'nam'])['resid'].mean().unstack()
        out = pd.DataFrame({'phan_du_tb': df.groupby('nhom')['resid'].mean(), 'so_ngay': df.groupby('nhom').size()})
        out['ty_le_nam_cung_dau'] = [(np.sign(by_year.loc[g].dropna()) == np.sign(out.loc[g, 'phan_du_tb'])).mean()
                                     for g in out.index]
        out['dat_luat'] = (out['phan_du_tb'].abs() >= EVIDENCE_MIN_RESID) & (out['ty_le_nam_cung_dau'] >= EVIDENCE_MIN_SHARE)
        return out

    def features(self, dates, kind, window):
        d = pd.DatetimeIndex(dates)
        X = self.base_linear(d)
        if self.use_first:
            for k in (1, 2, 3):
                X[f'is_first{k}'] = (d.day <= k).astype(float)
        td_ = self.tet_diff(d)
        if kind == 'linear':
            if self.use_tet:
                for b in range(-35, 35, 7):
                    X[f'tet_{b}'] = ((td_ >= b) & (td_ < b + 7)).astype(float)
        else:
            X['month'] = d.month; X['dom'] = d.day; X['doy'] = d.dayofyear; X['is_odd_year'] = (d.year % 2).astype(float)
            pf = self.promo_flags(d)
            X = X.join(pf[[c for c in pf if c.endswith('_since')]])
            if self.use_tet:
                X['tet_diff'] = np.clip(td_, -60, 60)
        if window != 'full':
            X = X.drop(columns='post2019')
        return X


# ---------------------------------------------------------------- mốc và model
class Forecaster:
    """Train và dự báo các ứng viên; nhớ kết quả từng lần fit để bản gộp dùng lại."""

    def __init__(self, sales, cal):
        self.sales, self.cal = sales, cal
        self.window_start = {'full': sales.index.min(), '2019': REGIME_START}
        self._cache, self._boosters, self.fit_log = {}, {}, []

    def train_slice(self, origin, window):
        return self.sales.loc[self.window_start[window]:origin]

    def model_log_forecast(self, model, target, origin, dates):
        """Dự báo log(target) của một model đơn cho `dates`, train trên dữ liệu ≤ origin. Trả (mean, lower80, upper80 | None)."""
        key = (model, target, origin, dates[0], len(dates))
        if key in self._cache:
            return self._cache[key]
        fam, window = model.split('_')
        tr = self.train_slice(origin, window)
        y = np.log(tr[target].values)
        t_fit = time.time()
        if fam == 'arima':
            res = SARIMAX(y, order=ARIMA_ORDER, trend='n').fit(disp=False, maxiter=MAXITER)
            self.fit_log.append(dict(model=model, target=target, origin=origin.date(), hoi_tu=bool(res.mle_retvals.get('converged')),
                                     du_phong=False, giay=round(time.time() - t_fit)))
            fc = res.get_forecast(steps=len(dates))
            ci = fc.conf_int(alpha=0.2)
            out = (np.asarray(fc.predicted_mean), np.asarray(ci)[:, 0], np.asarray(ci)[:, 1])
        elif fam == 'sarimax':
            # hằng số nằm trong exog; điểm xuất phát của bộ tối ưu = nghiệm hồi quy thường (OLS) trên cùng biến
            Xtr = self.cal.features(tr.index, 'linear', window).assign(const=1.0)
            Xf = self.cal.features(dates, 'linear', window).assign(const=1.0)
            beta, *_ = np.linalg.lstsq(Xtr.values, y, rcond=None)
            e = y - Xtr.values @ beta
            start = np.r_[beta, np.corrcoef(e[1:], e[:-1])[0, 1], 0.0, e.var()]
            mod = SARIMAX(y, exog=Xtr.values, order=SARIMAX_ORDER, trend='n')
            res = mod.fit(start_params=start, disp=False, maxiter=MAXITER)
            du_phong = not res.mle_retvals.get('converged')
            if du_phong:   # L-BFGS chưa báo hội tụ: chạy Powell từ cùng điểm xuất phát, rồi L-BFGS từ kết quả Powell
                res = mod.fit(start_params=mod.fit(start_params=start, method='powell', disp=False, maxiter=5 * MAXITER).params,
                              disp=False, maxiter=MAXITER)
            self.fit_log.append(dict(model=model, target=target, origin=origin.date(), hoi_tu=bool(res.mle_retvals.get('converged')),
                                     du_phong=du_phong, giay=round(time.time() - t_fit)))
            fc = res.get_forecast(steps=len(dates), exog=Xf.values)
            ci = fc.conf_int(alpha=0.2)
            out = (np.asarray(fc.predicted_mean), np.asarray(ci)[:, 0], np.asarray(ci)[:, 1])
        elif fam == 'lgbm':
            Xtr, Xf = self.cal.features(tr.index, 'tree', window), self.cal.features(dates, 'tree', window)
            booster = lgb.train(LGB_PARAMS, lgb.Dataset(Xtr, y), num_boost_round=LGB_ROUNDS)
            # Chỉ giữ booster G của bản cuối để giải thích; các booster backtest rất tốn RAM.
            if model == 'lgbm_full' and target == 'Revenue' and origin == self.sales.index.max():
                self._boosters[key] = booster
            out = (booster.predict(Xf), None, None)
        else:
            raise ValueError(model)
        self._cache[key] = out
        return out

    def explain_log_g(self, model, origin, dates):
        """Đóng góp LightGBM cho log(G), dùng đúng booster đã tạo dự báo cuối."""
        if model != 'lgbm_full':
            raise ValueError('B4a chỉ phân rã model chính lgbm_full')
        self.model_log_forecast(model, 'Revenue', origin, dates)
        key = (model, 'Revenue', origin, dates[0], len(dates))
        booster = self._boosters[key]
        features = self.cal.features(dates, 'tree', 'full')
        contrib = np.asarray(booster.predict(features, pred_contrib=True))
        forecast_log = np.asarray(self._cache[key][0])
        if contrib.shape != (len(dates), len(features.columns) + 1):
            raise ValueError('Số cột đóng góp LightGBM không khớp feature')
        if not np.allclose(contrib.sum(axis=1), forecast_log, rtol=0, atol=1e-8):
            raise ValueError('Đóng góp LightGBM không cộng về log(G) dự báo')
        return features.columns.tolist(), contrib, forecast_log

    def ratio_profile(self, origin, window):
        tr = self.train_slice(origin, window)
        ub = self.cal.promo_flags(tr.index)['promo_urban_blowout'].values
        g = tr.groupby([tr.index.month, ub])[['Revenue', 'COGS']].sum()
        by_month = tr.groupby(tr.index.month)[['Revenue', 'COGS']].sum()
        return (g['COGS'] / g['Revenue']), (by_month['COGS'] / by_month['Revenue'])

    def apply_ratio(self, dates, origin, window):
        prof, by_month = self.ratio_profile(origin, window)
        d = pd.DatetimeIndex(dates)
        ub = self.cal.promo_flags(d)['promo_urban_blowout'].values
        return np.array([prof.get((m, u), by_month[m]) for m, u in zip(d.month, ub)])

    def single_model(self, model, cogs_method, origin, dates):
        """G và COGS (đồng) của một model đơn."""
        g_log, g_lo, g_hi = self.model_log_forecast(model, 'Revenue', origin, dates)
        G = np.exp(g_log)
        if cogs_method == 'ratio':
            C = G * self.apply_ratio(dates, origin, model.split('_')[1])
        else:
            C = np.exp(self.model_log_forecast(model, 'COGS', origin, dates)[0])
        native = (np.exp(g_lo), np.exp(g_hi)) if g_lo is not None else (None, None)
        return G, C, native

    def blend_weight(self, origin, cogs_method):
        """Chọn w trên năm cuối của phần train: train tới origin − 365 ngày, chấm 365 ngày sau đó (đều ≤ origin)."""
        inner_origin = origin - pd.Timedelta(days=INNER_DAYS)
        dates = pd.date_range(inner_origin + pd.Timedelta(days=1), origin)
        truth = self.sales.loc[dates]
        Gs, Cs, _ = self.single_model('sarimax_full', cogs_method, inner_origin, dates)
        Gl, Cl, _ = self.single_model('lgbm_full', cogs_method, inner_origin, dates)
        scores = {w: score_of(truth.Revenue.values, truth.COGS.values, w * Gl + (1 - w) * Gs, w * Cl + (1 - w) * Cs)
                  for w in BLEND_GRID}
        return min(scores, key=scores.get)

    def candidate(self, model, cogs_method, origin, dates):
        """G, COGS, khoảng tự nhiên (nếu có), trọng số gộp (nếu có)."""
        if model == 'blend_full':
            w = self.blend_weight(origin, cogs_method)
            Gs, Cs, _ = self.single_model('sarimax_full', cogs_method, origin, dates)
            Gl, Cl, _ = self.single_model('lgbm_full', cogs_method, origin, dates)
            return w * Gl + (1 - w) * Gs, w * Cl + (1 - w) * Cs, (None, None), w
        G, C, native = self.single_model(model, cogs_method, origin, dates)
        return G, C, native, None

    def baseline(self, name, origin, dates):
        sales = self.sales
        d = pd.DatetimeIndex(dates)
        if name in ('naive1y', 'naive2y'):
            src = []
            for x in d:
                s1 = naive_source(x, origin, 1)
                if name == 'naive2y':
                    s2 = naive_source(x, origin, 2)
                    s1 = s2 if s2 >= REGIME_START else s1     # năm cùng chẵn/lẻ rơi trước mốc chế độ thì dùng naive 1 năm (hợp đồng §4.1)
                src.append(s1)
            src = pd.DatetimeIndex(src)
            return sales.loc[src, 'Revenue'].values, sales.loc[src, 'COGS'].values
        # baseline_cu: tái tạo cách của baseline.ipynb trên dữ liệu ≤ origin (trung bình mùa vụ × CAGR gộp)
        tr = sales.loc[:origin].copy()
        tr['year'], tr['month'], tr['day'] = tr.index.year, tr.index.month, tr.index.day
        annual = tr.groupby('year')[['Revenue', 'COGS']].agg(['sum', 'size'])
        full_years = [y for y in annual.index if annual.loc[y, ('Revenue', 'size')] >= 365 and y >= 2013]
        last_full = max(full_years)
        tot = annual.loc[full_years, [('Revenue', 'sum'), ('COGS', 'sum')]]
        growth = {t: (1 + tot[(t, 'sum')].pct_change().dropna()).prod() ** (1 / (len(full_years) - 1)) for t in ('Revenue', 'COGS')}
        norm = tr[['Revenue', 'COGS']] / tr.groupby('year')[['Revenue', 'COGS']].transform('mean')
        seasonal = norm.groupby([tr.month, tr.day]).mean()
        out = {}
        for t in ('Revenue', 'COGS'):
            base = annual.loc[last_full, (t, 'sum')] / 365
            prof = np.array([seasonal[t].get((x.month, x.day), 1.0) for x in d])
            out[t] = base * growth[t] ** (d.year.values - last_full) * prof
        return out['Revenue'], out['COGS']


def score_of(G_true, C_true, G, C):
    return (np.mean(np.abs(G_true - G)) + np.mean(np.abs(C_true - C))) / 2


def same_day(year, d):
    """Ngày (tháng, ngày) của d trong năm `year`; 29/02 sang năm không nhuận thì lấy 28/02."""
    day = 28 if (d.month == 2 and d.day == 29 and not pd.Timestamp(f'{year}-01-01').is_leap_year) else d.day
    return pd.Timestamp(year=year, month=d.month, day=day)


def naive_source(d, origin, step):
    y = d.year - step
    while same_day(y, d) > origin:
        y -= step
    return same_day(y, d)


# ---------------------------------------------------------------- backtest, chấm điểm, luật chọn
def backtest(fc, progress=None):
    """Mọi mốc và ứng viên trên ba fold. Trả (pred, weights): một dòng = ngày × ứng viên × fold."""
    t0 = time.time()
    parts, weights = [], {}
    for fold, origin in FOLDS.items():
        dates = pd.date_range(origin + pd.Timedelta(days=1), periods=H)
        truth = fc.sales.loc[dates]
        for b in BASELINES:
            G, C = fc.baseline(b, origin, dates)
            parts.append(pd.DataFrame(dict(fold=fold, model=b, cogs_method='copy', date=dates, G=truth.Revenue.values,
                                           C=truth.COGS.values, G_hat=G, C_hat=C, nat_lo=np.nan, nat_hi=np.nan)))
        for m, c in CANDIDATES:
            G, C, (lo, hi), w = fc.candidate(m, c, origin, dates)
            if w is not None:
                weights[(fold, c)] = w
            parts.append(pd.DataFrame(dict(fold=fold, model=m, cogs_method=c, date=dates, G=truth.Revenue.values,
                                           C=truth.COGS.values, G_hat=G, C_hat=C,
                                           nat_lo=lo if lo is not None else np.nan, nat_hi=hi if hi is not None else np.nan)))
        if progress:
            progress(f'{fold} xong sau {time.time() - t0:.0f} giây')
    pred = pd.concat(parts, ignore_index=True)
    pred['logres'] = np.log(pred.G) - np.log(pred.G_hat)
    return pred, weights


def check_convergence(fit_log):
    fits = pd.DataFrame(fit_log)
    if len(fits) and not fits.hoi_tu.all():
        raise ValueError('Có lần fit ARIMA/SARIMAX không hội tụ: dừng, không chấm điểm')
    return fits


def daily_metrics(g):
    out = {}
    for t, a, p in (('g', g.G, g.G_hat), ('cogs', g.C, g.C_hat)):
        err = a - p
        out[f'mae_{t}'] = np.mean(np.abs(err))
        out[f'rmse_{t}'] = np.sqrt(np.mean(err ** 2))
        out[f'r2_{t}'] = 1 - np.sum(err ** 2) / np.sum((a - a.mean()) ** 2)
    out['score'] = (out['mae_g'] + out['mae_cogs']) / 2
    return pd.Series(out)


def score_table(pred):
    return pred.groupby(['model', 'cogs_method', 'fold']).apply(daily_metrics).reset_index()


def select(scores):
    """scores: DataFrame cột model, cogs_method, fold, score. Trả bảng xếp hạng và ứng viên is_primary theo luật §5."""
    floor = scores[scores.model == FLOOR].set_index('fold')['score']
    rows = []
    for (m, c), g in scores[scores.model.isin(MODELS)].groupby(['model', 'cogs_method']):
        s = g.set_index('fold')['score']
        rows.append(dict(model=m, cogs_method=c, diem_tb=s.mean(), so_fold_thang_san=int((s < floor.reindex(s.index)).sum()),
                         qua_san=bool(len(s) == len(FOLDS) and (s < floor.reindex(s.index)).all())))
    tab = pd.DataFrame(rows)
    ok = tab[tab.qua_san]
    if ok.empty:
        return tab.sort_values('diem_tb'), (FLOOR, 'copy'), 'buoc_1_khong_ung_vien_nao_qua_san'
    best = ok.diem_tb.min()
    tied = ok[ok.diem_tb <= best * (1 + TIE)]
    pick = min(zip(tied.model, tied.cogs_method), key=lambda k: RANK[k])
    lowest = tuple(ok.loc[ok.diem_tb.idxmin(), ['model', 'cogs_method']])
    step = 'buoc_2_diem_thap_nhat' if pick == lowest else 'buoc_3_hoa_chon_don_gian'
    return tab.sort_values('diem_tb'), pick, step


def report_metrics(pred, bt, sales):
    """Chỉ số báo kèm theo ứng viên × fold: MAPE G tháng, tháng 8/2021, coverage 80% (notebook §7)."""
    g_aug20 = sales.loc['2020-08', 'Revenue'].sum()

    def month_mape(g):
        m = g.set_index('date')[['G', 'G_hat']]
        cnt = m.G.groupby(m.index.to_period('M')).size()
        full_m = cnt[cnt == cnt.index.days_in_month].index
        s = m.groupby(m.index.to_period('M')).sum().loc[full_m]
        return np.mean(np.abs(s.G - s.G_hat) / s.G) * 100

    def aug21(g):
        a = g.set_index('date').loc['2021-08']
        true_drop = 1 - a.G.sum() / g_aug20
        pred_drop = 1 - a.G_hat.sum() / g_aug20
        return pd.Series(dict(mae_g_t8_2021=np.mean(np.abs(a.G - a.G_hat)), tai_tao_bien_do=pred_drop / true_drop,
                              cogs_g_t8_du_bao=a.C_hat.sum() / a.G_hat.sum(), cogs_g_t8_thuc=a.C.sum() / a.G.sum()))

    def coverage(g):
        m, c, f = g.name
        other = pred[(pred.model == m) & (pred.cogs_method == c) & (pred.fold != f)].logres
        lo, hi = np.quantile(other, [0.1, 0.9])
        inside = (g.G >= g.G_hat * np.exp(lo)) & (g.G <= g.G_hat * np.exp(hi))
        nat = ((g.G >= g.nat_lo) & (g.G <= g.nat_hi)).mean() if g.nat_lo.notna().all() else np.nan
        return pd.Series(dict(coverage_80=inside.mean(), coverage_80_tu_nhien=nat))

    grp = pred.groupby(['model', 'cogs_method', 'fold'])
    extra = pd.concat([grp.apply(month_mape).rename('mape_g_thang_%'), grp.apply(aug21), grp.apply(coverage)], axis=1)
    return bt.set_index(['model', 'cogs_method', 'fold']).join(extra).reset_index()


REPORT_COLS = ['score', 'mae_g', 'mae_cogs', 'rmse_g', 'rmse_cogs', 'r2_g', 'r2_cogs', 'mape_g_thang_%', 'mae_g_t8_2021',
               'tai_tao_bien_do', 'cogs_g_t8_du_bao', 'cogs_g_t8_thuc', 'coverage_80', 'coverage_80_tu_nhien']


# ---------------------------------------------------------------- bản cuối và kiểm
def final_forecast(fc, pred, primary, step, dates):
    """Train tới ngày thực tế cuối, dự báo `dates` cho mọi mốc và ứng viên; khoảng 80% từ quantile phần dư log ba fold."""
    origin = fc.sales.index.max()
    final, final_w = [], {}
    for b in BASELINES:
        G, C = fc.baseline(b, origin, dates)
        final.append(pd.DataFrame(dict(model=b, cogs_method='copy', forecast_date=dates, yhat=G, cogs_yhat=C)))
    for m, c in CANDIDATES:
        G, C, _, w = fc.candidate(m, c, origin, dates)
        if w is not None:
            final_w[c] = w
        final.append(pd.DataFrame(dict(model=m, cogs_method=c, forecast_date=dates, yhat=G, cogs_yhat=C)))
    out = pd.concat(final, ignore_index=True)
    q = pred.groupby(['model', 'cogs_method']).logres.quantile([0.1, 0.9]).unstack()
    out = out.join(q, on=['model', 'cogs_method'])
    out['lower'], out['upper'] = out.yhat * np.exp(out[0.1]), out.yhat * np.exp(out[0.9])
    out = out.drop(columns=[0.1, 0.9])
    out['cogs_ratio_hat'] = out.cogs_yhat / out.yhat
    out['is_primary'] = (out.model == primary[0]) & (out.cogs_method == primary[1])
    out['selection_step'] = np.where(out.is_primary, step, None)
    out['trained_through'] = origin.date()
    out['interval_level'] = 0.8
    if not (out.groupby(['model', 'cogs_method']).size().eq(len(dates)).all()
            and (out.lower <= out.yhat).all() and (out.yhat <= out.upper).all()):
        raise ValueError('Bản cuối thiếu ngày hoặc khoảng dự báo sai thứ tự')
    return out, final_w


def august_2023_check(out, sales, primary):
    """Hợp đồng §9: G tháng 8/2023 thấp hơn G thực tế tháng 8/2022, và COGS/G tháng 8/2023 > 1."""
    g_aug22 = sales.loc['2022-08', 'Revenue'].sum()
    a23 = out[out.forecast_date.dt.strftime('%Y-%m') == '2023-08'].groupby(['model', 'cogs_method'])[['yhat', 'cogs_yhat']].sum()
    a23['G_t8_2023_so_voi_t8_2022'] = a23.yhat / g_aug22
    a23['cogs_g_t8_2023'] = a23.cogs_yhat / a23.yhat
    a23['dat'] = (a23.yhat < g_aug22) & (a23.cogs_g_t8_2023 > 1)
    if not a23.loc[primary, 'dat']:
        raise ValueError('Ứng viên chính không qua kiểm tháng 8/2023')
    return a23


def cogs_ratio_bounds(sales):
    """Khoảng kiểm COGS/G ngày: lịch sử nới 10% mỗi phía (hợp đồng §9)."""
    r = sales.COGS / sales.Revenue
    return r.min() * 0.9, r.max() * 1.1


def run(sales, promotions, dates, progress=None):
    """Toàn bộ B2 trên một bộ dữ liệu: dùng cho stage pipeline. Notebook gọi từng bước để hiển thị."""
    check_prerequisites(sales)
    cal = Calendar(sales, promotions)
    fc = Forecaster(sales, cal)
    pred, weights = backtest(fc, progress)
    check_convergence(fc.fit_log)
    bt = score_table(pred)
    ranking, primary, step = select(bt[['model', 'cogs_method', 'fold', 'score']])
    report = report_metrics(pred, bt, sales)
    out, final_w = final_forecast(fc, pred, primary, step, dates)
    fits = check_convergence(fc.fit_log)
    a23 = august_2023_check(out, sales, primary)
    lo, hi = cogs_ratio_bounds(sales)
    pp = out[out.is_primary]
    if not pp.cogs_ratio_hat.between(lo, hi).all():
        raise ValueError('COGS/G dự báo của ứng viên chính ra ngoài khoảng lịch sử nới 10%')
    return dict(cal=cal, forecaster=fc, pred=pred, weights=weights, bt=bt, ranking=ranking, primary=primary, step=step,
                report=report, final=out, final_weights=final_w, fits=fits, august_2023=a23)
