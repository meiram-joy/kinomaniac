"""Печать для пользователя. Данные фильма — только из каталога, от модели — только why."""

MESSAGES = {
    "no_match": "В каталоге нет подходящего фильма.",
    "invalid": "Модель ответила некорректно, показать нечего. Попробуйте ещё раз.",
    "refusal": "Модель отказалась отвечать на этот запрос.",
    "length": "Ответ модели оборвался. Попробуйте ещё раз.",
    "no_connection": "Нет связи с моделью. Проверьте, что Ollama запущена.",
}


def conditions(described: str, count: int) -> None:
    print(f"Условия запроса: {described}, подходит фильмов: {count}")


def films(shown: list[tuple[dict, str]]) -> None:
    for n, (film, why) in enumerate(shown, 1):
        print(f"{n}. {film['title']} ({film['year']}, {film['minutes']} мин)")
        print(f"   {film['description']}")
        print(f"   Почему: {why}")


def failure(outcome: str, note: str = "") -> None:
    if outcome.startswith("error_"):
        text = f"Сервис модели вернул ошибку ({outcome.removeprefix('error_')})."
    else:
        text = MESSAGES.get(outcome, f"Не получилось ({outcome}).")
    print(text)
    if outcome == "no_match" and note:
        print(f"Причина: {note}")
