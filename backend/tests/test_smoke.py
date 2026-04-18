from fastapi.testclient import TestClient

from linkhop.main import create_app


def test_app_instantiates():
    app = create_app()
    assert app.title == "linkhop"


def test_openapi_schema_available():
    client = TestClient(create_app())
    resp = client.get("/api/v1/openapi.json")
    assert resp.status_code == 200
    assert resp.json()["info"]["title"] == "linkhop"
