"""Заглушка клиента OpenAI для тестов: без сети, без ключа, без Ollama."""

import json

import httpx
import openai
import pytest
from openai.lib._parsing._completions import parse_chat_completion
from openai.types.chat import ChatCompletion

REQUEST = httpx.Request("POST", "http://127.0.0.1:9/v1/chat/completions")

FILMS = [
    {"id": "f-001", "title": "Тюльпан", "year": 2008, "minutes": 100,
     "genres": ["комедия", "драма"], "countries": ["Казахстан"],
     "languages": ["казахский"], "description": "Моряк возвращается в степь и сватается."},
    {"id": "f-002", "title": "Сталкер", "year": 1979, "minutes": 163,
     "genres": ["фантастика", "драма"], "countries": ["СССР"],
     "languages": ["русский"], "description": "Проводник ведёт двоих через Зону."},
    {"id": "f-003", "title": "Один дома", "year": 1990, "minutes": 103,
     "genres": ["комедия", "семейный"], "countries": ["США"],
     "languages": ["английский"], "description": "Мальчика забыли дома на Рождество."},
    {"id": "f-004", "title": "Король Лев", "year": 1994, "minutes": 88,
     "genres": ["мультфильм", "семейный"], "countries": ["США"],
     "languages": ["английский"], "description": "Львёнок возвращается, чтобы стать королём."},
]


def completion(payload, *, raw=None, refusal=None, finish="stop"):
    """ChatCompletion, как его вернул бы сервер. raw — сырой текст вместо JSON."""
    content = raw if raw is not None else (
        None if payload is None else json.dumps(payload, ensure_ascii=False))
    if finish == "length":
        content = content[: len(content) // 2]
    return ChatCompletion.model_validate({
        "id": "chatcmpl-test", "object": "chat.completion", "created": 0,
        "model": "stub",
        "choices": [{"index": 0, "finish_reason": finish,
                     "message": {"role": "assistant", "content": content,
                                 "refusal": refusal}}],
        "usage": {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120},
    })


class Stub:
    """Выглядит как OpenAI(): client.chat.completions.parse(...). Отвечает по сценарию."""

    def __init__(self, scenario, filters=None):
        self.scenario = scenario
        self.filters = filters or {}
        self.calls = []
        self.chat = self
        self.completions = self

    def parse(self, *, response_format, **kwargs):
        kind = "picks" if "picks" in response_format.model_fields else "filters"
        self.calls.append(dict(kwargs, kind=kind))
        reply = self.scenario() if kind == "picks" else completion(self.filters)
        return parse_chat_completion(response_format=response_format,
                                     chat_completion=reply, input_tools=openai.omit)

    def choice_calls(self):
        return [c for c in self.calls if c["kind"] == "picks"]

    def prompt(self):
        return "\n".join(m["content"] for m in self.choice_calls()[-1]["messages"])


def answer(*ids, status="ok"):
    return {"status": status, "reason": "тест",
            "picks": [{"film_id": i, "why": f"причина {i}"} for i in ids]}


@pytest.fixture
def films():
    return [dict(f) for f in FILMS]


@pytest.fixture(autouse=True)
def journal_in_tmp(tmp_path, monkeypatch):
    """Каждый тест пишет журнал во временную папку, настоящий calls.jsonl не трогаем."""
    monkeypatch.chdir(tmp_path)
    return tmp_path / "calls.jsonl"


def journal_rows(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def raise_connection():
    raise openai.APIConnectionError(request=REQUEST)


def raise_status(code):
    def scenario():
        response = httpx.Response(code, request=REQUEST)
        raise openai.APIStatusError(f"Error code: {code}", response=response, body=None)
    return scenario
