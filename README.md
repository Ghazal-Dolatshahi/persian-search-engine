# Search Engine

A Persian search engine built from scratch in Python, featuring HTML parsing, a positional inverted index, ranking, and spell correction.

## Features

- **Positional inverted index** storing URLs, titles, and document bodies. The index is built once and persisted to disk.
- **Persian text normalization:** unifies `ي/ك` with `ی/ک`, converts Persian and Arabic numerals to Latin digits, removes diacritics, tatweel, zero-width non-joiners, and punctuation.
- **AND search:** all query terms must be present in a document.
- **BM25F ranking:** gives higher weight to terms appearing in the title, with additional scores for term proximity and exact phrase matches.
- **Spell correction up to two errors:** supports insertion, deletion, substitution, and transposition, as well as detecting concatenated words (`لپتاپ → لپ تاپ`).
- **Highlighted snippets** extracted from the document text, along with result count and search time.
- **Search-as-you-type suggestions** and the `/` keyboard shortcut for focusing the search box.
- **Indexing statistics** available at `/stats`, including parsing time, index construction time, raw HTML size, and index file size.

## How It Works

```text
data/ ──► loader ──► parse (title + text) ──► normalize/tokenize ──► inverted index ──► index.pkl
                                      │
Browser ──► FastAPI ──► spell correction ──► posting intersection (AND) ──► ranking ──► snippets + highlights
```

### Ranking

For every document containing all query terms:

1. **BM25F:** term frequency in the title is weighted by 3, while term frequency in the body is weighted by 1. Document length is normalized using `k1=1.2` and `b=0.75`.
2. **Body proximity:** the smallest window containing all query terms is found; smaller windows receive a higher score.
3. **Exact phrase matching:** if the query terms appear consecutively and in the same order as the query, the document receives an additional score.
4. **Title matching:** the same proximity and exact phrase scoring is applied to the title with a larger weight. Documents containing all query terms in the title also receive an additional score.

### Spell Correction

For every query term that does not exist in the index:

1. If the term can be split into two existing words, that split is selected (`بیسیم → بی سیم`).
2. Otherwise, the closest indexed word is selected using Damerau–Levenshtein edit distance, allowing up to 2 edits (up to 1 edit for words of 4 characters or fewer). In case of a tie, the more frequent word is preferred.

The corrected query is displayed above the search results, along with a link to search for the original query using `&raw=1`.

## Context

This project was developed as the second assignment for the **Information Retrieval and Search Engines** course. It performs indexing, search, and ranking over the web pages crawled in Assignment 1.