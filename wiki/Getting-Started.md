# 快速上手

## Docker 部署（群晖 NAS）

### 前提条件

- 群晖 NAS 已安装 Docker 套件
- 已申请 VLM API Key（推荐 DeepSeek，https://platform.deepseek.com/）

### 步骤

**1. 下载项目**

```bash
git clone https://github.com/houzi5940/ink-memories.git
cd ink-memories
```

**2. 配置 API Key**

```bash
cp .env.example .env
# 编辑 .env 填写 VLM_API_KEY
```

**3. 配置照片目录**

编辑 `docker-compose.yml`，将 `/path/to/your/photos` 改为你的照片实际路径：

```yaml
volumes:
  - /volume1/homes/yourname/Photos:/photos:ro
  - ./data:/data
```

**4. 构建并启动**

```bash
sudo docker-compose up -d --build
```

**5. 分析照片**

首次需要手动触发分析：

```bash
sudo docker exec ink-memories python cli.py analyze
```

可在群晖「任务计划」中设置定时任务（推荐每天凌晨 2:00）。

**6. 访问 WebUI**

浏览器打开 `http://你的NASIP:8765`

## CLI 命令参考

项目入口 `cli.py` 支持以下子命令：

### `server` — 启动 WebUI

```bash
# 生产模式
python cli.py server

# 开发模式（可指定端口）
WEB_PORT=8765 python cli.py server
```

### `analyze` — 分析新照片

```bash
# 默认并发 2
python cli.py analyze

# 并发 4，最多分析 100 张
python cli.py analyze -j 4 -n 100
```

### `daily` — 查看今日精选（终端输出）

```bash
python cli.py daily
```

### `backfill-hashes` — 为旧数据回刷感知哈希

```bash
python cli.py backfill-hashes
```

## WebUI 使用

### 今日精选（首页）
- 自动展示「历史上的今天」照片
- 每张照片带每日全新描述的旁白
- 支持 Lightbox 放大查看

### 相册
- 按回忆分、美观分、日期、分析时间排序
- 按类型筛选（人物/旅行/猫咪/美食…）
- 按标签搜索筛选
- 分页浏览

### 编辑弹窗
- 点击照片卡片的 ✎ 按钮
- 支持修改：评分、分类、旁白、描述、理由、标签
- 标签系统支持搜索已有标签 / 新建标签 / 多选

### 统计
- 类型分布（柱状图 + 平均分）
- 回忆分分布（分段柱状图）
- 手动标签词云

### 搜索
- 按描述、理由、旁白、类型、标签关键词搜索
