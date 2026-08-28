# -*- coding: utf-8 -*-
"""Sinh bo bieu do EDA."""
import pandas as pd, numpy as np, warnings, os
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
warnings.filterwarnings('ignore')

plt.rcParams.update({
    'font.family': ['Segoe UI', 'Arial', 'DejaVu Sans'],
    'font.size': 11, 'axes.titlesize': 14, 'axes.titleweight': 'bold',
    'axes.spines.top': False, 'axes.spines.right': False,
    'axes.grid': True, 'grid.alpha': .25, 'grid.linestyle': '-',
    'figure.dpi': 130, 'savefig.dpi': 130, 'savefig.bbox': 'tight',
    'axes.axisbelow': True,
})
XANH, CAM, XAM, DO, LUC = '#2b6cb0', '#dd6b20', '#a0aec0', '#c53030', '#2f855a'
OUT = 'docs/hinh'
os.makedirs(OUT, exist_ok=True)

D = 'data/'
L = lambda t, **kw: pd.read_csv(D + t + '.csv', low_memory=False, **kw)
o = L('orders', parse_dates=['order_date']); oi = L('order_items'); p = L('products')
s = L('sales', parse_dates=['Date']); r = L('returns'); sh = L('shipments', parse_dates=['ship_date','delivery_date'])
c = L('customers'); w = L('web_traffic', parse_dates=['date']); pr = L('promotions', parse_dates=['start_date','end_date'])

t = oi[['order_id','product_id','quantity','unit_price','discount_amount','promo_id']].merge(
        o[['order_id','order_date','customer_id','order_status','order_source']], on='order_id')
t = t.merge(p[['product_id','category','cogs']], on='product_id')
t['rev'] = t.quantity*t.unit_price; t['cog'] = t.quantity*t.cogs; t['nam'] = t.order_date.dt.year

def luu(fig, ten):
    fig.savefig(f'{OUT}/{ten}.png'); plt.close(fig); print('  ->', ten)

# ---------- 1. Doanh thu theo nam ----------
n = s.assign(nam=s.Date.dt.year).groupby('nam').agg(rev=('Revenue','sum'), cogs=('COGS','sum'))
n['ty'] = n.rev/1e9; n['bien'] = (n.rev-n.cogs)/n.rev*100
nn = n.loc[2013:]
fig, ax = plt.subplots(figsize=(10,4.6))
mau = [DO if x in (2019,) else (XANH if x != 2016 else LUC) for x in nn.index]
ax.bar(nn.index, nn.ty, color=mau, width=.68)
for x, v in zip(nn.index, nn.ty):
    ax.text(x, v+.03, f'{v:.2f}', ha='center', fontsize=10, fontweight='bold')
ax.annotate('Đỉnh 2016\n2,10 tỷ', xy=(2016, 2.10), xytext=(2016, 2.55),
            ha='center', color=LUC, fontweight='bold', fontsize=10,
            arrowprops=dict(arrowstyle='->', color=LUC))
ax.annotate('2019: −38,6%\ntrong một năm', xy=(2019, 1.14), xytext=(2020.2, 2.1),
            ha='center', color=DO, fontweight='bold', fontsize=10,
            arrowprops=dict(arrowstyle='->', color=DO))
ax.set_title('Doanh thu đạt đỉnh 2016 rồi mất một nửa')
ax.set_ylabel('Tỷ đvtt'); ax.set_xticks(nn.index); ax.set_ylim(0, 2.85)
luu(fig, '01-doanh-thu-theo-nam')

# ---------- 2. Phan ra: so don vs gia tri don ----------
d = o.assign(nam=o.order_date.dt.year).groupby('nam').size()
gt = t.groupby('nam').rev.sum()/d
d, gt = d.loc[2013:], gt.loc[2013:]
fig, ax = plt.subplots(figsize=(10,4.6))
ax.plot(d.index, d/1000, 'o-', color=DO, lw=2.6, ms=7, label='Số đơn hàng (nghìn đơn)')
ax.set_ylabel('Số đơn hàng (nghìn)', color=DO); ax.tick_params(axis='y', labelcolor=DO)
ax.set_ylim(0, 95)
ax2 = ax.twinx(); ax2.grid(False)
ax2.plot(gt.index, gt/1000, 's--', color=XANH, lw=2.6, ms=7, label='Giá trị đơn TB (nghìn đvtt)')
ax2.set_ylabel('Giá trị đơn TB (nghìn đvtt)', color=XANH); ax2.tick_params(axis='y', labelcolor=XANH)
ax2.set_ylim(0, 40)
ax.text(2013.2, 90, '−56,2%\ntừ đỉnh 2016', color=DO, fontweight='bold', fontsize=11.5, va='top')
ax2.text(2020.5, 38.5, '+50,7%\ntừ 2013', color=XANH, fontweight='bold', fontsize=11.5, va='top')
ax.set_title('Nghịch lý: mỗi đơn đắt hơn, nhưng số đơn sụp một nửa')
ax.set_xticks(d.index)
h1,l1 = ax.get_legend_handles_labels(); h2,l2 = ax2.get_legend_handles_labels()
ax.legend(h1+h2, l1+l2, loc='lower left', frameon=False)
luu(fig, '02-phan-ra-so-don-gia-tri')

# ---------- 3. Traffic vs don hang vs CVR ----------
dn = o.groupby('order_date').size().rename('don')
wd = w.set_index('date').join(dn); wd['cvr'] = wd.don/wd.sessions*100; wd['nam'] = wd.index.year
a = wd.groupby('nam').agg(ss=('sessions','mean'), don=('don','mean'), cvr=('cvr','mean'))
fig, (ax, axb) = plt.subplots(2, 1, figsize=(10,6.4), sharex=True, height_ratios=[1.15,1])
iss = a.ss/a.ss.iloc[0]*100; idon = a.don/a.don.iloc[0]*100
ax.plot(a.index, iss, 'o-', color=LUC, lw=2.8, ms=7, label='Lưu lượng truy cập')
ax.plot(a.index, idon, 's-', color=DO, lw=2.8, ms=7, label='Số đơn hàng')
ax.fill_between(a.index, iss, idon, where=(iss > idon), color=DO, alpha=.10)
ax.axhline(100, color='#888', lw=1.2, ls=':')
ax.legend(frameon=False, loc='lower left'); ax.set_ylabel('Chỉ số (2013 = 100)')
ax.set_ylim(30, 180)
ax.annotate('+62,7%', xy=(2022, iss.iloc[-1]), xytext=(2021.3, 172),
            color=LUC, fontweight='bold', fontsize=12, ha='center',
            arrowprops=dict(arrowstyle='->', color=LUC))
ax.annotate('−53,1%', xy=(2022, idon.iloc[-1]), xytext=(2021.3, 62),
            color=DO, fontweight='bold', fontsize=12, ha='center',
            arrowprops=dict(arrowstyle='->', color=DO))
ax.text(2016.5, 118, 'Khoảng cách này chính là\nphần khách bị mất',
        ha='center', fontsize=10.5, color='#7a2020', style='italic')
ax.set_title('Người vào ngày càng đông, người mua ngày càng ít')
axb.bar(a.index, a.cvr, color=[DO if v < .6 else XANH for v in a.cvr], width=.68)
for x, v in zip(a.index, a.cvr): axb.text(x, v+.02, f'{v:.2f}%', ha='center', fontsize=9.5, fontweight='bold')
axb.set_ylabel('Tỷ lệ chuyển đổi'); axb.set_xticks(a.index); axb.set_ylim(0, 1.42)
axb.set_title('Tỷ lệ chuyển đổi sụp 71,8%: 1,17% → 0,33%', fontsize=12)
luu(fig, '03-traffic-vs-chuyen-doi')

# ---------- 4. Gia ban TB ----------
gia = t.groupby('nam').unit_price.mean()
sl = t.groupby('nam').quantity.mean()
fig, ax = plt.subplots(figsize=(10,4.2))
ax.plot(gia.index, gia, 'o-', color=DO, lw=2.8, ms=7)
ax.fill_between(gia.index, gia, alpha=.10, color=DO)
ax.set_ylabel('Giá bán TB mỗi sản phẩm (đvtt)')
ax.set_title('Toàn bộ mức tăng giá trị đơn đến từ tăng giá, không phải mua nhiều hơn')
for x, v in list(zip(gia.index, gia))[::2]:
    ax.text(x, v+180, f'{v:,.0f}', ha='center', fontsize=9.5)
ax.text(2013.2, 6500, 'Giá bán TB: +53,7%\nSố lượng mỗi dòng: đứng yên 4,49 → 4,49\nSố dòng mỗi đơn: 1,155 → 1,057 (giảm)',
        fontsize=10.5, va='top', bbox=dict(boxstyle='round,pad=.5', fc='#fff8e1', ec='#d6b656'))
ax.set_xticks(gia.index); ax.set_ylim(3800, 7600)
luu(fig, '04-gia-ban-tang')

# ---------- 5. Cu sup 2019 dong deu ----------
cat = t.pivot_table(index='nam', columns='category', values='rev', aggfunc='sum')
ch = t.pivot_table(index='nam', columns='order_source', values='rev', aggfunc='sum')
gc = ((cat.loc[2019]/cat.loc[2018]-1)*100).sort_values()
gh = ((ch.loc[2019]/ch.loc[2018]-1)*100).sort_values()
fig, (a1, a2) = plt.subplots(1, 2, figsize=(11,4.2))
a1.barh(gc.index, gc.values, color=DO); a1.set_title('Theo danh mục sản phẩm', fontsize=12)
a2.barh(gh.index, gh.values, color=DO); a2.set_title('Theo kênh bán', fontsize=12)
for a, gg in ((a1,gc),(a2,gh)):
    for i, v in enumerate(gg.values):
        a.text(v-1.5, i, f'{v:.1f}%', va='center', ha='right', color='white', fontweight='bold', fontsize=10)
    a.set_xlim(-62, 4); a.grid(axis='y', alpha=0)
fig.suptitle('Cú sụp 2019 diễn ra đồng đều — không danh mục hay kênh nào được miễn',
             fontsize=14, fontweight='bold', y=1.02)
luu(fig, '05-cu-sup-2019')

# ---------- 6. That thoat doanh thu ----------
tong = t.rev.sum(); huy = t[t.order_status=='cancelled'].rev.sum()
hoan = r.refund_amount.sum(); gg = t.discount_amount.sum()
giu = tong-huy-hoan-gg
fig, ax = plt.subplots(figsize=(10,4.2))
muc = [('Doanh thu gộp ghi nhận', tong, XAM), ('Đơn bị hủy', -huy, DO),
       ('Tiền hoàn trả', -hoan, DO), ('Giảm giá khuyến mại', -gg, CAM),
       ('Thực sự giữ lại', giu, LUC)]
x, day = 0, 0
for i, (ten, v, mau) in enumerate(muc):
    if i == 0 or i == len(muc)-1:
        ax.bar(i, v/1e9, color=mau, width=.62); day = v
        ax.text(i, v/1e9+.45, f'{v/1e9:.2f} tỷ', ha='center', fontweight='bold', fontsize=10.5)
    else:
        ax.bar(i, v/1e9, bottom=day/1e9, color=mau, width=.62); day += v
        ax.text(i, day/1e9-.75, f'−{-v/1e9:.2f} tỷ\n({-v/tong*100:.2f}%)', ha='center',
                va='top', color=mau, fontweight='bold', fontsize=10)
ax.set_xticks(range(len(muc))); ax.set_xticklabels([m[0] for m in muc], fontsize=10)
ax.set_ylabel('Tỷ đvtt'); ax.set_ylim(0, 19)
ax.set_title('Cứ 100 đồng ghi nhận thì 16,9 đồng không bao giờ về túi')
luu(fig, '06-that-thoat-doanh-thu')

# ---------- 7. Pareto SKU ----------
ban = t.groupby('product_id').rev.sum().sort_values(ascending=False)
cum = ban.cumsum()/ban.sum()*100
fig, ax = plt.subplots(figsize=(10,4.2))
xx = np.arange(1, len(ban)+1)/len(ban)*100
ax.plot(xx, cum.values, color=XANH, lw=2.8)
ax.fill_between(xx, cum.values, alpha=.12, color=XANH)
for m, lab in ((10,'65,4%'), (20,'81,8%')):
    v = cum.values[int(len(ban)*m/100)-1]
    ax.plot([m,m],[0,v], ':', color=DO, lw=1.8); ax.plot([0,m],[v,v], ':', color=DO, lw=1.8)
    ax.text(m+1.5, v-6, f'Top {m}% mã hàng\n→ {lab} doanh thu', color=DO, fontweight='bold', fontsize=10)
ax.set_xlabel('% số mã sản phẩm (xếp theo doanh thu giảm dần)')
ax.set_ylabel('% doanh thu tích lũy'); ax.set_xlim(0,100); ax.set_ylim(0,102)
ax.set_title('Tập trung cực đoan: 10% mã hàng tạo ra 65% doanh thu')
ax.text(45, 22, f'Ngoài ra: 814/2.412 mã ({814/2412*100:.1f}%)\nchưa từng bán được món nào',
        fontsize=10.5, bbox=dict(boxstyle='round,pad=.5', fc='#fff8e1', ec='#d6b656'))
luu(fig, '07-pareto-san-pham')

# ---------- 8. Nghich ly danh muc ----------
mix = t.groupby('category').agg(rev=('rev','sum'), cog=('cog','sum'))
mix['tt'] = mix.rev/mix.rev.sum()*100; mix['bien'] = (mix.rev-mix.cog)/mix.rev*100
mix = mix.sort_values('tt', ascending=False)
fig, ax = plt.subplots(figsize=(9,4.6))
ax.scatter(mix.tt, mix.bien, s=mix.tt*22+120, color=[DO,XANH,XAM,LUC], alpha=.85, zorder=3)
for k, row in mix.iterrows():
    ax.annotate(f'{k}\n{row.tt:.1f}% DT · biên {row.bien:.2f}%',
                (row.tt, row.bien), xytext=(0, -46 if k=='Streetwear' else 34),
                textcoords='offset points', ha='center', fontsize=10.5, fontweight='bold')
ax.axhline(13.8, ls='--', color=XAM, lw=1.5)
ax.text(60, 14.2, 'Biên LN gộp toàn hệ thống: 13,8%', color='#555', fontsize=10)
ax.set_xlabel('Tỷ trọng doanh thu (%)'); ax.set_ylabel('Biên lợi nhuận gộp (%)')
ax.set_xlim(-8, 95); ax.set_ylim(8, 22)
ax.set_title('Nghịch lý: danh mục bán chạy nhất lại có biên lợi nhuận thấp gần nhất')
luu(fig, '08-nghich-ly-danh-muc')

# ---------- 9. Mua vu ----------
sm = s.assign(th=s.Date.dt.month).groupby('th').Revenue.mean()/s.Revenue.mean()
fig, ax = plt.subplots(figsize=(10,4.2))
mau = [LUC if v >= 1.4 else (DO if v <= .65 else XANH) for v in sm]
ax.bar(sm.index, sm.values, color=mau, width=.7)
ax.axhline(1, color='#333', lw=1.4)
for x, v in zip(sm.index, sm.values):
    ax.text(x, v+.03, f'{v:.2f}', ha='center', fontsize=10, fontweight='bold')
ax.set_xticks(range(1,13)); ax.set_xticklabels([f'T{i}' for i in range(1,13)])
ax.set_ylabel('Chỉ số mùa vụ (1,0 = TB năm)'); ax.set_ylim(0, 1.78)
ax.set_title('Mùa vụ ngược quy luật ngành: đỉnh tháng 4–6, đáy tháng 11–1')
ax.text(7.6, 1.55, 'Biên độ đỉnh/đáy: 2,60 lần', fontsize=11, fontweight='bold',
        bbox=dict(boxstyle='round,pad=.5', fc='#fff8e1', ec='#d6b656'))
luu(fig, '09-mua-vu')

# ---------- 10. Khuyen mai + tra hang ----------
ngay = pd.date_range(s.Date.min(), s.Date.max()); km = pd.Series(False, index=ngay)
for _, x in pr.iterrows(): km[(ngay>=x.start_date)&(ngay<=x.end_date)] = True
sk = s.set_index('Date').join(km.rename('km'))
sd = sh.merge(o[['order_id','order_date','order_status']], on='order_id')
sd['ng'] = (sd.delivery_date-sd.order_date).dt.days; sd['tra'] = sd.order_status=='returned'
tt = sd.groupby('ng').tra.mean()*100; tt = tt[(tt.index>=2)&(tt.index<=10)]
fig, (a1, a2) = plt.subplots(1, 2, figsize=(11,4.2))
v1, v2 = sk[sk.km].Revenue.mean()/1e6, sk[~sk.km].Revenue.mean()/1e6
a1.bar(['Ngày CÓ\nkhuyến mại','Ngày KHÔNG\nkhuyến mại'], [v1,v2], color=[CAM,XANH], width=.55)
for i, v in enumerate([v1,v2]): a1.text(i, v+.06, f'{v:.2f} tr', ha='center', fontweight='bold')
a1.set_ylabel('Doanh thu TB/ngày (triệu đvtt)'); a1.set_ylim(0, 5.4)
a1.set_title('Khuyến mại không nâng doanh thu', fontsize=12)
a1.text(.5, 4.7, '−11,8%\nSố lượng mua TB: 4,49 vs 4,50', ha='center', fontsize=10.5, color=DO,
        fontweight='bold')
a2.plot(tt.index, tt.values, 'o-', color=XANH, lw=2.6, ms=8)
a2.set_ylim(0, 10); a2.set_xlabel('Số ngày từ đặt đến nhận hàng')
a2.set_ylabel('Tỷ lệ đơn bị trả (%)'); a2.set_xticks(range(2,11))
a2.set_title('Giao nhanh không giảm trả hàng', fontsize=12)
a2.text(6, 8.2, 'Dao động 6,08%–6,51%\nkhông có xu hướng', ha='center', fontsize=10.5,
        bbox=dict(boxstyle='round,pad=.4', fc='#fff8e1', ec='#d6b656'))
luu(fig, '10-khuyen-mai-va-tra-hang')

# ---------- 11. Khach hang ----------
slm = o.groupby('customer_id').size()
nhom = pd.Series({'Chưa từng mua': len(c)-len(slm), 'Mua 1 lần': (slm==1).sum(),
                  'Mua 2–4 lần': slm.between(2,4).sum(), 'Mua ≥5 lần': (slm>=5).sum()})
fig, ax = plt.subplots(figsize=(9,4.2))
mau = [XAM, CAM, XANH, LUC]
b = ax.barh(nhom.index[::-1], nhom.values[::-1], color=mau[::-1], height=.62)
for i, v in enumerate(nhom.values[::-1]):
    ax.text(v+700, i, f'{v:,}  ({v/len(c)*100:.1f}%)', va='center', fontweight='bold', fontsize=10.5)
ax.set_xlim(0, 62000); ax.grid(axis='y', alpha=0)
ax.set_xlabel('Số khách hàng  ·  % tính trên 121.930 tài khoản đăng ký', fontsize=10.5)
ax.set_title('Trong 90.246 khách từng mua, 45,3% đã quay lại từ 5 lần trở lên')
ax.text(43000, 1.5, '31.684 tài khoản đăng ký\nnhưng chưa từng mua\n→ tệp dễ khai thác nhất',
        fontsize=10.5, va='center', ha='left',
        bbox=dict(boxstyle='round,pad=.5', fc='#fff8e1', ec='#d6b656'))
luu(fig, '11-khach-hang')

print('\nXong. Bieu do luu tai', OUT)
