"""照片分析器 — 调用 VLM API 进行照片分析与评分"""

import base64
import io
import json
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests
from PIL import Image, ExifTags

import config
import database

logger = logging.getLogger(__name__)

# ============================================================
# VLM 提示词（基于 InkTime 优化）
# ============================================================

SCORE_SYSTEM_PROMPT = """你是一个个人相册照片评估助手。你的任务是分析用户的照片，返回严格的 JSON。

你需要完成：
1. type：照片分类，从以下选项中选一个或两个（用/分隔）：
   人物/孩子/猫咪/家庭/旅行/风景/美食/宠物/日常/文档/杂物/其他
2. memory_score：0-100的回忆价值评分
3. beauty_score：0-100的美观度评分
4. reason：简短的评分理由（20字以内）

## memory_score 评分标准：

**低分区（0-39）**：
- 截图、文档扫描、账单、收据、测试图片 → 0-25
- 无意义的模糊照片、重复的废片 → 10-30

**中分区（40-69）**：
- 普通日常照片，有一定记录价值 → 40-55
- 较好的日常记录，但不算特别 → 55-69

**高分区（70-100）**：
- 有明确情感价值的照片 → 70-79
- 重要的生活事件、珍贵的人际瞬间 → 80-89
- 不可替代的珍贵记忆 → 90-100

**加分因素**（叠加计算）：
- 有清晰人脸/亲密关系 → +10~20
- 重要场合（婚礼、毕业、生日等）→ +5~15
- 不可替代性（再也拍不到的场景）→ +10~20
- 情感强度（明显的喜悦、感动）→ +5~10
- 风景美感 → +5~10
- 旅行场景 → +5

**特殊规则**：
- 孩子/婴儿的照片：基准分从75开始，再叠加加分
- 宠物（猫/狗等）：基准分从70开始
- 家庭合照：基准分从72开始

**beauty_score 评分标准**：
- 构图、光线、色彩的综合美感
- 0-30：技术问题明显（模糊、过曝、欠曝）
- 30-60：普通水平
- 60-80：好看的 photo
- 80-100：摄影级作品

输出格式（严格 JSON，不要包含 markdown 代码块标记）：
{"type":"...","memory_score":75,"beauty_score":60,"reason":"..."}"""


def encode_image(image_path: str) -> tuple[str, int, int]:
    """读取图片，压缩到最大长边，返回 base64 和尺寸"""
    try:
        img = Image.open(image_path)
    except Exception as e:
        logger.warning(f"无法打开图片 {image_path}: {e}")
        return None, 0, 0

    # 处理 EXIF 旋转
    try:
        from PIL import ImageOps
        img = ImageOps.exif_transpose(img)
    except Exception:
        pass

    width, height = img.size

    # 压缩到最大长边
    max_edge = config.VLM_MAX_LONG_EDGE
    if max(width, height) > max_edge:
        ratio = max_edge / max(width, height)
        new_w = int(width * ratio)
        new_h = int(height * ratio)
        img = img.resize((new_w, new_h), Image.LANCZOS)

    # 转 RGB
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
    return b64, width, height


def extract_exif(image_path: str) -> dict:
    """提取 EXIF 信息"""
    exif_data = {
        "exif_datetime": None,
        "exif_make": None,
        "exif_model": None,
        "exif_iso": None,
        "exif_exposure_time": None,
        "exif_f_number": None,
        "exif_focal_length": None,
        "exif_gps_lat": None,
        "exif_gps_lon": None,
        "exif_gps_alt": None,
        "exif_city": None,
        "exif_json": "{}",
    }
    try:
        img = Image.open(image_path)
        raw_exif = img._getexif()
        if not raw_exif:
            return exif_data

        # 标准化 tag 名
        tag_map = {v: k for k, v in ExifTags.TAGS.items()}
        gps_tag_map = {v: k for k, v in ExifTags.GPSTags.items()}

        # 日期时间
        for dt_tag in ("DateTimeOriginal", "DateTimeDigitized", "DateTime"):
            tag_id = tag_map.get(dt_tag)
            if tag_id and tag_id in raw_exif:
                dt_str = raw_exif[tag_id]
                # 转换 "2023:07:05 14:30:00" → "2023-07-05 14:30:00"
                exif_data["exif_datetime"] = dt_str.replace(":", "-", 2)
                break

        # 相机信息
        exif_data["exif_make"] = raw_exif.get(tag_map.get("Make", 0))
        exif_data["exif_model"] = raw_exif.get(tag_map.get("Model", 0))

        # 拍摄参数
        iso_tag = tag_map.get("ISOSpeedRatings")
        if iso_tag and iso_tag in raw_exif:
            iso_val = raw_exif[iso_tag]
            exif_data["exif_iso"] = iso_val[0] if isinstance(iso_val, tuple) else iso_val

        et_tag = tag_map.get("ExposureTime")
        if et_tag and et_tag in raw_exif:
            et_val = raw_exif[et_tag]
            exif_data["exif_exposure_time"] = float(et_val[0]) / float(et_val[1]) if isinstance(et_val, tuple) else float(et_val)

        fn_tag = tag_map.get("FNumber")
        if fn_tag and fn_tag in raw_exif:
            fn_val = raw_exif[fn_tag]
            exif_data["exif_f_number"] = float(fn_val[0]) / float(fn_val[1]) if isinstance(fn_val, tuple) else float(fn_val)

        fl_tag = tag_map.get("FocalLength")
        if fl_tag and fl_tag in raw_exif:
            fl_val = raw_exif[fl_tag]
            exif_data["exif_focal_length"] = float(fl_val[0]) / float(fl_val[1]) if isinstance(fl_val, tuple) else float(fl_val)

        # GPS
        gps_info = raw_exif.get(tag_map.get("GPSInfo", 0))
        if gps_info:
            def get_gps_coord(ref_tag, val_tag):
                ref = gps_info.get(gps_tag_map.get(ref_tag, 0))
                val = gps_info.get(gps_tag_map.get(val_tag, 0))
                if ref and val:
                    d, m, s = float(val[0][0])/float(val[0][1]), float(val[1][0])/float(val[1][1]), float(val[2][0])/float(val[2][1])
                    coord = d + m/60 + s/3600
                    if ref in ("S", "W"):
                        coord = -coord
                    return round(coord, 6)
                return None

            exif_data["exif_gps_lat"] = get_gps_coord("GPSLatitudeRef", "GPSLatitude")
            exif_data["exif_gps_lon"] = get_gps_coord("GPSLongitudeRef", "GPSLongitude")

            alt = gps_info.get(gps_tag_map.get("GPSAltitude", 0))
            alt_ref = gps_info.get(gps_tag_map.get("GPSAltitudeRef", 0))
            if alt:
                exif_data["exif_gps_alt"] = round(float(alt[0])/float(alt[1]) - (float(alt_ref) if alt_ref else 0), 1)

        # 保存原始 EXIF JSON
        safe_exif = {}
        for k, v in raw_exif.items():
            try:
                json.dumps(v)
                safe_exif[str(k)] = v
            except (TypeError, ValueError):
                safe_exif[str(k)] = str(v)
        exif_data["exif_json"] = json.dumps(safe_exif, ensure_ascii=False, default=str)

    except Exception as e:
        logger.debug(f"EXIF 提取失败 {image_path}: {e}")

    return exif_data


def call_vlm(image_b64: str) -> dict:
    """调用 VLM API 进行照片评分"""
    last_error = None
    channels = config.API_CHANNELS[:]

    for attempt in range(len(channels)):
        channel = channels[attempt % len(channels)]
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
                        {"role": "system", "content": SCORE_SYSTEM_PROMPT},
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": "请分析这张照片："},
                                {
                                    "type": "image_url",
                                    "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"},
                                },
                            ],
                        },
                    ],
                    "temperature": 0.3,
                    "max_tokens": 512,
                },
                timeout=config.TIMEOUT,
            )

            if resp.status_code == 429:
                logger.warning(f"API 限流，切换通道...")
                time.sleep(2)
                continue

            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"].strip()

            # 清理 markdown 代码块标记
            if content.startswith("```"):
                content = content.split("\n", 1)[1] if "\n" in content else content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

            result = json.loads(content)

            # 校验必要字段
            required = ("type", "memory_score", "beauty_score", "reason")
            if not all(k in result for k in required):
                raise ValueError(f"缺少字段: {set(required) - set(result.keys())}")

            # 限制分数范围
            result["memory_score"] = max(0, min(100, float(result["memory_score"])))
            result["beauty_score"] = max(0, min(100, float(result["beauty_score"])))

            return result

        except json.JSONDecodeError as e:
            last_error = f"JSON 解析失败: {e}, 原始内容: {content[:200]}"
            logger.warning(last_error)
        except Exception as e:
            last_error = str(e)
            logger.warning(f"VLM 调用失败 (通道 {channel['model_name']}): {e}")

        time.sleep(1)

    return {"error": last_error}





def scan_photos() -> list[str]:
    """扫描照片目录，返回待处理的文件路径列表"""
    photo_dir = Path(config.PHOTO_DIR)
    if not photo_dir.exists():
        logger.error(f"照片目录不存在: {photo_dir}")
        return []

    analyzed = database.get_analyzed_paths()
    new_photos = []

    for root, dirs, files in os.walk(photo_dir):
        # 排除系统目录
        dirs[:] = [d for d in dirs if d not in config.EXCLUDE_DIRS]

        for f in files:
            ext = Path(f).suffix.lower()
            if ext not in config.SUPPORTED_EXTENSIONS:
                continue

            full_path = str(Path(root) / f)
            if full_path in analyzed:
                continue

            new_photos.append(full_path)

    logger.info(f"扫描完成: 发现 {len(new_photos)} 张新照片")
    return new_photos


def analyze_one_photo(filepath: str) -> dict | None:
    """分析单张照片"""
    logger.info(f"分析: {filepath}")

    # 编码图片
    image_b64, width, height = encode_image(filepath)
    if not image_b64:
        return None

    # 提取 EXIF
    exif = extract_exif(filepath)

    # 判断方向
    if width > 0 and height > 0:
        if width > height * 1.1:
            orientation = "landscape"
        elif height > width * 1.1:
            orientation = "portrait"
        else:
            orientation = "square"
    else:
        orientation = "unknown"

    # 调用 VLM 评分
    vlm_result = call_vlm(image_b64)
    if "error" in vlm_result:
        logger.error(f"VLM 评分失败 {filepath}: {vlm_result['error']}")
        return None

    # 组装记录（旁白与专属描述统一在 daily 中生成）
    record = {
        "path": filepath,
        "type": vlm_result["type"],
        "memory_score": vlm_result["memory_score"],
        "beauty_score": vlm_result["beauty_score"],
        "reason": vlm_result["reason"],
        "width": width,
        "height": height,
        "orientation": orientation,
        "raw_json": json.dumps(vlm_result, ensure_ascii=False),
        **exif,
    }

    return record


def run_analysis():
    """运行照片分析（主入口）"""
    database.init_db()

    photos = scan_photos()
    if not photos:
        logger.info("没有新照片需要分析")
        return

    # 限制批次大小
    if config.BATCH_LIMIT:
        photos = photos[:config.BATCH_LIMIT]

    logger.info(f"开始分析 {len(photos)} 张照片，并发数: {config.CONCURRENCY}")

    success_count = 0
    fail_count = 0

    with ThreadPoolExecutor(max_workers=config.CONCURRENCY) as executor:
        futures = {executor.submit(analyze_one_photo, p): p for p in photos}

        for future in as_completed(futures):
            filepath = futures[future]
            try:
                record = future.result()
                if record:
                    database.insert_photo(record)
                    success_count += 1
                    logger.info(f"✓ [{success_count}/{len(photos)}] {os.path.basename(filepath)} "
                               f"→ 回忆:{record['memory_score']:.0f} 美观:{record['beauty_score']:.0f} "
                               f"[{record['type']}]")
                else:
                    fail_count += 1
            except Exception as e:
                fail_count += 1
                logger.error(f"✗ {filepath}: {e}")

    logger.info(f"分析完成: 成功 {success_count}, 失败 {fail_count}")
