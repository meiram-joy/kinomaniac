"""Rare: условия запроса проверяет код."""

from conftest import Stub, answer, completion, journal_rows
from kino import pick

MODEL = "model-under-test"
QUERY = "что-нибудь до 100 минут"


def test_catalog_filtered_before_choice(films):
    stub = Stub(lambda: completion(answer("f-001")), filters={"max_minutes": 100})
    pick(stub, MODEL, QUERY, films)
    prompt = stub.prompt()
    assert "Сталкер" not in prompt            # 163 мин
    assert "Тюльпан" in prompt                # 100 мин


def test_code_drops_film_that_breaks_condition(films, journal_in_tmp):
    stub = Stub(lambda: completion(answer("f-002", "f-001")), filters={"max_minutes": 100})
    outcome, ids = pick(stub, MODEL, QUERY, films)
    assert (outcome, ids) == ("ok", ["f-001"])
    assert "f-002" in journal_rows(journal_in_tmp)[-1]["violations"]


def test_all_picks_break_conditions(films):
    stub = Stub(lambda: completion(answer("f-002")), filters={"max_minutes": 100})
    assert pick(stub, MODEL, QUERY, films) == ("no_match", [])


def test_nothing_left_after_filters_skips_model(films, journal_in_tmp):
    stub = Stub(lambda: completion(answer("f-001")), filters={"max_minutes": 10})
    assert pick(stub, MODEL, QUERY, films) == ("no_match", [])
    assert stub.choice_calls() == []
    rows = journal_rows(journal_in_tmp)
    assert rows[-1]["step"] == "choice" and QUERY in rows[-1]["request"]


def test_genres_and_language(films):
    stub = Stub(lambda: completion(answer("f-001", "f-003")),
                filters={"languages": ["казахский"], "exclude_genres": ["мультфильм"]})
    outcome, ids = pick(stub, MODEL, QUERY, films)
    assert (outcome, ids) == ("ok", ["f-001"])
    assert "Король Лев" not in stub.prompt()


def test_unknown_word_in_filters_falls_back_to_whole_catalog(films, journal_in_tmp):
    stub = Stub(lambda: completion(answer("f-002")), filters={"languages": ["kazakh"]})
    assert pick(stub, MODEL, QUERY, films) == ("ok", ["f-002"])
    assert journal_rows(journal_in_tmp)[0]["outcome"] == "invalid"
    assert "Сталкер" in stub.prompt()
