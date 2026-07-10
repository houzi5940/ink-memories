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
| **客户端组件** | React 18 + TypeScript |
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
│       ├── pages.py      # HTML 页面路由
│       ├── photos.py     # 照片 API（浏览/编辑/触发分析）
│       └── tags.py       # 标签 API
├── frontend/             # 前端
│   ├── src/              # React 源码
│   ├── templates/        # Jinja2 模板
│   └── static/           # 样式 + 构建产物
└── cli.py                # 项目入口
```

## 数据流

### 照片分析流程

```
1. scan_photos()         扫描目录，找出未分析的照片
       │
2. progress.start()      初始化进度追踪
       │
3. ThreadPoolExecutor    并发调用 VLM API
   ├── encode_image()    压缩并 Base64 编码
   ├── extract_exif()    提取 EXIF 信息
   ├── call_vlm()        调用 VLM API 评分
   ├── compute_avg_hash() 计算感知哈希
   └── deduplicate()     相似照片去重
       │
4. insert_photo()        写入 SQLite
       │
5. progress.tick()       更新进度
```

### 每日精选流程

```
1. choose_photos_for_today()
   ├── 策略1: 同月同日（历史上的今天）
   ├── 策略2: 向前回退最多 365 天
   └── 策略3: 全库最高分兜底
       │
2. _generate_daily_captions()
   └── 调用 VLM 为每张照片生成全新描述
       │
3. save_daily_caption()  缓存到 database
```

## 线程模型

- **主线程**: Uvicorn 处理 HTTP 请求
- **后台线程**: 照片分析（POST /api/analyze 触发）
- **并发分析**: ThreadPoolExecutor（可配置 CONCURRENCY）
- **进度同步**: threading.Lock 保护 progress 状态
