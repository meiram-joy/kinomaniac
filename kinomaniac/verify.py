"""Проверка ответа модели кодом. Главная защита проекта."""

from dataclasses import dataclass, field

from kinomaniac.schema import Choice

MAX_FILMS = 3


@dataclass
class Verdict:
    outcome: str
    shown: list[tuple[dict, str]] = field(default_factory=list)
    rejected: list[str] = field(default_factory=list)
    note: str = ""


def verify(choice: Choice, films: list[dict]) -> Verdict:
    by_id = {str(film["id"]): film for film in films}

    if choice.status == "no_match":
        return Verdict("no_match", note=choice.reason)

    rejected = [p.film_id for p in choice.picks if str(p.film_id) not in by_id]
    if rejected:
        return Verdict("invalid", rejected=rejected, note="id не из каталога")

    shown, seen = [], set()
    for p in choice.picks:
        key = str(p.film_id)
        if key not in seen:
            seen.add(key)
            shown.append((by_id[key], p.why))
    shown = shown[:MAX_FILMS]

    if not shown:
        return Verdict("invalid", note="status ok, но фильмов нет")
    return Verdict("ok", shown=shown)
