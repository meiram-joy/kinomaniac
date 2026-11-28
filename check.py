"""Прогон набора запросов queries.json через pick: исходы, чужие id, ожидания.

    uv run check.py                       # qwen3.5:4b в Ollama, каждый запрос 1 раз
    uv run check.py --runs 3              # каждый запрос 3 раза
    uv run check.py --model gpt-6-luna --base-url https://api.openai.com/v1
"""

import argparse
import contextlib
import io
import json
import sys
import time
from collections import Counter
from pathlib import Path

from kino import CATALOG, MODEL, OLLAMA, pick
from kinomaniac import journal
from kinomaniac.catalog import load_catalog

QUERIES = Path("queries.json")


def passed(expect: dict, outcome: str, ids: list) -> bool:
    """Пройден ли запрос с ожиданием."""
    shown = {str(i) for i in ids}
    if expect.get("no_match"):
        return outcome == "no_match"
    if outcome != "ok":
        return False
    must = {str(i) for i in expect.get("must", [])}
    forbid = {str(i) for i in expect.get("forbid", [])}
    return (not must or bool(must & shown)) and not (forbid & shown)


def journal_length() -> int:
    path = Path(journal.JOURNAL)
    return len(path.read_text(encoding="utf-8").splitlines()) if path.exists() else 0


def new_rows(before: int) -> list[dict]:
    lines = Path(journal.JOURNAL).read_text(encoding="utf-8").splitlines()[before:]
    return [json.loads(line) for line in lines if line.strip()]


def main() -> None:
    from openai import OpenAI

    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--base-url", default=OLLAMA)
    parser.add_argument("--api-key", default="ollama")
    parser.add_argument("--runs", type=int, default=1)
    args = parser.parse_args()

    films = load_catalog(CATALOG)
    titles = {str(f["id"]): f["title"] for f in films}
    items = json.loads(QUERIES.read_text(encoding="utf-8"))
    client = OpenAI(base_url=args.base_url, api_key=args.api_key,
                    max_retries=0, timeout=300)

    print(f"Модель: {args.model}, запросов {len(items)} × {args.runs}")
    outcomes, aliens, results = Counter(), 0, []
    started = time.time()
    for run in range(args.runs):
        for n, item in enumerate(items, 1):
            before = journal_length()
            with contextlib.redirect_stdout(io.StringIO()):
                outcome, ids = pick(client, args.model, item["query"], films)
            aliens += sum(len(r.get("rejected", [])) for r in new_rows(before))
            outcomes[outcome] += 1
            expect = item.get("expect")
            ok = passed(expect, outcome, ids) if expect else None
            results.append(ok)
            mark = {True: "✅", False: "❌", None: "  "}[ok]
            shown = "; ".join(titles.get(str(i), str(i)) for i in ids) or "—"
            print(f"{mark} [{run + 1}.{n:02d}] {outcome:13} {item['query'][:48]:48} → {shown[:70]}")

    checked = [r for r in results if r is not None]
    print()
    print(f"Исходы: {dict(outcomes)}")
    print(f"Чужих id поймано: {aliens}")
    print(f"Пройдено: {sum(checked)} из {len(checked)} запросов с ожиданием"
          + (f" ({sum(checked) / len(checked):.0%})" if checked else ""))
    print(f"Время: {time.time() - started:.0f} с. Все вызовы в calls.jsonl: uv run show.py")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
