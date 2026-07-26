#!/usr/bin/env python3
"""每日精选 → NeoFrame 墨水屏（模仿 InkTime 的选片+渲染逻辑）

流程:
  load_photos() → choose_photos_for_today() → render_card() → dither + push
"""

from __future__ import annotations

import logging
import os
import random
import sqlite3
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

# ══ venv 自动检测 ════════════════════════════════════════════
PROJECT_DIR = Path(__file__).resolve().parent
_VENV = PROJECT_DIR / "venv" / "bin" / "python"
if _VENV.exists() and sys.executable != str(_VENV):
    os.execv(str(_VENV), [str(_VENV)] + sys.argv)

try:
    import requests
    from PIL import Image, ImageDraw, ImageFont, ImageOps
except ImportError as e:
    print(f"缺少依赖: {e}")
    sys.exit(1)

try:
    import pillow_heif; pillow_heif.register_heif_opener()
except ImportError:
    pass

# 加载 .env（如果存在）
_env_file = PROJECT_DIR / ".env"
if _env_file.exists():
    for line in _env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger("daily")

# ══ 配置 ═══════════════════════════════════════════════════════

DB_PATH = PROJECT_DIR / "data" / "photos.db"
MEMORY_THRESHOLD = 70.0   # 最低回忆分
DAILY_QUANTITY = 1        # 每日推送张数

# NAS 配置（从环境变量读取，默认值用于局域网本地开发）
NEOFRAME_HOST = os.environ.get("NEOFRAME_HOST", "192.168.1.248")
NAS_USER    = os.environ.get("NAS_USER", "username")
NAS_PASS    = os.environ.get("NAS_PASS", "")
NAS_HOST    = os.environ.get("NAS_HOST", "192.168.1.244")
NAS_SHARE   = os.environ.get("NAS_SHARE", "homes")
NAS_USER_ID = os.environ.get("NAS_USER_ID", NAS_USER)  # SMB UID，默认与用户名相同
NAS_MOUNT   = Path(os.environ.get("NAS_MOUNT", "/tmp/nas_homes"))
NAS_PHOTO   = NAS_MOUNT / NAS_USER_ID / "Photos"

# 7.3 寸 6 色墨水屏
W, H = 480, 800
PHOTO_AREA_H = 580
TEXT_AREA_H = 220

# 字体
FONT_PATH = "/System/Library/Fonts/STHeiti Medium.ttc"

# NAS 路径映射
NAS_MOUNT = Path("/tmp/nas_homes")
NAS_PHOTO = NAS_MOUNT / "871669332" / "Photos"

# ══ NAS 挂载 ═══════════════════════════════════════════════════

def _ensure_nas() -> Optional[Path]:
    if NAS_PHOTO.exists():
        try: next(NAS_PHOTO.iterdir()); return NAS_PHOTO
        except: pass
    NAS_MOUNT.mkdir(parents=True, exist_ok=True)
    os.system(f'mount_smbfs //{NAS_USER}:{NAS_PASS}@{NAS_HOST}/{NAS_SHARE} "{NAS_MOUNT}" 2>/dev/null')
    return NAS_PHOTO if NAS_PHOTO.exists() else None

def _nas_path(docker_path: str) -> Path:
    """将 Docker 内路径 /photos/xxx → NAS 挂载路径"""
    if not docker_path.startswith("/photos/"):
        return Path(docker_path)
    p = Path(docker_path[len("/photos/"):])
    # 先看 NAS 有没有
    nas = _ensure_nas()
    if nas:
        local = nas / p
        if local.exists():
            return local
    return Path(docker_path)

# ══ 色彩处理（对齐 neoframe.html）══════════════════════════════

PALETTE = [
    (255, 255, 0,   0xe2),   # Yellow
    (41,  204, 20,  0x96),   # Green
    (0,   0,   255, 0x1d),   # Blue
    (255, 0,   0,   0x4c),   # Red
    (0,   0,   0,   0x00),   # Black
    (255, 255, 255, 0xff),   # White
]

def _rgb2lab(r, g, b):
    r/=255; g/=255; b/=255
    r = ((r+0.055)/1.055)**2.4 if r>0.04045 else r/12.92
    g = ((g+0.055)/1.055)**2.4 if g>0.04045 else g/12.92
    b = ((b+0.055)/1.055)**2.4 if b>0.04045 else b/12.92
    r*=100; g*=100; b*=100
    x=r*0.4124+g*0.3576+b*0.1805
    y=r*0.2126+g*0.7152+b*0.0722
    z=r*0.0193+g*0.1192+b*0.9505
    x/=95.047; y/=100.0; z/=108.883
    f=lambda t:t**(1/3)if t>0.008856 else 7.787*t+16/116
    return 116*f(y)-16, 500*(f(x)-f(y)), 200*(f(y)-f(z))

_PALETTE_LAB = [_rgb2lab(*c[:3]) for c in PALETTE]

def _lab_dist(lab1, lab2):
    dl=lab1[0]-lab2[0]; da=lab1[1]-lab2[1]; db=lab1[2]-lab2[2]
    return 0.2*dl*dl+3*da*da+3*db*db

def _nearest(r, g, b):
    """与 neoframe.html findClosestColor 一致"""
    if r<50 and g<150 and b>100:
        return PALETTE[2]
    lab = _rgb2lab(r, g, b)
    return PALETTE[min(range(6), key=lambda i: _lab_dist(lab, _PALETTE_LAB[i]))]

def _dither(img: Image.Image) -> Image.Image:
    """Floyd-Steinberg 抖动（对比度 1.2 + 饱和度增强）"""
    img = img.convert("RGB")
    w, h = img.size
    p = img.load()

    # 对比度 1.2 + 饱和度 1.3（让 6 色更明显）
    for y in range(h):
        for x in range(w):
            r, g, b = p[x, y]
            # 对比度
            r = max(0, min(255, int((r-128)*1.2+128)))
            g = max(0, min(255, int((g-128)*1.2+128)))
            b = max(0, min(255, int((b-128)*1.2+128)))
            # 饱和度增强（简单方法：加大 RGB 之间的差距）
            gray = (r + g + b) / 3
            r = max(0, min(255, int(gray + (r-gray)*1.3)))
            g = max(0, min(255, int(gray + (g-gray)*1.3)))
            b = max(0, min(255, int(gray + (b-gray)*1.3)))
            p[x, y] = (r, g, b)

    # F-S
    er, eg, eb = [0.0]*w, [0.0]*w, [0.0]*w
    nxt_r, nxt_g, nxt_b = [0.0]*w, [0.0]*w, [0.0]*w
    for y in range(h):
        for x in range(w):
            r, g, b = p[x, y]
            r=min(255,max(0,r+er[x])); g=min(255,max(0,g+eg[x])); b=min(255,max(0,b+eb[x]))
            pr, pg, pb, _ = _nearest(r, g, b)
            p[x, y] = (pr, pg, pb)
            er_q, eg_q, eb_q = r-pr, g-pg, b-pb
            if x+1<w:
                er[x+1]+=er_q*7/16; eg[x+1]+=eg_q*7/16; eb[x+1]+=eb_q*7/16
            if y+1<h:
                if x>0:
                    nxt_r[x-1]+=er_q*3/16; nxt_g[x-1]+=eg_q*3/16; nxt_b[x-1]+=eb_q*3/16
                nxt_r[x]+=er_q*5/16; nxt_g[x]+=eg_q*5/16; nxt_b[x]+=eb_q*5/16
                if x+1<w:
                    nxt_r[x+1]+=er_q/16; nxt_g[x+1]+=eg_q/16; nxt_b[x+1]+=eb_q/16
        if y+1<h:
            er, eg, eb = nxt_r[:], nxt_g[:], nxt_b[:]
            nxt_r, nxt_g, nxt_b = [0.0]*w, [0.0]*w, [0.0]*w
    return img

def _pack(img: Image.Image) -> bytes:
    """1 byte/pixel + NeoFrame 坐标变换 (x*800)+(799-y)"""
    img = img.convert("RGB")
    w, h = img.size
    out = bytearray(w*h)
    p = img.load()
    for y in range(h):
        for x in range(w):
            r, g, b = p[x, y]
            _, _, _, v = _nearest(r, g, b)
            out[x*h+(h-1-y)] = v
    return bytes(out)

# ══ DB 操作 ════════════════════════════════════════════════════

def load_photos(fresh_only: bool = True) -> list[dict]:
    """加载照片。fresh_only=True 时只选从未推送过的。"""
    if not DB_PATH.exists():
        logger.error(f"数据库不存在: {DB_PATH}")
        return []

    used_filter = "AND last_daily_used IS NULL" if fresh_only else ""
    conn = sqlite3.connect(str(DB_PATH))
    rows = conn.execute(f"""
        SELECT path, side_caption, memory_score, beauty_score, type, reason,
               exif_gps_lat, exif_gps_lon, exif_city
        FROM photo_scores
        WHERE memory_score IS NOT NULL AND status = 'done' {used_filter}
    """).fetchall()
    conn.close()

    if not rows and fresh_only:
        logger.info("所有照片已轮完一遍，重置池子")
        conn = sqlite3.connect(str(DB_PATH))
        conn.execute("UPDATE photo_scores SET last_daily_used = NULL WHERE status = 'done'")
        conn.commit()
        conn.close()
        return load_photos(fresh_only=True)

    import re
    items = []
    for p, side, score, beauty, ptype, reason, lat, lon, city in rows:
        if "screenshot" in str(p).lower():
            continue
        m = re.search(r'/(\d{4})/(\d{2})/', str(p))
        if not m:
            continue
        month = int(m.group(2))
        items.append({
            "path": str(p),
            "date": f"{m.group(1)}-{month:02d}-15",
            "md": f"{month:02d}-15",
            "side": side or "",
            "memory": float(score) if score else -1.0,
            "beauty": float(beauty) if beauty else 0,
            "type": ptype or "未知",
            "reason": reason or "",
            "lat": lat, "lon": lon, "city": city or "",
        })
    return items


def mark_used(photo_path: str) -> None:
    """标记照片已推送"""
    today = date.today().isoformat()
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("UPDATE photo_scores SET last_daily_used = ? WHERE path = ?",
                 (today, photo_path))
    conn.commit()
    conn.close()

# ══ 选片逻辑 ═══════════════════════════════════════════════════

def _md_to_doy(md: str) -> int:
    m, d = map(int, md.split("-"))
    days = [0,0,31,59,90,120,151,181,212,243,273,304,334]
    return days[m] + d

def _doy_to_md(doy: int) -> str:
    base = date(2001, 1, 1) + timedelta(days=doy-1)
    return f"{base.month:02d}-{base.day:02d}"

def choose_photos(items: list[dict], today: date, count: int = 1, threshold: float = 70.0) -> list[dict]:
    """"历史上的今天" 选片（对齐 InkTime choose_photos_for_today）"""
    if not items:
        return []

    by_md: dict[str, list[dict]] = {}
    for it in items:
        by_md.setdefault(it["md"], []).append(it)
    for arr in by_md.values():
        arr.sort(key=lambda x: x.get("memory", -1), reverse=True)

    target_doy = _md_to_doy(f"{today.month:02d}-{today.day:02d}")
    target_md = f"{today.month:02d}-{today.day:02d}"

    # 策略 1：同月同日 + 回忆分超阈值
    for offset in range(365):
        doy = target_doy - offset
        if doy <= 0:
            doy += 365
        md = _doy_to_md(doy)
        arr = by_md.get(md, [])
        if not arr:
            continue
        # 只看超过阈值的
        candidates = [p for p in arr if p.get("memory", -1) > threshold]
        if candidates:
            chosen = random.sample(candidates, min(count, len(candidates)))
            logger.info(f"选择: {md} (offset={-offset}, 候选={len(candidates)})")
            return chosen

    # 策略 2：全库最高分兜底
    logger.info("无同月日照片，使用全库最高分")
    all_sorted = sorted(items, key=lambda x: x.get("memory", -1), reverse=True)
    return all_sorted[:count]

# ══ 卡片渲染 ═══════════════════════════════════════════════════

def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font, max_w: int, max_lines: int = 3) -> list[str]:
    """中文自动换行"""
    if not text:
        return []
    lines = []
    cur = ""
    for ch in text:
        t = cur + ch
        if draw.textlength(t, font=font) <= max_w:
            cur = t
        else:
            if cur: lines.append(cur)
            cur = ch
            if len(lines) >= max_lines - 1:
                break
    if cur and len(lines) < max_lines:
        lines.append(cur)
    return lines

def render_card(item: dict, today: date) -> Image.Image:
    """渲染每日精选卡片（对齐 InkTime render_image）"""
    canvas = Image.new("RGB", (W, H), (255, 255, 255))
    draw = ImageDraw.Draw(canvas)

    # ── 加载照片 ──
    img_path = _nas_path(item["path"])
    if not img_path.exists():
        raise FileNotFoundError(f"照片不存在: {img_path}")

    photo = Image.open(img_path)
    photo = ImageOps.exif_transpose(photo).convert("RGB")
    pw, ph = photo.size

    # ── 缩放填充全屏 480×800 ──
    scale = max(W/pw, H/ph)
    nw, nh = int(pw*scale), int(ph*scale)
    photo = photo.resize((nw, nh), Image.Resampling.LANCZOS)
    left = (nw-W)//2; top = (nh-H)//2
    photo = photo.crop((left, top, left+W, top+H))
    canvas.paste(photo, (0, 0))

    # ── 文字区域（底部暗条 + 白字）──
    draw.rectangle([(0, H-140), (W, H)], fill=(40, 40, 40))
    draw.rectangle([(0, H-140), (W, H-138)], fill=(255, 255, 255))

    padding_x = 20; text_top = H - 124; text_w = W - 2*padding_x

    try:
        font_big = ImageFont.truetype(FONT_PATH, 36)
        font_mid = ImageFont.truetype(FONT_PATH, 28)
        font_sm = ImageFont.truetype(FONT_PATH, 22)
    except Exception:
        font_big = font_mid = font_sm = ImageFont.load_default()

    draw.rectangle([(0, H-140), (W, H)], fill=(40, 40, 40))  # 已在上面
    draw.rectangle([(0, H-140), (W, H-138)], fill=(255, 255, 255))  # 分隔线

    y = text_top

    side = item.get("side", "")
    date_str = item.get("date", "")
    city = item.get("city", "")

    # 旁白（白字）
    if side:
        lines = _wrap_text(draw, side, font_big, text_w, max_lines=2)
        for line in lines:
            draw.text((padding_x, y), line, fill=(255, 255, 255), font=font_big)
            y += 42
        y += 6

    # 日期 + 地点（灰色）
    if date_str:
        parts = date_str.split("-")
        date_disp = f"{parts[0]}.{int(parts[1])}.{int(parts[2])}" if len(parts)>=3 else date_str
        draw.text((padding_x, y+2), date_disp, fill=(180, 180, 180), font=font_mid)

    if city:
        tw = draw.textlength(city, font=font_mid)
        draw.text((W-padding_x-tw, y+2), city, fill=(180, 180, 180), font=font_mid)

    return canvas

# ══ 推送 ═══════════════════════════════════════════════════════

def push(host: str, img: Image.Image) -> bool:
    """抖动 + 打包 + multipart 上传"""
    dithered = _dither(img)
    data = _pack(dithered)
    try:
        r = requests.post(
            f"http://{host}/upload",
            files={"data": ("image_data.bin", data, "application/octet-stream")},
            timeout=60,
        )
        return r.status_code == 200
    except Exception as e:
        logger.error(f"推送失败: {e}")
        return False

# ══ 主入口 ═════════════════════════════════════════════════════

def main():
    import argparse
    p = argparse.ArgumentParser(description="每日精选 → NeoFrame")
    p.add_argument("--host", default=NEOFRAME_HOST)
    p.add_argument("--count", type=int, default=DAILY_QUANTITY)
    p.add_argument("--threshold", type=float, default=None,
                   help=f"最低回忆分，默认 {MEMORY_THRESHOLD}")
    p.add_argument("--random", action="store_true", help="跳过日期逻辑，随机选一张")
    args = p.parse_args()

    threshold = args.threshold if args.threshold is not None else MEMORY_THRESHOLD
    host = args.host

    # 1. 加载照片
    items = load_photos()
    if not items:
        logger.error("无可用照片"); return
    logger.info(f"已加载 {len(items)} 张照片")

    # 2. 选片
    today = date.today()
    if args.random:
        candidates = [p for p in items if p.get("memory", -1) > threshold]
        if not candidates:
            candidates = items
        chosen = random.sample(candidates, min(args.count, len(candidates)))
        logger.info(f"随机选择: {len(candidates)} 候选 → {len(chosen)} 张")
    else:
        chosen = choose_photos(items, today, count=args.count, threshold=threshold)
    if not chosen:
        logger.error("选片为空"); return

    # 3. 渲染 + 推送
    success = 0
    for i, item in enumerate(chosen):
        logger.info(f"[{i+1}/{len(chosen)}] {item['md']}")

        # 生成旁白（如果照片还没有旁白）
        if not item.get("side"):
            logger.info("   生成 AI 旁白...")
            try:
                sys.path.insert(0, str(PROJECT_DIR))
                from backend.daily import _generate_daily_captions_for_photo
                caption, side = _generate_daily_captions_for_photo({
                    "type": item.get("type", "未知"),
                    "memory_score": item.get("memory", 0),
                    "beauty_score": item.get("beauty", 0),
                    "reason": item.get("reason", ""),
                })
                if side:
                    item["side"] = side
                    logger.info(f"   📝 {side}")
            except Exception as e:
                logger.warning(f"   旁白生成失败: {e}")

        try:
            card = render_card(item, today)
        except FileNotFoundError as e:
            logger.warning(f"  跳过: {e}")
            continue

        if push(host, card):
            logger.info(f"   ✅ 已推送")
            mark_used(item["path"])
            success += 1
        else:
            logger.error(f"   ❌ 推送失败")

        time.sleep(3)

    logger.info(f"完成: {success}/{len(chosen)}")

if __name__ == "__main__":
    main()
