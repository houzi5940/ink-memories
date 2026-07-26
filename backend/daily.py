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
DAILY_CAPTION_PROMPT = """你是一个擅长为老照片写“每日新感受”的中文文案助手。请为照片写一句 30-60 字的短评，像是翻相册时随口说出的一句话。

创作原则：
1. 重点写“看完后的余味”，而不是复述画面本身
2. 句子要自然、轻松，带一点诗意和余韵，避免过于文艺或鸡汤
3. 可以有幽默、轻微感慨、微妙怀旧，但不要煽情
4. 不要使用“这张照片”“这一刻”“这个瞬间”“照片里”等直接指向照片的说法
5. 不要使用“岁月”“时光”“温柔”“美好”“感动”“治愈”“世界”“梦”这类空泛词
6. 每次都换一种角度说，即使是同一人同一场景，也要避免重复
7. 可以有少量细节想象，但必须与照片中的事实不冲突

输出：只输出描述文字本身，不要引号，不要解释。"""

DAILY_SIDE_CAPTION_PROMPT = """你是一位为“电子相框”撰写旁白短句的中文文案助手。你的目标不是描述画面，而是让画面多出一点“画外之意”。

创作原则：
1. 只基于图片中能确定的信息进行联想，不要虚构时间、人物关系或事件背景
2. 文案要自然、有趣，带一点幽默或诗意，避免煽情和鸡汤
3. 不要复述画面内容本身，而是写“看完画面后，心里多出来的一句话”
4. 避免使用“世界、梦、时光、岁月、温柔、治愈、美好、回忆、珍惜、感动”这类空泛词
5. 避免使用“……里……着整个世界”“……里……着整个夏天”“像……”“比……还……”这类模板式比喻
6. 句子建议 8-20 个汉字，最多不超过 25 个汉字
7. 不要出现“这张照片”“这一刻”“那天”等直接指向照片本身的表达

输出：只输出一句中文短句，不要换行，不要引号。"""


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
                "temperature": 0.95,
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
                "temperature": 0.9,
                "max_tokens": 64,
            },
            timeout=30,
        )
        resp.raise_for_status()
        side = resp.json()["choices"][0]["message"]["content"].strip().strip('"').strip("'")
    except Exception as e:
        logger.warning(f"每日旁白生成失败: {e}")

    return caption or "", side or ""


def _pick_weighted(candidates: list[dict], count: int, recent: set[str], result: list[dict]) -> int:
    """从候选中挑选 count 张，优先挑近期未用过的

    Returns: 实际挑选的数量
    """
    existing_paths = {p["path"] for p in result}
    fresh = [p for p in candidates if p["path"] not in recent and p["path"] not in existing_paths]
    stale = [p for p in candidates if p["path"] in recent and p["path"] not in existing_paths]

    picked = []
    if fresh:
        n = min(count, len(fresh))
        picked = random.sample(fresh, n)
        count -= n
    if count > 0 and stale:
        n = min(count, len(stale))
        picked.extend(random.sample(stale, n))
        count -= n
    result.extend(picked)
    return len(picked)


def choose_photos_for_today(today: datetime = None, count: int = None) -> list[dict]:
    """
    选择今日精选照片

    算法：
    1. 查找所有年份同 MM-DD 的照片（memory_score >= 阈值）
    2. 随机挑选 count 张，优先选 60 天内未用过的
    3. 如果当天没有候选，向前回退最多 365 天
    4. 如果 365 天都没有，从全库最高分中选
    """
    if today is None:
        today = datetime.now()
    if count is None:
        count = config.DAILY_PHOTO_QUANTITY

    # 获取近期（60 天）用过的照片路径
    recent = database.get_recently_used_paths(days=60)
    result = []

    # 策略 1：同月同日（历史上的今天）
    mm_dd = today.strftime("%m-%d")
    candidates = database.get_photos_by_date(mm_dd)
    if candidates:
        _pick_weighted(candidates, count, recent, result)
        count = config.DAILY_PHOTO_QUANTITY - len(result)

    # 策略 2：向前回退最多 365 天
    if count > 0:
        for offset in range(1, 366):
            target_date = today - timedelta(days=offset)
            target_mm_dd = target_date.strftime("%m-%d")
            if target_mm_dd == mm_dd:
                continue
            candidates = database.get_photos_by_date(target_mm_dd)
            if candidates:
                n = _pick_weighted(candidates, count, recent, result)
                count -= n
                if count <= 0:
                    break

    # 策略 3：全库最高分兜底
    if count > 0:
        top = database.get_top_photos(count * 5)
        _pick_weighted(top, count, recent, result)

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
