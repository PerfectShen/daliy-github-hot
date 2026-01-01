import requests
import json
import os
import time
import hmac
import hashlib
import base64
import random

# ================= 配置区域 =================
FEISHU_WEBHOOK = os.getenv("FEISHU_WEBHOOK")
FEISHU_SECRET = os.getenv("FEISHU_SECRET")
# 小红书 Cookie (可选，如果不填则自动跳过)
XHS_COOKIE = os.getenv("XHS_COOKIE") 
# ===========================================

def gen_sign(timestamp, secret):
    string_to_sign = '{}\n{}'.format(timestamp, secret)
    hmac_code = hmac.new(string_to_sign.encode("utf-8"), digestmod=hashlib.sha256).digest()
    sign = base64.b64encode(hmac_code).decode('utf-8')
    return sign

def get_headers():
    """随机 User-Agent，伪装成浏览器"""
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.4951.64 Safari/537.36"
    ]
    return {
        "User-Agent": random.choice(user_agents),
        "Referer": "https://www.google.com/"
    }

def get_bilibili_hot():
    """📺 B站 - 全站热门视频"""
    print("正在抓取 Bilibili...")
    url = "https://api.bilibili.com/x/web-interface/ranking/v2?rid=0&type=all"
    try:
        resp = requests.get(url, headers=get_headers(), timeout=10)
        data = resp.json()
        items = data['data']['list'][:5] # 取前5
        
        lines = []
        for i, item in enumerate(items):
            title = item['title']
            # B站短链接
            link = item['short_link_v2'] if 'short_link_v2' in item else f"https://www.bilibili.com/video/{item['bvid']}"
            view = item['stat']['view']
            view_str = f"{view/10000:.1f}万" if view > 10000 else str(view)
            lines.append(f"{i+1}. [{title}]({link}) `▶️{view_str}`")
            
        return "**📺 Bilibili 热门**\n" + "\n".join(lines)
    except Exception as e:
        print(f"B站失败: {e}")
        return None

def get_zhihu_hot():
    """🧠 知乎 - 热榜"""
    print("正在抓取 知乎...")
    url = "https://www.zhihu.com/api/v3/feed/topstory/hot-lists/total?limit=50&desktop=true"
    try:
        resp = requests.get(url, headers=get_headers(), timeout=10)
        data = resp.json()
        items = data['data'][:5]
        
        lines = []
        for i, item in enumerate(items):
            target = item['target']
            title = target['title']
            link = f"https://www.zhihu.com/question/{target['id']}"
            hot_val = item.get('detail_text', '热度未知')
            lines.append(f"{i+1}. [{title}]({link}) `{hot_val}`")
            
        return "**🧠 知乎热榜**\n" + "\n".join(lines)
    except Exception as e:
        print(f"知乎失败: {e}")
        return None

def get_douyin_hot():
    """🎵 抖音 - 热搜词 (Web API)"""
    print("正在抓取 抖音...")
    # 这是一个相对稳定的 Web 接口
    url = "https://www.iesdouyin.com/web/api/v2/hotsearch/billboard/word/"
    try:
        resp = requests.get(url, headers=get_headers(), timeout=10)
        data = resp.json()
        items = data['word_list'][:5]
        
        lines = []
        for i, item in enumerate(items):
            word = item['word']
            # 抖音热度值
            hot_value = f"{item['hot_value']/10000:.1f}w"
            # 搜索链接
            link = f"https://www.douyin.com/search/{word}"
            lines.append(f"{i+1}. [{word}]({link}) `🔥{hot_value}`")
            
        return "**🎵 抖音热搜**\n" + "\n".join(lines)
    except Exception as e:
        print(f"抖音失败: {e}")
        return None

def get_xhs_hot():
    """📕 小红书 - (需要 Cookie)"""
    print("正在抓取 小红书...")
    if not XHS_COOKIE:
        print("⚠️ 未配置 XHS_COOKIE，跳过小红书抓取")
        return None # 返回 None 表示跳过

    # 小红书 Web 搜索接口 (如果不带 Cookie 极大概率 403)
    # 这里我们尝试抓取“热点”页面，或者搜索建议
    # 由于 XHS 接口极其复杂，这里使用一个简单的 Explore 页面尝试
    url = "https://www.xiaohongshu.com/api/sns/web/v1/homefeed"
    
    headers = get_headers()
    headers['Cookie'] = XHS_COOKIE
    headers['Content-Type'] = 'application/json'
    
    try:
        # 小红书首页 Feed 流
        data_payload = {"cursor_score":"","num":10,"refresh_type":1,"note_index":0,"unread_begin_note_id":"","unread_end_note_id":"","unread_note_count":0,"category":"homefeed_recommend"}
        resp = requests.post(url, headers=headers, json=data_payload, timeout=5)
        
        if resp.status_code != 200:
            return "**📕 小红书**\nCookie 失效或被拦截"

        data = resp.json()
        items = data['data']['items'][:5]
        
        lines = []
        for i, item in enumerate(items):
            # 只要笔记类型的
            if item.get('model_type') == 'note':
                title = item['note_card']['display_title']
                note_id = item['id']
                user = item['note_card']['user']['nickname']
                link = f"https://www.xiaohongshu.com/explore/{note_id}"
                likes = item['note_card']['interact_info']['liked_count']
                
                lines.append(f"{i+1}. [{title}]({link})\n👤 {user} | ❤️ {likes}")
        
        if not lines: return "**📕 小红书**\n未获取到热门笔记"
        return "**📕 小红书推荐**\n" + "\n".join(lines)
        
    except Exception as e:
        print(f"小红书失败: {e}")
        return None

def send_to_feishu(content_list):
    if not FEISHU_WEBHOOK: return
    timestamp = str(int(time.time()))
    sign = gen_sign(timestamp, FEISHU_SECRET)
    
    # 过滤空数据
    valid_contents = [c for c in content_list if c]
    if not valid_contents: return

    final_content = "\n\n----------------\n\n".join(valid_contents)
    
    payload = {
        "timestamp": timestamp,
        "sign": sign,
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": "🔥 全网热榜聚合"},
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
    
    # 1. Bilibili (最稳)
    msgs.append(get_bilibili_hot())
    
    # 2. Zhihu (稳)
    msgs.append(get_zhihu_hot())
    
    # 3. Douyin (Web接口尚可)
    msgs.append(get_douyin_hot())
    
    # 4. Xiaohongshu (需要 Cookie，不稳定)
    msgs.append(get_xhs_hot())
    
    send_to_feishu(msgs)