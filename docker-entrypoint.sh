#!/bin/bash
set -e

# 确保配置目录存在
mkdir -p /app/config

# 创建或设置crontab
if [ "$DISABLE_CRON" != "true" ]; then
    echo "设置定时任务..."
    # 创建一个临时的crontab文件
    echo "0 4 * * * cd /app && python main.py --first_test >> /app/logs/first_test.log 2>&1" > /tmp/crontab
    echo "0 5 * * * cd /app && python main.py --http_test >> /app/logs/http_test.log 2>&1" >> /tmp/crontab
    echo "10 5 * * * cp -f /app/output/result.* /volume1/web/myweb/iptv/ >> /app/logs/copy.log 2>&1" >> /tmp/crontab
    
    # 安装crontab
    crontab /tmp/crontab
    rm /tmp/crontab
    
    # 启动cron服务
    echo "启动定时服务..."
    cron
    echo "定时任务已设置。"
fi

# 如果传入了命令参数，则执行对应的命令
if [ "$1" = "first_test" ]; then
    echo "执行第一次测速..."
    python main.py --first_test
elif [ "$1" = "http_test" ]; then
    echo "执行第二次测速..."
    python main.py --http_test
    
    # 复制测速结果到指定目录
    echo "复制测速结果到 /volume1/web/myweb/iptv/ 目录..."
    mkdir -p /volume1/web/myweb/iptv/
    cp -f /app/output/result.* /volume1/web/myweb/iptv/
elif [ "$1" = "full" ]; then
    echo "执行完整测速流程..."
    python main.py
    
    # 复制测速结果到指定目录
    echo "复制测速结果到 /volume1/web/myweb/iptv/ 目录..."
    mkdir -p /volume1/web/myweb/iptv/
    cp -f /app/output/result.* /volume1/web/myweb/iptv/
elif [ "$1" = "shell" ]; then
    exec /bin/bash
else
    # 默认启动时自动执行一次完整测速流程
    echo "容器已启动，开始执行初始测速..."
    python main.py
    
    # 复制测速结果到指定目录
    echo "复制测速结果到 /volume1/web/myweb/iptv/ 目录..."
    mkdir -p /volume1/web/myweb/iptv/
    cp -f /app/output/result.* /volume1/web/myweb/iptv/
    
    echo "初始测速完成，定时任务将在后台继续执行..."
    # 保持容器运行
    tail -f /dev/null
fi 