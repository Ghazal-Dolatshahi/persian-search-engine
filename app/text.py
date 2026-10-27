import re
import unicodedata

_PERSIAN_DIGITS = "۰۱۲۳۴۵۶۷۸۹"
_ARABIC_DIGITS = "٠١٢٣٤٥٦٧٨٩"

_MAP = {
    "ي": "ی", "ى": "ی", "ك": "ک", "ة": "ه", "ۀ": "ه",
    "أ": "ا", "إ": "ا", "ٱ": "ا",
    "\u200c": " ",   # نیم‌فاصله
    "\u200d": "", "\u200e": "", "\u200f": "", "\u0640": "",  
}
for i, (p, a) in enumerate(zip(_PERSIAN_DIGITS, _ARABIC_DIGITS)):
    _MAP[p] = str(i)
    _MAP[a] = str(i)
_TABLE = str.maketrans(_MAP)

_DIACRITICS = re.compile("[\u064B-\u065F\u0670]")
_NUM_SEP = re.compile(r"(?<=\d)[,٬،](?=\d)")  
_TOKEN = re.compile(r"[^\W_]+")               


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "")
    text = text.translate(_TABLE)
    text = _DIACRITICS.sub("", text)
    text = _NUM_SEP.sub("", text)
    return text.lower()


def tokenize(text: str) -> list[str]:
    return _TOKEN.findall(normalize(text))
