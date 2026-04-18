from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from linkhop.models.domain import MatchType


class SourceContent(BaseModel):
    service: str
    type: Literal["track", "album", "artist"]
    id: str
    url: str
    title: str
    artists: list[str]
    album: str | None = None
    duration_ms: int | None = None
    isrc: str | None = None
    upc: str | None = None
    artwork: str = ""


class TargetResult(BaseModel):
    status: Literal["ok", "not_found", "error"]
    url: str | None = None
    confidence: float | None = None
    match: MatchType | None = None
    message: str | None = None


class ShareInfo(BaseModel):
    id: str
    url: str


class CacheInfo(BaseModel):
    hit: bool
    ttl_seconds: int


class ConvertResponse(BaseModel):
    source: SourceContent
    targets: dict[str, TargetResult]
    cache: CacheInfo
    share: ShareInfo | None = None


class ServiceInfo(BaseModel):
    id: str
    name: str
    capabilities: list[Literal["track", "album", "artist"]]


class ServicesResponse(BaseModel):
    services: list[ServiceInfo]


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    redis: bool
    postgres: bool


class ErrorBody(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorBody
