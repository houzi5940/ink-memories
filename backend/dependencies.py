"""FastAPI dependencies."""

from backend import database


def get_db():
    """Ensure the database is initialized before handling a request."""
    database.init_db()
    return database
