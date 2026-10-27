import os
import pickle
import time
from collections import defaultdict
from datetime import datetime
from .loader import data_signature, iter_documents, parse_html
from .text import tokenize

FORMAT_VERSION = 2

class Index:
    def __init__(self):
        self.docs: list[dict] = []     
        self.postings: dict = {}       
        self.stats: dict = {}
        self.signature = ""
        self.version = FORMAT_VERSION

    def save(self, path: str):
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        for _ in range(2):  
            with open(path, "wb") as f:
                pickle.dump(self, f, protocol=pickle.HIGHEST_PROTOCOL)
            self.stats["index_bytes"] = os.path.getsize(path)

    @staticmethod
    def load(path: str) -> "Index":
        with open(path, "rb") as f:
            idx = pickle.load(f)
        if getattr(idx, "version", 0) != FORMAT_VERSION:
            raise ValueError("نسخه‌ی نمایه قدیمی است")
        return idx


def build_index(data_dir: str, log=print) -> Index:
    idx = Index()
    idx.signature = data_signature(data_dir)
    t_start = time.perf_counter()
    parse_time = 0.0
    raw_bytes = 0
    seen: set[str] = set()
    postings: dict = defaultdict(dict)

    for url, html in iter_documents(data_dir):
        url = url.strip()
        if url in seen:
            continue
        seen.add(url)
        raw_bytes += len(html.encode("utf-8", "ignore"))

        t0 = time.perf_counter()
        title, body = parse_html(html)
        parse_time += time.perf_counter() - t0
        t_toks, b_toks = tokenize(title), tokenize(body)
        if not t_toks and not b_toks:
            continue

        doc_id = len(idx.docs)
        idx.docs.append({"url": url, "title": title or url, "body": body,
                         "tlen": len(t_toks), "blen": len(b_toks)})
        for pos, tok in enumerate(t_toks):
            postings[tok].setdefault(doc_id, ([], []))[0].append(pos)
        for pos, tok in enumerate(b_toks):
            postings[tok].setdefault(doc_id, ([], []))[1].append(pos)
        if len(idx.docs) % 50 == 0:
            log(f"  … {len(idx.docs)} صفحه نمایه شد")

    idx.postings = dict(postings)
    total = time.perf_counter() - t_start
    n = max(len(idx.docs), 1)
    idx.stats = {
        "n_docs": len(idx.docs),
        "n_terms": len(idx.postings),
        "n_postings": sum(len(p) for p in idx.postings.values()),
        "raw_html_bytes": raw_bytes,
        "parse_seconds": parse_time,
        "index_seconds": total - parse_time,
        "total_seconds": total,
        "avg_title_len": sum(d["tlen"] for d in idx.docs) / n,
        "avg_body_len": sum(d["blen"] for d in idx.docs) / n,
        "built_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "index_bytes": 0,
    }
    return idx


def load_or_build(data_dir: str, index_path: str, log=print) -> Index:
    force = os.getenv("REBUILD", "0") == "1"
    if not force and os.path.exists(index_path):
        try:
            idx = Index.load(index_path)
            if idx.signature == data_signature(data_dir):
                log(f"نمایه از فایل بارگذاری شد ({idx.stats['n_docs']} سند)")
                return idx
            log("داده‌ها تغییر کرده‌اند؛ نمایه از نو ساخته می‌شود …")
        except Exception as e:  # noqa: BLE001
            log(f"بارگذاری نمایه ممکن نشد ({e}); ساخت مجدد …")
    log(f"شروع نمایه‌سازی از {data_dir} …")
    idx = build_index(data_dir, log)
    idx.save(index_path)
    s = idx.stats
    log(f"نمایه‌سازی تمام شد: {s['n_docs']} سند، {s['n_terms']} واژه، "
        f"{s['total_seconds']:.2f} ثانیه، {s['index_bytes'] / 1024:.0f} KB")
    return idx
