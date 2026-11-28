"""Журнал вызовов calls.jsonl: исходы, токены, секунды и цена.

    uv run show.py        последние 10 вызовов и итог по всему журналу
    uv run show.py all    все вызовы
"""

import json
import sys
from collections import Counter
from pathlib import Path

from kinomaniac.journal import PRICE

JOURNAL = Path("calls.jsonl")
LAST = 10
REFERENCE = "gpt-6-luna"


def tokens(row, key):
    return (row.get("usage") or {}).get(key) or 0


def table(rows):
    print(f"{'время':19}  {'модель':12}  {'шаг':7}  {'исход':13}  {'вход':>6}  "
          f"{'выход':>5}  {'сек':>5}  {'$':>9}")
    for row in rows:
        print(f"{row.get('time', ''):19}  {row['model'][:12]:12}  {row.get('step', 'choice'):7}  "
              f"{row['outcome']:13}  {tokens(row, 'prompt_tokens'):>6}  "
              f"{tokens(row, 'completion_tokens'):>5}  {row.get('seconds', 0):>5}  "
              f"{row.get('usd', 0):>9.6f}")


def summary(rows):
    print()
    print(f"Вызовов: {len(rows)} ("
          + ", ".join(f"{k} {v}" for k, v in Counter(r["outcome"] for r in rows).most_common())
          + ")")
    print("Отклонено чужих id:", sum(len(r.get("rejected", [])) for r in rows))
    for model, count in Counter(r["model"] for r in rows).most_common():
        mine = [r for r in rows if r["model"] == model and r.get("usage")]
        if not mine:
            continue
        avg_in = sum(tokens(r, "prompt_tokens") for r in mine) / len(mine)
        avg_out = sum(tokens(r, "completion_tokens") for r in mine) / len(mine)
        avg_sec = sum(r.get("seconds", 0) for r in mine) / len(mine)
        usd = sum(r.get("usd", 0) for r in mine)
        print(f"\n{model}: {count} вызовов, в среднем вход {avg_in:.0f} ток., "
              f"выход {avg_out:.0f} ток., {avg_sec:.1f} с, всего ${usd:.4f}")
        price_in, price_out = PRICE.get(model, PRICE[REFERENCE])
        one = (avg_in * price_in + avg_out * price_out) / 1_000_000
        label = model if model in PRICE else f"{REFERENCE} (для сравнения; {model} бесплатна)"
        print(f"  один запрос по цене {label}: ${one:.6f}, 10 000 запросов: ${one * 10_000:.2f}")


def main():
    if not JOURNAL.exists():
        print("Журнал пуст: файла calls.jsonl ещё нет")
        return
    rows = [json.loads(line) for line in JOURNAL.read_text(encoding="utf-8").splitlines()
            if line.strip()]
    table(rows if "all" in sys.argv[1:] else rows[-LAST:])
    summary(rows)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
