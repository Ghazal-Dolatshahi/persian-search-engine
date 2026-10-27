import os
from .indexer import build_index

if __name__ == "__main__":
    data_dir = os.getenv("DATA_DIR", "/data")
    index_path = os.getenv("INDEX_PATH", "/index/index.pkl")
    idx = build_index(data_dir)
    idx.save(index_path)
    for k, v in idx.stats.items():
        print(f"{k:>18}: {v}")
