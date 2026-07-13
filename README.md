# InkMemories · AI 照片回忆系统

> 基于 [InkTime](https://github.com/dai-hongtao/InkTime) 的 AI 照片评分思路，去掉墨水屏硬件部分，纯软件方案部署在群晖 NAS 上。

## ✨ 功能

- **AI 智能评分** — 双维度评分（回忆值 + 美观值），自动分类（人物/旅行/猫咪/美食…）
- **人工审核** — 平铺勾选 / 滑动选择(Tinder风格) / 按月浏览三种模式，节省 token 消耗，只对精选照片执行 VLM 评分
- **诗意旁白** — 为每张照片生成一句话文案
- **每日精选** — 从「历史上的今天」中选出最值得回忆的照片，每日全新描述
- **WebUI 浏览** — 按类型、评分、日期浏览，支持搜索描述/标签
- **手动编辑** — 在线修改评分、分类、旁白、描述、标签
- **标签系统** — React 标签选择器，支持搜索已有标签和新建标签（shadcn/ui + lucide-react）
- **相似照片去重** — 基于感知哈希自动识别重复照片，降分处理
- **分析进度条** — 实时显示分析进度和统计（成功/失败数）
- **增量分析** — 已分析的照片自动跳过，可随时中断重启

## 🚀 快速开始

### 1. 配置 API Key

```bash
cp .env.example .env
# 编辑 .env，填写 VLM_API_KEY
```

### 2. 部署到群晖 NAS

```bash
# 将项目上传到 NAS
scp -r ./* user@your-nas-ip:/path/to/ink-memories/

# SSH 登录 NAS
ssh user@your-nas-ip

# 进入项目目录
cd /path/to/ink-memories

# 构建并启动
sudo docker-compose up -d --build
```

### 3. 分析照片

```bash
# 在 NAS 上执行
sudo docker exec ink-memories python cli.py analyze

# 指定并发数和限制
sudo docker exec ink-memories python cli.py analyze -j 4 -n 100
```

### 4. 访问 WebUI

浏览器打开 `http://your-nas-ip:8765`

## 📁 项目结构

```
ink-memories/
├── backend/                    # FastAPI 后端
│   ├── cli.py                  # CLI 入口（analyze / server / daily）
│   ├── main.py                 # FastAPI 应用入口
│   ├── config.py               # 配置管理
│   ├── database.py             # SQLite 数据库操作
│   ├── analyzer.py             # VLM 照片分析 + 去重
│   ├── daily.py                # 每日精选逻辑
│   ├── progress.py             # 分析进度追踪（线程安全）
│   ├── dependencies.py         # FastAPI 依赖注入
│   ├── templates.py            # Jinja2 模板配置
│   └── routers/
│       ├── pages.py            # 页面路由（首页/相册/统计/搜索/审核）
│       ├── photos.py           # 照片 API（浏览/编辑/分析）
│       └── tags.py             # 标签 API
├── frontend/                   # React + TypeScript + Tailwind
│   ├── src/
│   │   ├── main.tsx            # React 入口（TagSelector）
│   │   ├── review/
│   │   │   ├── main.tsx        # 人工审核页 React 入口
│   │   │   ├── App.tsx         # 审核主应用（3 种模式+状态管理）
│   │   │   ├── api.ts          # 审核 API 请求封装
│   │   │   ├── types.ts        # 类型定义
│   │   │   └── components/
│   │   │       ├── GridMode.tsx    # 平铺勾选模式
│   │   │       ├── SwipeMode.tsx   # 滑动选择模式（Tinder风格）
│   │   │       └── MonthMode.tsx   # 按月浏览模式
│   │   ├── index.css           # Tailwind 基础样式
│   │   ├── components/
│   │   │   ├── TagSelector.tsx       # 标签下拉选组件
│   │   │   └── TagSelectorRoot.tsx   # 标签选择器根组件
│   │   └── components/ui/      # shadcn/ui 组件
│   ├── templates/              # WebUI 页面（Jinja2 服务端渲染）
│   │   ├── base.html           # 布局 + 导航 + 编辑弹窗 + 进度条
│   │   ├── index.html          # 今日精选
│   │   ├── gallery.html        # 照片库（排序/筛选/分页）
│   │   ├── stats.html          # 统计仪表盘
│   │   ├── search.html         # 搜索页面
│   │   └── review.html         # 人工审核页（独立 React SPA）
│   ├── static/
│   │   └── style.css           # 应用样式（现代温暖风格）
│   ├── package.json
│   └── vite.config.ts
├── cli.py                      # 项目入口（委托给 backend.cli）
├── Dockerfile                  # 多阶段构建
├── docker-compose.yml
├── .env.example                # 环境变量模板
├── requirements.txt
└── .dockerignore
```

## ⚙️ 配置说明

在 `config.py` 或 `.env` 中修改：

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `VLM_API_URL` | VLM API 地址 | DeepSeek |
| `VLM_API_KEY` | API Key | (必填) |
| `VLM_MODEL` | 模型名称 | deepseek-chat |
| `CONCURRENCY` | 并发数 | 2 |
| `BATCH_LIMIT` | 每次最多分析数 | 0 (不限) |
| `TIMEOUT` | 单张超时（秒）| 120 |
| `LOW_MEMORY_THRESHOLD_GB` | 低内存阈值（GB）| 3.0 |
| `LOW_MEMORY_CONCURRENCY` | 低内存时并发数 | 1 |
| `MEMORY_THRESHOLD` | 精选最低回忆分 | 70 |
| `DAILY_PHOTO_QUANTITY` | 每日精选数量 | 5 |
| `SIMILARITY_THRESHOLD` | 去重哈希距离阈值 | 5 |
| `SIMILARITY_PENALTY_SCORE` | 重复照片降分值 | 10 |

## 📡 API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/` | 今日精选页面 |
| `GET` | `/gallery` | 照片库 |
| `GET` | `/stats` | 统计页面 |
| `GET` | `/search` | 搜索页面 |
| `GET` | `/review` | 人工审核页（React SPA，三种模式） |
| `GET` | `/photo/{path}` | 照片文件服务 |
| `POST` | `/api/analyze` | 触发全量分析（后台） |
| `GET` | `/api/analyze/progress` | 分析进度轮询（含队列 pending/analyzing） |
| `GET` | `/api/photo/detail` | 照片详情 |
| `POST` | `/api/photo/update` | 编辑照片 |
| `POST` | `/api/photo/analyze` | 重新分析单张照片（入队） |
| `GET` | `/api/review/photos` | 未评分照片列表（分页） |
| `POST` | `/api/review/submit` | 提交选中照片入分析队列 |
| `POST` | `/api/review/skip` | 跳过未选中照片 |
| `GET` | `/api/tags` | 标签列表 |
| `GET` | `/api/status` | 系统状态 |

## 🔄 定时任务

建议在群晖「任务计划」中添加：

- **每天凌晨 2:00**：分析新照片
  ```bash
  sudo docker exec ink-memories python cli.py analyze
  ```

## 💰 费用估算

按 DeepSeek API 计价，分析 1 万张照片约 ¥10-20（仅首次全量分析时产生，后续增量分析费用很小）。

## 🧪 本地开发

```bash
# 1. 创建虚拟环境
python3 -m venv venv && source venv/bin/activate

# 2. 安装依赖
pip install -r requirements.txt

# 3. 构建前端
cd frontend && npm install && npm run build && cd ..

# 4. 生成测试数据
python seed_local.py

# 5. 启动服务器
PHOTO_DIR=./test_photos DB_PATH=./data/photos.db python cli.py server
```

## 🔬 照片分析流程详解

### 完整调用链

```
run_analysis_async()                       ← asyncio 异步入口
  ├─ scan_photos()                         ← 扫描目录，增量检测
  ├─ get_effective_concurrency()           ← 内存自适应并发数
  └─ schedule_photo_analysis(paths)        ← asyncio 并发调度
       └─ ThreadPoolExecutor(N) × asyncio  ← 异步 + 线程池
            └─ analyze_one_photo(path)
                 ├─ encode_image(path)         ← HEIC→JPEG→Base64
                 ├─ extract_exif(path)         ← EXIF 元数据提取
                 ├─ call_vlm(base64)           ← VLM API 评分
                 ├─ compute_avg_hash(path)     ← 感知哈希 (aHash)
                 └─ deduplicate_similar_photos() ← 相似去重
```

### 单张照片分析 (`analyze_one_photo`)

**① 编码图片** — `encode_image(path)`
- 读取原图，按 EXIF Orientation 校正旋转
- 压缩到最长边 ≤ 2560px（配置项 `VLM_MAX_LONG_EDGE`）
- RGBA/P 转 RGB，JPEG quality=85
- 返回 base64 字符串 + 原始宽高

**② 提取 EXIF** — `extract_exif(path)`
- 解析拍摄时间（DateTimeOriginal → DateTimeDigitized → DateTime）
- 相机型号（Make / Model）
- 拍摄参数（ISO / 曝光时间 / 光圈 / 焦距）
- GPS 坐标（经纬度 → 十进制度数，海拔）
- 原始 EXIF 保存为 JSON 供后续扩展

**③ VLM 评分** — `call_vlm(base64)`
- 支持多通道故障转移：配置多个 API 通道时，一个失败自动切换
- 遇 429 Too Many Requests 自动等待后重试
- 模型返回需是严格 JSON：`{"type","memory_score","beauty_score","reason"}`
- 自动清理 markdown 代码块包裹 (`\`\`\`json ... \`\`\``)

**④ 感知哈希** — `compute_avg_hash(path)`
- 平均哈希算法：灰度 → 8×8 → 64bit → 与均值比较 → 二进制字符串
- 先校正 EXIF 旋转确保同场景不同朝向哈希一致

**⑤ 相似去重** — `deduplicate_similar_photos()`
- 将新照片哈希与库中所有有哈希的照片做海明距离比较
- 距离 ≤ `SIMILARITY_THRESHOLD`（默认 5/64）视为相似
- 一组相似照片只保留回忆分最高的一张，其余降至 `SIMILARITY_PENALTY_SCORE`（默认 10）
- 新照片可能被保留，也可能被已有高分照片降分

### 增量机制

- `scan_photos()` 调用 `get_analyzed_paths()` 获取已分析的路径集合
- 只在全路径不在集合中时加入待分析列表
- 已分析的照片自动跳过，可随时中断重启

### 故障转移

```python
channels = config.API_CHANNELS[:]    # 多通道配置
for attempt in range(len(channels)):
    channel = channels[attempt % len(channels)]
    try:
        POST channel 请求评分
        if 429: time.sleep(2); continue   # 限流等待
        return JSON 结果
    except:
        continue                           # 切下一个通道
return {"error": last_error}              # 全部失败
```

## 致谢

- 核心 AI 提示词和评分思路来自 [InkTime](https://github.com/dai-hongtao/InkTime) by dai-hongtao
