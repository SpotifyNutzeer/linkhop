from fastapi import FastAPI


def create_app() -> FastAPI:
    app = FastAPI(title="linkhop", version="0.1.0", docs_url="/api/docs", openapi_url="/api/v1/openapi.json")
    return app


app = create_app()
