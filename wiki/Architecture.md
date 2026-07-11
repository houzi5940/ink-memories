# 系统架构

## 整体架构

```
┌──────────────┐     ┌──────────────────┐     ┌──────────────┐
│  浏览器      │────▶│  Uvicorn         │────▶│  SQLite      │
│  (Jinja2     │     │  FastAPI 应用    │     │  photos.db   │
│   + React)   │◀────│  port 8765       │◀────│              │
└──────────────┘     └──────────────────┘     └──────────────┘
                            │
                            ▼
                     ┌──────────────┐
                     │  VLM API     │
                     │  (DeepSeek   │
                     │   等)        │
                     └──────────────┘
```

## 技术栈

| 层 | 技术 |
|----|------|
| **Web 框架** | FastAPI (Python 3.10+) |
| **服务端渲染** | Jinja2 模板 |
| **客户端组件** | React 18 + TypeScript（TagSelector + 人工审核页）|
| **UI 框架** | Tailwind CSS + shadcn/ui |
| **图标** | lucide-react |
| **数据库** | SQLite |
| **图片处理** | Pillow |
| **HTTP 客户端** | requests |
| **ASGI 服务器** | Uvicorn |
| **容器化** | Docker + docker-compose |

## 代码结构

```
ink-memories/
├── backend/              # Python 后端
│   ├── cli.py            # CLI 入口 (analyze/server/daily/backfill)
│   ├── main.py           # FastAPI app 初始化 + 路由挂载
│   ├── config.py         # 配置管理（环境变量）
│   ├── database.py       # SQLite 数据层
│   ├── analyzer.py       # 照片分析核心（VLM + 哈希去重）
│   ├── daily.py          # 每日精选算法
│   ├── progress.py       # 分析进度追踪（线程安全）
│   ├── dependencies.py   # FastAPI 依赖注入
│   ├── templates.py      # Jinja2 模板引擎配置
│   └── routers/
│       ├── pages.py      # HTML 页面路由（含 /review 审核页）
│       ├── photos.py     # 照片 API（浏览/编辑/触发分析/审核提交/跳过）
│       └── tags.py       # 标签 API
├── frontend/             # 前端
│   ├── src/              # React 源码
│   │   ├── main.tsx      # TagSelector 入口
│   │   ├── review/       # 人工审核页（独立入口，三种模式）
│   │   │   ├── main.tsx / App.tsx / api.ts / types.ts
│   │   │   └── components/ (GridMode / SwipeMode / MonthMode)
│   ├── templates/        # Jinja2 模板
│   └── static/           # 样式 + 构建产物
└── cli.py                # 项目入口
```

## 数据流

### 照片分析流程

```
run_analysis()
  │
  ├─ 1. 初始化进度
  │    pr.start_analysis()       → phase="scanning", total=0
  │
  ├─ 2. scan_photos()
  │    os.walk(PHOTO_DIR)
  │    ├─ 过滤后缀（.jpg/.png/.heic…）
  │    ├─ 排除系统目录（@eaDir / #recycle…）
  │    └─ 跳过已分析路径（增量）
  │    → 返回新照片列表 []
  │
  ├─ 3. 更新进度
  │    pr.start_analysis(total=N)  → phase="analyzing"
  │
  └─ 4. ThreadPoolExecutor (CONCURRENCY)
       for each photo:
         submit(analyze_one_photo, path)

       as_completed:
         ├─ analyze_one_photo()
         │    ├─ encode_image()     读取→压缩→base64
         │    ├─ extract_exif()     解析 EXIF→dict
         │    ├─ call_vlm()         POST API→JSON
         │    ├─ compute_avg_hash() aHash 64bit
         │    └─ deduplicate()     相似去重→最终评分
         │
         ├─ insert_photo(record)   写入 SQLite
         └─ pr.report_tick()       更新进度
  │
  └─ 5. pr.report_done()           → phase="done"
```

### 人工审核流程

```
用户访问 /review (React SPA)
  │
  ├─ GET /api/review/photos?limit=20
  │    scan_unanalyzed_photos()
  │    ├─ os.walk(PHOTO_DIR)
  │    ├─ 排除已分析的（get_analyzed_paths()）
  │    └─ 按文件 mtime 降序 → 返回 20 张
  │
  ├─ 用户勾选/滑动/按月选择
  │   ┌─────────────┬──────────────┬──────────────┐
  │   │ 平铺 (Grid) │ 滑动 (Swipe) │ 按月 (Month) │
  │   ├─────────────┼──────────────┼──────────────┤
  │   │ 点击切换选中 │ 左滑=跳过   │ 按月份折叠   │
  │   │ 跨批保持选中 │ 右滑=选中   │ 整月全选     │
  │   └─────────────┴──────────────┴──────────────┘
  │
  ├─ POST /api/review/submit {paths: [...]}
  │    analyze_selected_photos(paths)
  │    └─ ThreadPoolExecutor → analyze_one_photo(path)
  │
  └─ POST /api/review/skip {paths: [...]}
       batch_skip_photos(paths)
       └─ INSERT score=0 → 标记为已处理
```

### 每日精选流程

```
get_daily_summary()
  │
  ├─ choose_photos_for_today()
  │    ├─ 策略1: 同月同日（历史上的今天）
  │    │   database.get_photos_by_date(MM-DD)
  │    │   WHERE memory_score >= MEMORY_THRESHOLD
  │    │
  │    ├─ 策略2: 向前回退最多 365 天
  │    │   for offset in 1..365:
  │    │     database.get_photos_by_date(prev_MM-DD)
  │    │
  │    └─ 策略3: 全库最高分兜底
  │        database.get_top_photos(count×3)
  │
  ├─ 检查缓存
  │    database.get_daily_captions(today)
  │    未缓存的照片 → 调用 VLM 生成专属描述
  │
  └─ 返回 {date, weekday, photos[], total_in_db}
```

## 线程模型

- **主线程**: Uvicorn 处理 HTTP 请求
- **后台线程**: 照片分析（POST /api/analyze 或 POST /api/review/submit 触发）
- **并发分析**: ThreadPoolExecutor（可配置 CONCURRENCY）
- **进度同步**: threading.Lock 保护 progress 状态
