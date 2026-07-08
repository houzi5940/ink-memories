FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# 照片和数据通过 volume 挂载
VOLUME ["/photos", "/data"]

EXPOSE 8765

ENTRYPOINT ["python", "cli.py"]
CMD ["server"]
