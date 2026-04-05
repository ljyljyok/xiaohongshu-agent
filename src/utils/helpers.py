#!/usr/bin/env python3
"""工具函数模块"""

import os
import json
import time
import random
from datetime import datetime


def save_data(data, file_path):
    """
    保存数据到JSON文件
    
    Args:
        data: 要保存的数据
        file_path: 文件路径
    """
    try:
        # 确保目录存在
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"保存数据时出错: {e}")
        return False


def load_data(file_path):
    """
    从JSON文件加载数据
    
    Args:
        file_path: 文件路径
        
    Returns:
        加载的数据，如果文件不存在或出错则返回None
    """
    try:
        if not os.path.exists(file_path):
            return None
        
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data
    except Exception as e:
        print(f"加载数据时出错: {e}")
        return None


def get_timestamp():
    """
    获取当前时间戳
    
    Returns:
        格式化的时间戳字符串
    """
    return datetime.now().strftime('%Y-%m-%d_%H-%M-%S')


def generate_random_delay(min_delay=1, max_delay=3):
    """
    生成随机延迟
    
    Args:
        min_delay: 最小延迟时间（秒）
        max_delay: 最大延迟时间（秒）
        
    Returns:
        随机延迟时间
    """
    return random.uniform(min_delay, max_delay)


def format_number(num):
    """
    格式化数字，处理万、千等单位
    
    Args:
        num: 数字字符串
        
    Returns:
        格式化后的数字
    """
    if not num:
        return 0
    
    num = num.strip()
    
    if '万' in num:
        return int(float(num.replace('万', '')) * 10000)
    elif '千' in num:
        return int(float(num.replace('千', '')) * 1000)
    else:
        try:
            return int(num)
        except:
            return 0


def filter_high_quality_posts(posts, min_likes=100):
    """
    过滤高质量帖子
    
    Args:
        posts: 帖子列表
        min_likes: 最小点赞数
        
    Returns:
        过滤后的帖子列表
    """
    filtered_posts = []
    
    for post in posts:
        likes = format_number(post.get('likes', '0'))
        if likes >= min_likes:
            filtered_posts.append(post)
    
    return filtered_posts


def sort_posts_by_likes(posts):
    """
    按点赞数排序帖子
    
    Args:
        posts: 帖子列表
        
    Returns:
        排序后的帖子列表
    """
    return sorted(posts, key=lambda x: format_number(x.get('likes', '0')), reverse=True)
