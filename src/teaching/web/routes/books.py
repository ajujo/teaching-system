"""Book endpoints (F9.1)."""

import os
from pathlib import Path

import structlog
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from teaching.core.tutor import list_available_books_with_metadata, get_chapter_info
from teaching.utils.validators import get_available_book_ids
from teaching.web.schemas import (
    BookSummary,
    BookDetail,
    BookListResponse,
    ChapterSummary,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/books", tags=["books"])

# Default data directory
DATA_DIR = Path("data")


class BooksDebugResponse(BaseModel):
    """Debug info for books endpoint (dev only)."""

    source: str
    data_dir: str
    data_dir_exists: bool
    books_dir_exists: bool
    book_dirs_found: int
    books_with_metadata: int
    book_ids: list[str]
    cwd: str


@router.get("/debug", response_model=BooksDebugResponse, tags=["debug"])
async def debug_books() -> BooksDebugResponse:
    """Debug endpoint to diagnose book loading (dev only).

    Returns diagnostic info about how books are discovered.
    """
    books_dir = DATA_DIR / "books"
    book_ids = get_available_book_ids(DATA_DIR)
    books_with_meta = list_available_books_with_metadata(DATA_DIR)

    logger.info(
        "books_debug",
        data_dir=str(DATA_DIR.absolute()),
        books_dir_exists=books_dir.exists(),
        book_dirs_found=len(book_ids),
        books_with_metadata=len(books_with_meta),
    )

    return BooksDebugResponse(
        source="data/books/ directory scan",
        data_dir=str(DATA_DIR.absolute()),
        data_dir_exists=DATA_DIR.exists(),
        books_dir_exists=books_dir.exists(),
        book_dirs_found=len(book_ids),
        books_with_metadata=len(books_with_meta),
        book_ids=book_ids,
        cwd=os.getcwd(),
    )


@router.get("", response_model=BookListResponse)
async def list_books() -> BookListResponse:
    """List all available books."""
    books_data = list_available_books_with_metadata(DATA_DIR)

    logger.info("books_list", count=len(books_data))

    books = [
        BookSummary(
            id=b["book_id"],
            title=b["title"],
            authors=b.get("authors", []),
            total_chapters=b.get("total_chapters", 0),
            has_outline=b.get("has_outline", False),
            has_units=b.get("has_units", False),
        )
        for b in books_data
    ]

    return BookListResponse(books=books, count=len(books))


@router.get("/{book_id}", response_model=BookDetail)
async def get_book(book_id: str) -> BookDetail:
    """Get details of a specific book."""
    books_data = list_available_books_with_metadata(DATA_DIR)

    # Find the book
    book_data = None
    for b in books_data:
        if b["book_id"] == book_id:
            book_data = b
            break

    if book_data is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Book '{book_id}' not found",
        )

    # Get chapter info
    chapters = []
    for i in range(1, book_data.get("total_chapters", 0) + 1):
        chapter_info = get_chapter_info(book_id, i, DATA_DIR)
        if chapter_info:
            chapters.append(
                ChapterSummary(
                    number=chapter_info.get("chapter_number", i),
                    title=chapter_info.get("title", f"Chapter {i}"),
                    unit_count=len(chapter_info.get("unit_ids", [])),
                )
            )

    return BookDetail(
        id=book_data["book_id"],
        title=book_data["title"],
        authors=book_data.get("authors", []),
        total_chapters=book_data.get("total_chapters", 0),
        has_outline=book_data.get("has_outline", False),
        has_units=book_data.get("has_units", False),
        chapters=chapters,
    )
