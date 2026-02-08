"""Route handlers for Web API (F9)."""

from teaching.web.routes.health import router as health_router
from teaching.web.routes.students import router as students_router
from teaching.web.routes.personas import router as personas_router
from teaching.web.routes.sessions import router as sessions_router
from teaching.web.routes.books import router as books_router

__all__ = [
    "health_router",
    "students_router",
    "personas_router",
    "sessions_router",
    "books_router",
]
