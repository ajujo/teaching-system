"""FastAPI application factory (F9).

Main entry point for the Teaching System Web API.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from teaching.web.routes import (
    health_router,
    students_router,
    personas_router,
    sessions_router,
)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        Configured FastAPI app instance
    """
    app = FastAPI(
        title="Teaching System API",
        description="Web API for the Teaching System tutor",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # CORS middleware for web clients
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure appropriately for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers
    app.include_router(health_router)
    app.include_router(students_router)
    app.include_router(personas_router)
    app.include_router(sessions_router)

    return app


# Default app instance for uvicorn
app = create_app()
