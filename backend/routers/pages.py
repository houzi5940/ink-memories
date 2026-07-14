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
    current_tag = tag or ""

    # 类型筛选：逗号分隔多选，如 type=人物,旅行
    selected_types = [t.strip() for t in type.split(",") if t.strip()] if type else []
    filter_skipped = "跳过" in selected_types
    # 非跳过模式默认排除 status=skipped
    exclude_skipped = not filter_skipped

    if filter_skipped:
        # 只显示跳过的照片
        total = db.get_photo_count(status="skipped")
        photos = db.get_all_photos(
            limit=per_page, offset=(page - 1) * per_page,
            order_by=order, status="skipped",
        )
    elif selected_types:
        # 多类型 OR 匹配：搜索每个类型后合并去重
        all_photos = []
        seen = set()
        for t in selected_types:
            batch = db.search_photos(t, limit=per_page * 20)
            for p in batch:
                if p["path"] in seen:
                    continue
                # 精确匹配 type 字段包含该类型
                if t in (p.get("type") or ""):
                    if p.get("status") != "skipped":
                        seen.add(p["path"])
                        all_photos.append(p)
        # 按 memory_score 降序
        all_photos.sort(key=lambda p: -(p.get("memory_score") or 0))
        total = len(all_photos)
        photos = all_photos[(page - 1) * per_page : page * per_page]
    elif current_tag:
        photos = db.search_photos(current_tag, limit=per_page * 10)
        photos = [
            p
            for p in photos
            if current_tag in [t.strip() for t in (json.loads(p["tags"]) if p.get("tags") else [])]
        ]
        photos = [p for p in photos if p.get("status") != "skipped"]
        total = len(photos)
        photos = photos[(page - 1) * per_page : page * per_page]
    else:
        total = db.get_photo_count(exclude_skipped=True)
        photos = db.get_all_photos(limit=per_page, offset=(page - 1) * per_page, order_by=order, exclude_skipped=True)

    total_pages = max(1, (total + per_page - 1) // per_page)
    page = max(1, min(page, total_pages))

    return templates.TemplateResponse(
        request,
        "gallery.html",
        {
            "photos": photos,
            "page": page,
            "total_pages": total_pages,
            "total": total,
            "current_order": order,
            "current_type": type or "",
            "selected_types": selected_types,
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
