"""
Second Opinion — FastAPI Application Entry Point

Main application factory and configuration.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.api.routes import health, audits
from app.db.database import get_database_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup/shutdown events."""
    # Startup
    settings = get_settings()
    print(f"Starting Second Opinion Backend on {settings.backend_host}:{settings.backend_port}")
    print(f"Frontend origin: {settings.frontend_origin}")
    print(f"LLM configured: {settings.has_llm_config}")
    print(f"Database: {settings.database_url.split('@')[-1] if '@' in settings.database_url else 'local'}")

    yield

    # Shutdown
    db_manager = get_database_manager()
    await db_manager.close()
    print("Shutting down Second Opinion Backend")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="Second Opinion API",
        description="AI-Powered Claim Auditing and Evidence Verification Platform",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    # Include routers
    app.include_router(health.router, prefix="/api", tags=["health"])
    app.include_router(audits.router, prefix="/api", tags=["audits"])

    @app.get("/")
    async def root():
        """Root endpoint with basic API information."""
        return {
            "name": "Second Opinion API",
            "version": "0.1.0",
            "description": "AI-Powered Claim Auditing and Evidence Verification Platform",
            "docs": "/docs",
            "health": "/api/health",
        }

    return app


# Create the app instance for uvicorn
app = create_app()


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.backend_host,
        port=settings.backend_port,
        reload=True,
        log_level=settings.log_level.lower(),
    )