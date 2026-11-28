"""Черновик каталога из Wikidata и Википедии.

    uv run tools/fetch_wikidata.py build      # черновик tools/films_draft.json
    uv run tools/fetch_wikidata.py finalize   # черновик + tools/descriptions.json -> films.json
"""

import json
import sys
import time
from pathlib import Path
from urllib.parse import unquote

import httpx

HEADERS = {"User-Agent": "kinomaniac-study/0.1"}
SPARQL_URL = "https://query.wikidata.org/sparql"
SUMMARY_URL = "https://ru.wikipedia.org/api/rest_v1/page/summary/"
DRAFT = Path(__file__).parent / "films_draft.json"
DESCRIPTIONS = Path(__file__).parent / "descriptions.json"
CATALOG = Path(__file__).parent.parent / "films.json"
FIELDS = ["id", "title", "year", "minutes", "genres", "countries", "languages"]

PAUSE = 2
MIN_MINUTES = 60


TEMPLATE = """
SELECT ?film ?title ?article (MIN(YEAR(?date)) AS ?year) (MAX(?dur) AS ?minutes) ?sitelinks
       (GROUP_CONCAT(DISTINCT ?genreLabel; separator="|") AS ?genres)
       (GROUP_CONCAT(DISTINCT ?countryLabel; separator="|") AS ?countries)
       (GROUP_CONCAT(DISTINCT ?langLabel; separator="|") AS ?languages)
WHERE {
  FILTER_HERE
  ?film wikibase:sitelinks ?sitelinks.
  FILTER(?sitelinks >= MIN_HERE)
  ?film wdt:P577 ?date; wdt:P2047 ?dur; rdfs:label ?title.
  FILTER(LANG(?title) = "ru")
  ?article schema:about ?film; schema:isPartOf <https://ru.wikipedia.org/>.
  OPTIONAL { ?film wdt:P136 ?g. ?g rdfs:label ?genreLabel. FILTER(LANG(?genreLabel) = "ru") }
  OPTIONAL { ?film wdt:P495 ?c. ?c rdfs:label ?countryLabel. FILTER(LANG(?countryLabel) = "ru") }
  OPTIONAL { ?film wdt:P364 ?l. ?l rdfs:label ?langLabel. FILTER(LANG(?langLabel) = "ru") }
}
GROUP BY ?film ?title ?article ?sitelinks ORDER BY DESC(?sitelinks) LIMIT LIMIT_HERE
"""


CATEGORIES = [
    ("казахстанские", "?film wdt:P31 wd:Q11424; wdt:P495 wd:Q232.", 3, 12),
    ("советские", "?film wdt:P31 wd:Q11424; wdt:P495 wd:Q15180.", 40, 7),
    ("фантастика", "?film wdt:P31 wd:Q11424; wdt:P136 wd:Q471839.", 60, 6),
    ("комедия", "?film wdt:P31 wd:Q11424; wdt:P136 wd:Q157443.", 80, 6),
    ("ужасы", "?film wdt:P31 wd:Q11424; wdt:P136 wd:Q200092.", 60, 5),
    ("семейный", "?film wdt:P31 wd:Q11424; wdt:P136 wd:Q1361932.", 50, 5),
    ("мультфильм", "?film wdt:P31 wd:Q202866.", 60, 6),
    ("документальный", "?film wdt:P31 wd:Q11424; wdt:P136 wd:Q93204.", 30, 5),
]


GENRES = {
    "драматический фильм": "драма",
    "историческая драма": "драма",
    "комедийная драма": "комедия",
    "комедийный фильм": "комедия",
    "трагикомедия": "комедия",
    "эксцентрическая комедия": "комедия",
    "кинопародия": "комедия",
    "научно-фантастический фильм": "фантастика",
    "боевая фантастика": "фантастика",
    "киберпанк": "фантастика",
    "фильм о путешествиях во времени": "фантастика",
    "фильм ужасов": "ужасы",
    "научно-фантастический фильм ужасов": "ужасы",
    "фильм-триллер": "триллер",
    "экшен-триллер": "триллер",
    "технотриллер": "триллер",
    "психологический триллер": "триллер",
    "боевик": "боевик",
    "приключенческий фильм": "приключения",
    "романтический фильм": "мелодрама",
    "мелодрама": "мелодрама",
    "семейный фильм": "семейный",
    "детский фильм": "семейный",
    "документальный фильм": "документальный",
    "исторический фильм": "исторический",
    "военный фильм": "военный",
    "биографический фильм": "биография",
    "криминальный фильм": "криминал",
    "фэнтезийный фильм": "фэнтези",
    "фильм-сказка": "фэнтези",
    "музыкальный фильм": "мюзикл",
    "вестерн": "вестерн",
}
MAX_GENRES = 4


GENRE_ORDER = ["мультфильм", "документальный", "фантастика", "ужасы", "комедия",
               "мелодрама", "семейный", "вестерн", "военный", "фэнтези", "боевик",
               "триллер", "криминал", "приключения", "биография", "исторический",
               "мюзикл", "драма"]


EXCLUDE = {
    "Q156497": "«Триумф воли» — нацистская пропаганда, не для советов на вечер",
    "Q11252497": "«Плохой кот Шерафеттин» — мультфильм для взрослых, а Wikidata "
                 "пометила его детским: попал бы в запросы «с детьми»",
}
GENRE_OVERRIDES = {
    "Q206388": ["криминал", "драма"],
    "Q182692": ["военный", "драма"],
    "Q103569": ["фантастика", "ужасы"],
    "Q162255": ["фантастика", "боевик"],
    "Q736731": ["мультфильм", "комедия", "семейный", "мюзикл"],
}


def build_query(filter_: str, min_links: int, limit: int) -> str:
    """Подставить значения категории в шаблон."""
    return (TEMPLATE.replace("FILTER_HERE", filter_)
            .replace("MIN_HERE", str(min_links))
            .replace("LIMIT_HERE", str(limit)))


def split(value: str) -> list[str]:
    """'a|b' -> ['a', 'b'];  '' -> [].  Просто "".split("|") дал бы ['']."""
    return [x for x in value.split("|") if x]


def sparql(query: str) -> list[dict]:
    """Строки ответа Wikidata в виде простых словарей."""
    response = httpx.get(SPARQL_URL, params={"query": query, "format": "json"},
                         headers=HEADERS, timeout=90)
    response.raise_for_status()
    rows = response.json()["results"]["bindings"]
    return [
        {
            "qid": row["film"]["value"].rsplit("/", 1)[1],
            "title": row["title"]["value"],
            "year": int(row["year"]["value"]),
            "minutes": round(float(row["minutes"]["value"])),
            "sitelinks": int(row["sitelinks"]["value"]),
            "article": row["article"]["value"],

            "wikidata_genres": split(row.get("genres", {}).get("value", "")),
            "countries": split(row.get("countries", {}).get("value", "")),
            "wikidata_languages": split(row.get("languages", {}).get("value", "")),
        }
        for row in rows
    ]


def catalog_genres(raw: list[str], category: str) -> list[str]:
    """Жанры Wikidata -> до MAX_GENRES слов словаря каталога, без повторов."""
    words = {GENRES[g] for g in raw if g in GENRES}
    if category == "мультфильм":
        words.add("мультфильм")
    return sorted(words, key=GENRE_ORDER.index)[:MAX_GENRES]


LANGUAGES = {
    "американский вариант английского языка": "английский",
    "австралийский английский": "английский",
    "бразильский вариант португальского языка": "португальский",
    "севернокитайский": "китайский", "путунхуа": "китайский",
    "кантонский диалект": "кантонский", "юэ": "кантонский",
    "новогреческий": "греческий", "арамейские языки": "арамейский",
    "майяские языки": "майя", "Арикара": "арикара",
}
COUNTRIES = {
    "Республика Корея": "Южная Корея", "Британский Гонконг": "Гонконг",
    "Германский рейх": "Германия", "Веймарская республика": "Германия",
    "Королевство Италия": "Италия", "Китайская Республика": "Китай",
}


def unique(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))


def catalog_languages(raw: list[str]) -> list[str]:
    """Языки Wikidata -> слова каталога: 'русский язык' -> 'русский', 'путунхуа' -> 'китайский'."""
    names = [x.removesuffix(" язык") for x in raw]
    return unique([LANGUAGES.get(x, x) for x in names])


def catalog_countries(raw: list[str]) -> list[str]:
    """Страны Wikidata -> слова каталога: 'Республика Корея' -> 'Южная Корея'."""
    return unique([COUNTRIES.get(x, x) for x in raw])


def wiki_extract(article_url: str) -> str:
    """Вводный абзац статьи русской Википедии (материал для описания)."""
    title = unquote(article_url.rsplit("/", 1)[1])
    for attempt in range(1, 5):
        response = httpx.get(SUMMARY_URL + title, headers=HEADERS, timeout=30,
                             follow_redirects=True)
        if response.status_code == 200:
            return response.json().get("extract", "")
        if response.status_code not in (429, 500, 502, 503, 504):
            break
        time.sleep(5 * attempt)
    print(f"  нет абзаца Википедии для {title}: {response.status_code}")
    return ""


def build() -> None:
    films: dict[str, dict] = {}
    for name, filter_, min_links, limit in CATEGORIES:
        rows = sparql(build_query(filter_, min_links, limit))
        added = 0
        for row in rows:
            if (row["minutes"] < MIN_MINUTES or row["qid"] in films
                    or row["qid"] in EXCLUDE):
                continue
            row["category"] = name
            films[row["qid"]] = row
            added += 1
        print(f"{name}: найдено {len(rows)}, добавлено {added}")
        time.sleep(PAUSE)

    draft = []
    for n, row in enumerate(films.values(), 1):
        draft.append({
            "id": f"f-{n:03d}",
            "title": row["title"],
            "year": row["year"],
            "minutes": row["minutes"],
            "genres": GENRE_OVERRIDES.get(
                row["qid"], catalog_genres(row["wikidata_genres"], row["category"])),
            "countries": catalog_countries(row["countries"]),
            "languages": catalog_languages(row["wikidata_languages"]),
            "description": "",

            "qid": row["qid"],
            "category": row["category"],
            "wikidata_genres": row["wikidata_genres"],
            "extract": wiki_extract(row["article"]),
        })
        time.sleep(1)

    DRAFT.write_text(json.dumps(draft, ensure_ascii=False, indent=2), encoding="utf-8")
    kz = sum("Казахстан" in f["countries"] for f in draft)
    print(f"\nЧерновик: {DRAFT} — {len(draft)} фильмов, казахстанских {kz}")
    unknown = sorted({g for f in films.values() for g in f["wikidata_genres"]} - set(GENRES))
    print("Жанры Wikidata без перевода (отброшены):", ", ".join(unknown))


def finalize() -> None:
    """Черновик + описания -> films.json только с полями каталога."""
    draft = json.loads(DRAFT.read_text(encoding="utf-8"))
    descriptions = json.loads(DESCRIPTIONS.read_text(encoding="utf-8"))
    missing = [f["title"] for f in draft if f["qid"] not in descriptions]
    if missing:
        print("Нет описания у:", ", ".join(missing))
        return
    films = [{key: f[key] for key in FIELDS} | {"description": descriptions[f["qid"]]}
             for f in draft]
    for film in films:
        film["languages"] = catalog_languages(film["languages"])
        film["countries"] = catalog_countries(film["countries"])
    CATALOG.write_text(json.dumps(films, ensure_ascii=False, indent=2) + "\n",
                       encoding="utf-8")
    print(f"{CATALOG}: {len(films)} фильмов")


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode == "build":
        build()
    elif mode == "finalize":
        finalize()
    else:
        print("Запуск: uv run tools/fetch_wikidata.py build | finalize")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
