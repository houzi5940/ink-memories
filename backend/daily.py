"""每日精选 — 从「历史上的今天」中选出最值得回忆的照片"""

import json
import logging
import random
import time
from datetime import datetime, timedelta

import requests

from backend import config, database

logger = logging.getLogger(__name__)


# 每日精选的创意描述提示词 — 每次生成不一样的描述
DAILY_CAPTION_PROMPT = """你是一个为老照片写每日新感受的文案高手。规则：

1. 用 30-60 字描述你今天看到这张照片的感想，要像老朋友翻相册时随口说的话
2. 每张照片的描述要不同，即使是同一个人同一场景，换一个角度说
3. 不要写"这张照片"、"这一刻"、"这个瞬间"、"照片中"等词
4. 可以随意编造有趣的细节，只要不偏离照片的事实
5. 风格：轻松、自然，像随口说出来的话，不要太文艺
6. 可以幽默，可以感慨，可以怀旧，每次不同
7. 不要用"岁月"、"时光"、"温柔"、"美好"、"感动"这类词

输出：只说描述文字本身，不要引号，不要多余内容。"""

DAILY_SIDE_CAPTION_PROMPT = """为这张照片写一句8-20字的旁白，像随口一句话，不要用书名号、引号。

要求：
- 不要用"世界、梦、时光、岁月、温柔、治愈、美好、回忆、珍惜、感动"这些词
- 要具体、有画面感，不要抽象抒情
- 每天写出来的风格可以不同，今天可以幽默，明天可以安静
- 像是偶然翻到这张照片时脱口而出的话

输出：只说旁白本身，不要引号。"""


def _generate_daily_captions_for_photo(photo: dict) -> tuple[str, str]:
    """为单张照片生成本日专属的描述和旁白（基于 analyzer 的评分与类型）"""
    if not config.API_CHANNELS:
        return "", ""

    channel = config.API_CHANNELS[0]
    base_info = (
        f"照片类型：{photo.get('type','未知')}  "
        f"回忆评分：{photo.get('memory_score', 0):.0f}  "
        f"美观评分：{photo.get('beauty_score', 0):.0f}  "
        f"评分理由：{photo.get('reason','')[:80]}"
    )

    caption = None
    try:
        resp = requests.post(
            channel["api_url"],
            headers={
                "Authorization": f"Bearer {channel['api_key']}",
                "Content-Type": "application/json",
            },
            json={
                "model": channel["model_name"],
                "messages": [
                    {"role": "system", "content": DAILY_CAPTION_PROMPT},
                    {"role": "user", "content": base_info},
                ],
                "temperature": 0.9,
                "max_tokens": 120,
            },
            timeout=30,
        )
        resp.raise_for_status()
        caption = resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logger.warning(f"每日描述生成失败: {e}")

    side = None
    try:
        resp = requests.post(
            channel["api_url"],
            headers={
                "Authorization": f"Bearer {channel['api_key']}",
                "Content-Type": "application/json",
            },
            json={
                "model": channel["model_name"],
                "messages": [
                    {"role": "system", "content": DAILY_SIDE_CAPTION_PROMPT},
                    {"role": "user", "content": base_info},
                ],
                "temperature": 0.85,
                "max_tokens": 64,
            },
            timeout=30,
        )
        resp.raise_for_status()
        side = resp.json()["choices"][0]["message"]["content"].strip().strip('"').strip("'")
    except Exception as e:
        logger.warning(f"每日旁白生成失败: {e}")

    return caption or "", side or ""


def choose_photos_for_today(today: datetime = None, count: int = None) -> list[dict]:
    """
    选择今日精选照片

    算法：
    1. 查找所有年份同 MM-DD 的照片（memory_score >= 阈值）
    2. 随机挑选 count 张
    3. 如果当天没有候选，向前回退最多 365 天
    4. 如果 365 天都没有，从全库最高分中选
    """
    if today is None:
        today = datetime.now()
    if count is None:
        count = config.DAILY_PHOTO_QUANTITY

    result = []

    # 策略 1：同月同日（历史上的今天）
    mm_dd = today.strftime("%m-%d")
    candidates = database.get_photos_by_date(mm_dd)
    if candidates:
        picked = random.sample(candidates, min(count, len(candidates)))
        result.extend(picked)
        count -= len(picked)

    # 策略 2：向前回退最多 365 天
    if count > 0:
        for offset in range(1, 366):
            target_date = today - timedelta(days=offset)
            target_mm_dd = target_date.strftime("%m-%d")
            if target_mm_dd == mm_dd:
                continue
            candidates = database.get_photos_by_date(target_mm_dd)
            if candidates:
                picked = random.sample(candidates, min(count, len(candidates)))
                # 去重
                existing_paths = {p["path"] for p in result}
                picked = [p for p in picked if p["path"] not in existing_paths]
                result.extend(picked)
                count -= len(picked)
                if count <= 0:
                    break

    # 策略 3：全库最高分兜底
    if count > 0:
        top = database.get_top_photos(count * 3)
        existing_paths = {p["path"] for p in result}
        for p in top:
            if count <= 0:
                break
            if p["path"] not in existing_paths:
                result.append(p)
                existing_paths.add(p["path"])
                count -= 1

    return result


def get_daily_summary() -> dict:
    """获取今日精选摘要（带每日全新描述）"""
    today = datetime.now()
    date_str = today.strftime("%Y-%m-%d")

    # 先查今日精选缓存
    cached_paths = database.get_daily_selection(date_str)
    if cached_paths:
        # 从 DB 按路径加载照片数据
        photos = []
        for p in cached_paths:
            photo = database.get_photo_by_path(p)
            if photo:
                photos.append(photo)
    else:
        # 首次访问：生成今日精选并缓存
        photos = choose_photos_for_today(today)
        if photos:
            database.save_daily_selection(date_str, photos)

    # 检查是否有今日的缓存描述
    cached = database.get_daily_captions(date_str)
    needs_gen = []

    for photo in photos:
        path = photo["path"]
        if path not in cached:
            needs_gen.append(photo)

    # 生成本日新描述
    if needs_gen:
        logger.info(f"生成本日 {len(needs_gen)} 张照片的专属描述...")
        for photo in needs_gen:
            cap, side = _generate_daily_captions_for_photo(photo)
            database.save_daily_caption(photo["path"], date_str, cap, side)
            time.sleep(0.3)  # 避免 API 限流

        # 重新读取
        cached = database.get_daily_captions(date_str)

    # 合并每日描述到照片数据中
    for photo in photos:
        daily = cached.get(photo["path"], {})
        if daily:
            photo["daily_caption"] = daily.get("caption", "")
            photo["daily_side_caption"] = daily.get("side_caption", "")

    return {
        "date": date_str,
        "weekday": ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][today.weekday()],
        "photos": photos,
        "total_in_db": database.get_photo_count(),
    }
