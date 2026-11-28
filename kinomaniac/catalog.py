"""Каталог: модель Фильма, словарь каталога и проверка файла каталога."""

import json
from collections import Counter
from pathlib import Path

from pydantic import BaseModel, Field


GENRES = {
    "драма", "комедия", "фантастика", "ужасы", "триллер", "боевик", "приключения",
    "мелодрама", "семейный", "мультфильм", "документальный", "исторический",
    "военный", "биография", "криминал", "фэнтези", "мюзикл", "вестерн",
}


class Film(BaseModel):
    id: str
    title: str
    year: int = Field(ge=1880, le=2030)
    minutes: int = Field(ge=1, le=600)
    genres: list[str]
    countries: list[str]
    languages: list[str]
    description: str = Field(min_length=10)


def check_catalog(films: list[dict]) -> list[str]:
    """Список проблем каталога; пустой список — каталог в порядке."""
    problems = []
    for n, raw in enumerate(films):
        try:
            film = Film.model_validate(raw)
        except ValueError as error:
            problems.append(f"фильм №{n}: {error}")
            continue
        unknown = set(film.genres) - GENRES
        if unknown:
            problems.append(f"{film.id}: жанры не из словаря {sorted(unknown)}")
    repeats = [i for i, count in Counter(str(f.get("id")) for f in films).items()
               if count > 1]
    if repeats:
        problems.append(f"повтор id: {repeats}")
    return problems


def load_catalog(path: str | Path) -> list[dict]:
    """Прочитать и проверить каталог. При ошибке — ValueError с перечнем проблем."""
    films = json.loads(Path(path).read_text(encoding="utf-8"))
    problems = check_catalog(films)
    if problems:
        raise ValueError("каталог не прошёл проверку:\n" + "\n".join(problems))
    return films
