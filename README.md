# InkMemories · AI 照片回忆系统

> 基于 [InkTime](https://github.com/dai-hongtao/InkTime) 的 AI 照片评分思路，去掉墨水屏硬件部分，纯软件方案部署在群晖 NAS 上。

## ✨ 功能

- **AI 智能评分**：双维度评分（回忆值 + 美观值），自动分类
- **诗意旁白**：为每张照片生成一句话文案
- **每日精选**：从「历史上的今天」中选出最值得回忆的照片
- **WebUI 浏览**：按类型、评分、日期浏览和搜索照片
- **增量分析**：已分析的照片自动跳过，可随时中断重启

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
├── cli.py              # CLI 入口
├── config.py           # 配置
├── database.py         # SQLite 数据库操作
├── analyzer.py         # VLM 照片分析
├── daily.py            # 每日精选逻辑
├── server.py           # Flask WebUI
├── Dockerfile
├── docker-compose.yml
├── .env.example        # 环境变量模板
├── requirements.txt
└── templates/          # WebUI 模板
    ├── base.html
    ├── index.html      # 今日精选
    ├── gallery.html    # 照片库
    ├── stats.html      # 统计
    └── search.html     # 搜索
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
| `MEMORY_THRESHOLD` | 精选最低分 | 70 |
| `DAILY_PHOTO_QUANTITY` | 每日精选数 | 5 |

## 🔄 定时任务

建议在群晖「任务计划」中添加：

- **每天凌晨 2:00**：分析新照片
  ```bash
  sudo docker exec ink-memories python cli.py analyze
  ```

## 💰 费用估算

按 DeepSeek API 计价，分析 1 万张照片约 ¥10-20（仅首次全量分析时产生，后续增量分析费用很小）。

## 致谢

- 核心 AI 提示词和评分思路来自 [InkTime](https://github.com/dai-hongtao/InkTime) by dai-hongtao
