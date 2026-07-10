"""Tag and status API routes."""

from fastapi import APIRouter, Depends

from backend import config
from backend.dependencies import get_db


router = APIRouter()


@router.get("/api/tags")
def api_tags(db=Depends(get_db)):
    """获取所有已存在的手动标签及其使用数量（用于编辑下拉选择）

    返回形如 [{"tag": "旅行", "count": 5}, ...]，按使用数量降序。
    """
    return db.get_tag_distribution()


@router.get("/api/status")
def api_status(db=Depends(get_db)):
    """获取系统状态"""
    return {
        "photo_dir": config.PHOTO_DIR,
        "total_photos": db.get_photo_count(),
        "types": db.get_type_distribution(),
    }
