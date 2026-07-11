# 部署指南（群晖 NAS）

## Docker 部署

### 1. 安装 Docker 套件

打开群晖「套件中心」，搜索并安装 Docker。

### 2. 上传项目

有多种方式：

**方法 A — Git 克隆（推荐，需要开启 SSH）：**
```bash
# SSH 登录群晖
ssh user@192.168.1.100

# 安装 Git（如果未安装）
sudo synopkg install_from_server git

# 克隆项目
cd /volume1/docker/
git clone https://github.com/houzi5940/ink-memories.git
```

**方法 B — SCP 上传：**
```bash
# 从本地上传（由于群晖禁用 SCP，使用 base64+SSH 管道）
# 或用 File Station 手动上传后解压
```

**方法 C — File Station：**
直接在群晖 DSM 的 File Station 中上传项目压缩包并解压。

### 3. 配置

```bash
cd /path/to/ink-memories

# 配置 API Key
cp .env.example .env
vi .env  # 编辑 VLM_API_KEY

# 修改 docker-compose.yml 中的照片路径
vi docker-compose.yml
# 将 /path/to/your/photos 改为你的实际照片路径
```

### 4. 构建并启动

```bash
# 使用 Docker Compose
sudo docker-compose up -d --build

# 或使用旧版 docker-compose
sudo docker-compose up -d --build
```

### 5. 验证

```bash
# 检查容器状态
sudo docker ps | grep ink-memories

# 查看日志
sudo docker logs ink-memories
```

浏览器访问 `http://你的NASIP:8765`

### 6. 首次分析

```bash
sudo docker exec ink-memories python cli.py analyze
```

## 定时任务

在群晖「控制面板 → 任务计划」中设置：

### 每天分析新照片（推荐）

- **任务名称**: InkMemories 分析
- **用户**: root
- **计划**: 每天 02:00
- **运行命令**:
  ```bash
  docker exec ink-memories python cli.py analyze
  ```

## Docker Compose 参考

```yaml
version: "3.8"

services:
  ink-memories:
    build: .
    image: ink-memories:latest
    container_name: ink-memories
    restart: unless-stopped
    ports:
      - "8765:8765"
    volumes:
      - /volume1/homes/user/Photos:/photos:ro
      - ./data:/data
    environment:
      - VLM_API_URL=${VLM_API_URL:-https://api.deepseek.com/v1/chat/completions}
      - VLM_API_KEY=${VLM_API_KEY:-}
      - VLM_MODEL=${VLM_MODEL:-deepseek-chat}
      - CONCURRENCY=${CONCURRENCY:-2}
      - BATCH_LIMIT=${BATCH_LIMIT:-0}
      - LOW_MEMORY_THRESHOLD_GB=${LOW_MEMORY_THRESHOLD_GB:-4.0}
      - LOW_MEMORY_CONCURRENCY=${LOW_MEMORY_CONCURRENCY:-1}
      - WEB_PORT=8765
```

## Dockerfile 说明

多阶段构建：

1. **Stage 1 (frontend-builder)**: 基于 Node 20，构建 React 前端
2. **Stage 2 (runtime)**: 基于 Python 3.11，运行 FastAPI 后端

## 维护命令

```bash
# 查看实时日志
sudo docker logs -f ink-memories

# 重启
sudo docker restart ink-memories

# 停止
sudo docker stop ink-memories

# 更新（拉取新代码后重新构建）
sudo docker-compose up -d --build --force-recreate

# 查看今日精选
sudo docker exec ink-memories python cli.py daily
```
