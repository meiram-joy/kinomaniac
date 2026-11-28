"""Вызов модели. Любой сбой превращается в Исход, программа не падает."""

from dataclasses import dataclass
from typing import Any

import openai
import pydantic

LIMIT = 1000


@dataclass
class Reply:
    outcome: str | None
    parsed: Any = None
    completion: Any = None
    note: str = ""


def ask(client, model: str, messages: list[dict], schema, effort: str = "none") -> Reply:
    try:
        completion = client.chat.completions.parse(
            model=model,
            messages=messages,
            response_format=schema,
            max_completion_tokens=LIMIT,
            reasoning_effort=effort,
        )
    except openai.APIConnectionError:
        return Reply("no_connection", note="нет связи с сервером модели")
    except openai.APIStatusError as error:
        return Reply(f"error_{error.status_code}", note=f"ошибка API: {error.message}")
    except openai.LengthFinishReasonError as error:
        return Reply("length", completion=error.completion,
                     note="ответ обрезан на лимите токенов")
    except openai.ContentFilterFinishReasonError:
        return Reply("refusal", note="ответ заблокирован фильтром содержимого")
    except pydantic.ValidationError as error:
        return Reply("invalid", note=f"ответ не по схеме: {error.error_count()} ошибок")

    message = completion.choices[0].message
    if message.refusal:
        return Reply("refusal", completion=completion, note=f"модель отказалась: {message.refusal}")
    if message.parsed is None:
        return Reply("invalid", completion=completion, note="пустой ответ")
    return Reply(None, parsed=message.parsed, completion=completion)
