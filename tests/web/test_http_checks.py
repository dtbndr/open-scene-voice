import base64

import pytest
from web_http_helper import HOST, ORIGIN, PORT, make_request

from scenevoice.web import (
    Request,
    authenticate,
    check_host,
    check_origin,
    cookie_name,
    make_token,
    read_cookie,
    redeem_token,
    security_headers,
    stale_response,
    token_matches,
)


def test_exact_host_passes() -> None:
    assert check_host(make_request(headers=[("host", HOST)]), PORT) is None


@pytest.mark.parametrize(
    "host",
    ["127.0.0.1:5001", "127.0.0.1:50000", "localhost:5000", "evil.test"],
)
def test_any_other_host_is_forbidden(host: str) -> None:
    refusal = check_host(make_request(headers=[("host", host)]), PORT)
    assert refusal is not None
    assert refusal.status == 403
    assert b'"bad_host"' in refusal.body


def test_missing_host_is_forbidden() -> None:
    refusal = check_host(make_request(headers=[]), PORT)
    assert refusal is not None
    assert refusal.status == 403
    assert b'"bad_host"' in refusal.body


FOREIGN = ["http://localhost:5000", "http://127.0.0.1:5001", "http://evil.test", "null"]


def refused(method: str, origin: str | None) -> bool:
    headers = [("host", HOST)] + ([("origin", origin)] if origin is not None else [])
    refusal = check_origin(make_request(method, headers=headers), PORT)
    if refusal is None:
        return False
    assert refusal.status == 403
    assert b'"bad_origin"' in refusal.body
    return True


@pytest.mark.parametrize("method", ["POST", "PUT", "DELETE"])
def test_non_get_needs_the_exact_origin(method: str) -> None:
    assert not refused(method, ORIGIN)
    assert refused(method, None)
    for origin in FOREIGN:
        assert refused(method, origin)


@pytest.mark.parametrize("method", ["GET", "HEAD"])
def test_get_without_origin_passes_and_a_foreign_origin_is_refused(method: str) -> None:
    assert not refused(method, None)
    assert not refused(method, ORIGIN)
    for origin in FOREIGN:
        assert refused(method, origin)


TOKEN = "tok-en_123"
COOKIE = f"scenevoice_{PORT}"


def request(
    method: str = "GET", path: str = "/", query: str = "", cookie: str | None = None
) -> Request:
    headers = [("host", HOST)] + ([("cookie", cookie)] if cookie is not None else [])
    return Request(method, path, query, tuple(headers))


def test_a_valid_cookie_is_allowed() -> None:
    assert authenticate(request(cookie=f"{COOKIE}={TOKEN}"), TOKEN, PORT) == "allowed"
    assert authenticate(request("POST", "/api/keys", cookie=f"x=1; {COOKIE}={TOKEN}"), TOKEN, PORT) == "allowed"


@pytest.mark.parametrize(
    "cookie", [None, f"{COOKIE}=wrong", f"scenevoice_1={TOKEN}"]  # the last: a cookie for another port (cross-origin)
)
def test_a_wrong_or_missing_cookie_is_stale(cookie: str | None) -> None:
    assert authenticate(request(cookie=cookie), TOKEN, PORT) == "stale"
    assert authenticate(request("POST", "/api/keys", cookie=cookie), TOKEN, PORT) == "stale"


def test_the_correct_token_in_the_query_is_redeem_and_a_wrong_one_is_stale() -> None:
    assert authenticate(request(query=f"token={TOKEN}"), TOKEN, PORT) == "redeem"
    assert authenticate(request(query="token=nope"), TOKEN, PORT) == "stale"


def redeemed(req: Request):
    response = redeem_token(req, TOKEN, PORT)
    assert response.status == 303
    assert response.body == b""
    return response, dict(response.headers)


def test_redeem_gives_303_to_the_same_path_and_sets_the_cookie() -> None:
    response, headers = redeemed(request(path="/projects", query=f"token={TOKEN}"))
    assert headers["Location"] == "/projects"
    assert headers["Set-Cookie"] == f"{COOKIE}={TOKEN}; HttpOnly; SameSite=Lax; Path=/"
    assert [name for name, _ in response.headers].count("Set-Cookie") == 1


@pytest.mark.parametrize(
    ("path", "location"),
    [
        ("//evil.example", "/evil.example"),
        ("/\\evil.example", "/evil.example"),  # browsers read a backslash as a slash
        ("http://evil.example/x", "/x"),
    ],
)
def test_open_redirect_shapes_give_a_single_slash_same_origin_location(path: str, location: str) -> None:
    assert redeemed(request(path=path, query=f"token={TOKEN}"))[1]["Location"] == location


@pytest.mark.parametrize(
    "req",
    [
        request(query="token=wrong"),
        request(query=f"token={TOKEN}&token={TOKEN}"),
        request("POST", query=f"token={TOKEN}"),
        request(path="//api/keys", query=f"token={TOKEN}"),
        request(path="/x\r\nSet-Cookie: a=b", query=f"token={TOKEN}"),
    ],
)
def test_these_requests_do_not_redeem(req: Request) -> None:
    assert authenticate(req, TOKEN, PORT) == "stale"


def test_make_token_is_urlsafe_with_enough_entropy_and_differs_each_call() -> None:
    first, second = make_token(), make_token()
    assert first != second
    assert len(base64.urlsafe_b64decode(first + "=" * (-len(first) % 4))) >= 32
    assert all(ch.isalnum() or ch in "-_" for ch in first)


def test_token_matches_only_the_exact_token() -> None:
    assert token_matches("abc", "abc")
    assert not token_matches("abd", "abc")
    assert not token_matches("abcd", "abc")


@pytest.mark.parametrize("candidate", ["café"])
def test_token_matches_treats_empty_and_non_ascii_as_a_mismatch_without_raising(candidate: str) -> None:
    assert not token_matches(candidate, "abc")
    assert not token_matches(candidate, "")


def test_cookie_name_carries_the_port() -> None:
    assert cookie_name(5000) == "scenevoice_5000"
    assert cookie_name(5001) != cookie_name(5000)


def cookie_request(*headers: str):
    return make_request(headers=[("cookie", value) for value in headers])


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        ("scenevoice_5000=tok", "tok"),
        ("a=1; scenevoice_5000=tok; b=2", "tok"),
        ("scenevoice_5001=other", None),
        ("\x00\xff garbage ;;", None),
    ],
)
def test_read_cookie_picks_the_named_cookie_and_tolerates_malformed_headers(
    header: str, expected: str | None
) -> None:
    assert read_cookie(cookie_request(header), "scenevoice_5000") == expected


WORDING = (
    "This link is from an earlier run of SceneVoice. Open Terminal, type scenevoice web "
    "and press Return. A new window opens with your projects."
)


@pytest.mark.parametrize("path", ["/api/keys", "/api/"])
def test_api_paths_get_the_stale_link_envelope(path: str) -> None:
    response = stale_response(make_request(path=path))
    assert response.status == 401
    assert response.no_store
    assert b'"stale_link"' in response.body
    assert ("Content-Type", "application/json; charset=utf-8") in response.headers


@pytest.mark.parametrize("path", ["/", "/app.js", "/api", "/%61pi/keys", "/apiary/x"])
def test_every_other_path_gets_the_inline_page_with_the_exact_wording(path: str) -> None:
    response = stale_response(make_request(path=path))
    assert response.status == 401
    assert response.no_store
    assert ("Content-Type", "text/html; charset=utf-8") in response.headers
    html = response.body.decode("utf-8")
    assert html.startswith("<!doctype html>")
    assert WORDING in html


def test_the_four_headers_are_always_present() -> None:
    for no_store in (False, True):
        headers = dict(security_headers(no_store))
        assert headers["Referrer-Policy"] == "no-referrer"
        assert headers["X-Content-Type-Options"] == "nosniff"
        assert headers["X-Frame-Options"] == "DENY"
        assert headers["Content-Security-Policy"] == "frame-ancestors 'none'"


def test_no_store_only_when_asked() -> None:
    assert "Cache-Control" not in dict(security_headers(False))
    assert dict(security_headers(True))["Cache-Control"] == "no-store"
