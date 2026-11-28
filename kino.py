"""«Киноманьяк»: подбор фильма по сложному запросу только из своего каталога.

    uv run kino.py "фильм как Интерстеллар, но не про космос"
"""

import os
import sys
import time

from kinomaniac import journal, llm, render
from kinomaniac.prompt import build_messages
from kinomaniac.schema import Choice
from kinomaniac.verify import verify

MODEL = "qwen3.5:4b"
OLLAMA = "http://127.0.0.1:11434/v1"
CATALOG = "films.json"


def pick(client, model, query, films):
    """Подобрать до трёх фильмов из films под запрос query."""
    started = time.time()
    request = journal.request_text(query, films)
    reply = llm.ask(client, model, build_messages(query, films), Choice)

    if reply.outcome is not None:
        render.failure(reply.outcome, reply.note)
        journal.write(model, request, reply.outcome, started,
                      completion=reply.completion, note=reply.note)
        return reply.outcome, []

    verdict = verify(reply.parsed, films)
    if verdict.outcome == "ok":
        render.films(verdict.shown)
    else:
        render.failure(verdict.outcome, verdict.note)
    journal.write(model, request, verdict.outcome, started,
                  completion=reply.completion, rejected=verdict.rejected,
                  note=verdict.note)
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
