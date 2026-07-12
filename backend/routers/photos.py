"""Photo serving and photo-related API routes."""

import asyncio
import logging
import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from backend import config, database
from backend.analyzer import run_analysis_async, analyze_selected_photos
from backend import progress as pr
from backend.dependencies import get_db


router = APIRouter()
logger = logging.getLogger(__name__)

def create_background_task(coro, task_name: str):
    task = asyncio.create_task(coro)

    def _handle_done(t: asyncio.Task):
        if t.cancelled():
            logger.warning(f"{task_name} 后台任务被取消")
            return
        exc = t.exception()
        if exc:
            logger.error(f"{task_name} 后台任务失败: {exc}", exc_info=exc)

    task.add_done_callback(_handle_done)
    return task


class PhotoUpdatePayload(BaseModel):
    path: str
    memory_score: Optional[float] = None
    beauty_score: Optional[float] = None
    type: Optional[str] = None
    side_caption: Optional[str] = None
    caption: Optional[str] = None
    reason: Optional[str] = None
    tags: Optional[List[str]] = None


@router.get("/photo/{filepath:path}")
def serve_photo(filepath: str):
    """提供照片文件

    兼容三种传入形式：
    - 相对 PHOTO_DIR 的路径（如 sample2.jpg，来自 relphoto 过滤器）
    - 绝对路径（如 /Users/.../sample2.jpg）
    - 被去掉前导斜杠的绝对路径（如 Users/.../sample2.jpg，来自编辑弹窗预览）

    HEIC/HEIF 文件自动转码为 JPEG（浏览器不原生支持 HEIC）。
    """
    from io import BytesIO
    from pathlib import Path as PathLib

    if not filepath:
        raise HTTPException(status_code=404, detail="Not Found")

    photo_dir = os.path.realpath(config.PHOTO_DIR)
    filepath_no_slash = filepath.lstrip("/")

    candidates = [
        filepath,
        os.path.join(config.PHOTO_DIR, filepath_no_slash),
        "/" + filepath_no_slash,
    ]

    full_path = None
    for candidate in candidates:
        resolved = os.path.realpath(candidate)
        # 限制在 PHOTO_DIR 内，防止路径穿越。使用 commonpath 可正确处理 PHOTO_DIR 为 / 的情况。
        if os.path.commonpath([photo_dir, resolved]) == photo_dir:
            if os.path.exists(resolved):
                full_path = resolved
                break

    if not full_path:
        raise HTTPException(status_code=404, detail="Not Found")

    try:
        return FileResponse(full_path, headers={"Cache-Control": "max-age=3600"})
    except Exception as e:
        logger.error(f"提供照片失败 {filepath}: {e}")
        raise HTTPException(status_code=500, detail="Error")


@router.post("/api/analyze")
async def api_analyze():
    """触发分析（后台运行）"""
    try:
        create_background_task(run_analysis_async(), "全量分析")
    except Exception as e:
        logger.error(f"分析任务启动失败: {e}")
        raise HTTPException(status_code=500, detail="分析任务启动失败")
    return {"status": "started", "message": "分析任务已启动"}


@router.get("/api/analyze/progress")
def api_analyze_progress():
    """获取分析进度"""
    return pr.get_progress()


@router.get("/api/photo/detail")
def api_photo_detail(path: str = Query(...), db=Depends(get_db)):
    """获取单张照片详情"""
    if not path:
        raise HTTPException(status_code=400, detail="缺少 path")
    photo = db.get_photo_by_path(path)
    if not photo:
        raise HTTPException(status_code=404, detail="未找到")
    return photo


class PhotoPathPayload(BaseModel):
    path: str


@router.post("/api/photo/analyze")
async def api_photo_analyze(payload: PhotoPathPayload):
    """重新分析单张照片"""
    if not payload.path:
        raise HTTPException(status_code=400, detail="缺少 path")

    try:
        create_background_task(analyze_selected_photos([payload.path]), "单张照片重新分析")
    except Exception as e:
        logger.error(f"重新分析任务启动失败: {e}")
        raise HTTPException(status_code=500, detail="重新分析任务启动失败")

    return {
        "status": "started",
        "message": "重新分析任务已启动，完成后请刷新页面查看结果",
    }


@router.post("/api/photo/update")
def api_photo_update(payload: PhotoUpdatePayload, db=Depends(get_db)):
    """手动更新照片的评分、标签、旁白"""
    data = payload.model_dump(exclude_unset=True)
    path = data.pop("path", None)
    if not path:
        raise HTTPException(status_code=400, detail="缺少 path")

    updates: Dict[str, Any] = {}
    for key, val in data.items():
        if val is None:
            continue
        if key in ("memory_score", "beauty_score"):
            try:
                val = float(val)
                val = max(0, min(100, val))
            except (ValueError, TypeError):
                continue
        elif key == "tags":
            if isinstance(val, str):
                val = [t.strip() for t in val.replace("，", ",").split(",") if t.strip()]
            if not isinstance(val, list):
                continue
        updates[key] = val

    if updates:
        db.update_photo(path, updates)
        return {"status": "ok", "updated": updates}
    raise HTTPException(status_code=400, detail="没有可更新的字段")


# ============================================================
# 人工审核 API
# ============================================================

class ReviewPathsPayload(BaseModel):
    paths: list[str]


@router.get("/api/review/photos")
def api_review_photos(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    """获取未评分的照片列表（按文件修改时间排序，最新的在前）"""
    from backend.database import scan_unanalyzed_photos, get_unanalyzed_count

    photos = scan_unanalyzed_photos(limit=limit, offset=offset)
    total = get_unanalyzed_count()
    return {"photos": photos, "total": total}


@router.post("/api/review/submit")
async def api_review_submit(payload: ReviewPathsPayload):
    """提交选中照片进行 VLM 评分"""
    if not payload.paths:
        raise HTTPException(status_code=400, detail="没有选择照片")

    from backend.analyzer import analyze_selected_photos

    try:
        create_background_task(analyze_selected_photos(payload.paths), "选中照片分析")
    except Exception as e:
        logger.error(f"选中照片分析启动失败: {e}")
        raise HTTPException(status_code=500, detail="分析任务启动失败")

    return {
        "status": "started",
        "message": f"已提交 {len(payload.paths)} 张照片进行分析",
    }


@router.post("/api/review/skip")
def api_review_skip(payload: ReviewPathsPayload):
    """跳过未勾选的照片（标记为已处理）"""
    if not payload.paths:
        return {"status": "ok", "skipped": 0}

    from backend.database import batch_skip_photos

    batch_skip_photos(payload.paths)
    return {"status": "ok", "skipped": len(payload.paths)}
