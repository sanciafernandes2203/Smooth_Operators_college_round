"""
Health Check Endpoint

GET /api/health
Returns basic service status.
"""
from fastapi import APIRouter, Response
from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Health check response model."""
    status: str = "ok"


router = APIRouter()


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    description="Returns the service status. Used for load balancer health checks and monitoring.",
    responses={
        200: {"description": "Service is healthy"},
    },
)
async def health_check() -> HealthResponse:
    """
    Health check endpoint.

    Returns:
        HealthResponse: Object with status field set to "ok"
    """
    return HealthResponse(status="ok")


@router.get(
    "/health/ready",
    response_model=HealthResponse,
    summary="Readiness check",
    description="Returns service readiness. Can be extended to check database, LLM provider, etc.",
)
async def readiness_check() -> HealthResponse:
    """
    Readiness check endpoint.

    In the future, this can verify:
    - Database connectivity
    - LLM provider availability
    - OCR engine availability

    Returns:
        HealthResponse: Object with status field set to "ok"
    """
    # TODO: Add actual dependency checks (database, LLM, OCR)
    return HealthResponse(status="ok")