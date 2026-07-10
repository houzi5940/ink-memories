"""Photo serving and photo-related API routes."""

import logging
import os
import threading
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from backend import config, database
from backend.analyzer import run_analysis
from backend.dependencies import get_db


router = APIRouter()
logger = logging.getLogger(__name__)


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
    """提供照片文件（缩略图）

    兼容三种传入形式：
    - 相对 PHOTO_DIR 的路径（如 sample2.jpg，来自 relphoto 过滤器）
    - 绝对路径（如 /Users/.../sample2.jpg）
    - 被去掉前导斜杠的绝对路径（如 Users/.../sample2.jpg，来自编辑弹窗预览）
    """
    photo_dir = os.path.realpath(config.PHOTO_DIR)

    candidates = []
    if filepath.startswith("/"):
        candidates.append(filepath)
    else:
        candidates.append(os.path.join(config.PHOTO_DIR, filepath))
        candidates.append("/" + filepath)

    full_path = None
    for candidate in candidates:
        resolved = os.path.realpath(candidate)
        # 限制在 PHOTO_DIR 内，防止路径穿越
        if resolved == photo_dir or resolved.startswith(photo_dir + os.sep):
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
def api_analyze():
    """触发分析（后台运行）"""

    def run():
        try:
            run_analysis()
        except Exception as e:
            logger.error(f"分析任务失败: {e}")

    t = threading.Thread(target=run, daemon=True)
    t.start()
    return {"status": "started", "message": "分析任务已启动"}


@router.get("/api/photo/detail")
def api_photo_detail(path: str = Query(...), db=Depends(get_db)):
    """获取单张照片详情"""
    if not path:
        raise HTTPException(status_code=400, detail="缺少 path")
    photo = db.get_photo_by_path(path)
    if not photo:
        raise HTTPException(status_code=404, detail="未找到")
    return photo


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
