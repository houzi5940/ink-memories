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
│   ├── main.py           # FastAPI app + lifespan（启动/关闭分析 worker）
│   ├── config.py         # 配置管理（环境变量）
│   ├── database.py       # SQLite 数据层 + 分析任务队列（status 字段）
│   ├── analyzer.py       # 照片分析核心（VLM + 哈希去重 + 常驻 worker）
│   ├── daily.py          # 每日精选算法
│   ├── progress.py       # 分析进度追踪（线程安全，worker 单写）
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
├── push_to_ink.py        # NeoFrame 电子相框推送脚本
└── cli.py                # 项目入口
```

## 数据流

### 照片分析流程

```
run_analysis_async()
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
  ├─ 3. get_effective_concurrency()
  │    检测内存 → 自适应并发数
  │
  ├─ 4. 更新进度
  │    pr.start_analysis(total=N)  → phase="analyzing"
  │
  └─ 5. schedule_photo_analysis()   ← asyncio + ThreadPoolExecutor
       for each photo:
         ensure_future(loop.run_in_executor(executor, analyze_one_photo, path))

       asyncio.as_completed:
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
  └─ 6. pr.report_done()           → phase="done"
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
  │    database.enqueue_pending(paths)   ← 同步写 status='pending'
  │    analyzer.signal_worker()          ← 唤醒常驻 worker，接口立即返回
  │
  ├─ POST /api/review/skip {paths: [...]}
  │    batch_skip_photos(paths)
  │    └─ INSERT status='skipped' → 标记为已处理
  │
  └─ 常驻 analysis_worker（后台，被唤醒后）
       claim_pending_batch() → analyze_one_photo() → mark_status(done/failed)
       逐批领取直到队列排空；进度由 worker 统一上报
```

### 分析任务队列（常驻 worker）

```
提交/重分析 ──enqueue_pending / requeue_paths──▶ photo_scores(status='pending')
                                                      │ signal_worker()
                                                      ▼
                              analysis_worker()  ← asyncio 常驻任务
                                while wake_event:
                                  claim_pending_batch(N)   status: pending→analyzing
                                  run_in_executor(analyze_one_photo)
                                  insert_photo + mark_status(done/failed)
                                  pr.report_tick / extend_total
                                队列排空 → 挂起等待下次唤醒

启动恢复：reset_stale_analyzing()  上次中断的 analyzing → pending
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
- **应用生命周期**: `lifespan` 上下文管理器在启动时执行 `reset_stale_analyzing()` 并拉起常驻分析 worker，关闭时 cancel worker
- **常驻分析 worker**: 单个 asyncio 任务消费 `photo_scores` 中的 pending 队列；被 `signal_worker()` 唤醒，队列排空后挂起等待
- **asyncio 事件循环**: 协调分析任务的异步调度（`schedule_photo_analysis` / worker）
- **后台任务**: 全量分析通过 `create_background_task()` 启动，异常自动捕获记录
- **并发分析**: `ThreadPoolExecutor` + asyncio 混合模型，并发数由 `get_effective_concurrency()` 根据可用内存动态调整
- **内存检测**: 启动分析前自动检测 cgroup 限制 / /proc/meminfo / sysconf，低内存环境自动降级并发数
- **进度同步**: threading.Lock 保护 progress 状态；worker 是进度唯一写者，避免并发提交互相重置计数
- **数据库写锁**: threading.Lock 串行化 SQLite 写操作（含队列领取/状态更新），避免并发冲突
