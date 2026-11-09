from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1", tags=["health"])


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    service: Literal["carecircle-api"] = "carecircle-api"
    stage: Literal["whole-team-s1-sandip-s2"] = "whole-team-s1-sandip-s2"


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Process liveness only. No database, auth or feature readiness implied."""
    return HealthResponse()


