import os
from contextlib import asynccontextmanager
from urllib.parse import urlparse, unquote
from fastapi import FastAPI, Query, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from .indexer import load_or_build
from .search import SearchEngine

BASE = os.path.dirname(__file__)
DATA_DIR = os.getenv("DATA_DIR", "/data")
INDEX_PATH = os.getenv("INDEX_PATH", "/index/index.pkl")

templates = Jinja2Templates(directory=os.path.join(BASE, "templates"))
_FA = str.maketrans("0123456789.", "۰۱۲۳۴۵۶۷۸۹٫")


def fa(value, digits=None) -> str:
    if isinstance(value, float) and digits is not None:
        value = f"{value:.{digits}f}"
    elif isinstance(value, int):
        value = f"{value:,}".replace(",", "٬")
    return str(value).translate(_FA)


def human_bytes(n: int) -> str:
    for unit in ("بایت", "کیلوبایت", "مگابایت", "گیگابایت"):
        if n < 1024 or unit == "گیگابایت":
            return fa(f"{n:.1f}" if unit != "بایت" else int(n)) + " " + unit
        n /= 1024


def crumbs(url: str) -> str:
    p = urlparse(url)
    parts = [p.netloc] + [unquote(x) for x in p.path.split("/") if x]
    return " › ".join(parts[:4]) if p.netloc else url


templates.env.filters.update(fa=fa, human_bytes=human_bytes, crumbs=crumbs)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.engine = SearchEngine(load_or_build(DATA_DIR, INDEX_PATH))
    yield


app = FastAPI(title="غز غز", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=os.path.join(BASE, "static")), name="static")

EXAMPLES = ["گوشی سامسونگ", "لپ تاپ ایسوس", "هدفون بی سیم", "ساعت هوشمند", "کنسول بازی"]


@app.get("/")
async def home(request: Request):
    eng: SearchEngine = request.app.state.engine
    return templates.TemplateResponse(request, "home.html",
                                      {"stats": eng.index.stats, "examples": EXAMPLES})


@app.get("/search")
async def search(request: Request, q: str = "", page: int = Query(1, ge=1), raw: int = 0):
    eng: SearchEngine = request.app.state.engine
    res = eng.search(q, page, spellcheck=not raw)
    return templates.TemplateResponse(request, "results.html",
                                      {"q": q, "res": res, "stats": eng.index.stats, "raw": raw})


@app.get("/api/suggest")
async def suggest(request: Request, q: str = ""):
    return JSONResponse({"suggestions": request.app.state.engine.suggest(q)})


@app.get("/stats")
async def stats(request: Request):
    return templates.TemplateResponse(request, "stats.html",
                                      {"stats": request.app.state.engine.index.stats})


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}
