"""InkMemories 配置文件"""

import os

# ============================================================
# 照片源
# ============================================================
PHOTO_DIR = "/photos"  # Docker 容器内挂载路径
SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".heic", ".heif"}
EXCLUDE_DIRS = ["@eaDir", "#recycle", "@__thumb", "@SynoPhotoParcel"]

# ============================================================
# 数据库
# ============================================================
DB_PATH = "/data/photos.db"  # Docker 容器内持久化路径

# ============================================================
# VLM API 配置（支持多通道轮询 + 故障转移）
# ============================================================
API_CHANNELS = [
    {
        "api_url": os.environ.get("VLM_API_URL", "https://api.deepseek.com/v1/chat/completions"),
        "api_key": os.environ.get("VLM_API_KEY", ""),
        "model_name": os.environ.get("VLM_MODEL", "deepseek-chat"),
    },
]
BATCH_LIMIT = int(os.environ.get("BATCH_LIMIT", "0")) or None  # 0 = 不限制
TIMEOUT = int(os.environ.get("TIMEOUT", "120"))
CHANNEL_FAILOVER_COOLDOWN_SEC = 300

# ============================================================
# 分析参数
# ============================================================
VLM_MAX_LONG_EDGE = 2560  # 发送给 VLM 的图片最大长边
CONCURRENCY = int(os.environ.get("CONCURRENCY", "2"))

# ============================================================
# 精选参数
# ============================================================
MEMORY_THRESHOLD = 70.0  # 最低回忆分
DAILY_PHOTO_QUANTITY = 5  # 每日精选数量

# ============================================================
# WebUI
# ============================================================
FLASK_HOST = "0.0.0.0"
FLASK_PORT = int(os.environ.get("WEB_PORT", "8765"))
