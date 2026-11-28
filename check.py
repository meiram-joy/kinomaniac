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

from kino import MODEL, load_catalog, make_client, pick
from kinomaniac import journal

QUERIES = Path("queries.json")
CHECKS = Path("checks.jsonl")


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
    return len(journal.read())


def new_rows(before: int) -> list[dict]:
    return journal.read()[before:]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--base-url", default=None, help="по умолчанию KINO_BASE_URL или Ollama")
    parser.add_argument("--api-key", default=None, help="по умолчанию OPENAI_API_KEY")
    parser.add_argument("--runs", type=int, default=1)
    args = parser.parse_args()

    films = load_catalog()
    titles = {str(f["id"]): f["title"] for f in films}
    if not QUERIES.exists():
        print("Нет файла queries.json в корне проекта: создайте его, формат в README.")
        return
    items = json.loads(QUERIES.read_text(encoding="utf-8"))
    client = make_client(args.base_url, args.api_key)

    print(f"Модель: {args.model}, запросов {len(items)} × {args.runs}")
    outcomes, aliens, violations, results, rates = Counter(), 0, 0, [], []
    usd, seconds = 0.0, []
    started = time.time()
    for run in range(args.runs):
        run_results = []
        for n, item in enumerate(items, 1):
            before = journal_length()
            t = time.time()
            with contextlib.redirect_stdout(io.StringIO()):
                outcome, ids = pick(client, args.model, item["query"], films)
            seconds.append(time.time() - t)
            rows = new_rows(before)
            aliens += sum(len(r.get("rejected", [])) for r in rows)
            violations += sum(len(r.get("violations", {})) for r in rows)
            usd += sum(r.get("usd", 0) for r in rows)
            outcomes[outcome] += 1
            expect = item.get("expect")
            ok = passed(expect, outcome, ids) if expect else None
            run_results.append(ok)
            mark = {True: "✅", False: "❌", None: "  "}[ok]
            shown = "; ".join(titles.get(str(i), str(i)) for i in ids) or "—"
            print(f"{mark} [{run + 1}.{n:02d}] {outcome:13} {item['query'][:48]:48} → {shown[:70]}")
        checked = [r for r in run_results if r is not None]
        rates.append(sum(checked) / len(checked) if checked else 0)
        results += run_results

    checked = [r for r in results if r is not None]
    summary = {
        "time": time.strftime("%Y-%m-%d %H:%M:%S"), "model": args.model, "queries": len(items),
        "runs": args.runs, "pass_rate": round(sum(checked) / len(checked), 3) if checked else 0,
        "pass_rate_by_run": [round(r, 3) for r in rates], "aliens": aliens,
        "violations": violations, "outcomes": dict(outcomes),
        "seconds_per_query": round(sum(seconds) / len(seconds), 1), "usd": round(usd, 6),
    }
    with CHECKS.open("a", encoding="utf-8") as file:
        file.write(json.dumps(summary, ensure_ascii=False) + "\n")
    print()
    print(f"Исходы: {dict(outcomes)}")
    print(f"Чужих id поймано: {aliens}")
    print(f"Нарушений условий поймано: {violations}")
    print(f"Пройдено: {sum(checked)} из {len(checked)} запросов с ожиданием"
          + (f" ({sum(checked) / len(checked):.0%})" if checked else "")
          + (f", по прогонам: {', '.join(f'{r:.0%}' for r in rates)}" if args.runs > 1 else ""))
    print(f"Секунд на запрос: {summary['seconds_per_query']}, цена прогона: ${usd:.4f}")
    print(f"Время: {time.time() - started:.0f} с. Итог записан в {CHECKS}, вызовы — uv run show.py")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
