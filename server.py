"""Flask WebUI — 照片浏览、管理和编辑"""

import os
import logging
import json
from pathlib import Path

from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for

import config
import database
import daily

app = Flask(__name__)
logger = logging.getLogger(__name__)


def init():
    """初始化数据库"""
    database.init_db()


@app.before_request
def before_request():
    database.init_db()


# ============================================================
# 页面路由
# ============================================================

@app.route("/")
def index():
    """首页 — 今日精选"""
    summary = daily.get_daily_summary()
    return render_template("index.html", summary=summary)


@app.route("/gallery")
def gallery():
    """照片库"""
    page = int(request.args.get("page", 1))
    per_page = 20
    order = request.args.get("order", "memory_score DESC")
    photo_type = request.args.get("type", "")

    if photo_type:
        # 按类型筛选
        photos = database.search_photos(photo_type, limit=per_page * 10)
        photos = [p for p in photos if photo_type in (p.get("type") or "")]
        total = len(photos)
        photos = photos[(page-1)*per_page : page*per_page]
    else:
        total = database.get_photo_count()
        photos = database.get_all_photos(limit=per_page, offset=(page-1)*per_page, order_by=order)

    total_pages = max(1, (total + per_page - 1) // per_page)

    return render_template("gallery.html",
                           photos=photos,
                           page=page,
                           total_pages=total_pages,
                           total=total,
                           current_order=order,
                           current_type=photo_type)


@app.route("/stats")
def stats():
    """统计页面"""
    return render_template("stats.html",
                           total=database.get_photo_count(),
                           types=database.get_type_distribution(),
                           scores=database.get_score_distribution())


@app.route("/search")
def search():
    """搜索"""
    q = request.args.get("q", "").strip()
    photos = database.search_photos(q) if q else []
    return render_template("search.html", photos=photos, query=q)


# ============================================================
# API 路由
# ============================================================

@app.route("/photo/<path:filepath>")
def serve_photo(filepath):
    """提供照片文件（缩略图）"""
    # 保证路径以 / 开头（模板中 lstrip 后可能是相对路径）
    if not filepath.startswith("/"):
        filepath = "/" + filepath
    # 安全检查：只允许从 PHOTO_DIR 下读取
    full_path = os.path.realpath(filepath)
    photo_dir = os.path.realpath(config.PHOTO_DIR)

    if not full_path.startswith(photo_dir):
        return "Forbidden", 403

    if not os.path.exists(full_path):
        return "Not Found", 404

    try:
        return send_file(full_path, max_age=3600)
    except Exception as e:
        logger.error(f"提供照片失败 {filepath}: {e}")
        return "Error", 500


@app.route("/api/analyze", methods=["POST"])
def api_analyze():
    """触发分析（后台运行）"""
    import threading
    from analyzer import run_analysis

    def run():
        try:
            run_analysis()
        except Exception as e:
            logger.error(f"分析任务失败: {e}")

    t = threading.Thread(target=run, daemon=True)
    t.start()
    return jsonify({"status": "started", "message": "分析任务已启动"})


@app.route("/api/status")
def api_status():
    """获取系统状态"""
    return jsonify({
        "photo_dir": config.PHOTO_DIR,
        "total_photos": database.get_photo_count(),
        "types": database.get_type_distribution(),
    })


@app.route("/api/photo/update", methods=["POST"])
def api_photo_update():
    """手动更新照片的评分、标签、旁白"""
    data = request.get_json(force=True)
    path = data.get("path")
    if not path:
        return jsonify({"error": "缺少 path"}), 400

    # 允许更新的字段
    updates = {}
    for key in ("memory_score", "beauty_score", "type", "side_caption", "caption", "reason"):
        if key in data and data[key] is not None and data[key] != "":
            val = data[key]
            if key in ("memory_score", "beauty_score"):
                try:
                    val = float(val)
                    val = max(0, min(100, val))
                except (ValueError, TypeError):
                    continue
            updates[key] = val

    if updates:
        database.update_photo(path, updates)
        return jsonify({"status": "ok", "updated": updates})
    return jsonify({"error": "没有可更新的字段"}), 400


@app.route("/api/photo/detail", methods=["GET"])
def api_photo_detail():
    """获取单张照片详情"""
    path = request.args.get("path")
    if not path:
        return jsonify({"error": "缺少 path"}), 400
    photo = database.get_photo_by_path(path)
    if not photo:
        return jsonify({"error": "未找到"}), 404
    return jsonify(photo)


# ============================================================
# 启动
# ============================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    database.init_db()
    app.run(host=config.FLASK_HOST, port=config.FLASK_PORT, debug=False)
