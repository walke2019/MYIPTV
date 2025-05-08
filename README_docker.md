# IPTV测速工具 Docker 使用说明

## 群晖NAS环境下的部署方法

### 前提条件
- 群晖NAS已安装Docker套件
- 了解基本的Docker和Docker Compose命令

### 快速部署步骤

1. **准备目录结构**

   在群晖NAS上创建以下目录结构：
   ```
   /volume1/docker/iptvtest/
   ├── config/            # 配置文件目录
   │   ├── subscribe.txt  # 订阅源地址列表
   │   ├── include_list.txt # 需要包含的频道列表
   │   └── test.txt       # 需要测速的频道列表
   ├── output/            # 测速结果输出目录
   └── logs/              # 日志目录
   ```

   确保 `/volume1/web/myweb/iptv` 目录存在，用于存放最终的测速结果文件。

2. **克隆代码仓库**

   将本项目克隆到群晖NAS上的临时目录中。

3. **复制Docker相关文件**

   将 `Dockerfile`、`docker-entrypoint.sh` 和 `docker-compose.yml` 文件复制到 `/volume1/docker/iptvtest/` 目录。

4. **配置文件准备**

   在 `/volume1/docker/iptvtest/config/` 目录中创建并编辑以下配置文件：
   
   - `subscribe.txt`: 每行一个IPTV源地址
   - `include_list.txt`: 配置需要包含的频道组和频道
   - `test.txt`: 需要进行测速的频道列表

5. **构建并启动容器**

   在SSH终端中进入到 `/volume1/docker/iptvtest/` 目录，然后执行：
   ```bash
   docker-compose up -d
   ```

### 定时任务说明

容器启动后，会自动设置以下定时任务：

- 每天凌晨4:00（北京时间12:00）执行第一次测速（HTTP响应时间测试）
- 每天凌晨5:00（北京时间13:00）执行第二次测速（视频流测速）
- 每天凌晨5:10（北京时间13:10）将测速结果复制到 `/volume1/web/myweb/iptv/` 目录

### 手动执行测速

如需手动执行测速，可以使用以下命令：

```bash
# 执行第一次测速（HTTP响应时间测试）
docker exec iptvtest /docker-entrypoint.sh first_test

# 执行第二次测速（视频流测速）
docker exec iptvtest /docker-entrypoint.sh http_test

# 执行完整测速流程
docker exec iptvtest /docker-entrypoint.sh full

# 进入容器Shell
docker exec -it iptvtest /docker-entrypoint.sh shell
```

### 查看日志

测速过程的日志保存在 `/volume1/docker/iptvtest/logs/` 目录下：

- `first_test.log`: 第一次测速日志
- `http_test.log`: 第二次测速日志
- `copy.log`: 复制文件操作日志

### 自定义定时任务

如需自定义定时任务，可以编辑 `docker-entrypoint.sh` 文件中的crontab设置，然后重新构建容器。

### 禁用定时任务

如果只想手动执行测速，可以在 `docker-compose.yml` 文件中将 `DISABLE_CRON` 环境变量设置为 `true`。 