import bisect
import html
import math
import time
from functools import lru_cache
from .indexer import Index
from .text import tokenize

K1, B = 1.2, 0.75
W_TITLE, W_BODY = 3.0, 1.0
PER_PAGE = 10
SNIPPET_WORDS = 34


@lru_cache(maxsize=300_000)
def _word_tokens(word: str) -> tuple:
    return tuple(tokenize(word))


def _damerau(a: str, b: str, limit: int) -> int:
    if abs(len(a) - len(b)) > limit:
        return limit + 1
    prev2, prev = None, list(range(len(b) + 1))
    for i in range(1, len(a) + 1):
        cur = [i] + [0] * len(b)
        for j in range(1, len(b) + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                cur[j] = min(cur[j], prev2[j - 2] + 1)
        if min(cur) > limit:
            return limit + 1
        prev2, prev = prev, cur
    return prev[-1]


def _min_gap(lists):
    events = sorted((p, i) for i, lst in enumerate(lists) for p in lst)
    need, cnt, have, best, left = len(lists), [0] * len(lists), 0, None, 0
    for p, i in events:
        cnt[i] += 1
        if cnt[i] == 1:
            have += 1
        while have == need:
            span = p - events[left][0] + 1
            if best is None or span < best:
                best = span
            j = events[left][1]
            cnt[j] -= 1
            if cnt[j] == 0:
                have -= 1
            left += 1
    return None if best is None else best - need


def _has_phrase(lists) -> bool:
    sets = [set(lst) for lst in lists]
    return any(all((p + k) in sets[k] for k in range(1, len(lists))) for p in lists[0])


class SearchEngine:
    def __init__(self, index: Index):
        self.index = index
        self.docs = index.docs
        self.postings = index.postings
        self.n = len(self.docs)
        self.df = {t: len(p) for t, p in self.postings.items()}
        self.vocab_sorted = sorted(self.postings)
        self.by_len: dict[int, list[str]] = {}
        for t in self.postings:
            self.by_len.setdefault(len(t), []).append(t)
        s = index.stats
        self.avg_len = max(W_TITLE * s.get("avg_title_len", 0) + W_BODY * s.get("avg_body_len", 0), 1.0)

    def correct(self, term: str) -> str | None:
        if term in self.postings or term.isdigit():
            return None
        splits = [(a, term[:i], term[i:]) for i in range(2, len(term) - 1)
                  for a in [0] if term[:i] in self.postings and term[i:] in self.postings]
        if splits:
            _, x, y = max(splits, key=lambda t: self.df[t[1]] * self.df[t[2]])
            return f"{x} {y}"
        limit = 1 if len(term) <= 4 else 2
        best = None  # (distance, -df, term)
        for length in range(len(term) - limit, len(term) + limit + 1):
            for cand in self.by_len.get(length, ()):
                d = _damerau(term, cand, limit)
                if d <= limit:
                    key = (d, -self.df[cand], cand)
                    if best is None or key < best:
                        best = key
        return best[2] if best else None

    def suggest(self, q: str, limit: int = 6) -> list[str]:
        words = q.split()
        if not words:
            return []
        prefix_words = tokenize(words[-1])
        if not prefix_words:
            return []
        pre = prefix_words[-1]
        head = " ".join(words[:-1])
        lo = bisect.bisect_left(self.vocab_sorted, pre)
        found = []
        for t in self.vocab_sorted[lo:lo + 400]:
            if not t.startswith(pre):
                break
            if t != pre or len(found) < limit:
                found.append(t)
        found.sort(key=lambda t: -self.df[t])
        return [(head + " " + t).strip() for t in found[:limit]]

    def search(self, query: str, page: int = 1, spellcheck: bool = True) -> dict:
        t0 = time.perf_counter()
        terms = list(dict.fromkeys(tokenize(query)))
        out = {"query": query, "terms": terms, "corrected": None, "total": 0,
               "results": [], "page": page, "pages": 0, "took_ms": 0.0}
        if not terms or not self.n:
            return out

        if spellcheck:
            fixed, changed = [], False
            for t in terms:
                c = self.correct(t)
                fixed.extend(tokenize(c) if c else [t])
                changed |= c is not None
            if changed:
                terms = list(dict.fromkeys(fixed))
                out["corrected"] = " ".join(terms)
                out["terms"] = terms

        if any(t not in self.postings for t in terms):
            out["took_ms"] = (time.perf_counter() - t0) * 1000
            return out

        by_df = sorted(terms, key=lambda t: self.df[t])
        cands = set(self.postings[by_df[0]])
        for t in by_df[1:]:
            cands &= self.postings[t].keys()
            if not cands:
                break

        idf = {t: math.log(1 + (self.n - self.df[t] + 0.5) / (self.df[t] + 0.5)) for t in terms}
        sum_idf = sum(idf.values())
        multi = len(terms) > 1
        scored = []
        for d in cands:
            doc = self.docs[d]
            dl = W_TITLE * doc["tlen"] + W_BODY * doc["blen"]
            norm = K1 * (1 - B + B * dl / self.avg_len)
            score, tpos, bpos = 0.0, [], []
            for t in terms:
                tp, bp = self.postings[t][d]
                tf = W_TITLE * len(tp) + W_BODY * len(bp)
                score += idf[t] * tf * (K1 + 1) / (tf + norm)
                tpos.append(tp)
                bpos.append(bp)
            if multi:
                if all(bpos):
                    g = _min_gap(bpos)
                    if g is not None:
                        score += 0.8 * sum_idf / (1 + g)
                    if _has_phrase(bpos):
                        score += 0.6 * sum_idf
                if all(tpos):
                    g = _min_gap(tpos)
                    if g is not None:
                        score += 1.5 * sum_idf / (1 + g)
                    if _has_phrase(tpos):
                        score += 1.0 * sum_idf
            if all(tpos):
                score += 0.5 * sum_idf
            scored.append((-score, d))
        scored.sort()

        total = len(scored)
        pages = math.ceil(total / PER_PAGE)
        page = min(max(page, 1), max(pages, 1))
        qset = set(terms)
        results = []
        for neg, d in scored[(page - 1) * PER_PAGE: page * PER_PAGE]:
            doc = self.docs[d]
            results.append({
                "url": doc["url"],
                "title_html": self._highlight(doc["title"].split(), qset),
                "snippet_html": self._snippet(doc["body"], qset),
                "score": -neg,
            })
        out.update(total=total, results=results, page=page, pages=pages,
                   took_ms=(time.perf_counter() - t0) * 1000)
        return out

    @staticmethod
    def _highlight(words: list[str], qset: set, flags=None) -> str:
        flags = flags or [bool(qset.intersection(_word_tokens(w))) for w in words]
        return " ".join(f"<mark>{html.escape(w)}</mark>" if f else html.escape(w)
                        for w, f in zip(words, flags))

    def _snippet(self, body: str, qset: set) -> str:
        words = body.split(" ", 4000)[:4000]
        flags = [bool(qset.intersection(_word_tokens(w))) for w in words]
        hits = [i for i, f in enumerate(flags) if f][:300]
        start = 0
        if hits:
            best = -1
            for h in hits:
                lo, hi = max(0, h - 8), h - 8 + SNIPPET_WORDS
                covered = len({t for i in hits if lo <= i < hi
                               for t in qset.intersection(_word_tokens(words[i]))})
                if covered > best:
                    best, start = covered, lo
        end = min(len(words), start + SNIPPET_WORDS)
        text = self._highlight(words[start:end], qset, flags[start:end])
        return ("… " if start > 0 else "") + text + (" …" if end < len(words) else "")
