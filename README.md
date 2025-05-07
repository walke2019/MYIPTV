![IPTV](https://socialify.git.ci/walke2019/IPTV_SuperA/image?description=1&descriptionEditable=IPTV%20%E7%9B%B4%E6%92%AD%E6%BA%90&forks=1&language=1&name=1&owner=1&pattern=Circuit%20Board&stargazers=1&theme=Auto)

# IPTV-API

一个可高度自定义的IPTV接口更新项目📺，自定义频道菜单，自动获取直播源，测速验效后生成可用的结果，可实现『✨秒播级体验🚀』

## 快速上手
### 工作流部署
1. Fork本项目：打开 https://github.com/walke2019/IPTV_SuperA 点击右上角的`Fork`按钮。
2. 修改配置：
   - 订阅源（`config/subscribe.txt`）：支持txt和m3u地址作为订阅，程序将依次读取其中的频道接口数据
   - 频道列表（`config/include_list.txt`）：定义需要保留的频道组和频道名称
   - 测速列表（`config/test.txt`）：定义需要进行测速的频道列表

3. 运行更新工作流：
   - 首次执行工作流需要您手动触发，后续执行（默认每天凌晨`00:00`）将自动触发
   - 如果您修改了配置文件想立刻执行更新，可以在Actions页面手动触发`Run workflow`
   - 工作流执行成功后（绿色勾图标），会生成以下文件：
     - `output/result_http_test.m3u`：第一次HTTP响应测速的结果
     - `output/result_http_test.txt`：第一次HTTP响应测速的结果（TXT格式）
     - `output/result.m3u`：最终测速优化后的结果
     - `output/result.txt`：最终测速优化后的结果（TXT格式）

4. 使用生成的直播源：
   - 直接访问：`https://raw.githubusercontent.com/您的用户名/IPTV_SuperA/main/output/result.m3u`
   - CDN加速：`https://cdn.jsdelivr.net/gh/您的用户名/IPTV_SuperA@main/output/result.txt`
   - 将以上链接复制到支持IPTV直播的播放器中即可使用

## 特性说明
- 支持M3U和TXT格式的订阅源
- 两次测速保证频道质量：
  1. 第一次HTTP响应测速
  2. 第二次视频流测速（针对`config/test.txt`中的频道）
- 自动去重：去除相同URL的重复频道
- 分组整理：根据`include_list.txt`配置的分组保存频道
- 测速排序：测速频道会按照响应速度排序
- 每日自动更新：自动获取最新的直播源并进行测速
