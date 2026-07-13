# API 接口文档

## 页面路由

### `GET /`
今日精选首页。从「历史上的今天」中选出最值得回忆的照片。

### `GET /gallery`
照片库页面。

**查询参数：**
| 参数 | 类型 | 说明 | 示例 |
|------|------|------|------|
| `page` | int | 页码（默认 1）| `page=2` |
| `order` | string | 排序方式 | `memory_score DESC` |
| `type` | string | 按类型筛选 | `type=猫咪` |
| `tag` | string | 按标签筛选 | `tag=杭州` |

可用排序值：`memory_score DESC`, `beauty_score DESC`, `exif_datetime DESC`, `analyzed_at DESC`

> 分页支持直接输入页码跳转（页码越界会被后端钳制到 `1 ~ total_pages`）。

### `GET /stats`
统计仪表盘。显示照片总数、类型分布、评分分布、标签词云。

### `GET /search`
搜索页面。

**查询参数：**
| 参数 | 类型 | 说明 |
|------|------|------|
| `q` | string | 关键词（匹配 caption/reason/side_caption/type/tags）|

### `GET /photo/{path}`
提供照片文件。支持缓存（`Cache-Control: max-age=3600`）。

**路径说明：** path 可以是相对路径（相对于 PHOTO_DIR）或绝对路径。自动限制在 PHOTO_DIR 内防止路径穿越。

### `GET /review`
人工审核页。三种交互模式 — 平铺勾选、滑动选择（Tinder 风格）、按月浏览。React SPA，独立加载。

---

## API 接口

### `POST /api/analyze`
触发全量扫描分析（后台运行）。

**响应：**
```json
{"status": "started", "message": "分析任务已启动"}
```

### `GET /api/analyze/progress`
获取分析进度（轮询接口）。进度由常驻分析 worker 统一上报。

**响应：**
```json
{
  "running": true,
  "total": 50,
  "done": 12,
  "success": 11,
  "fail": 1,
  "current_file": "/photos/IMG_001.jpg",
  "phase": "analyzing",
  "elapsed": 15.3,
  "pending": 8,
  "analyzing": 2
}
```

**字段说明：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `running` | bool | 是否正在分析 |
| `total` | int | 本轮已领取总数（随队列排空逐步累加）|
| `done` | int | 已完成数 |
| `success` | int | 成功数 |
| `fail` | int | 失败数 |
| `current_file` | string | 当前正在分析的文件名 |
| `phase` | string | `scanning` / `analyzing` / `done` |
| `elapsed` | float | 已耗时（秒）|
| `pending` | int | 队列中待分析数（实时统计）|
| `analyzing` | int | 正在分析中的数量（实时统计）|

### `GET /api/photo/detail`
获取单张照片详情。

**查询参数：**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `path` | string | 是 | 照片的完整路径 |

**响应：** 完整的 photo_scores 记录（含 caption, type, memory_score, tags, EXIF 等）。

### `POST /api/photo/update`
手动更新照片的评分、标签、旁白等。

**请求体（JSON）：**
```json
{
  "path": "/photos/IMG_001.jpg",
  "memory_score": 88,
  "beauty_score": 75,
  "type": "旅行",
  "side_caption": "想再去一次",
  "caption": "新的描述",
  "reason": "评分理由",
  "tags": ["旅行", "海边", "夏天"]
}
```

所有字段均为可选，只更新提供的字段。score 自动限制在 0-100 区间。

### `GET /api/tags`
获取所有手动标签及其使用次数。

**响应：**
```json
[
  {"tag": "杭州", "count": 5},
  {"tag": "旅行", "count": 3}
]
```

按使用次数降序排列。

### `POST /api/review/submit`
提交选中照片进入分析队列。同步将路径写入 `photo_scores`（`status='pending'`）并唤醒常驻 worker，接口立即返回，不阻塞。

**请求体（JSON）：**
```json
{"paths": ["/photos/IMG_001.jpg", "/photos/IMG_002.jpg"]}
```

**响应：**
```json
{"status": "queued", "count": 2, "message": "已提交 2 张照片进入分析队列"}
```

> `count` 为实际新入队数量（已在库的路径不重复入队）。

### `POST /api/review/skip`
跳过未选中的照片（写入 photo_scores，memory_score=0，标记为已处理）。

**请求体（JSON）：**
```json
{"paths": ["/photos/IMG_003.jpg"]}
```

**响应：**
```json
{"status": "ok", "skipped": 1}
```

### `POST /api/photo/analyze`
重新分析单张照片。将该路径强制置回 `status='pending'` 重新入队，由常驻 worker 消费。

**请求体（JSON）：**
```json
{"path": "/photos/IMG_001.jpg"}
```

**响应：**
```json
{"status": "queued", "message": "已重新入队，完成后请刷新页面查看结果"}
```

### `GET /api/review/photos`
获取未评分的照片列表（分页，按文件修改时间降序）。

**查询参数：**
| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `limit` | int | 20 | 每页数量（1-100）|
| `offset` | int | 0 | 偏移量 |

**响应：**
```json
{
  "photos": [
    {"path": "/photos/IMG_001.jpg", "date": "", "type": ""}
  ],
  "total": 50
}
```

### `GET /api/status`
系统状态概览。

**响应：**
```json
{
  "photo_dir": "/photos",
  "total_photos": 150,
  "types": [
    {"type": "旅行", "cnt": 30, "avg_score": 82.5}
  ]
}
```

## 数据模型

### photo_scores 表

| 字段 | 类型 | 说明 |
|------|------|------|
| `path` | TEXT (PK) | 照片完整路径 |
| `caption` | TEXT | 照片描述 |
| `type` | TEXT | 分类（如"旅行""人物/家庭"）|
| `memory_score` | REAL | 回忆评分 0-100 |
| `beauty_score` | REAL | 美观评分 0-100 |
| `reason` | TEXT | 评分理由 |
| `side_caption` | TEXT | 旁白 |
| `width/height` | INTEGER | 图片尺寸 |
| `orientation` | TEXT | landscape/portrait/square |
| `exif_datetime` | TEXT | 拍摄时间 |
| `exif_city` | TEXT | 拍摄城市 |
| `exif_gps_lat/lon` | REAL | GPS 坐标 |
| `tags` | TEXT | JSON 数组，如 `["旅行","海边"]` |
| `perceptual_hash` | TEXT | 感知哈希（用于去重）|
| `status` | TEXT | 分析状态：`pending`/`analyzing`/`done`/`failed`/`skipped` |
| `analyzed_at` | TIMESTAMP | 分析时间 |

### daily_captions 表

| 字段 | 类型 | 说明 |
|------|------|------|
| `photo_path` | TEXT | 照片路径 |
| `date` | TEXT | 日期 YYYY-MM-DD |
| `caption` | TEXT | 每日专属描述 |
| `side_caption` | TEXT | 每日专属旁白 |
