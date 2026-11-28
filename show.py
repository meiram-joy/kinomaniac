"""Журнал вызовов calls.jsonl: исходы, токены, секунды и цена.

    uv run show.py        последние 10 вызовов и итог по всему журналу
    uv run show.py all    все вызовы
"""

import sys
from collections import Counter

from kinomaniac import journal

LAST = 10


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
    choices = [r for r in rows if r.get("step", "choice") == "choice"]
    print(f"Из них подбор фильма (step choice): {len(choices)}, "
          f"остальное — {dict(Counter(r.get('step') for r in rows if r not in choices))}")
    for model, count in Counter(r["model"] for r in choices).most_common():
        mine = [r for r in rows if r["model"] == model
                and r.get("step", "choice") in ("filters", "choice")]
        avg_in = sum(tokens(r, "prompt_tokens") for r in mine) / count
        avg_out = sum(tokens(r, "completion_tokens") for r in mine) / count
        avg_sec = sum(r.get("seconds", 0) for r in mine) / count
        spent = sum(r.get("usd", 0) for r in mine)
        print(f"\n{model}: {count} запросов, на запрос (все шаги) вход {avg_in:.0f} ток., "
              f"выход {avg_out:.0f} ток., {avg_sec:.1f} с, всего ${spent:.4f}")
        priced = model if model in journal.PRICE else journal.REFERENCE
        one = journal.usd(priced, avg_in, avg_out)
        label = (model if model in journal.PRICE
                 else f"{journal.REFERENCE} (для сравнения; {model} бесплатна)")
        print(f"  один запрос по цене {label}: ${one:.6f}, 10 000 запросов: ${one * 10_000:.2f}")


def main():
    rows = journal.read()
    if not rows:
        print("Журнал пуст: файла calls.jsonl ещё нет")
        return
    table(rows if "all" in sys.argv[1:] else rows[-LAST:])
    summary(rows)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
