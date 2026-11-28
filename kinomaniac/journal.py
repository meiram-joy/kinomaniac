"""Журнал calls.jsonl: одна строка JSON на каждый вызов модели."""

import json
import time
from pathlib import Path

JOURNAL = "calls.jsonl"


PRICE = {"gpt-6-luna": (0.10, 0.50), "gpt-6-astra": (10.00, 50.00)}


def request_text(query: str, films: list[dict]) -> str:
    """Что ушло модели: текст запроса и id каталога. Весь каталог раздул бы журнал."""
    ids = ", ".join(str(film["id"]) for film in films)
    return f"<каталог>{len(films)} фильмов, id: [{ids}]</каталог>\n<запрос>{query}</запрос>"


def write(model: str, request: str, outcome: str, started: float, *,
          step: str = "choice", completion=None, rejected=None, violations=None,
          note: str = "") -> dict:
    row = {
        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "model": model,
        "step": step,
        "request": request,
        "outcome": outcome,
        "seconds": round(time.time() - started, 1),
    }
    if rejected:
        row["rejected"] = [str(x) for x in rejected]
    if violations:
        row["violations"] = violations
    if note:
        row["note"] = note
    usage = getattr(completion, "usage", None)
    if usage is not None:
        price_in, price_out = PRICE.get(model, (0, 0))
        row["usage"] = usage.model_dump()
        row["usd"] = (usage.prompt_tokens * price_in
                      + usage.completion_tokens * price_out) / 1_000_000
    with Path(JOURNAL).open("a", encoding="utf-8") as file:
        file.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row
