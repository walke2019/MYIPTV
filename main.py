import asyncio
import aiohttp
import logging
import os
from collections import OrderedDict
import re
import time
import shutil
import argparse  # 添加argparse库来解析命令行参数
import subprocess  # 添加subprocess库用于执行ffmpeg命令
import random

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 在文件开头修改配置
# EPG_URL = "http://epg.51zmt.top:8000/e.xml"  # EPG 源
# LOGO_URL = "http://epg.51zmt.top:8000/pics"  # 修改台标基础URL

# 读取订阅文件中的 URL
def read_subscribe_file(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        logging.error(f"未找到订阅文件: {file_path}")
        return []


# 读取包含想保留的组名或频道的文件
def read_include_list_file(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        logging.error(f"未找到包含列表文件: {file_path}")
        return []


# 异步获取 URL 内容并测试响应时间
async def fetch_url(session, url):
    start_time = time.time()
    try:
        async with session.get(url, timeout=10) as response:
            if response.status == 200:
                content = await response.text()
                elapsed_time = time.time() - start_time
                return content, elapsed_time
            else:
                logging.warning(f"请求 {url} 失败，状态码: {response.status}")
    except Exception as e:
        logging.error(f"请求 {url} 时发生错误: {e}")
    return None, float('inf')


# 解析 M3U 格式内容
def parse_m3u_content(content):
    channels = []
    lines = content.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith('#EXTINF:'):
            info = line.split(',', 1)
            if len(info) == 2:
                metadata = info[0]
                name = info[1]
                tvg_id = re.search(r'tvg-id="([^"]+)"', metadata)
                tvg_name = re.search(r'tvg-name="([^"]+)"', metadata)
                tvg_logo = re.search(r'tvg-logo="([^"]+)"', metadata)
                group_title = re.search(r'group-title="([^"]+)"', metadata)
                i += 1
                if i < len(lines):
                    url = lines[i].strip()
                    channel = {
                        'name': name,
                        'url': url,
                        'tvg_id': tvg_id.group(1) if tvg_id else None,
                        'tvg_name': tvg_name.group(1) if tvg_name else None,
                        'tvg_logo': tvg_logo.group(1) if tvg_logo else None,
                        'group_title': group_title.group(1) if group_title else None,
                        'response_time': float('inf')
                    }
                    channels.append(channel)
        i += 1
    return channels


# 解析 TXT 格式内容
def parse_txt_content(content):
    channels = []
    current_group = None
    lines = content.splitlines()
    for line in lines:
        line = line.strip()
        if line.endswith('#genre#'):
            current_group = line.replace('#genre#', '').strip()
        elif line:
            parts = line.split(',', 1)
            if len(parts) == 2:
                name, url = parts
                channel = {
                    'name': name,
                    'url': url,
                    'tvg_id': None,
                    'tvg_name': None,
                    'group_title': current_group,
                    'response_time': float('inf')
                }
                channels.append(channel)
    return channels


# 合并并去重频道
def merge_and_deduplicate(channels_list):
    all_channels = []
    for channels in channels_list:
        all_channels.extend(channels)
    unique_channels = []
    url_set = set()
    for channel in all_channels:
        if channel['url'] not in url_set:
            unique_channels.append(channel)
            url_set.add(channel['url'])
    return unique_channels


# 测试每个频道的响应时间
async def test_channel_response_time(session, channel):
    start_time = time.time()
    try:
        async with session.get(channel['url'], timeout=10) as response:
            if response.status == 200:
                elapsed_time = time.time() - start_time
                channel['response_time'] = elapsed_time
    except Exception as e:
        logging.error(f"测试 {channel['url']} 响应时间时发生错误: {e}")
    return channel


# 分组映射关系
GROUP_MAPPING = {
    '央视频道': '🍓央视频道',
    'CCTV': '🍓央视频道',
    '卫视频道': '🐧卫视频道',
    '卫视': '🐧卫视频道',
    '湖南': '🍄湖南频道',
    '港澳台': '🦄️港·澳·台',
    '港·澳·台': '🦄️港·澳·台',
    '斯玛特': None,  # None 表示要排除的分组
    '斯玛特,': None
}

def normalize_group_title(title):
    """标准化分组标题"""
    if not title:
        return ''
    
    # 移除末尾的 #genre# 和逗号
    title = title.strip().rstrip('#genre#').rstrip(',').strip()
    
    # 检查是否需要映射到其他分组
    for old_group, new_group in GROUP_MAPPING.items():
        if old_group in title:
            return new_group if new_group else ''
            
    return title

def normalize_channel_name(name):
    """标准化频道名称"""
    name = name.strip().upper()
    variants = set()  # 使用集合去重
    
    # 处理 CCTV-1/CCTV1 这样的规则
    if '/' in name:
        parts = [n.strip() for n in name.split('/')]
    else:
        parts = [name]
        
    for part in parts:
        # 添加原始格式
        variants.add(part)
        
        # 如果包含 CCTV，生成不同的变体
        if 'CCTV' in part:
            # 移除所有分隔符
            clean_name = part.replace('-', '').replace('_', '').replace(' ', '')
            variants.add(clean_name)
            
            # 提取数字部分
            number = ''.join(c for c in clean_name if c.isdigit())
            if number:
                # 添加带连字符的版本
                variants.add(f'CCTV-{number}')
                # 添加不带连字符的版本
                variants.add(f'CCTV{number}')
                
    return list(variants)

def get_channel_id(name):
    """根据频道名称获取对应的频道ID"""
    # 常见频道ID映射
    channel_ids = {
        'CCTV-1': 'cctv1',
        'CCTV1': 'cctv1',
        'CCTV-2': 'cctv2',
        'CCTV2': 'cctv2',
        'CCTV-3': 'cctv3',
        'CCTV3': 'cctv3',
        'CCTV-4': 'cctv4',
        'CCTV4': 'cctv4',
        'CCTV-5': 'cctv5',
        'CCTV5': 'cctv5',
        'CCTV-5+': 'cctv5plus',
        'CCTV5+': 'cctv5plus',
        'CCTV-6': 'cctv6',
        'CCTV6': 'cctv6',
        'CCTV-7': 'cctv7',
        'CCTV7': 'cctv7',
        'CCTV-8': 'cctv8',
        'CCTV8': 'cctv8',
        'CCTV-9': 'cctv9',
        'CCTV9': 'cctv9',
        'CCTV-10': 'cctv10',
        'CCTV10': 'cctv10',
        'CCTV-11': 'cctv11',
        'CCTV11': 'cctv11',
        'CCTV-12': 'cctv12',
        'CCTV12': 'cctv12',
        'CCTV-13': 'cctv13',
        'CCTV13': 'cctv13',
        'CCTV-14': 'cctv14',
        'CCTV14': 'cctv14',
        'CCTV-15': 'cctv15',
        'CCTV15': 'cctv15',
        'CCTV-16': 'cctv16',
        'CCTV16': 'cctv16',
        'CCTV-17': 'cctv17',
        'CCTV17': 'cctv17',
        '湖南卫视': 'hunan',
        '浙江卫视': 'zhejiang',
        '江苏卫视': 'jiangsu',
        '北京卫视': 'beijing',
        '东方卫视': 'dongfang',
        '安徽卫视': 'anhui',
        '广东卫视': 'guangdong',
        '深圳卫视': 'shenzhen',
        '辽宁卫视': 'liaoning',
        '山东卫视': 'shandong',
        '黑龙江卫视': 'heilongjiang',
        '湖北卫视': 'hubei',
        '河南卫视': 'henan',
        '陕西卫视': 'shanxi',
        '四川卫视': 'sichuan',
        '重庆卫视': 'chongqing',
        '江西卫视': 'jiangxi',
        '贵州卫视': 'guizhou',
        '河北卫视': 'hebei',
        '福建卫视': 'fujian',
        '东南卫视': 'dongnan',
        '海南卫视': 'hainan',
        '云南卫视': 'yunnan',
        '吉林卫视': 'jilin',
        '内蒙古卫视': 'neimeng',
        '甘肃卫视': 'gansu',
        '宁夏卫视': 'ningxia',
        '青海卫视': 'qinghai',
        '西藏卫视': 'xizang',
        '新疆卫视': 'xinjiang',
        '凤凰中文': 'fenghuangzhongwen',
        '凤凰资讯': 'fenghuangzixun',
        '翡翠台': 'tvb',
        'TVB翡翠台': 'tvb',
        '明珠台': 'pearl',
        'Pearl明珠台': 'pearl',
        'TVBS新闻': 'tvbs',
        '无线新闻': 'tvbnews',
        '湖南都市': 'hunandushi',
        '湖南经视': 'hunanjingshi',
        '湖南娱乐': 'hunanyule',
        '金鹰纪实': 'jinyingjishi',
        '快乐垂钓': 'kuailechuidiao'
    }
    
    # 清理频道名称
    name = name.upper().strip()
    
    # 尝试直接匹配
    if name in channel_ids:
        return channel_ids[name]
    
    # 处理CCTV频道
    if 'CCTV' in name:
        number = ''.join(filter(str.isdigit, name))
        if number:
            return f'cctv{number}'
    
    # 处理卫视频道
    if '卫视' in name:
        province = name.replace('卫视', '').strip()
        pinyin = {
            '北京': 'beijing',
            '东方': 'dongfang',
            '浙江': 'zhejiang',
            '江苏': 'jiangsu',
            '湖南': 'hunan',
            '安徽': 'anhui',
            # ... 可以添加更多拼音映射
        }
        if province in pinyin:
            return pinyin[province]
    
    # 如果没有匹配到，返回小写的频道名
    return name.lower()

def filter_channels(channels, include_list):
    filtered_channels = []
    current_group = None
    channel_group_mapping = {}
    channel_name_mapping = {}  # 存储标准频道名映射
    processed_channels = set()  # 用于去重
    channel_variants = {}  # 存储频道名称的不同变体
    allowed_channels = set()  # 存储允许的频道名称变体
    
    # 解析 include_list 中的分组信息和频道名称
    for line in include_list:
        line = line.strip()
        if line.startswith('group:'):
            current_group = line.replace('group:', '').strip()
        elif line and current_group:
            # 获取频道名称的所有变体
            original_name = line  # 保存原始名称作为标准名称
            variants = normalize_channel_name(line)
            for variant in variants:
                channel_variants[variant] = current_group
                channel_name_mapping[variant] = original_name  # 记录标准名称映射
                allowed_channels.add(variant)  # 添加到允许的频道列表
    
    # 过滤并重新分组频道
    for channel in channels:
        original_name = channel['name'].strip()
        name = original_name.upper()  # 转换为大写以进行比较
        url = channel['url'].strip()
        
        # 生成唯一标识（频道名+URL）
        channel_id = f"{name}_{url}"
        
        # 跳过已处理的频道
        if channel_id in processed_channels:
            continue
            
        # 获取当前频道名称的所有可能变体
        current_variants = normalize_channel_name(name)
        
        # 检查频道名是否匹配任何允许的变体
        matched = False
        for variant in current_variants:
            if variant in allowed_channels:  # 只处理允许的频道
                standard_name = channel_name_mapping[variant].split('/')[0]  # 使用第一个名称作为标准名称
                channel['group_title'] = f"{channel_variants[variant]}#genre#"
                channel['name'] = standard_name
                filtered_channels.append(channel)
                processed_channels.add(channel_id)
                matched = True
                break
            
    return filtered_channels


def get_group_order_from_include_list(include_list):
    """从 include_list 中获取分组顺序和每个分组内的频道顺序"""
    groups = []
    channel_order = {}  # 存储每个频道的顺序
    current_group = None
    channel_index = 0
    
    for line in include_list:
        line = line.strip()
        if line.startswith('group:'):
            current_group = line.replace('group:', '').strip()
            if current_group not in groups:
                groups.append(current_group)
        elif line and current_group:
            # 保存频道的顺序
            channel_name = line.split('/')[0].strip()  # 取第一个名称作为主要名称
            channel_order[channel_name] = channel_index
            channel_index += 1
    
    return groups, channel_order


# 生成 M3U 文件，增加 EPG 回放支持
def generate_m3u_file(channels, output_path, replay_days=7, custom_sort_order=None, include_list=None):
    # 获取 include_list 中的分组顺序和频道顺序
    group_order, channel_order = get_group_order_from_include_list(include_list) if include_list else ([], {})
    
    # 读取需要测速的频道列表
    test_channels = []
    try:
        with open('config/test.txt', 'r', encoding='utf-8') as f:
            test_channels = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        logging.warning("未找到test.txt文件，跳过测速排序")
    
    test_channels_set = set(test_channels)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('#EXTM3U x-tvg-url="http://epg.51zmt.top:8000/e.xml"\n')
        
        # 添加时间戳注释，确保每次生成文件内容不同
        current_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        f.write(f'#生成时间: {current_time}\n')
        
        # 按分组标题分组
        group_channels = {}
        for channel in channels:
            group_title = channel['group_title'] or ''
            # 清理分组名称中的多余字符
            group_title = group_title.strip().rstrip('#genre#').rstrip(',').strip()
            if group_title not in group_channels:
                group_channels[group_title] = []
            group_channels[group_title].append(channel)

        def custom_sort_key(group_title):
            try:
                return group_order.index(group_title)
            except ValueError:
                return float('inf')

        # 使用 include_list 中的分组顺序
        sorted_groups = sorted(group_channels.keys(), key=custom_sort_key)
        
        for group_title in sorted_groups:
            group = group_channels[group_title]
            
            # 对分组内的频道进行排序
            def channel_sort_key(channel):
                channel_name = channel['name'].split('/')[0].strip()
                # 首先按照include_list中的顺序排序
                list_order = channel_order.get(channel_name, float('inf'))
                
                # 如果是测速频道，还要考虑速度排序
                if channel_name in test_channels_set:
                    stream_time = channel.get('stream_response_time', float('inf'))
                    speed = channel.get('speed', 0)
                    # 对于相同频道名称的源，按速度和响应时间排序
                    return (list_order, -speed, stream_time)
                
                return (list_order, 0, float('inf'))
            
            sorted_group = sorted(group, key=channel_sort_key)
            
            for channel in sorted_group:
                channel_name = channel['name']
                # 构建EPG和台标信息
                # 对于CCTV频道，去掉tvg-id和logo URL中的连字符
                if 'CCTV-' in channel_name:
                    logo_name = channel_name.replace('-', '')
                    tvg_id = logo_name.replace(' ', '_')
                    tvg_logo = f"https://live.izbds.com/logo/{logo_name}.png"
                else:
                    tvg_id = channel_name.replace(' ', '_')
                    tvg_logo = f"https://live.izbds.com/logo/{channel_name}.png"
                
                f.write(f'#EXTINF:-1 tvg-id="{tvg_id}" tvg-name="{channel_name}" tvg-logo="{tvg_logo}" group-title="{group_title}",{channel_name}\n')
                f.write(f'{channel["url"]}\n')


# 生成 TXT 文件
def generate_txt_file(channels, output_path, custom_sort_order=None, include_list=None):
    # 获取 include_list 中的分组顺序和频道顺序
    group_order, channel_order = get_group_order_from_include_list(include_list) if include_list else ([], {})
    
    # 读取需要测速的频道列表
    test_channels = []
    try:
        with open('config/test.txt', 'r', encoding='utf-8') as f:
            test_channels = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        logging.warning("未找到test.txt文件，跳过测速排序")
    
    test_channels_set = set(test_channels)
    
    # 按分组标题分组
    group_channels = {}
    for channel in channels:
        group_title = channel['group_title'] or ''
        # 清理分组名称中的多余字符
        group_title = group_title.strip().rstrip('#genre#').rstrip(',').strip()
        if group_title not in group_channels:
            group_channels[group_title] = []
        group_channels[group_title].append(channel)

    def custom_sort_key(group_title):
        try:
            return group_order.index(group_title)
        except ValueError:
            return float('inf')

    # 使用 include_list 中的分组顺序
    sorted_groups = sorted(group_channels.keys(), key=custom_sort_key)

    with open(output_path, 'w', encoding='utf-8') as f:
        # 添加更新时间信息
        current_time = time.strftime("%Y%m%d %H:%M:%S", time.localtime())
        f.write('更新时间,#genre#\n')
        f.write(f'{current_time},https://cdn.jsdelivr.net/gh/walke2019/MYIPTV@main/output/ad/ad.mp4\n\n')
        
        for group_title in sorted_groups:
            group = group_channels[group_title]
            
            # 对分组内的频道进行排序
            def channel_sort_key(channel):
                channel_name = channel['name'].split('/')[0].strip()
                # 首先按照include_list中的顺序排序
                list_order = channel_order.get(channel_name, float('inf'))
                
                # 如果是测速频道，还要考虑速度排序
                if channel_name in test_channels_set:
                    stream_time = channel.get('stream_response_time', float('inf'))
                    speed = channel.get('speed', 0)
                    # 对于相同频道名称的源，按速度和响应时间排序
                    return (list_order, -speed, stream_time)
                
                return (list_order, 0, float('inf'))
            
            sorted_group = sorted(group, key=channel_sort_key)
            
            if group_title:
                f.write(f'{group_title}#genre#\n')
            for channel in sorted_group:
                f.write(f'{channel["name"]},{channel["url"]}\n')
            f.write('\n')


async def test_stream_speed(session, url, timeout=5):
    """使用aiohttp测试视频流速度"""
    try:
        logging.info(f"开始测试视频流: {url}")
        start_time = time.time()
        total_size = 0
        chunk_size = 8192  # 8KB chunks
        
        async with session.get(url, timeout=timeout) as response:
            if response.status != 200:
                # 对于某些特殊状态码，我们认为可能是临时性的
                if response.status in [301, 302, 307, 308]:
                    location = response.headers.get('Location')
                    if location:
                        return await test_stream_speed(session, location, timeout)
                
                logging.warning(f"视频流响应状态码异常: {response.status}")
                return {
                    'success': False,
                    'response_time': time.time() - start_time,
                    'error': f'HTTP status {response.status}'
                }
            
            content_type = response.headers.get('content-type', '').lower()
            
            # 如果是m3u8文件，解析并测试第一个分片
            if 'application/vnd.apple.mpegurl' in content_type or 'm3u8' in content_type or url.endswith('.m3u8'):
                try:
                    m3u8_content = await response.text()
                    # 查找第一个.ts文件链接
                    ts_url = None
                    for line in m3u8_content.splitlines():
                        if line.strip() and not line.startswith('#'):
                            if line.startswith('http'):
                                ts_url = line
                            else:
                                # 处理相对路径
                                base_url = str(response.url)
                                if base_url.endswith('m3u8'):
                                    base_url = base_url.rsplit('/', 1)[0]
                                if not base_url.endswith('/'):
                                    base_url += '/'
                                ts_url = base_url + line
                            break
                    
                    if ts_url:
                        logging.info(f"测试m3u8分片: {ts_url}")
                        try:
                            async with session.get(ts_url, timeout=timeout) as ts_response:
                                if ts_response.status == 200:
                                    chunk_start_time = time.time()
                                    async for chunk in ts_response.content.iter_chunked(chunk_size):
                                        total_size += len(chunk)
                                        if time.time() - chunk_start_time > timeout:
                                            break
                                else:
                                    # 即使分片请求失败，我们也不立即判定为失败
                                    return {
                                        'success': True,
                                        'response_time': time.time() - start_time,
                                        'speed': 0.1,
                                        'error': None
                                    }
                        except Exception as e:
                            # 分片测试失败，但m3u8已经成功获取
                            return {
                                'success': True,
                                'response_time': time.time() - start_time,
                                'speed': 0.1,
                                'error': None
                            }
                    else:
                        # m3u8解析成功但没有找到分片，仍然认为是可用的
                        return {
                            'success': True,
                            'response_time': time.time() - start_time,
                            'speed': 0.1,
                            'error': None
                        }
                except Exception as e:
                    logging.error(f"解析m3u8文件失败: {str(e)}")
                    # m3u8解析失败但获取成功，给一个较低的评分
                    return {
                        'success': True,
                        'response_time': time.time() - start_time,
                        'speed': 0.05,
                        'error': f'M3U8 parse error: {str(e)}'
                    }
            else:
                # 对于非m3u8文件，直接测试流速度
                chunk_start_time = time.time()
                async for chunk in response.content.iter_chunked(chunk_size):
                    total_size += len(chunk)
                    if time.time() - chunk_start_time > timeout:
                        break
            
            end_time = time.time()
            elapsed_time = end_time - start_time
            speed = total_size / (1024 * 1024 * elapsed_time)  # MB/s
            
            logging.info(f"视频流测试完成 - URL: {url}")
            logging.info(f"响应时间: {elapsed_time:.2f}秒")
            logging.info(f"下载速度: {speed:.2f} MB/s")
            
            return {
                'success': True,
                'response_time': elapsed_time,
                'speed': speed,
                'error': None
            }
            
    except asyncio.TimeoutError:
        logging.warning(f"视频流测试超时: {url}")
        return {
            'success': False,
            'response_time': float('inf'),
            'error': 'Timeout'
        }
    except Exception as e:
        logging.error(f"视频流测试异常: {url}")
        logging.error(f"异常信息: {str(e)}")
        return {
            'success': False,
            'response_time': float('inf'),
            'error': str(e)
        }

async def test_specific_channels_speed(session, channels, test_channels_list):
    """测试特定频道列表中的频道速度"""
    test_channels_set = set(test_channels_list)
    test_results = {}
    
    total_channels = sum(1 for channel in channels if channel['name'].split('/')[0].strip() in test_channels_set)
    tested_channels = 0
    
    logging.info(f"开始测试指定频道，共 {total_channels} 个频道需要测试")
    
    # 创建信号量来限制并发数
    sem = asyncio.Semaphore(10)  # 限制最大并发数为10
    
    async def test_single_channel(channel):
        nonlocal tested_channels
        channel_name = channel['name'].split('/')[0].strip()
        
        async with sem:  # 使用信号量控制并发
            tested_channels += 1
            logging.info(f"正在测试第 {tested_channels}/{total_channels} 个频道: {channel_name}")
            
            if channel_name not in test_results:
                test_results[channel_name] = []
            
            # 保留原有的HTTP响应时间
            http_response_time = channel.get('response_time', float('inf'))
            logging.info(f"频道 {channel_name} 的HTTP响应时间: {http_response_time:.2f}秒")
            
            # 使用新的流媒体测试方法
            result = await test_stream_speed(session, channel['url'])
            
            # 无论成功与否都记录结果
            speed = result.get('speed', 0)
            response_time = result.get('response_time', float('inf'))
            
            # 如果测试失败，给予较低的评分而不是丢弃
            if not result['success']:
                speed = 0.01  # 给予一个很低的速度
                response_time = float('inf')  # 响应时间设为最大
                
            logging.info(f"频道 {channel_name} 测试完成")
            logging.info(f"HTTP响应时间: {http_response_time:.2f}秒, 视频流响应时间: {response_time:.2f}秒, 速度: {speed:.2f} MB/s")
            
            test_results[channel_name].append({
                'url': channel['url'],
                'http_response_time': http_response_time,
                'stream_response_time': response_time,
                'speed': speed,
                'channel': channel,
                'error': result.get('error', None)
            })
    
    # 创建所有测试任务
    test_tasks = []
    for channel in channels:
        channel_name = channel['name'].split('/')[0].strip()
        if channel_name in test_channels_set:
            test_tasks.append(test_single_channel(channel))
    
    # 并发执行所有测试任务
    await asyncio.gather(*test_tasks)
    
    # 对每个频道的所有源进行排序，但保留所有源
    optimized_channels = []
    logging.info("\n开始处理测速结果:")
    
    for channel_name, results in test_results.items():
        if results:
            # 按速度和响应时间排序
            sorted_results = sorted(results, key=lambda x: (-x.get('speed', 0), x['stream_response_time'], x['http_response_time']))
            
            # 添加所有源，但保持排序
            for result in sorted_results:
                channel = result['channel']
                channel['http_response_time'] = result['http_response_time']
                channel['stream_response_time'] = result['stream_response_time']
                channel['speed'] = result['speed']
                optimized_channels.append(channel)
                
                # 只为最快的源打印详细日志
                if result == sorted_results[0]:
                    logging.info(f"频道: {channel_name}")
                    logging.info(f"  - 最佳源: {channel['url']}")
                    logging.info(f"  - HTTP响应时间: {channel['http_response_time']:.2f}秒")
                    logging.info(f"  - 视频流响应时间: {channel['stream_response_time']:.2f}秒")
                    logging.info(f"  - 下载速度: {channel['speed']:.2f} MB/s")
    
    logging.info(f"\n测速完成，共测试 {tested_channels} 个频道源，保留所有源但已按速度排序")
    return optimized_channels


async def main():
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='IPTV频道测速和整理工具')
    parser.add_argument('--first_test', action='store_true', help='只执行第一次测速（HTTP响应时间测试）')
    parser.add_argument('--http_test', action='store_true', help='只执行第二次测速（视频流测速）')
    parser.add_argument('--ffmpeg_test', action='store_true', help='使用FFmpeg对指定频道进行测试')
    args = parser.parse_args()

    # 设置输入和输出文件路径
    subscribe_file = 'config/subscribe.txt'
    include_list_file = 'config/include_list.txt'
    test_channels_file = 'config/test.txt'
    ffmpeg_test_file = 'config/ffmpeg.txt'
    
    # 输出文件路径
    output_dir = 'output'
    output_first_test_m3u = f'{output_dir}/first_test.m3u'
    output_first_test_txt = f'{output_dir}/first_test.txt'
    output_m3u = f'{output_dir}/result.m3u'
    output_txt = f'{output_dir}/result.txt'

    # 自定义排序顺序
    custom_sort_order = ['🍄湖南频道', '🍓央视频道', '🐧卫视频道', '🦄️港·澳·台']

    # 确保输出目录存在
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # 如果是FFmpeg测试，只处理result.m3u文件中的指定频道
    if args.ffmpeg_test:
        # 读取需要用FFmpeg测试的频道列表
        ffmpeg_channels = read_include_list_file(ffmpeg_test_file)
        if not ffmpeg_channels:
            logging.error("FFmpeg测试频道文件中没有有效的频道名称。")
            return
            
        logging.info("\n==================== FFmpeg测试阶段 ====================")
        logging.info(f"即将使用FFmpeg测试以下频道：{', '.join(ffmpeg_channels)}")
        
        if not os.path.exists(output_m3u):
            logging.error(f"找不到文件 {output_m3u}，请先运行普通测速生成该文件。")
            return
            
        # 读取现有的m3u文件
        with open(output_m3u, 'r', encoding='utf-8') as f:
            m3u_content = f.read()
            
        # 解析m3u文件内容
        channels = parse_m3u_content(m3u_content)
        
        # 过滤出需要测试的频道
        ffmpeg_channel_set = set(ffmpeg_channels)
        channels_to_test = []
        
        for channel in channels:
            channel_name = channel['name'].split('/')[0].strip()
            if channel_name in ffmpeg_channel_set:
                channels_to_test.append(channel)
                
        if not channels_to_test:
            logging.warning("在现有m3u文件中未找到指定的FFmpeg测试频道。")
            return
            
        # 对这些频道进行FFmpeg测试
        tested_channels = await test_channels_with_ffmpeg(channels_to_test)
        
        # 更新原始频道列表中的测试结果
        updated_channels = []
        tested_dict = {f"{ch['name']}_{ch['url']}": ch for ch in tested_channels}
        
        # 创建一个字典来存储每个频道名称对应的成功测试通过的频道列表
        successful_channels_by_name = {}
        for ch in tested_channels:
            if ch.get('ffmpeg_status') == 'success':
                channel_name = ch['name'].split('/')[0].strip()
                if channel_name not in successful_channels_by_name:
                    successful_channels_by_name[channel_name] = []
                successful_channels_by_name[channel_name].append(ch)
        
        # 处理原始频道列表
        for channel in channels:
            channel_key = f"{channel['name']}_{channel['url']}"
            channel_name = channel['name'].split('/')[0].strip()
            
            if channel_name in ffmpeg_channel_set:
                # 这是需要测试的频道
                if channel_key in tested_dict and tested_dict[channel_key].get('ffmpeg_status') == 'success':
                    # 这个具体的源测试成功了，添加到更新列表
                    updated_channels.append(tested_dict[channel_key])
                # 不再保留测试失败的源
            else:
                # 这不是我们需要测试的频道，保留原样
                updated_channels.append(channel)
        
        # 重新生成m3u和txt文件
        logging.info("\n生成FFmpeg测试后的文件...")
        
        # 添加特殊标记，确保文件内容在每次测试后都会变化
        current_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        for channel in updated_channels:
            # 添加测试标记
            channel['test_timestamp'] = current_time
            
        # 读取包含列表文件
        include_list = read_include_list_file(include_list_file)
        generate_m3u_file(updated_channels, output_m3u, custom_sort_order=custom_sort_order, include_list=include_list)
        generate_txt_file(updated_channels, output_txt, custom_sort_order=custom_sort_order, include_list=include_list)
        
        # 输出测试统计信息
        total_tested = len(channels_to_test)
        success_count = sum(1 for ch in tested_channels if ch.get('ffmpeg_status') == 'success')
        fail_count = total_tested - success_count
        
        logging.info(f"✅ FFmpeg测试完成，共测试 {total_tested} 个频道源")
        logging.info(f"✅ 测试成功: {success_count} 个")
        logging.info(f"❌ 测试失败: {fail_count} 个")
        logging.info(f"✓ 保留频道总数: {len(updated_channels)} 个")
        return

    # 读取订阅文件
    urls = read_subscribe_file(subscribe_file)
    if not urls:
        logging.error("订阅文件中没有有效的 URL。")
        return

    # 读取包含列表文件
    include_list = read_include_list_file(include_list_file)
    
    # 读取需要测速的频道列表
    test_channels = read_include_list_file(test_channels_file)

    # 异步获取所有 URL 的内容
    async with aiohttp.ClientSession() as session:
        tasks = [fetch_url(session, url) for url in urls]
        results = await asyncio.gather(*tasks)

    all_channels = []
    for content, _ in results:
        if content:
            if '#EXTM3U' in content:
                channels = parse_m3u_content(content)
            else:
                channels = parse_txt_content(content)
            all_channels.append(channels)

    # 合并并去重频道
    unique_channels = merge_and_deduplicate(all_channels)

    # 如果是第一次测速或没有指定参数，执行HTTP响应时间测试
    if args.first_test or (not args.first_test and not args.http_test):
        # 测试每个频道的响应时间
        async with aiohttp.ClientSession() as session:
            logging.info("\n==================== 第一阶段：HTTP响应时间测试 ====================")
            tasks = [test_channel_response_time(session, channel) for channel in unique_channels]
            unique_channels = await asyncio.gather(*tasks)
            
            # 保存第一次测速结果（HTTP响应时间测试后）
            filtered_channels_first = filter_channels(unique_channels, include_list)
            generate_m3u_file(filtered_channels_first, output_first_test_m3u, custom_sort_order=custom_sort_order, include_list=include_list)
            generate_txt_file(filtered_channels_first, output_first_test_txt, custom_sort_order=custom_sort_order, include_list=include_list)
            logging.info("✅ 第一阶段测试完成，已保存HTTP响应时间测试结果。")
        
    # 如果是第二次测速或没有指定参数，执行视频流测速
    if args.http_test or (not args.first_test and not args.http_test):
        # 对特定频道进行测速
        if test_channels:
            async with aiohttp.ClientSession() as session:
                logging.info("\n==================== 第二阶段：视频流测速 ====================")
                logging.info(f"即将测试以下频道的视频流质量：{', '.join(test_channels)}")
                optimized_channels = await test_specific_channels_speed(session, unique_channels, test_channels)
                
                # 更新原始频道列表中的响应时间
                optimized_channels_dict = {f"{ch['name']}_{ch['url']}": ch for ch in optimized_channels}
                for channel in unique_channels:
                    channel_key = f"{channel['name']}_{channel['url']}"
                    if channel_key in optimized_channels_dict:
                        channel.update(optimized_channels_dict[channel_key])

    # 过滤频道
    filtered_channels = filter_channels(unique_channels, include_list)

    # 生成最终的 M3U 和 TXT 文件
    if args.http_test or (not args.first_test and not args.http_test):
        if test_channels:
            logging.info("\n生成最终文件（包含测速结果）...")
            generate_m3u_file(filtered_channels, output_m3u, custom_sort_order=custom_sort_order, include_list=include_list)
            generate_txt_file(filtered_channels, output_txt, custom_sort_order=custom_sort_order, include_list=include_list)
            logging.info("✅ 第二阶段测试完成，已更新频道测速信息。")
        else:
            logging.warning("⚠️ 未找到需要测速的频道列表，跳过第二阶段测速。")

    # 如果没有指定具体测试，则执行完整流程
    if not args.first_test and not args.http_test:
        logging.info("\n==================== 测速任务完成 ====================")
        logging.info("✅ 已生成所有结果文件：")
        logging.info(f"  - {output_first_test_m3u}：第一阶段HTTP测速结果")
        logging.info(f"  - {output_first_test_txt}：第一阶段HTTP测速结果（TXT格式）")
        logging.info(f"  - {output_m3u}：第二阶段视频流测速结果")
        logging.info(f"  - {output_txt}：第二阶段视频流测速结果（TXT格式）")
    elif args.first_test:
        logging.info("\n==================== 第一阶段测速任务完成 ====================")
        logging.info("✅ 已生成第一阶段测速结果文件：")
        logging.info(f"  - {output_first_test_m3u}：HTTP响应时间测试结果")
        logging.info(f"  - {output_first_test_txt}：HTTP响应时间测试结果（TXT格式）")
    elif args.http_test:
        logging.info("\n==================== 第二阶段测速任务完成 ====================")
        logging.info("✅ 已生成第二阶段测速结果文件：")
        logging.info(f"  - {output_m3u}：视频流测速结果")
        logging.info(f"  - {output_txt}：视频流测速结果（TXT格式）")


async def test_channels_with_ffmpeg(channels):
    """使用FFmpeg测试频道流的稳定性和速度"""
    logging.info(f"开始使用FFmpeg测试频道，共 {len(channels)} 个频道")
    
    # 记录测试开始时间
    test_start_time = time.time()
    current_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    logging.info(f"FFmpeg测试开始时间: {current_time}")
    
    results = []
    for i, channel in enumerate(channels):
        logging.info(f"正在测试第 {i+1}/{len(channels)} 个频道: {channel['name']}")
        
        # 保存原有的测试数据
        channel['ffmpeg_response_time'] = float('inf')
        channel['ffmpeg_speed'] = 0
        channel['ffmpeg_error'] = None
        channel['ffmpeg_status'] = 'failed'  # 默认为失败状态
        # 添加测试时间戳
        channel['test_time'] = current_time

        try:
            # 构建FFmpeg命令
            # 设置5秒超时，只获取关键帧，不保存输出
            ffmpeg_cmd = [
                'ffmpeg',
                '-timeout', '5000000',  # 5秒超时（微秒单位）
                '-i', channel['url'],
                '-t', '5',  # 只测试5秒
                '-c', 'copy',  # 不做转码，只复制流
                '-f', 'null',  # 输出到空设备
                '-'
            ]
            
            start_time = time.time()
            
            # 执行FFmpeg命令
            proc = subprocess.Popen(
                ffmpeg_cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE, 
                text=True
            )
            
            try:
                # 设置超时
                stdout, stderr = proc.communicate(timeout=15)  # 15秒总超时
                
                # 计算执行时间
                elapsed_time = time.time() - start_time
                channel['ffmpeg_response_time'] = elapsed_time
                
                # 检查是否有错误输出
                if proc.returncode != 0:
                    channel['ffmpeg_error'] = f"FFmpeg返回非零状态码: {proc.returncode}"
                    logging.warning(f"FFmpeg测试返回非零状态码: {proc.returncode}")
                    logging.debug(f"错误输出: {stderr}")
                    
                    # 根据不同的错误码设置不同的失败标记
                    if proc.returncode == 8:
                        channel['ffmpeg_status'] = 'not_found'  # 找不到文件或无法打开流
                    elif proc.returncode == 146:
                        channel['ffmpeg_status'] = 'refused'  # 连接被拒绝
                    else:
                        channel['ffmpeg_status'] = 'failed'  # 其他错误
                        
                else:
                    # 解析输出，查找速度信息
                    speed_pattern = r'speed=\s*([0-9.]+)x'
                    matches = re.findall(speed_pattern, stderr)
                    if matches:
                        # 取最后一个速度值
                        last_speed = float(matches[-1])
                        channel['ffmpeg_speed'] = last_speed
                        channel['ffmpeg_status'] = 'success'  # 标记为成功
                        logging.info(f"频道 {channel['name']} 的FFmpeg测试速度: {last_speed}x")
                    else:
                        logging.warning(f"未能从FFmpeg输出中解析到速度信息")
                        
            except subprocess.TimeoutExpired:
                proc.kill()
                logging.warning(f"FFmpeg测试超时: {channel['name']}")
                channel['ffmpeg_error'] = "Timeout after 15 seconds"
                channel['ffmpeg_status'] = 'timeout'  # 标记为超时
        
        except Exception as e:
            logging.error(f"FFmpeg测试异常: {str(e)}")
            channel['ffmpeg_error'] = str(e)
            channel['ffmpeg_status'] = 'error'  # 标记为错误
        
        # 给每个频道添加一个随机波动值，确保每次测试结果略有不同
        small_variation = random.uniform(0.97, 1.03)  # 添加±3%的随机波动
        
        # 更新频道对象
        if channel['ffmpeg_status'] == 'success' and channel['ffmpeg_speed'] > 0:
            # 如果FFmpeg测试成功，使用FFmpeg的速度来排序
            channel['speed'] = channel['ffmpeg_speed'] * small_variation
            channel['stream_response_time'] = channel['ffmpeg_response_time'] * small_variation
        
        # 添加所有频道到结果，包括失败的
        results.append(channel)
    
    # 按频道名称分组
    grouped_channels = {}
    for channel in results:
        channel_name = channel['name'].split('/')[0].strip()
        if channel_name not in grouped_channels:
            grouped_channels[channel_name] = []
        grouped_channels[channel_name].append(channel)
    
    # 对每个频道组内的链接按FFmpeg速度排序，同时过滤掉失败的频道
    sorted_results = []
    for channel_name, channels in grouped_channels.items():
        # 将频道分为成功和失败两组
        success_channels = [ch for ch in channels if ch['ffmpeg_status'] == 'success']
        failed_channels = [ch for ch in channels if ch['ffmpeg_status'] != 'success']
        
        # 按FFmpeg速度排序成功的频道
        sorted_success = sorted(success_channels, key=lambda x: -x.get('ffmpeg_speed', 0))
        
        # 打印最佳源的信息
        if sorted_success:
            best = sorted_success[0]
            logging.info(f"频道 {channel_name} 的最佳源:")
            logging.info(f"  URL: {best['url']}")
            logging.info(f"  FFmpeg速度: {best.get('ffmpeg_speed', 0):.2f}x")
            logging.info(f"  FFmpeg响应时间: {best.get('ffmpeg_response_time', float('inf')):.2f}秒")
            
            # 添加所有成功的源到结果中，按速度排序
            sorted_results.extend(sorted_success)
            
            # 记录过滤掉了多少不可用源
            if failed_channels:
                logging.info(f"频道 {channel_name} 过滤掉 {len(failed_channels)} 个不可用源")
        else:
            logging.warning(f"频道 {channel_name} 没有可用的源！所有 {len(failed_channels)} 个源都测试失败")
            # 如果没有可用源，保留所有源以防万一
            sorted_results.extend(channels)
    
    # 记录测试结束时间和总耗时
    test_end_time = time.time()
    test_duration = test_end_time - test_start_time
    logging.info(f"FFmpeg测试总耗时: {test_duration:.2f}秒")
    logging.info(f"FFmpeg测试完成，共测试 {len(results)} 个频道源，保留 {len(sorted_results)} 个源")
    
    return sorted_results


if __name__ == '__main__':
    asyncio.run(main())
