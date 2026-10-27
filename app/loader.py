import csv
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Iterator
from bs4 import BeautifulSoup

URL_KEYS = ("url", "link", "address", "href", "page_url", "source_url")
HTML_KEYS = ("html", "raw_html", "content", "page_source", "source", "body", "response", "page", "text")
STRIP_BOILERPLATE = os.getenv("STRIP_BOILERPLATE", "1") == "1"
EXTS = {".jsonl", ".ndjson", ".json", ".csv", ".html", ".htm"}

csv.field_size_limit(min(sys.maxsize, 2**31 - 1))


def _read_text(path: Path) -> str:
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "utf-16", "cp1256"):
        try:
            return raw.decode(enc)
        except UnicodeError:
            continue
    return raw.decode("utf-8", "ignore")


def _pick(rec: dict, keys) -> str | None:
    lowered = {str(k).lower(): v for k, v in rec.items()}
    for k in keys:
        v = lowered.get(k)
        if isinstance(v, str) and v.strip():
            return v
    return None


def _from_record(rec) -> tuple[str, str] | None:
    if not isinstance(rec, dict):
        return None
    url, html = _pick(rec, URL_KEYS), _pick(rec, HTML_KEYS)
    return (url, html) if url and html else None


def _sniff_url(html: str, fallback: str) -> str:
    m = re.match(r"\s*<!--\s*(?:url:)?\s*(https?://\S+?)\s*-->", html, re.I)
    if m:
        return m.group(1)
    head = BeautifulSoup(html[:20000], "html.parser")
    link = head.find("link", rel="canonical")
    if link and link.get("href"):
        return link["href"]
    og = head.find("meta", property="og:url")
    if og and og.get("content"):
        return og["content"]
    return fallback


def data_files(data_dir: str) -> list[Path]:
    root = Path(data_dir)
    if not root.exists():
        return []
    return sorted(p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in EXTS)


def data_signature(data_dir: str) -> str:
    h = hashlib.sha1()
    for p in data_files(data_dir):
        st = p.stat()
        h.update(f"{p.name}:{st.st_size}:{int(st.st_mtime)}".encode())
    return h.hexdigest()


def iter_documents(data_dir: str) -> Iterator[tuple[str, str]]:
    for path in data_files(data_dir):
        ext = path.suffix.lower()
        if ext in (".html", ".htm"):
            html = _read_text(path)
            yield _sniff_url(html, path.stem), html
        elif ext in (".jsonl", ".ndjson"):
            for line in _read_text(path).splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    item = _from_record(json.loads(line))
                except json.JSONDecodeError:
                    continue
                if item:
                    yield item
        elif ext == ".json":
            try:
                data = json.loads(_read_text(path))
            except json.JSONDecodeError:
                continue
            if isinstance(data, dict):
                for key in ("pages", "data", "items", "results", "documents"):
                    if isinstance(data.get(key), list):
                        data = data[key]
                        break
            if isinstance(data, dict):  # {url: html}
                for u, h in data.items():
                    if isinstance(h, str) and "<" in h:
                        yield u, h
            else:
                for rec in data:
                    item = _from_record(rec)
                    if item:
                        yield item
        elif ext == ".csv":
            with path.open(newline="", encoding="utf-8-sig", errors="ignore") as f:
                for rec in csv.DictReader(f):
                    item = _from_record(rec)
                    if item:
                        yield item


_DROP = ["script", "style", "noscript", "svg", "template", "iframe", "canvas"]
_BOILER = ["nav", "header", "footer", "aside"]
_WS = re.compile(r"\s+")


def parse_html(html: str) -> tuple[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    if soup.title and soup.title.get_text(strip=True):
        title = soup.title.get_text(" ", strip=True)
    else:
        og = soup.find("meta", property="og:title")
        h1 = soup.find("h1")
        title = og["content"] if og and og.get("content") else (h1.get_text(" ", strip=True) if h1 else "")
    for tag in soup(_DROP):
        tag.decompose()
    if STRIP_BOILERPLATE:
        for tag in soup(_BOILER):
            tag.decompose()
    root = soup.body or soup
    body = _WS.sub(" ", root.get_text(" ", strip=True)).strip()
    return _WS.sub(" ", title).strip(), body
