"""FastAPI application factory (F9).

Main entry point for the Teaching System Web API.
"""

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from teaching.core.tutor import list_available_books_with_metadata
from teaching.web.routes import (
    health_router,
    students_router,
    personas_router,
    sessions_router,
    books_router,
)

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan context manager for startup/shutdown events."""
    # Startup
    data_dir = Path("data")
    books = list_available_books_with_metadata(data_dir)
    logger.info(
        "api_startup",
        books_found=len(books),
        books_dir=str((data_dir / "books").absolute()),
        book_ids=[b["book_id"] for b in books],
    )
    yield
    # Shutdown (nothing to do for now)


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
        lifespan=lifespan,
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
    app.include_router(books_router)

    return app


# Default app instance for uvicorn
app = create_app()
