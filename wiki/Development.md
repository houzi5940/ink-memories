# 本地开发

## 环境要求

- Python 3.10+
- Node.js 20+（前端构建）
- 一个 VLM API Key（可选，用于实际分析；测试可跳过）

## 一步启动

```bash
# 1. 克隆项目
git clone https://github.com/houzi5940/ink-memories.git
cd ink-memories

# 2. Python 虚拟环境
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 3. 前端构建
cd frontend
npm install
npm run build
cd ..

# 4. 生成测试数据
python seed_local.py

# 5. 启动服务器
PHOTO_DIR=./test_photos DB_PATH=./data/photos.db python cli.py server
```

浏览器打开 `http://localhost:8765`

## 种子数据

`seed_local.py` 会创建：
- **10 张测试照片**（带颜色的纯色图片，标注文字）
- **10 条数据库记录**（含评分、类型、标签、EXIF 城市等）
- **占位前端文件**（React 构建产物会被 Vite 覆盖）

种子数据特点：
- 包含 8 种类型（旅行/猫咪/家庭/风景/日常/美食/毕业/夜景）
- 评分覆盖 72-96 分
- 35 个手写标签（杭州、西湖、猫咪、骑行…）
- 模拟了不同日期、不同城市

## 调试

### VLM API 调用

如果配置了 VLM API Key，可以从首页点击「开始分析」测试真实分析流程（前提是 `test_photos/` 中有未被分析的图片）。

如未配置，项目仍可正常运行和浏览种子数据。

### 常用命令

```bash
# 查看今日精选（终端）
python cli.py daily

# 查看当前分析进度（API）
curl http://localhost:8765/api/analyze/progress

# 查看系统状态
curl http://localhost:8765/api/status
```

### 前端开发

前端使用 Vite + React + Tailwind：

```bash
cd frontend

# 开发模式（HMR）
npm run dev

# 构建生产版本
npm run build

# TypeScript 类型检查
npm run typecheck
```

前端 React 组件通过 `window.getSelectedTags()` 和 `ink:tags:update` 自定义事件与 Jinja2 模板通信。编辑弹窗的 TagSelector 是 `main.tsx` 渲染到 `<div id="tag-selector-root">` 的。

## 项目路线图

- [x] AI 双维度评分
- [x] 每日精选
- [x] WebUI 浏览/搜索
- [x] 手动编辑（评分/标签/旁白）
- [x] 标签系统（React + shadcn/ui）
- [x] 相似照片去重
- [x] 分析进度条
- [ ] 人脸识别分组
- [ ] 多用户支持
- [ ] 分享功能
