"""Отбор кандидатов без языковой модели: условия из запроса правилами + TF-IDF по описаниям."""

import math
import re
from collections import Counter

WORD = re.compile(r"[a-zа-яёәғқңөұүһі0-9]+")
STOP = {"фильм", "фильмы", "кино", "что", "нибудь", "посмотреть", "про", "для", "с", "на",
        "и", "или", "в", "по", "о", "об", "как", "но", "не", "без", "кроме", "только",
        "это", "мне", "хочу", "какой", "какое", "года", "год", "мин", "минут", "часа",
        "часов", "до", "после", "от", "фильмі", "туралы"}

GENRE_CUES = {
    "комедия": ("комеди", "смешн", "весел", "весёл", "күлкі", "юмор"),
    "мультфильм": ("мульт", "анимац", "аниме"),
    "ужасы": ("ужас", "страшн", "хоррор", "қорқынышт"),
    "фантастика": ("фантаст", "будущ", "робот", "инопланет"),
    "документальный": ("документ",),
    "военный": ("военн", "войн", "соғыс"),
    "семейный": ("семейн", "отбасы", "детск", "детей", "ребён", "балалар", "мамой"),
    "мелодрама": ("мелодрам", "романтич", "любов", "махаббат"),
    "боевик": ("боевик", "экшн"),
    "триллер": ("триллер", "напряж"),
    "криминал": ("криминал", "гангстер", "мафи", "бандит"),
    "исторический": ("историч", "тарих"),
    "мюзикл": ("мюзикл", "песн", "танц"),
    "фэнтези": ("фэнтези", "сказк", "волшеб", "магия"),
    "вестерн": ("вестерн", "ковбо"),
    "приключения": ("приключ",),
    "драма": ("драм",),
}
LANGUAGE_CUES = {
    "казахский": ("казахск", "қазақ"), "русский": ("русск",), "английский": ("английск",),
    "киргизский": ("киргиз", "кыргыз"), "корейский": ("корейск",), "японский": ("японск",),
    "немецкий": ("немецк",), "французский": ("французск",), "итальянский": ("итальянск",),
    "хинди": ("индийск", "хинди"), "испанский": ("испанск",),
}
COUNTRY_CUES = {
    "СССР": ("советск",), "Казахстан": ("казахстанск",), "США": ("американск",),
    "Россия": ("российск",), "Франция": ("французск",), "Япония": ("японск",),
}
NEGATION = ("не", "без", "кроме", "емес", "жоқ")
NUMBERS = {None: 1, "одного": 1, "полутора": 1.5, "двух": 2, "трех": 3}


def words(text: str) -> list[str]:
    return WORD.findall(text.lower().replace("ё", "е"))


def stem(word: str) -> str:
    return word[:6] if len(word) > 6 else word


def terms(text: str) -> list[str]:
    return [stem(w) for w in words(text) if w not in STOP and len(w) > 1]


def cues(query: str) -> dict:
    """Условия запроса без модели: минуты, годы, языки, жанры нужные и исключённые."""
    q = query.lower().replace("ё", "е")
    tokens = words(q)
    found = {"max_minutes": None, "min_minutes": None, "year_from": None, "year_to": None,
             "languages": [], "genres": [], "exclude_genres": [],
             "countries": [], "exclude_countries": []}

    if m := re.search(r"до (\d+) мин", q):
        found["max_minutes"] = int(m.group(1))
    elif m := re.search(r"(?:до|не дольше|не больше) (?:(одного|полутора|двух|трех) )?час", q):
        found["max_minutes"] = int(NUMBERS[m.group(1)] * 60)
    elif m := re.search(r"не дольше (\d+)", q):
        found["max_minutes"] = int(m.group(1))
    if m := re.search(r"(?:больше|дольше|длиннее) (?:(одного|полутора|двух|трех) )?час", q):
        found["min_minutes"] = int(NUMBERS[m.group(1)] * 60)
    if "коротк" in q and not found["max_minutes"]:
        found["max_minutes"] = 100

    if m := re.search(r"(1[89]\d0|20[0-2]0)-х", q):
        found["year_from"], found["year_to"] = int(m.group(1)), int(m.group(1)) + 9
    if m := re.search(r"(?:до|раньше) (1[89]\d\d|20\d\d)", q):
        found["year_to"] = int(m.group(1)) - 1
    if m := re.search(r"(?:после|позже) (1[89]\d\d|20\d\d)", q):
        found["year_from"] = int(m.group(1)) + 1
    exact = re.search(r"\b(1[89]\d\d|20\d\d) года\b", q)
    if exact and found["year_from"] is None and found["year_to"] is None:
        found["year_from"] = found["year_to"] = int(exact.group(1))
    if re.search(r"(^|\s)стар(ый|ое|ые|ая|ого|ых|енький|енькое)(\s|$|,)", q) and found["year_to"] is None:
        found["year_to"] = 1985
    if re.search(r"(^|\s)(новинк\w*|нов(ый|ое|ые|ая)|свеж\w*)(\s|$|,)", q) and found["year_from"] is None:
        found["year_from"] = 2015

    for language, stems in LANGUAGE_CUES.items():
        if any(s in q for s in stems):
            found["languages"].append(language)

    for i, token in enumerate(tokens):
        for genre, stems in GENRE_CUES.items():
            if token.startswith(stems):
                negated = any(t in NEGATION for t in tokens[max(0, i - 3):i])
                key = "exclude_genres" if negated else "genres"
                if genre not in found[key]:
                    found[key].append(genre)
        for country, stems in COUNTRY_CUES.items():
            if token.startswith(stems):
                negated = any(t in NEGATION for t in tokens[max(0, i - 3):i])
                found["exclude_countries" if negated else "countries"].append(country)
    if "казахский" in found["languages"] and "Казахстан" in found["countries"]:
        found["languages"].remove("казахский")
    return found


def named_film(query: str, films: list[dict]):
    """Фильм каталога, на который запрос просит похожий («как Интерстеллар»), или None."""
    if not re.search(r"(^|\s)(как|похож\w*|вроде|типа)\s", query.lower()):
        return None
    q = " ".join(stem(w) for w in words(query))
    best = None
    for film in films:
        title = " ".join(stem(w) for w in words(film["title"]))
        if len(title) >= 5 and title in q and (best is None or len(film["title"]) > len(best["title"])):
            best = film
    return best


def fits(film: dict, c: dict) -> bool:
    if c["max_minutes"] and film["minutes"] > c["max_minutes"]:
        return False
    if c["min_minutes"] and film["minutes"] < c["min_minutes"]:
        return False
    if c["year_from"] and film["year"] < c["year_from"]:
        return False
    if c["year_to"] and film["year"] > c["year_to"]:
        return False
    if c["languages"] and not set(c["languages"]) & set(film["languages"]):
        return False
    if c["countries"] and not set(c["countries"]) & set(film["countries"]):
        return False
    if set(c["exclude_countries"]) & set(film["countries"]):
        return False
    return not set(c["exclude_genres"]) & set(film["genres"])


class Index:
    """TF-IDF по названию, описанию и полям фильма."""

    def __init__(self, films: list[dict]):
        self.films = films
        docs = [terms(" ".join([f["title"], f["description"], *f["genres"],
                                *f["countries"], *f["languages"]])) for f in films]
        df = Counter(t for doc in docs for t in set(doc))
        n = len(docs)
        self.idf = {t: math.log((1 + n) / (1 + d)) + 1 for t, d in df.items()}
        self.vectors = [self._vector(doc) for doc in docs]

    def _vector(self, doc: list[str]) -> dict[str, float]:
        tf = Counter(doc)
        vec = {t: c * self.idf.get(t, 0) for t, c in tf.items()}
        norm = math.sqrt(sum(v * v for v in vec.values())) or 1
        return {t: v / norm for t, v in vec.items()}

    def similarity(self, query: str) -> list[float]:
        q = self._vector(terms(query))
        return [sum(w * vec.get(t, 0) for t, w in q.items()) for vec in self.vectors]


_cache: dict[int, Index] = {}


def index_for(films: list[dict]) -> Index:
    key = id(films)
    if key not in _cache or _cache[key].films is not films:
        _cache.clear()
        _cache[key] = Index(films)
    return _cache[key]


def candidates(query: str, films: list[dict], k: int = 30) -> list:
    """До k id фильмов-кандидатов под запрос. Языковая модель не вызывается."""
    c = cues(query)
    sims = index_for(films).similarity(query)
    like = named_film(query, films)
    total = len(films)
    scored = []
    for rank, (film, sim) in enumerate(zip(films, sims)):
        if like is not None and film is like:
            continue
        score = sim
        score += 0.6 * len(set(c["genres"]) & set(film["genres"]))
        if like is not None:
            score += 0.3 * len(set(like["genres"]) & set(film["genres"]))
        score += 0.05 * (1 - rank / total)
        scored.append((score, rank, film))
    allowed = [s for s in scored if fits(s[2], c)]
    pool = allowed if allowed else scored
    pool.sort(key=lambda s: (-s[0], s[1]))
    return [film["id"] for _, _, film in pool[:k]]
