"""Data validation helpers.

ID conventions per contracts_v1.md:
- book_id: "author-year-title" normalized (lowercase, hyphens, no special chars)
- Hierarchical IDs: "book_id:ch:N", "book_id:ch:N:sec:M", "book_id:unit:N"

Functions:
- resolve_book_id(prefix, candidates) -> str: Resolve prefix to unique book_id
- parse_id(entity_id) -> dict: Decompose hierarchical ID
- get_book_id(entity_id) -> str: Extract book_id from any hierarchical ID
"""

from pathlib import Path


class AmbiguousBookIdError(Exception):
    """Raised when a book_id prefix matches multiple books."""

    def __init__(self, prefix: str, candidates: list[str]):
        self.prefix = prefix
        self.candidates = candidates
        super().__init__(
            f"Prefijo '{prefix}' es ambiguo. Candidatos:\n"
            + "\n".join(f"  - {c}" for c in candidates)
        )


class BookNotFoundError(Exception):
    """Raised when no book matches the given prefix."""

    def __init__(self, prefix: str):
        self.prefix = prefix
        super().__init__(f"No se encontró ningún libro con prefijo '{prefix}'")


def resolve_book_id(prefix: str, candidates: list[str]) -> str:
    """Resolve a book_id prefix to a unique full book_id.

    Args:
        prefix: Partial or full book_id (e.g., "martin" or "martin-2008-clean")
        candidates: List of all available book_ids

    Returns:
        The unique matching book_id

    Raises:
        BookNotFoundError: If no candidates match the prefix
        AmbiguousBookIdError: If multiple candidates match the prefix
    """
    # Exact match first
    if prefix in candidates:
        return prefix

    # Prefix match
    matches = [c for c in candidates if c.startswith(prefix)]

    if len(matches) == 0:
        raise BookNotFoundError(prefix)
    elif len(matches) == 1:
        return matches[0]
    else:
        raise AmbiguousBookIdError(prefix, matches)


def get_available_book_ids(data_dir: Path | None = None) -> list[str]:
    """Get list of all available book_ids from data/books/.

    Args:
        data_dir: Path to data directory. Defaults to ./data

    Returns:
        List of book_id strings (directory names in data/books/)
    """
    if data_dir is None:
        data_dir = Path("data")

    books_dir = data_dir / "books"
    if not books_dir.exists():
        return []

    return [
        d.name
        for d in books_dir.iterdir()
        if d.is_dir() and not d.name.startswith(".")
    ]


def parse_id(entity_id: str) -> dict:
    """Parse a hierarchical entity ID into components.

    Examples:
        "martin-2008-clean" -> {"book_id": "martin-2008-clean"}
        "martin-2008-clean:ch:3" -> {"book_id": "martin-2008-clean", "chapter": 3}
        "martin-2008-clean:ch:3:sec:2" -> {"book_id": "...", "chapter": 3, "section": 2}
        "martin-2008-clean:unit:5" -> {"book_id": "martin-2008-clean", "unit": 5}

    Args:
        entity_id: Hierarchical ID string

    Returns:
        Dictionary with parsed components
    """
    parts = entity_id.split(":")
    result = {"book_id": parts[0]}

    i = 1
    while i < len(parts) - 1:
        key = parts[i]
        value = parts[i + 1]

        if key == "ch":
            result["chapter"] = int(value)
        elif key == "sec":
            result["section"] = int(value)
        elif key == "unit":
            result["unit"] = int(value)
        elif key == "ex":
            result["exercise"] = int(value)

        i += 2

    return result


def get_book_id(entity_id: str) -> str:
    """Extract book_id from any hierarchical ID.

    Args:
        entity_id: Any entity ID (book, chapter, section, unit, etc.)

    Returns:
        The book_id component
    """
    return entity_id.split(":")[0]
