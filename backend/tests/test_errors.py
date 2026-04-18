from fastapi import FastAPI
from fastapi.testclient import TestClient

from linkhop.errors import AppError, SourceNotFoundError, install_error_handlers
from linkhop.url_parser import UnsupportedUrlError


def make_app() -> FastAPI:
    app = FastAPI()
    install_error_handlers(app)

    @app.get("/raise-app")
    def _raise_app():
        raise AppError(code="test_error", status=418, message="I am a teapot")

    @app.get("/raise-unsupported")
    def _raise_unsupported():
        raise UnsupportedUrlError("bad url")

    @app.get("/raise-not-found")
    def _raise_not_found():
        raise SourceNotFoundError("spotify/track/xyz")

    @app.get("/raise-keyerror")
    def _raise_keyerror():
        # KeyError is a LookupError subclass. The handler must NOT map it to 404,
        # otherwise every dict-miss in route logic masquerades as "source_unavailable".
        raise KeyError("some_internal_key")

    return app


def test_app_error_mapped_to_response():
    client = TestClient(make_app())
    resp = client.get("/raise-app")
    assert resp.status_code == 418
    assert resp.json() == {"error": {"code": "test_error", "message": "I am a teapot"}}


def test_app_error_str_is_message():
    # Guards against the dataclass-Exception pitfall: without __post_init__ calling
    # super().__init__(message), str(exc) == "" and exc.args == () — kills logs.
    exc = AppError(code="c", status=500, message="boom")
    assert str(exc) == "boom"
    assert exc.args == ("boom",)


def test_unsupported_url_mapped_to_400():
    client = TestClient(make_app())
    resp = client.get("/raise-unsupported")
    assert resp.status_code == 400
    body = resp.json()
    assert body["error"]["code"] == "unsupported_service"
    assert "bad url" in body["error"]["message"]


def test_source_not_found_mapped_to_404():
    client = TestClient(make_app())
    resp = client.get("/raise-not-found")
    assert resp.status_code == 404
    body = resp.json()
    assert body["error"]["code"] == "source_unavailable"
    assert "spotify/track/xyz" in body["error"]["message"]


def test_keyerror_is_not_caught_as_source_not_found():
    # Regression guard: we deliberately do NOT use LookupError as the handler target
    # because KeyError/IndexError are LookupError subclasses.
    client = TestClient(make_app(), raise_server_exceptions=False)
    resp = client.get("/raise-keyerror")
    assert resp.status_code == 500  # FastAPI default for unhandled
