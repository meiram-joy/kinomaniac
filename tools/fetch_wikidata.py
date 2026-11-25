import sys 
import httpx

API = "https://www.wikidata.org/w/api.php"
HEADERS = {"User-Agent": "kinomaniac-study/0.1"}

SPARQL_URL = "https://query.wikidata.org/sparql"

KZ_FILMS = """
SELECT ?film ?title (MIN(YEAR(?date)) AS ?year) (MAX(?dur) AS ?minutes) ?sitelinks WHERE {
  ?film wdt:P31 wd:Q11424; wdt:P495 wd:Q232; wdt:P577 ?date; wdt:P2047 ?dur;
        rdfs:label ?title; wikibase:sitelinks ?sitelinks.
  FILTER(LANG(?title) = "ru")
  ?art schema:about ?film; schema:isPartOf <https://ru.wikipedia.org/>.
} GROUP BY ?film ?title ?sitelinks ORDER BY DESC(?sitelinks) LIMIT 15
"""

def sparql(query: str) -> list[dict]:
                params = {"query": query,"format": "json"}
                respounce = httpx.get(SPARQL_URL,params = params,headers=HEADERS,timeout=60)
                respounce.raise_for_status()
                data = respounce.json()
                items = data["results"]["bindings"]
                return [{ "qid": i["film"]["value"].rsplit("/",1), "title": i["title"]["value"], "year" : int(i.["year"]["value"]), "minutes": int(i.["minutes"]["value"])} for i in items]


def main() -> None:
        mode = sys.argv[1]
        if mode == "kz":
          films = sparql(KZ_FILMS)
          for film in films:
            print(f" {film['qid']} | {film['title']} | {film['year']} | {film['minutes']}")
  
if __name__ == "__main__":
  sys.stdout.reconfigure(encoding="utf-8")
  main()