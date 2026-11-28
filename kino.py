"""«Киноманьяк»: подбор фильма по сложному запросу только из своего каталога.

    uv run kino.py "фильм как Интерстеллар, но не про космос"
"""

import json
import os
import sys
import time
from pathlib import Path

from kinomaniac import filters, journal, llm, render
from kinomaniac.catalog import check_catalog
from kinomaniac.prompt import build_messages
from kinomaniac.schema import Choice
from kinomaniac.search import candidates
from kinomaniac.verify import verify

MODEL = "qwen3.5:4b"
OLLAMA = "http://127.0.0.1:11434/v1"
CATALOG = "films.json"


def load_catalog(path=CATALOG) -> list[dict]:
    """Прочитать каталог из файла и проверить; при ошибке — ValueError с перечнем проблем."""
    films = json.loads(Path(path).read_text(encoding="utf-8"))
    problems = check_catalog(films)
    if problems:
        raise ValueError("каталог не прошёл проверку:\n" + "\n".join(problems))
    return films


def make_client(base_url=None, api_key=None, timeout=300):
    """Клиент OpenAI-совместимого сервера: по умолчанию локальная Ollama."""
    from dotenv import load_dotenv
    from openai import OpenAI

    load_dotenv()
    return OpenAI(base_url=base_url or os.environ.get("KINO_BASE_URL", OLLAMA),
                  api_key=api_key or os.environ.get("OPENAI_API_KEY", "ollama"),
                  max_retries=0, timeout=timeout)


def read_filters(client, model, query, films):
    """Первый вызов: условия запроса. При сбое — без условий, весь каталог."""
    started = time.time()
    schema = filters.filters_schema(films)
    reply = llm.ask(client, model, filters.build_messages(query, films), schema)
    conditions = reply.parsed if reply.outcome is None else schema()
    journal.write(model, f"<запрос>{query}</запрос>", reply.outcome or "ok", started,
                  step="filters", completion=reply.completion,
                  note=reply.note or filters.describe(conditions))
    return conditions


def pick_big(client, model, query, films):
    """Как pick, но модели уходят только кандидаты, отобранные без модели."""
    ids = {str(i) for i in candidates(query, films, k=30)}
    return pick(client, model, query, [f for f in films if str(f["id"]) in ids])


def pick(client, model, query, films, use_filters=True):
    """Подобрать до трёх фильмов из films под запрос query."""
    if use_filters:
        conditions = read_filters(client, model, query, films)
    else:
        conditions = filters.filters_schema(films)()
    allowed = filters.apply(films, conditions)
    if filters.active(conditions):
        render.conditions(filters.describe(conditions), len(allowed))

    started = time.time()
    request = journal.request_text(query, allowed)
    if not allowed:
        render.failure("no_match", "под условия запроса в каталоге ничего нет")
        journal.write(model, request, "no_match", started, note="после фильтров пусто")
        return "no_match", []

    reply = llm.ask(client, model, build_messages(query, allowed), Choice)
    if reply.outcome is not None:
        render.failure(reply.outcome, reply.note)
        journal.write(model, request, reply.outcome, started,
                      completion=reply.completion, note=reply.note)
        return reply.outcome, []

    verdict, broken = filters.recheck(verify(reply.parsed, films), conditions)
    if verdict.outcome == "ok":
        render.films(verdict.shown)
    else:
        render.failure(verdict.outcome, verdict.note)
    journal.write(model, request, verdict.outcome, started,
                  completion=reply.completion, rejected=verdict.rejected,
                  violations=broken, note=verdict.note)
    return verdict.outcome, [film["id"] for film, _ in verdict.shown]


def main() -> None:
    if len(sys.argv) < 2 or not sys.argv[1].strip():
        print('Запуск: uv run kino.py "какой фильм хочется посмотреть"')
        return
    pick(make_client(), os.environ.get("KINO_MODEL", MODEL), sys.argv[1], load_catalog())


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
