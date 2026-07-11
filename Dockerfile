# 构建前端
FROM node:20-slim AS frontend-builder

WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# 运行后端
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
COPY --from=frontend-builder /app/frontend/static/js /app/frontend/static/js

# 照片和数据通过 volume 挂载
VOLUME ["/photos", "/data"]

EXPOSE 8765

ENTRYPOINT ["python", "cli.py"]
CMD ["server"]
