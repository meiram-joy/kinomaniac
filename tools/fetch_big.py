"""Большой каталог films_big.json (1000+ фильмов) из Wikidata и русской Википедии.

    uv run tools/fetch_big.py              # собрать из Wikidata и Википедии
    uv run tools/fetch_big.py normalize    # заново привести языки и страны к словам каталога
"""

import json
import sys
import time
from pathlib import Path
from urllib.parse import unquote

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_wikidata import (EXCLUDE, HEADERS, catalog_countries, catalog_genres,  # noqa: E402
                            catalog_languages, sparql)

ROOT = Path(__file__).resolve().parent.parent
BIG = ROOT / "films_big.json"
WIKI_API = "https://ru.wikipedia.org/w/api.php"
MAX_DESCRIPTION = 350

TEMPLATE = """
SELECT ?film ?title ?article (MIN(YEAR(?date)) AS ?year) (MAX(?dur) AS ?minutes) ?sitelinks
       (GROUP_CONCAT(DISTINCT ?genreLabel; separator="|") AS ?genres)
       (GROUP_CONCAT(DISTINCT ?countryLabel; separator="|") AS ?countries)
       (GROUP_CONCAT(DISTINCT ?langLabel; separator="|") AS ?languages)
WHERE {
  ?film wdt:P31 wd:Q11424; wikibase:sitelinks ?sitelinks.
  FILTER(?sitelinks >= MIN_HERE)
  ?film wdt:P577 ?date; wdt:P2047 ?dur; rdfs:label ?title.
  FILTER(LANG(?title) = "ru")
  FILTER(YEAR(?date) >= FROM_HERE && YEAR(?date) < TO_HERE)
  ?article schema:about ?film; schema:isPartOf <https://ru.wikipedia.org/>.
  OPTIONAL { ?film wdt:P136 ?g. ?g rdfs:label ?genreLabel. FILTER(LANG(?genreLabel) = "ru") }
  OPTIONAL { ?film wdt:P495 ?c. ?c rdfs:label ?countryLabel. FILTER(LANG(?countryLabel) = "ru") }
  OPTIONAL { ?film wdt:P364 ?l. ?l rdfs:label ?langLabel. FILTER(LANG(?langLabel) = "ru") }
}
GROUP BY ?film ?title ?article ?sitelinks ORDER BY DESC(?sitelinks) LIMIT LIMIT_HERE
"""

# (с, по, минимум sitelinks, сколько взять)
DECADES = [
    (1920, 1940, 15, 70), (1940, 1960, 20, 120), (1960, 1970, 20, 110),
    (1970, 1980, 20, 120), (1980, 1990, 25, 140), (1990, 2000, 25, 150),
    (2000, 2010, 25, 160), (2010, 2020, 25, 160), (2020, 2026, 15, 80),
]
KAZAKH = (1960, 2026, 1, 60)


def query(start, end, min_links, limit, extra=""):
    q = (TEMPLATE.replace("MIN_HERE", str(min_links)).replace("FROM_HERE", str(start))
         .replace("TO_HERE", str(end)).replace("LIMIT_HERE", str(limit)))
    return q.replace("?film wdt:P31 wd:Q11424;", "?film wdt:P31 wd:Q11424; " + extra) if extra else q


def fetch(q):
    for attempt in range(1, 5):
        try:
            return sparql(q)
        except httpx.HTTPError as error:
            print(f"  повтор {attempt}: {error}")
            time.sleep(10 * attempt)
    return []


def extracts(titles: list[str]) -> dict[str, str]:
    """Вводные абзацы статей пачкой (до 20 за запрос)."""
    params = {"action": "query", "prop": "extracts", "exintro": 1, "explaintext": 1,
              "exsentences": 3, "exlimit": 20, "redirects": 1, "format": "json",
              "titles": "|".join(titles)}
    for attempt in range(1, 6):
        response = httpx.get(WIKI_API, params=params, headers=HEADERS, timeout=60)
        if response.status_code == 200:
            break
        time.sleep(5 * attempt)
    else:
        return {}
    data = response.json()["query"]
    back = {}
    for step in data.get("normalized", []) + data.get("redirects", []):
        back[step["to"]] = back.get(step["from"], step["from"])
    result = {}
    for page in data.get("pages", {}).values():
        title = page.get("title", "")
        result[back.get(title, title)] = page.get("extract", "")
    return result


def shorten(text: str) -> str:
    text = " ".join(text.split())
    return text if len(text) <= MAX_DESCRIPTION else text[:MAX_DESCRIPTION].rsplit(" ", 1)[0] + "…"


def build() -> None:
    small = json.loads((ROOT / "films.json").read_text(encoding="utf-8"))
    draft = json.loads((ROOT / "tools" / "films_draft.json").read_text(encoding="utf-8"))
    taken = {f["qid"] for f in draft} | set(EXCLUDE)

    rows = {}
    for start, end, min_links, limit in DECADES:
        found = fetch(query(start, end, min_links, limit))
        rows.update({r["qid"]: r for r in found if r["qid"] not in taken and r["minutes"] >= 60})
        print(f"{start}-{end}: {len(found)}, всего {len(rows)}")
        time.sleep(3)
    found = fetch(query(*KAZAKH, extra="wdt:P495 wd:Q232;"))
    rows.update({r["qid"]: r for r in found if r["qid"] not in taken and r["minutes"] >= 60})
    print(f"казахстанские: {len(found)}, всего {len(rows)}")

    titles = {r["qid"]: unquote(r["article"].rsplit("/", 1)[1]).replace("_", " ")
              for r in rows.values()}
    texts, names = {}, list(titles.values())
    for i in range(0, len(names), 20):
        texts.update(extracts(names[i:i + 20]))
        time.sleep(1)
    print(f"абзацев Википедии: {sum(bool(v) for v in texts.values())} из {len(names)}")

    big = [dict(f) for f in small]
    n = 0
    for qid, r in sorted(rows.items(), key=lambda x: -x[1]["sitelinks"]):
        text = shorten(texts.get(titles[qid], ""))
        if len(text) < 40:
            continue
        n += 1
        big.append({"id": f"b-{n:04d}", "title": r["title"], "year": r["year"],
                    "minutes": r["minutes"], "genres": catalog_genres(r["wikidata_genres"], ""),
                    "countries": catalog_countries(r["countries"]),
                    "languages": catalog_languages(r["wikidata_languages"]),
                    "description": text})
    save(big)


def normalize() -> None:
    """Без сети: фильмы малого каталога заново из films.json, языки и страны — по таблицам."""
    small = {f["id"]: f for f in json.loads((ROOT / "films.json").read_text(encoding="utf-8"))}
    big = json.loads(BIG.read_text(encoding="utf-8"))
    for n, film in enumerate(big):
        film = dict(small.get(film["id"], film))
        film["languages"] = catalog_languages(film["languages"])
        film["countries"] = catalog_countries(film["countries"])
        big[n] = film
    save(big)


def save(big: list[dict]) -> None:
    BIG.write_text(json.dumps(big, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{BIG}: {len(big)} фильмов, казахстанских "
          f"{sum('Казахстан' in f['countries'] for f in big)}")


def main() -> None:
    normalize() if sys.argv[1:] == ["normalize"] else build()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
