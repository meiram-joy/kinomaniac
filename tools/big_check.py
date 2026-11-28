"""Замеры уровня Epic на films_big.json.

    uv run tools/big_check.py size                   # сколько токенов весь каталог (без модели)
    uv run tools/big_check.py recall                 # отбор: попал ли must в 30 кандидатов
    uv run tools/big_check.py path --limit 10        # весь путь: кандидаты против всего каталога
"""

import argparse
import contextlib
import io
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from check import journal_length, new_rows, passed               # noqa: E402
from kino import MODEL, make_client, pick, pick_big               # noqa: E402
from kinomaniac import journal                                    # noqa: E402
from kinomaniac.prompt import build_messages                      # noqa: E402
from kinomaniac.search import candidates                          # noqa: E402

BIG = ROOT / "films_big.json"
SMALL = ROOT / "films.json"
QUERIES = ROOT / "queries.json"
RESULTS = ROOT / "tools" / "big_results.json"

# Замер на малом каталоге: промпт из films.json (16 318 символов JSON) занял 6 257 токенов
# у qwen3.5:4b (calls.jsonl, 2026-11-28). Отсюда символов на токен для такого промпта.
SMALL_PROMPT_TOKENS = 6257


def load(path=BIG):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def prompt_chars(films) -> int:
    return sum(len(m["content"]) for m in build_messages("тестовый запрос", films))


def size() -> dict:
    small, big = load(SMALL), load(BIG)
    per_token = prompt_chars(small) / SMALL_PROMPT_TOKENS
    estimate = round(prompt_chars(big) / per_token)
    print(f"Промпт с films.json: {prompt_chars(small)} символов = {SMALL_PROMPT_TOKENS} токенов "
          f"({per_token:.2f} символа на токен)")
    print(f"Промпт с films_big.json ({len(big)} фильмов): {prompt_chars(big)} символов "
          f"≈ {estimate} токенов")
    return {"films": len(big), "prompt_chars": prompt_chars(big),
            "chars_per_token": round(per_token, 2), "tokens_estimate": estimate}


def recall() -> dict:
    films = load()
    with_must = [x for x in load(QUERIES) if (x.get("expect") or {}).get("must")]
    if not with_must:
        print("В queries.json нет запросов с must")
        return {}
    hits, started = [], time.time()
    for item in with_must:
        found = {str(i) for i in candidates(item["query"], films, 30)}
        hit = bool(found & {str(i) for i in item["expect"]["must"]})
        hits.append(hit)
        print(f"{'✅' if hit else '❌'} {item['query']}")
    ms = (time.time() - started) / len(with_must) * 1000
    print(f"\nФильм из must попал в 30 кандидатов: {sum(hits)} из {len(hits)} "
          f"({sum(hits) / len(hits):.0%}); {ms:.0f} мс на запрос, без модели")
    return {"recall": round(sum(hits) / len(hits), 3), "hits": sum(hits),
            "queries": len(hits), "ms_per_query": round(ms)}


def only_candidates(client, model, query, films):
    """Кандидаты без шага фильтров: чистый вклад отбора."""
    ids = {str(i) for i in candidates(query, films, k=30)}
    return pick(client, model, query, [f for f in films if str(f["id"]) in ids],
                use_filters=False)


def whole_catalog(client, model, query, films):
    return pick(client, model, query, films, use_filters=False)


def run(fn, client, model, items, films) -> dict:
    results, tokens_in, tokens_out, seconds = [], 0, 0, 0.0
    for item in items:
        before = journal_length()
        started = time.time()
        with contextlib.redirect_stdout(io.StringIO()):
            outcome, ids = fn(client, model, item["query"], films)
        seconds += time.time() - started
        for row in new_rows(before):
            usage = row.get("usage") or {}
            tokens_in += usage.get("prompt_tokens", 0)
            tokens_out += usage.get("completion_tokens", 0)
        ok = passed(item["expect"], outcome, ids)
        results.append(ok)
        print(f"  {'✅' if ok else '❌'} {outcome:13} {item['query']}")
    n = len(items)
    return {"pass_rate": round(sum(results) / n, 3), "passed": sum(results), "queries": n,
            "tokens_in": round(tokens_in / n), "tokens_out": round(tokens_out / n),
            "seconds": round(seconds / n, 1),
            f"usd_{journal.REFERENCE}": round(journal.usd(journal.REFERENCE, tokens_in / n,
                                                         tokens_out / n), 6)}


def path(limit: int, model: str, base_url: str | None) -> dict:
    films = load()
    items = [x for x in load(QUERIES) if x.get("expect")][:limit]
    client = make_client(base_url, timeout=1800)
    variants = {"candidates": only_candidates, "candidates_filters": pick_big,
                "whole_catalog": whole_catalog}
    result = {"model": model}
    for name, fn in variants.items():
        print(f"{name}, {model}:")
        result[name] = run(fn, client, model, items, films)
    for name in variants:
        r = result[name]
        print(f"{name:19} пройдено {r['passed']}/{r['queries']}, вход {r['tokens_in']} ток., "
              f"{r['seconds']} с, ${r[f'usd_{journal.REFERENCE}']} по цене {journal.REFERENCE}")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["size", "recall", "path"])
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--base-url", default=None)
    args = parser.parse_args()
    saved = json.loads(RESULTS.read_text(encoding="utf-8")) if RESULTS.exists() else {}
    if args.mode == "size":
        saved["size"] = size()
    elif args.mode == "recall":
        saved["recall"] = recall()
    else:
        saved["path"] = path(args.limit, args.model, args.base_url)
    RESULTS.write_text(json.dumps(saved, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
