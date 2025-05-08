FROM python:3.13-slim

# 设置工作目录
WORKDIR /app

# 安装必要的软件包和依赖
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    cron \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 安装 pipenv
RUN pip install --no-cache-dir pipenv

# 复制项目文件
COPY . /app/

# 使用pipenv安装依赖
RUN pipenv install --deploy --system

# 创建用于存储结果和日志的目录
RUN mkdir -p /app/output /app/logs

# 设置时区
ENV TZ=Asia/Shanghai

# 添加定时任务脚本
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# 设置挂载点
VOLUME ["/app/config", "/app/output", "/app/logs"]

# 启动命令
ENTRYPOINT ["/docker-entrypoint.sh"] 