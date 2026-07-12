"""Jinja2 template engine setup for FastAPI."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.templating import Jinja2Templates
from jinja2 import pass_context

from backend import config


TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "frontend" / "templates"


templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@pass_context
def _url_for(context: dict, endpoint: str, **kwargs: object) -> str:
    """Flask-compatible url_for for Jinja2 templates.

    Supports:
      - url_for('static', filename='style.css') -> /static/style.css?v=...
      - url_for('index') -> uses request.url_for('index')

    Static files include a cache-busting query parameter based on mtime.
    """
    if endpoint == "static":
        filename = kwargs.get("filename", "")
        path = f"/static/{filename}"
        try:
            file_path = Path(__file__).resolve().parent.parent / "frontend" / "static" / filename
            mtime = file_path.stat().st_mtime
            return f"{path}?v={int(mtime)}"
        except (OSError, FileNotFoundError):
            return path
    request = context.get("request")
    if request is None:
        raise ValueError("url_for requires 'request' in template context")
    return str(request.url_for(endpoint, **kwargs))


def _fromjson_filter(value: object) -> object:
    """Parse a JSON string into a Python object."""
    try:
        return json.loads(value) if value else []  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return []


def _relphoto_filter(path: str | None) -> str:
    """Return a photo path relative to PHOTO_DIR for URL generation."""
    if not path:
        return ""
    photo_dir = config.PHOTO_DIR.rstrip("/") + "/"
    if path.startswith(photo_dir):
        return path[len(photo_dir) :]
    return path.lstrip("/")


def _safe_score(value: float | None) -> str:
    """安全格式化评分，处理 None 值"""
    if value is None:
        return "-"
    return f"{value:.0f}"


templates.env.globals["url_for"] = _url_for
templates.env.filters["fromjson"] = _fromjson_filter
templates.env.filters["relphoto"] = _relphoto_filter
templates.env.filters["safescore"] = _safe_score
