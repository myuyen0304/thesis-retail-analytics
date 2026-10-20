"""Tìm tri thức B5 bằng BM25 thuần Python trên bản chụp đóng gói cùng app.

Văn bản là dữ liệu không đáng tin: chỉ đưa đoạn đã che chữ số, không cấp claim.
"""
import hashlib
import json
import math
import re
from collections import Counter
from functools import lru_cache
from pathlib import Path

CORPUS = Path(__file__).with_name('knowledge_corpus.json')
MAX_SNIPPET_CHARS = 320
MAX_RESULTS = 3
_TOKEN = re.compile(r'[^\W_]+(?:_[^\W_]+)*', re.UNICODE)
_NUMBER = re.compile(r'(?<!\w)[+−-]?\d[\d.,/%–-]*', re.UNICODE)
_STOP = frozenset('là gì của có cho theo trong một những và với từ được như nào thế tại sao vì sao '
                  'hãy giải thích tôi bạn dữ liệu tài liệu số liệu bao nhiêu không chính khác'.split())
_ALIASES = {'ngành': ('category',), 'vùng': ('region',), 'kênh': ('acquisition_channel',)}


def tokenize(text: str) -> list[str]:
    """Giữ nguyên dấu tiếng Việt, viết thường; không tự suy từ đồng âm bỏ dấu."""
    return [t for t in _TOKEN.findall(text.lower()) if t not in _STOP]


@lru_cache(maxsize=1)
def corpus() -> dict:
    data = json.loads(CORPUS.read_text(encoding='utf-8'))
    content = json.dumps(data['records'], ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    expected = hashlib.sha256(content.encode('utf-8')).hexdigest()[:16]
    if data['corpus_version'] != expected:
        raise ValueError('Bản chụp tri thức sai corpus_version')
    return data


def _citation(row: dict) -> str:
    part = row['section'].split(' ', 1)[0].rstrip('.')
    if row['source_path'] == 'CLAUDE.md' and not part[0].isdigit():
        part = '5'
    return f"{row['source_path']} §{part}"


def _snippet(row: dict, terms: list[str]) -> str:
    # Chữ số trong tài liệu chỉ giúp truy xuất nội bộ; model không nhìn thấy giá trị để chép làm số liệu.
    text = _NUMBER.sub('[số tài liệu]', row['text'])
    hits = [m.start() for t in terms if (m := re.search(re.escape(t), text, re.I))]
    start = max(0, min(hits) - 55) if hits else 0
    prefix = 'Đề xuất, chờ BA chốt: ' if row['status'] == 'đề xuất' else ''
    room = MAX_SNIPPET_CHARS - len(prefix)
    body = text[start:start + room].strip()
    if start:
        body = '…' + body[1:]
    if start + room < len(text):
        body = body[:-1] + '…'
    return prefix + body


def search(query: str, k: int = MAX_RESULTS, *, data: dict | None = None) -> list[dict]:
    """BM25 chuẩn (k1=1.5, b=0.75), chỉ trả khi có từ chủ đề trùng thật."""
    if not isinstance(query, str) or not 1 <= k <= MAX_RESULTS:
        return []
    terms = tokenize(query)
    terms += [alias for term in terms for alias in _ALIASES.get(term, ())]
    if not terms:
        return []
    snapshot = data if data is not None else corpus()
    rows = snapshot['records']
    tokens = [tokenize(r['section'] + ' ' + r['text']) for r in rows]
    n = len(rows)
    if not n:
        return []
    avg = sum(map(len, tokens)) / n
    df = Counter(t for doc in tokens for t in set(doc))
    scores = []
    metric_codes = {'r', 'g', 'n', 'u', 'p', 'c', 'q', 'f', 'aov'}
    asks_definition = bool(re.search(r'là gì|định nghĩa|được tính|tính thế nào', query.lower()))
    asks_forecast_contract = 'g' in terms and 'dự báo' in query.lower() and 'hợp đồng' in query.lower()
    needed = 1 if set(terms) <= metric_codes else min(2, len(set(terms)))
    for i, doc in enumerate(tokens):
        counts = Counter(doc)
        overlap = set(terms) & counts.keys()
        ps_exact = any(re.fullmatch(r'ps[1-5]', t) and rows[i]['text'].lower().startswith(f'| {t}:')
                       for t in terms)
        metric_exact = any(t in metric_codes and rows[i]['source_path'] == 'docs/star_schema.md'
                           and rows[i]['text'].lower().startswith(f'| {t} |') for t in terms)
        contract_exact = (asks_forecast_contract and rows[i]['source_path'] == 'docs/hop_dong_du_bao.md'
                          and rows[i]['section'].startswith('2.1 '))
        if not ps_exact and not (asks_definition and metric_exact) and not contract_exact and (len(overlap) < needed or
                             (len(set(terms)) > 2 and len(overlap) / len(set(terms)) < .3)):
            continue
        score = sum(math.log(1 + (n - df[t] + .5) / (df[t] + .5)) * counts[t] * 2.5 /
                    (counts[t] + 1.5 * (.25 + .75 * len(doc) / avg)) for t in set(terms) if counts[t])
        # Dòng định nghĩa ký hiệu được ưu tiên khi câu hỏi nêu đúng mã R/G/N/U/P.
        if rows[i]['source_path'] == 'docs/star_schema.md':
            score += sum(20 if asks_definition else 10 for t in set(terms) if t in metric_codes
                         and rows[i]['text'].lower().startswith(f'| {t} |'))
        score += sum(8 for t in set(terms) if re.fullmatch(r'ps[1-5]', t)
                     and rows[i]['text'].lower().startswith(f'| {t}:'))
        if contract_exact:
            score += 12
        scores.append((score, i))
    chosen = sorted(scores, key=lambda x: (-x[0], x[1]))[:k]
    return [{'source_path': rows[i]['source_path'], 'section': rows[i]['section'],
             'citation': _citation(rows[i]), 'status': rows[i]['status'],
             'snippet': _snippet(rows[i], terms), 'corpus_version': snapshot['corpus_version']}
            for _, i in chosen]
