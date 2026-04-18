from __future__ import annotations

from dataclasses import dataclass

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from linkhop.url_parser import UnsupportedUrlError


@dataclass
class AppError(Exception):
    code: str
    status: int
    message: str

    def __post_init__(self) -> None:
        # dataclass-generated __init__ skips Exception.__init__, so str(exc) and
        # exc.args end up empty — breaks logging. Wire the message through.
        super().__init__(self.message)


class SourceNotFoundError(Exception):
    """Raised by the pipeline when a parsed source URL cannot be resolved.

    Using a dedicated type instead of LookupError prevents KeyError/IndexError
    (both LookupError subclasses) from being maskedly mapped to 404.
    """


def _body(code: str, message: str) -> dict:
    return {"error": {"code": code, "message": message}}


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError):
        return JSONResponse(status_code=exc.status, content=_body(exc.code, exc.message))

    @app.exception_handler(UnsupportedUrlError)
    async def _unsupported(_: Request, exc: UnsupportedUrlError):
        return JSONResponse(status_code=400, content=_body("unsupported_service", str(exc)))

    @app.exception_handler(SourceNotFoundError)
    async def _source_not_found(_: Request, exc: SourceNotFoundError):
        return JSONResponse(status_code=404, content=_body("source_unavailable", str(exc)))
