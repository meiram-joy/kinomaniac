"""Схема ответа модели (структурированный вывод)."""

from typing import Literal

from pydantic import BaseModel


class Pick(BaseModel):
    film_id: str
    why: str


class Choice(BaseModel):
    status: Literal["ok", "no_match"]
    reason: str
    picks: list[Pick]
