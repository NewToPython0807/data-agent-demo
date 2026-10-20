# 轻量「智能问数」Data Agent 镜像
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# 国内可覆盖为镜像源，例如：
#   docker build --build-arg PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple -t data-agent .
ARG PIP_INDEX_URL=https://pypi.org/simple

WORKDIR /app

COPY requirements.txt ./
RUN pip install --index-url ${PIP_INDEX_URL} -r requirements.txt

COPY app ./app
COPY static ./static

# 数据与日志目录（运行时挂载宿主机目录以持久化）
RUN mkdir -p /app/data

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
