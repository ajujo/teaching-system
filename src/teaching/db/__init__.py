"""Database module for SQLite persistence.

Provides:
- Database connection management
- Schema initialization
- Repository functions for books table (F2)

Future phases will add:
- Progress tracking (F4+)
- Attempts and corrections (F5+)
- Exam results (F6+)
"""

from teaching.db.database import get_db, init_db

__all__ = ["get_db", "init_db"]
