"""Оценка запроса по ожиданию: ошибка здесь тихо исказила бы все цифры README."""

from check import passed


def test_no_match_expected():
    assert passed({"no_match": True}, "no_match", [])
    assert not passed({"no_match": True}, "ok", ["f-001"])


def test_must_needs_one_of_them_shown():
    assert passed({"must": ["f-001", "f-002"]}, "ok", ["f-003", "f-002"])
    assert not passed({"must": ["f-001"]}, "ok", ["f-003"])


def test_forbid_fails_even_with_must():
    assert not passed({"must": ["f-001"], "forbid": ["f-002"]}, "ok", ["f-001", "f-002"])
    assert passed({"forbid": ["f-002"]}, "ok", ["f-001"])


def test_not_ok_outcome_fails():
    assert not passed({"must": ["f-001"]}, "invalid", [])
    assert not passed({"forbid": ["f-002"]}, "no_connection", [])
