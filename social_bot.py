import requests
import os
import time
import hmac
import hashlib
import base64
import json
import random

# ================= 配置区域 =================
FEISHU_WEBHOOK = os.getenv("FEISHU_WEBHOOK")
FEISHU_SECRET = os.getenv("FEISHU_SECRET")
# ===========================================

def gen_sign(timestamp, secret):
    string_to_sign = '{}\n{}'.format(timestamp, secret)
    hmac_code = hmac.new(string_to_sign.encode("utf-8"), digestmod=hashlib.sha256).digest()
    sign = base64.b64encode(hmac_code).decode('utf-8')
    return sign

def get_headers():
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://www.google.com"
    }

def fetch_oioweb(type_key, title_name):
    """
    方案A: 调用 oioweb 聚合接口 (目前最稳)
    文档: https://api.oioweb.cn/doc/common/HotList
    """
    print(f"🔄 正在尝试从 API 获取 {title_name} ...")
    url = f"https://api.oioweb.cn/api/common/HotList?type={type_key}"
    
    try:
        resp = requests.get(url, headers=get_headers(), timeout=15)
        data = resp.json()
        
        # oioweb 的数据通常在 result 字段里
        if data.get('code') == 200:
            items = data.get('result', [])[:5]
            lines = []
            for i, item in enumerate(items):
                # 不同的接口返回字段可能略有不同，做个容错
                title = item.get('title')
                link = item.get('href') or item.get('url')
                hot = item.get('hot', '')
                
                # 简单的格式化
                hot_str = f"`🔥{hot}`" if hot else ""
                lines.append(f"{i+1}. [{title}]({link}) {hot_str}")
            
            return f"**{title_name}**\n" + "\n".join(lines)
        else:
            print(f"⚠️ {title_name} API 返回状态非200")
            return None
            
    except Exception as e:
        print(f"❌ {title_name} API 抓取失败: {e}")
        return None

# ========================================
# 方案B: 官方接口备用 (防止 API 挂了)
# ========================================

def get_bilibili_fallback():
    print("⚠️ 启用 B站 备用官方源...")
    url = "https://api.bilibili.com/x/web-interface/ranking/v2?rid=0&type=all"
    try:
        resp = requests.get(url, headers=get_headers(), timeout=10)
        items = resp.json()['data']['list'][:5]
        lines = [f"{i+1}. [{item['title']}]({item['short_link_v2']}) `▶️{item['stat']['view']}`" for i, item in enumerate(items)]
        return "**📺 B站热门 (官方源)**\n" + "\n".join(lines)
    except: return None

def get_weibo_fallback():
    print("⚠️ 启用 微博 备用官方源...")
    url = "https://weibo.com/ajax/side/hotSearch"
    try:
        resp = requests.get(url, headers=get_headers(), timeout=10)
        items = resp.json()['data']['realtime'][:5]
        lines = [f"{i+1}. [{item['word_scheme']}](https://s.weibo.com/weibo?q={item['word']})" for i, item in enumerate(items)]
        return "**🍉 微博热搜 (官方源)**\n" + "\n".join(lines)
    except: return None

# ================= 主逻辑 =================

def get_bilibili():
    # 尝试 API -> 失败则尝试 官方
    return fetch_oioweb("bilibili", "📺 B站热门") or get_bilibili_fallback()

def get_zhihu():
    # 知乎 oioweb 很稳
    return fetch_oioweb("zhihuHot", "🧠 知乎热榜")

def get_douyin():
    # 抖音 oioweb 很稳
    return fetch_oioweb("douyinHot", "🎵 抖音热搜")

def get_weibo():
    # 微博 API -> 官方
    return fetch_oioweb("weibo", "🍉 微博热搜") or get_weibo_fallback()

def send_to_feishu(content_list):
    if not FEISHU_WEBHOOK: return
    timestamp = str(int(time.time()))
    sign = gen_sign(timestamp, FEISHU_SECRET)
    
    valid_contents = [c for c in content_list if c]
    if not valid_contents: 
        print("所有接口都失败，取消推送")
        return

    final_content = "\n\n----------------\n\n".join(valid_contents)
    
    payload = {
        "timestamp": timestamp,
        "sign": sign,
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": "🔥 全网热榜 (Pro版)"},
                "template": "red"
            },
            "elements": [
                {"tag": "markdown", "content": final_content}
            ]
        }
    }
    requests.post(FEISHU_WEBHOOK, json=payload)
    print("推送成功")

if __name__ == "__main__":
    msgs = []
    
    # 依次获取
    msgs.append(get_bilibili())
    msgs.append(get_zhihu())
    msgs.append(get_douyin())
    msgs.append(get_weibo())
    
    send_to_feishu(msgs)
