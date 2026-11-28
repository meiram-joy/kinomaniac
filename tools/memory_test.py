"""Опыт с памятью модели: год и длительность 10 фильмов БЕЗ каталога в контексте.

    uv run tools/memory_test.py
"""

import json
import random
import sys
import time
from pathlib import Path

from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from kino import CATALOG, MODEL, make_client     # noqa: E402
from kinomaniac import journal, llm              # noqa: E402

RESULTS = Path(__file__).parent / "memory_results.json"
COUNT = 10
SEED = 7


class Facts(BaseModel):
    year: int
    minutes: int


def main() -> None:
    films = json.loads(Path(CATALOG).read_text(encoding="utf-8"))
    sample = random.Random(SEED).sample(films, COUNT)
    client = make_client()
    rows, wrong_year, wrong_minutes = [], 0, 0
    for film in sample:
        question = (f"Фильм «{film['title']}». В каком году он вышел и сколько минут "
                    "длится? Ответь по памяти.")
        started = time.time()
        reply = llm.ask(client, MODEL, [{"role": "user", "content": question}], Facts)
        journal.write(MODEL, question, reply.outcome or "ok", started,
                      step="memory", completion=reply.completion, note=reply.note)
        if reply.outcome:
            print(f"{film['title']}: {reply.outcome}")
            continue
        facts = reply.parsed
        year_ok = facts.year == film["year"]
        minutes_ok = abs(facts.minutes - film["minutes"]) <= 2
        wrong_year += not year_ok
        wrong_minutes += not minutes_ok
        rows.append({"title": film["title"], "catalog": [film["year"], film["minutes"]],
                     "model": [facts.year, facts.minutes],
                     "year_ok": year_ok, "minutes_ok": minutes_ok})
        print(f"{film['title'][:40]:40} каталог {film['year']}, {film['minutes']:>3} мин | "
              f"модель {facts.year}, {facts.minutes:>3} мин  "
              f"{'✅' if year_ok else '❌'} {'✅' if minutes_ok else '❌'}")
    print(f"\nИз {len(rows)} фильмов: год неверен у {wrong_year}, "
          f"длительность (±2 мин) неверна у {wrong_minutes}")
    RESULTS.write_text(json.dumps({"model": MODEL, "films": rows, "wrong_year": wrong_year,
                                   "wrong_minutes": wrong_minutes},
                                  ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
