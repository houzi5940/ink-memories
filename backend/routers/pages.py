"""HTML page routes."""

import json
from typing import Optional

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from backend import daily
from backend.dependencies import get_db
from backend.templates import templates


router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def index(request: Request, db=Depends(get_db)):
    """首页 — 今日精选"""
    summary = daily.get_daily_summary()
    return templates.TemplateResponse(
        request, "index.html", {"summary": summary}
    )


@router.get("/gallery", response_class=HTMLResponse)
def gallery(
    request: Request,
    page: int = 1,
    order: str = "memory_score DESC",
    type: Optional[str] = "",
    tag: Optional[str] = "",
    db=Depends(get_db),
):
    """照片库"""
    per_page = 20
    photo_type = type or ""
    current_tag = tag or ""

    if photo_type:
        photos = db.search_photos(photo_type, limit=per_page * 10)
        photos = [p for p in photos if photo_type in (p.get("type") or "")]
        total = len(photos)
        photos = photos[(page - 1) * per_page : page * per_page]
    elif current_tag:
        photos = db.search_photos(current_tag, limit=per_page * 10)
        photos = [
            p
            for p in photos
            if current_tag in [t.strip() for t in (json.loads(p["tags"]) if p.get("tags") else [])]
        ]
        total = len(photos)
        photos = photos[(page - 1) * per_page : page * per_page]
    else:
        total = db.get_photo_count()
        photos = db.get_all_photos(limit=per_page, offset=(page - 1) * per_page, order_by=order)

    total_pages = max(1, (total + per_page - 1) // per_page)

    return templates.TemplateResponse(
        request,
        "gallery.html",
        {
            "photos": photos,
            "page": page,
            "total_pages": total_pages,
            "total": total,
            "current_order": order,
            "current_type": photo_type,
            "current_tag": current_tag,
        },
    )


@router.get("/stats", response_class=HTMLResponse)
def stats(request: Request, db=Depends(get_db)):
    """统计页面"""
    return templates.TemplateResponse(
        request,
        "stats.html",
        {
            "total": db.get_photo_count(),
            "types": db.get_type_distribution(),
            "scores": db.get_score_distribution(),
            "tags": db.get_tag_distribution(),
        },
    )


@router.get("/search", response_class=HTMLResponse)
def search(request: Request, q: Optional[str] = "", db=Depends(get_db)):
    """搜索"""
    query = (q or "").strip()
    photos = db.search_photos(query) if query else []
    return templates.TemplateResponse(
        request, "search.html", {"photos": photos, "query": query}
    )


@router.get("/review", response_class=HTMLResponse)
def review_page(request: Request):
    """人工审核页"""
    return templates.TemplateResponse(request, "review.html")
