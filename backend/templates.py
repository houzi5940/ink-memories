"""Jinja2 template engine setup for FastAPI."""

import json
from pathlib import Path

from fastapi.templating import Jinja2Templates
from jinja2 import pass_context


TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "frontend" / "templates"


templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@pass_context
def _url_for(context: dict, endpoint: str, **kwargs: object) -> str:
    """Flask-compatible url_for for Jinja2 templates.

    Supports:
      - url_for('static', filename='style.css') -> /static/style.css
      - url_for('index') -> uses request.url_for('index')
    """
    if endpoint == "static":
        filename = kwargs.get("filename", "")
        return f"/static/{filename}"
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


templates.env.globals["url_for"] = _url_for
templates.env.filters["fromjson"] = _fromjson_filter
