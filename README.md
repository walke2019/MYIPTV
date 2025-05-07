![IPTV](https://socialify.git.ci/walke2019/MYIPTV/image?description=1&descriptionEditable=IPTV%20%E7%9B%B4%E6%92%AD%E6%BA%90&forks=1&language=1&name=1&owner=1&pattern=Circuit%20Board&stargazers=1&theme=Auto)

# IPTV-API

一个可高度自定义的IPTV接口更新项目📺，自定义频道菜单，自动获取直播源，测速验效后生成可用的结果，可实现『✨秒播级体验🚀』

## 功能特性

### 1. 多源聚合
- 支持从多个源获取IPTV频道列表
- 支持M3U和TXT格式的订阅源
- 自动去重（基于URL去重）
- 自动合并相似分组

### 2. 智能测速
- 两阶段测速机制：
  1. 第一阶段：HTTP响应时间测试
     - 测试所有频道的HTTP响应时间
     - 生成初步测速结果：`result_http_test.m3u`和`result_http_test.txt`
  2. 第二阶段：视频流测速
     - 仅对`config/test.txt`中指定的频道进行测速
     - 测试视频流的实际下载速度
     - 生成最终优化结果：`result.m3u`和`result.txt`

### 3. 分组管理
- 支持自定义分组名称映射
- 自动合并相似分组（如"央视频道"和"CCTV"）
- 支持排除特定分组
- 分组内频道智能排序

## 配置说明

### 1. 订阅源配置（config/subscribe.txt）
```
http://example1.com/live.m3u
http://example2.com/live.txt
```
- 每行一个订阅源地址
- 支持M3U和TXT格式
- 程序会自动识别格式并解析

### 2. 分组和频道配置（config/include_list.txt）
```
group:🍄湖南频道
湖南都市
湖南经视
湖南娱乐

group:🍓央视频道
CCTV-1/CCTV1
CCTV-2/CCTV2

group:🐧卫视频道
湖南卫视
浙江卫视

group:🦄️港·澳·台
凤凰中文
TVB翡翠台
```
- 使用`group:`前缀定义分组
- 每个频道可以有多个名称变体（用`/`分隔）
- 分组顺序决定最终显示顺序
- 支持emoji作为分组图标
- 内置分组映射关系：
  - 央视频道 ⟺ 🍓央视频道
  - CCTV ⟺ 🍓央视频道
  - 卫视频道 ⟺ 🐧卫视频道
  - 湖南 ⟺ 🍄湖南频道
  - 港澳台 ⟺ 🦄️港·澳·台

### 3. 测速频道配置（config/test.txt）
```
湖南都市
湖南经视
湖南娱乐
湖南卫视
CCTV-1/CCTV1
```
- 每行一个频道名称
- 只有在此列表中的频道才会进行视频流测速
- 支持频道名称变体（与include_list.txt一致）
- 测速结果会影响频道排序（速度快的排在前面）

## 使用说明

### 1. 快速开始
1. Fork本项目：打开 https://github.com/walke2019/MYIPTV 点击右上角的`Fork`按钮
2. 修改配置文件：
   - `config/subscribe.txt`：添加你的IPTV订阅源
   - `config/include_list.txt`：配置需要的分组和频道
   - `config/test.txt`：配置需要测速的频道

### 2. 自动更新
- GitHub Actions会在每天凌晨00:00自动运行
- 每次运行会生成4个文件：
  - `output/result_http_test.m3u`：第一阶段HTTP测速结果（M3U格式）
  - `output/result_http_test.txt`：第一阶段HTTP测速结果（TXT格式）
  - `output/result.m3u`：最终优化结果（M3U格式）
  - `output/result.txt`：最终优化结果（TXT格式）

### 3. 使用生成的直播源
- 直接访问：`https://raw.githubusercontent.com/您的用户名/MYIPTV/main/output/result.m3u`
- CDN加速：`https://cdn.jsdelivr.net/gh/您的用户名/MYIPTV@main/output/result.txt`

## 最佳实践
1. 建议在`test.txt`中只包含常用的频道，这样可以加快更新速度
2. 使用`include_list.txt`来整理和规范化频道分组
3. 定期检查GitHub Actions运行日志，了解更新状态
4. 如果需要立即更新，可以手动触发GitHub Actions工作流

## 测试文件信息
最后更新时间：2025-05-08 02:42:23

### 测试文件列表
total 8
-rw-r--r-- 1 runner docker  64 May  8 02:42 test1.txt
-rw-r--r-- 1 runner docker 133 May  8 02:42 test2.txt

### 文件内容预览
#### test1.txt
```
这是修改后的测试文件1 - 修改于 2025-05-08 02:42:23
```

#### test2.txt
```
这是测试文件2
创建时间：2025-05-08 02:42:23
测试多行内容
行1
行2
行3
这是追加的内容 - 2025-05-08 02:42:23
```

## 最新更新信息
更新时间：2025-05-08 02:55:32

### 可用文件
- M3U格式：[`result.m3u`](https://raw.githubusercontent.com/walke2019/MYIPTV/main/output/result.m3u)
- TXT格式：[`result.txt`](https://raw.githubusercontent.com/walke2019/MYIPTV/main/output/result.txt)

### HTTP测速结果
- M3U格式：[`result_http_test.m3u`](https://raw.githubusercontent.com/walke2019/MYIPTV/main/output/result_http_test.m3u)
- TXT格式：[`result_http_test.txt`](https://raw.githubusercontent.com/walke2019/MYIPTV/main/output/result_http_test.txt)

## 最新更新信息
更新时间：2025-05-08 04:48:33

### 可用文件
- M3U格式：[`result.m3u`](https://raw.githubusercontent.com/walke2019/MYIPTV/main/output/result.m3u)
- TXT格式：[`result.txt`](https://raw.githubusercontent.com/walke2019/MYIPTV/main/output/result.txt)

### HTTP测速结果
- M3U格式：[`result_http_test.m3u`](https://raw.githubusercontent.com/walke2019/MYIPTV/main/output/result_http_test.m3u)
- TXT格式：[`result_http_test.txt`](https://raw.githubusercontent.com/walke2019/MYIPTV/main/output/result_http_test.txt)
