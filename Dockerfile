FROM debian:bullseye-slim

# 接收构建参数
ARG PIP_INDEX_URL=https://pypi.org/simple/
ARG PIP_TRUSTED_HOST=pypi.org

# 设置工作目录
WORKDIR /app

# 设置pip源
RUN echo "[global]" > /etc/pip.conf && \
    echo "index-url = ${PIP_INDEX_URL}" >> /etc/pip.conf && \
    echo "trusted-host = ${PIP_TRUSTED_HOST}" >> /etc/pip.conf

# 替换为国内apt源
RUN cp /etc/apt/sources.list /etc/apt/sources.list.bak && \
    echo "deb http://mirrors.163.com/debian/ bullseye main contrib non-free" > /etc/apt/sources.list && \
    echo "deb http://mirrors.163.com/debian/ bullseye-updates main contrib non-free" >> /etc/apt/sources.list && \
    echo "deb http://mirrors.163.com/debian-security bullseye-security main contrib non-free" >> /etc/apt/sources.list

# 安装必要的软件包和依赖
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    ffmpeg \
    git \
    cron \
    tzdata \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && ln -sf python3 /usr/bin/python

# 复制项目文件
COPY . /app/

# 安装Python依赖
RUN pip3 install --no-cache-dir aiohttp asyncio

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