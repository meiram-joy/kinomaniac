"""Epic: отбор кандидатов без модели и pick_big."""

from conftest import Stub, answer, completion
from kino import pick_big
from kinomaniac.search import candidates, cues


def big(films, extra=60):
    more = [{"id": f"b-{n:04d}", "title": f"Фильм {n}", "year": 1950 + n % 70,
             "minutes": 80 + n % 90, "genres": ["драма"], "countries": ["США"],
             "languages": ["английский"], "description": f"Обычная драма номер {n} о жизни."}
            for n in range(extra)]
    return films + more


def test_candidates_without_model(films):
    catalog = big(films)
    ids = candidates("мультфильм про льва", catalog, k=30)
    assert 0 < len(ids) <= 30
    assert ids[0] == "f-004"


def test_candidates_respect_conditions(films):
    catalog = big(films)
    ids = candidates("на казахском до двух часов", catalog, k=30)
    assert ids == ["f-001"]


def test_cues():
    c = cues("комедия на казахском до двух часов, без мультфильмов")
    assert c["max_minutes"] == 120 and c["languages"] == ["казахский"]
    assert c["genres"] == ["комедия"] and c["exclude_genres"] == ["мультфильм"]
    assert cues("очень длинный фильм, больше трёх часов")["min_minutes"] == 180
    assert cues("фильм 1990-х годов")["year_from"] == 1990
    assert cues("что-нибудь до часа")["max_minutes"] == 60
    assert cues("фильм ужасов, снятый до 1970 года")["year_to"] == 1969
    assert cues("старый советский фильм")["year_to"] == 1985
    assert cues("про старт ракеты")["year_to"] is None
    assert cues("советская фантастика")["countries"] == ["СССР"]


def test_pick_big_sends_only_candidates(films):
    catalog = big(films, extra=200)
    stub = Stub(lambda: completion(answer("f-004")))
    assert pick_big(stub, "m", "мультфильм про льва", catalog) == ("ok", ["f-004"])
    data = stub.choice_calls()[-1]["messages"][-1]["content"]
    assert data.count('"id":') <= 30


def test_pick_big_alien_id_invalid(films):
    stub = Stub(lambda: completion(answer("f-004", "zzz")))
    assert pick_big(stub, "m", "мультфильм про льва", big(films)) == ("invalid", [])
