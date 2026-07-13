# 照片分析管线

本文档深入解析 `run_analysis()` 的每一步执行细节，包括增量扫描、多通道故障转移、感知哈希去重等核心机制。

## 调用入口

```
CLI:  python cli.py analyze [-j N] [-n N]
API:  POST /api/analyze → 后台线程执行
```

## 步骤一：初始化进度

```python
pr.start_analysis()       # running=true, phase="scanning", total=0
```

此时前端轮询 `/api/analyze/progress` 会看到 `{"phase":"scanning", "total":0}`，进度条显示"正在扫描照片目录…"

## 步骤二：扫描新照片 — `scan_photos()`

```python
def scan_photos() -> list[str]:
    photo_dir = Path(config.PHOTO_DIR)
    analyzed = database.get_analyzed_paths()   # ← 已分析的照片全路径集合

    for root, dirs, files in os.walk(photo_dir):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]  # 排除系统目录

        for f in files:
            ext = Path(f).suffix.lower()
            if ext not in SUPPORTED_EXTENSIONS:    # 只处理 .jpg/.png/.heic 等
                continue
            full_path = str(Path(root) / f)
            if full_path in analyzed:               # 已分析的跳过
                continue
            new_photos.append(full_path)

    return new_photos
```

**增量机制：** `get_analyzed_paths()` 从 SQLite 的 `photo_scores` 表查询所有已有 `path` 值，返回一个 Python `set()`，`in` 判断是 O(1) 的。已分析过的照片即使被重新扫描也不会重复处理。

**限制批次：** 如果 `BATCH_LIMIT > 0`，只取前 N 张。

## 步骤三：更新进度

```python
pr.start_analysis(total=len(photos))   # 现在知道总数了
pr.report_analyzing()                  # phase="analyzing"
```

## 步骤四：异步并发调度

```python
async def schedule_photo_analysis(paths: list[str]):
    # 先并行写入"待分析"状态
    await asyncio.gather(*[
        asyncio.to_thread(_insert_pending_photo, path)
        for path in paths
    ])

    loop = asyncio.get_running_loop()
    effective_concurrency = get_effective_concurrency()  # 内存自适应
    logger.info(f"开始调度 {len(paths)} 张照片分析，并发数: {effective_concurrency}")

    with ThreadPoolExecutor(max_workers=effective_concurrency) as executor:
        task_to_path = {
            asyncio.ensure_future(loop.run_in_executor(executor, analyze_one_photo, path)): path
            for path in paths
        }
        tasks = list(task_to_path.keys())

        for task in asyncio.as_completed(tasks):
            path = task_to_path[task]
            record = await task
            if record:
                await asyncio.to_thread(database.insert_photo, record)
                pr.report_tick(path, success=True)
            else:
                await asyncio.to_thread(_mark_analysis_failed, path)
                pr.report_tick(path, success=False)
```

`schedule_photo_analysis` 使用 asyncio + ThreadPoolExecutor 混合模型：
- **asyncio** 管理并发调度和 IO（数据库写入）
- **ThreadPoolExecutor** 执行 CPU 密集型工作（图片编码、哈希计算）
- `as_completed` 确保先完成的先入库，不会因为某张照片超时阻塞其他照片
- 后台任务异常通过 `create_background_task()` 统一捕获记录

### 内存自适应并发

系统启动分析前会自动检测可用内存并调整并发数：

```python
def get_effective_concurrency() -> int:
    concurrency = max(1, config.CONCURRENCY)
    cpus = os.cpu_count() or 1
    if concurrency > cpus:
        concurrency = cpus
    available_mb = get_available_memory_mb()
    if available_mb is not None and available_mb <= config.LOW_MEMORY_THRESHOLD_GB * 1024:
        concurrency = min(concurrency, config.LOW_MEMORY_CONCURRENCY)
    return max(1, concurrency)
```

检测优先级：
1. **cgroup 内存限制** — Docker 容器分配的内存上限
2. **/proc/meminfo MemAvailable** — 系统当前可用内存
3. **os.sysconf** — POSIX 系统调用回退

配置项（`.env` 或环境变量）：
| 配置 | 默认 | 说明 |
|------|------|------|
| `CONCURRENCY` | 2 | 正常情况下的最大并发数 |
| `LOW_MEMORY_THRESHOLD_GB` | 4.0 | 低于此值触发降级 |
| `LOW_MEMORY_CONCURRENCY` | 1 | 低内存时的并发数上限 |

### 每个子任务：`analyze_one_photo(path)`

#### ① 编码图片 — `encode_image(path)`

```python
ext = Path(image_path).suffix.lower()
if ext in {".heic", ".heif"} and pillow_heif is None:
    return None, 0, 0  # HEIC/HEIF 需要 pillow-heif

with Image.open(image_path) as img:
    img = ImageOps.exif_transpose(img)    # 校正旋转
    width, height = img.size

    if max(width, height) > VLM_MAX_LONG_EDGE:     # 默认 2560px
        img = img.resize(保持比例, Image.LANCZOS)

    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    elif img.mode == "L":
        img = img.convert("RGB")

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    b64 = base64.b64encode(buf.getvalue())
    return b64, width, height
```

> **改进点：** 使用 `with` 上下文管理器确保图片资源正确释放；HEIC/HEIF 文件在开头做早期检查，避免无意义的错误日志；灰度（L 模式）图片也转为 RGB，确保 JPEG 编码兼容。

**为什么压缩到 2560px？**
- VLM API 通常有图片大小限制（几 MB～20MB）
- 缩小长边能显著减少 token 消耗和传输时间
- 评分不需要原图细节，压缩后不影响判断

#### ② 提取 EXIF — `extract_exif(path)`

```python
try:
    raw_exif = Image.open(path)._getexif()
    # 日期时间（优先选最精确的标签）
    DateTimeOriginal > DateTimeDigitized > DateTime
    # 转换格式 "2023:07:05 14:30:00" → "2023-07-05 14:30:00"

    # 相机信息
    Make, Model

    # 拍摄参数
    ISOSpeedRatings, ExposureTime, FNumber, FocalLength

    # GPS
    GPSLatitudeRef + GPSLatitude  → 十进制度数
    GPSLongitudeRef + GPSLongitude → 十进制度数
    GPSAltitude + GPSAltitudeRef  → 海拔（米）
except:
    pass  # 无 EXIF 不阻塞分析
```

#### ③ VLM 评分 — `call_vlm(base64)`

```python
channels = config.API_CHANNELS[:]   # 从配置读取通道列表

for attempt in range(len(channels)):
    channel = channels[attempt % len(channels)]

    POST channel["api_url"]
    Headers: Authorization = Bearer {api_key}
    Body:
        model: channel["model_name"]
        messages: [
            system → SCORE_SYSTEM_PROMPT（评分标准）
            user → text("请分析这张照片：") + image_url(base64)
        ]
        temperature: 0.3      # 低温度 = 更稳定的输出
        max_tokens: 512

    ← 返回: {"type":"...", "memory_score":75, "beauty_score":60, "reason":"..."}
```

**故障转移顺序：**

```
请求 → 429 Too Many Requests?
  ├─ 是 → time.sleep(2) → 切换下一个通道
  └─ 否 → HTTP 其他错误?
       ├─ 是 → 记录 warning → 切换下一个通道
       └─ 否 → JSON 解析成功?
            ├─ 否 → 记录原内容 → 切换下一个通道
            └─ 是 → 缺少必填字段?
                 ├─ 是 → ValueError → 切换下一个通道
                 └─ 否 → 校验通过 → 返回结果

所有通道都失败 → return {"error": last_error}
```

**清理逻辑：** 模型有时会在 JSON 外面包 markdown 代码块：
```python
if content.startswith("```"):   # 去掉开头的 ```json
    content = content.split("\n", 1)[1]
if content.endswith("```"):     # 去掉结尾的 ```
    content = content[:-3]
result = json.loads(content)    # 解析 JSON
```

#### ④ 感知哈希 — `compute_avg_hash(path)`

**平均哈希（aHash）算法：**

```
原图 → 校正 EXIF 旋转 → 灰度 (L) → resize(8×8) → 64 个像素值
→ 计算均值 → 逐像素比较 → 高于均值写"1", 否则写"0"
→ 返回 64 位二进制字符串
```

**为什么选择 aHash？**

| 算法 | 特点 | 适用场景 |
|------|------|----------|
| **aHash**（平均哈希）| 快，对轻微缩放/亮度变化鲁棒 | 相似照片判定 |
| pHash（感知哈希）| 更精确但更慢 | 重复图片检测 |
| dHash（差异哈希）| 最快，对梯度敏感 | 缩略图对比 |

aHash 在速度和精度之间取得平衡，适合照片去重场景。

**EXIF 旋转校正的重要性：**
同样的场景用手机横拍和竖拍，EXIF Orientation 不同。如果不先校正旋转，两张照片的哈希值会完全不同，导致去重失效。

#### ⑤ 相似去重 — `deduplicate_similar_photos(phash, new_path, new_score)`

```python
existing = database.get_all_photo_hashes()
# ← [{path, perceptual_hash, memory_score}, ...]

similar = [
    row for row in existing
    if hamming_distance(phash, row["perceptual_hash"]) <= SIMILARITY_THRESHOLD
]

if not similar:
    return new_score    # 无相似照片，保持原分

# 新照片 + 已有的相似照片 → 找出最高分
candidates = similar + [{"path": new_path, "memory_score": new_score}]
top = max(candidates, key=lambda x: x["memory_score"])

# 除了最高分，其余全部降分
for c in candidates:
    if c["path"] != top["path"]:
        database.update_photo(c["path"], {"memory_score": SIMILARITY_PENALTY_SCORE})

# 如果新照片不是最高分，它自己被降至惩罚分
return top["memory_score"] if top["path"] == new_path else SIMILARITY_PENALTY_SCORE
```

**示例场景：**

```
库中存在: photo_A.jpg  哈希=1010...  评分=85
新照片:   photo_B.jpg  哈希=1011...  VLM评分=92
两者距离 = 2（≤ 5）
计算: candidates = [A(85), B(92)]
最高分: B(92)
结果: A→10分（降分）, B→92分（保留）
```

```
库中存在: photo_A.jpg  哈希=1010...  评分=95
新照片:   photo_B.jpg  哈希=1011...  VLM评分=80
两者距离 = 2（≤ 5）
计算: candidates = [A(95), B(80)]
最高分: A(95)
结果: A→95分（保留）, B→10分（降分后入库）
```

## 步骤五：完成

```python
logger.info(f"分析完成: 成功 {success_count}, 失败 {fail_count}")
pr.report_done()     # running=false, phase="done"
```

前端轮询到 `running=false` 后，进度条显示"分析完成 ✓"，2 秒后自动隐藏。

## 输出记录结构

```python
{
    "path": "/photos/IMG_001.jpg",
    "type": "旅行",
    "memory_score": 85.0,                   # 可能被去重逻辑改写
    "beauty_score": 72.0,
    "reason": "西湖风景优美，色彩层次丰富",
    "width": 1200, "height": 800,
    "orientation": "landscape",
    "raw_json": "{...}",                    # VLM 原始返回
    "perceptual_hash": "101101...",         # 64位 aHash
    # 以下来自 extract_exif:
    "exif_datetime": "2024-07-11 14:30:00",
    "exif_make": "Apple",
    "exif_model": "iPhone 15 Pro",
    "exif_iso": 100,
    "exif_f_number": 1.8,
    "exif_exposure_time": 0.01,
    "exif_focal_length": 5.1,
    "exif_gps_lat": 30.25,
    "exif_gps_lon": 120.17,
    "exif_gps_alt": 10.5,
    "exif_city": None,                      # 需要外部补充
    "exif_json": "{...}",                   # 原始 EXIF 完整 JSON
}
```

## 配置项速查

| 配置 | 默认 | 影响环节 |
|------|------|----------|
| `CONCURRENCY` | 2 | ThreadPoolExecutor 并发数 |
| `LOW_MEMORY_THRESHOLD_GB` | 4.0 | 低内存检测阈值（低于此值自动降级）|
| `LOW_MEMORY_CONCURRENCY` | 1 | 低内存时的并发数上限 |
| `BATCH_LIMIT` | 0 (不限) | 单次最大分析数 |
| `TIMEOUT` | 120s | VLM API HTTP 超时 |
| `VLM_MAX_LONG_EDGE` | 2560px | encode_image 压缩尺寸 |
| `SIMILARITY_THRESHOLD` | 5/64 | 去重敏感度（越小越严格）|
| `SIMILARITY_PENALTY_SCORE` | 10 | 重复照片降分目标值 |

## 人工审核评分流：分析任务队列 + 常驻 worker

`POST /api/review/submit` 不再直接启动分析，而是 **同步入队 + 唤醒常驻 worker**：接口把选中路径写入 `photo_scores`（`status='pending'`）后立即返回，实际分析由后台常驻 `analysis_worker()` 消费。

### 入队端：`analyze_selected_photos(paths)`

```python
async def analyze_selected_photos(paths: list[str]):
    # 收敛为“入队 + 唤醒”，不再在请求内跑分析
    database.enqueue_pending(paths)   # INSERT OR IGNORE, status='pending'
    analyzer.signal_worker()          # 唤醒 worker
```

> `POST /api/review/submit` 和 `POST /api/photo/analyze`（单张重分析，走 `requeue_paths` 强制置 pending）都只做入队+唤醒。

### 消费端：`analysis_worker()`

```python
async def analysis_worker():
    ev = _get_wake_event()
    while True:
        await ev.wait(); ev.clear()
        started = False
        while True:
            paths = database.claim_pending_batch(concurrency)  # pending→analyzing 原子领取
            if not paths:
                break
            if not started:
                pr.start_analysis(total=0); pr.report_analyzing(); started = True
            pr.extend_total(len(paths))          # 总数逐批累加（不清零）
            await _analyze_claimed_batch(paths)  # 线程池并发 analyze_one_photo
        if started:
            pr.report_done()
```

- `claim_pending_batch()` 在写锁内 `SELECT ... WHERE status='pending' LIMIT N` + `UPDATE status='analyzing'` 原子领取，避免重复处理。
- 每张完成后：成功→`insert_photo()` + `mark_status(done)`；失败→`_mark_analysis_failed()` + `mark_status(failed)`。
- 队列排空后 worker 挂起（`await ev.wait()`），新提交再次唤醒。

### 启动恢复

`lifespan` 启动时调用 `reset_stale_analyzing()`，将上次进程中断遗留的 `analyzing` 重置为 `pending`，并唤醒 worker 续跑，避免任务丢失。

### 与 `run_analysis_async()` 的区别

| 环节 | `run_analysis_async()`（全量） | 审核队列（submit → worker） |
|------|-----------------|----------------------------|
| 照片来源 | `scan_photos()` 扫描全目录 | 前端传入的 `paths` 入队 |
| 触发方式 | 后台任务一次性调度 | 入队后由常驻 worker 逐批领取 |
| 进度 total | 开始即定 | `extend_total` 随队列排空累加 |
| 重启恢复 | 不涉及 | `reset_stale_analyzing()` 续跑 |
| 适用场景 | 全量/定时分析 | 人工审核后只对选中照片评分 |
