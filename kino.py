"""«Киноманьяк»: подбор фильма по сложному запросу только из своего каталога.

    uv run kino.py "фильм как Интерстеллар, но не про космос"
"""

import os
import sys
import time

from kinomaniac import filters, journal, llm, render
from kinomaniac.prompt import build_messages
from kinomaniac.schema import Choice
from kinomaniac.verify import verify

MODEL = "qwen3.5:4b"
OLLAMA = "http://127.0.0.1:11434/v1"
CATALOG = "films.json"


def read_filters(client, model, query, films):
    """Первый вызов: условия запроса. При сбое — без условий, весь каталог."""
    started = time.time()
    schema = filters.filters_schema(films)
    reply = llm.ask(client, model, filters.build_messages(query, films), schema)
    flt = reply.parsed if reply.outcome is None else schema()
    journal.write(model, f"<запрос>{query}</запрос>", reply.outcome or "ok", started,
                  step="filters", completion=reply.completion,
                  note=reply.note or filters.describe(flt))
    return flt


def pick(client, model, query, films):
    """Подобрать до трёх фильмов из films под запрос query."""
    flt = read_filters(client, model, query, films)
    candidates = filters.apply(films, flt)
    if filters.active(flt):
        print(f"Условия запроса: {filters.describe(flt)}, подходит фильмов: {len(candidates)}")

    started = time.time()
    request = journal.request_text(query, candidates)
    if not candidates:
        render.failure("no_match", "под условия запроса в каталоге ничего нет")
        journal.write(model, request, "no_match", started, note="после фильтров пусто")
        return "no_match", []

    reply = llm.ask(client, model, build_messages(query, candidates), Choice)
    if reply.outcome is not None:
        render.failure(reply.outcome, reply.note)
        journal.write(model, request, reply.outcome, started,
                      completion=reply.completion, note=reply.note)
        return reply.outcome, []

    verdict = verify(reply.parsed, films)
    broken = {str(film["id"]): filters.violations(film, flt) for film, _ in verdict.shown}
    broken = {k: v for k, v in broken.items() if v}
    if broken:
        verdict.shown = [(f, why) for f, why in verdict.shown if str(f["id"]) not in broken]
        if not verdict.shown:
            verdict.outcome, verdict.note = "no_match", "все предложенные фильмы нарушают условия"

    if verdict.outcome == "ok":
        render.films(verdict.shown)
    else:
        render.failure(verdict.outcome, verdict.note)
    journal.write(model, request, verdict.outcome, started,
                  completion=reply.completion, rejected=verdict.rejected,
                  violations=broken, note=verdict.note)
    return verdict.outcome, [film["id"] for film, _ in verdict.shown]


def main() -> None:
    from openai import OpenAI

    from kinomaniac.catalog import load_catalog

    if len(sys.argv) < 2 or not sys.argv[1].strip():
        print('Запуск: uv run kino.py "какой фильм хочется посмотреть"')
        return
    films = load_catalog(CATALOG)
    client = OpenAI(base_url=os.environ.get("KINO_BASE_URL", OLLAMA),
                    api_key=os.environ.get("OPENAI_API_KEY", "ollama"),
                    max_retries=0, timeout=300)
    pick(client, os.environ.get("KINO_MODEL", MODEL), sys.argv[1], films)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
