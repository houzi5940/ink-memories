# InkMemories · AI 照片回忆系统

> 基于 [InkTime](https://github.com/dai-hongtao/InkTime) 的 AI 照片评分思路，去掉墨水屏硬件部分，纯软件方案部署在群晖 NAS 上。

## ✨ 功能

- **AI 智能评分** — 双维度评分（回忆值 + 美观值），自动分类（人物/旅行/猫咪/美食…）
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
│       ├── pages.py            # 页面路由（首页/相册/统计/搜索）
│       ├── photos.py           # 照片 API（浏览/编辑/分析）
│       └── tags.py             # 标签 API
├── frontend/                   # React + TypeScript + Tailwind
│   ├── src/
│   │   ├── main.tsx            # React 入口
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
│   │   └── search.html         # 搜索页面
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
| `GET` | `/photo/{path}` | 照片文件服务 |
| `POST` | `/api/analyze` | 触发分析（后台） |
| `GET` | `/api/analyze/progress` | 分析进度轮询 |
| `GET` | `/api/photo/detail` | 照片详情 |
| `POST` | `/api/photo/update` | 编辑照片 |
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

## 致谢

- 核心 AI 提示词和评分思路来自 [InkTime](https://github.com/dai-hongtao/InkTime) by dai-hongtao
