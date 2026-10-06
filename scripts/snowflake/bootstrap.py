"""Chuẩn bị đăng nhập Snowflake cho một account mới (mỗi lần đổi account trial), không cần mạng:

1. Tạo cặp khóa RSA cho user service RETAIL_DBT — chỉ tạo lần đầu, ở ~/.snowflake/ (NGOÀI repo). Các account sau dùng
   lại cùng khóa, nên chỉ cần dán SQL, không phải đổi gì phía máy.
2. Điền khóa CÔNG KHAI + hạn mức credit vào scripts/snowflake/bootstrap.sql → warehouse/snowflake_bootstrap.sql (gitignore)
   để dán vào Snowsight. Khóa bí mật không bao giờ vào file SQL.
3. Tạo .env.snowflake.local (Git ignore) nếu chưa có, để điền SNOWFLAKE_ACCOUNT của account mới.

Chạy từ root repo:  .venv/Scripts/python.exe scripts/snowflake/bootstrap.py [--credit-quota 20]
"""
import argparse
import os

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

KEY_PATH = os.path.expanduser('~/.snowflake/retail_dbt_rsa_key.p8')
ENV_FILE = '.env.snowflake.local'
ENV_TEMPLATE = """# CẤU HÌNH SNOWFLAKE CỦA RETAIL ANALYTICS — file cá nhân, Git ignore. Tạo bởi scripts/snowflake/bootstrap.py.
# Mở lại file này để xem account đang dùng. Mỗi lần đổi account trial: sửa mục 1, chạy lại bootstrap.py, dán SQL.
# Paste giá trị vào giữa hai dấu nháy đơn, giữ nguyên tên biến bên trái.

# ── 1. ACCOUNT (đổi mỗi lần tạo account trial mới) ───────────────────────
# Snowsight → góc dưới trái (tên tài khoản) → Account → "View account details" → Account identifier,
# dạng <ORGNAME>-<ACCOUNTNAME>, ví dụ ABCDEFG-XY12345. Không dán cả URL.
SNOWFLAKE_ACCOUNT=''
# Ngày đăng ký trial (trial hết sau 30 ngày hoặc khi hết credit), ví dụ 2026-11-20.
RETAIL_SNOWFLAKE_TRIAL_STARTED_ON=''
# Email đã dùng đăng ký account này, chỉ để tra lại.
RETAIL_SNOWFLAKE_SIGNUP_EMAIL=''

# ── 2. ĐĂNG NHẬP (do bootstrap.sql tạo, thường không cần sửa) ────────────
SNOWFLAKE_USER='RETAIL_DBT'
SNOWFLAKE_PRIVATE_KEY_PATH='{key_path}'
SNOWFLAKE_ROLE='TRANSFORMER'
SNOWFLAKE_WAREHOUSE='TRANSFORM_WH'
SNOWFLAKE_DATABASE='RETAIL'

# ── 3. GHI NHẬN ──────────────────────────────────────────────────────────
# Chỉ điền sau khi đã nạp + dbt build + đối soát thành công trên account này (UTC), ví dụ 2026-11-20T08:30:00Z.
RETAIL_SNOWFLAKE_LAST_VERIFIED_AT=''
RETAIL_SNOWFLAKE_NOTES=''
"""

ap = argparse.ArgumentParser()
ap.add_argument('--credit-quota', type=int, default=20,
                help='credit/tháng của RETAIL_MONITOR; XSMALL tốn 1 credit/giờ chạy')
a = ap.parse_args()

if not os.path.exists(KEY_PATH):
    os.makedirs(os.path.dirname(KEY_PATH), exist_ok=True)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    with open(KEY_PATH, 'wb') as f:
        f.write(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                  serialization.NoEncryption()))
    print(f'Đã tạo khóa bí mật mới: {KEY_PATH} (giữ trên máy, không gửi ai, không commit)')
else:
    print(f'Dùng lại khóa có sẵn: {KEY_PATH}')
with open(KEY_PATH, 'rb') as f:
    key = serialization.load_pem_private_key(f.read(), password=None)
pub = key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()
pub = ''.join(line for line in pub.splitlines() if 'PUBLIC KEY' not in line)   # Snowflake nhận phần base64, bỏ header

with open('scripts/snowflake/bootstrap.sql', encoding='utf-8') as f:
    sql = f.read().replace('{{rsa_public_key}}', pub).replace('{{credit_quota}}', str(a.credit_quota))
os.makedirs('warehouse', exist_ok=True)
with open('warehouse/snowflake_bootstrap.sql', 'w', encoding='utf-8') as f:
    f.write(sql)
print('Đã điền SQL: warehouse/snowflake_bootstrap.sql → mở trong Snowsight (ACCOUNTADMIN) → Run All')

if not os.path.exists(ENV_FILE):
    with open(ENV_FILE, 'w', encoding='utf-8') as f:
        f.write(ENV_TEMPLATE.format(key_path=KEY_PATH.replace('\\', '/')))
    print(f'Đã tạo {ENV_FILE} → điền SNOWFLAKE_ACCOUNT')
else:
    print(f'{ENV_FILE} đã có → nhớ sửa SNOWFLAKE_ACCOUNT nếu vừa đổi account')
