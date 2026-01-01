import requests
import feedparser
import os
import time
import hmac
import hashlib
import base64
from bs4 import BeautifulSoup
from datetime import datetime

# ================= 配置 =================
FEISHU_WEBHOOK = os.getenv("FEISHU_WEBHOOK")
FEISHU_SECRET = os.getenv("FEISHU_SECRET")
# =======================================

def gen_sign(timestamp, secret):
    string_to_sign = '{}\n{}'.format(timestamp, secret)
    hmac_code = hmac.new(string_to_sign.encode("utf-8"), digestmod=hashlib.sha256).digest()
    sign = base64.b64encode(hmac_code).decode('utf-8')
    return sign

def get_product_hunt():
    """获取 Product Hunt 今日最佳产品"""
    print("正在获取 Product Hunt...")
    url = "https://www.producthunt.com/feed"
    try:
        feed = feedparser.parse(url)
        products = []
        for entry in feed.entries[:5]: # 取前5个
            title = entry.title
            link = entry.link
            # 简短描述
            desc = entry.summary.split('<br')[0][:100].replace('\n', ' ')
            products.append(f"🚀 **{title}**\n> {desc}\n[查看产品]({link})")
            
        return "**🦄 Product Hunt Daily**\n" + "\n\n".join(products)
    except Exception as e:
        print(f"PH Error: {e}")
        return None

def get_weibo_hot():
    """获取微博热搜 Top 10"""
    print("正在获取微博热搜...")
    url = "https://s.weibo.com/top/summary"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Cookie": "SUB=1" # 简单的游客 Cookie 绕过验证
    }
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(resp.text, 'lxml')
        items = soup.select('td.td-02 > a')
        
        hot_list = []
        # 跳过第0个（通常是置顶广告），从第1个开始取
        for i, item in enumerate(items[1:11]): 
            title = item.get_text().strip()
            link = "https://s.weibo.com" + item.get('href')
            # 热度值
            hot_val = item.find_next_sibling('span')
            hot_text = hot_val.get_text().strip() if hot_val else ""
            
            # 前3名加火苗图标
            icon = "🔥" if i < 3 else str(i+1) + "."
            
            hot_list.append(f"{icon} [{title}]({link}) `{hot_text}`")
            
        return "**🍉 微博热搜 Top 10**\n" + "\n".join(hot_list)
    except Exception as e:
        print(f"Weibo Error: {e}")
        return None

def get_history_today():
    """获取历史上的今天"""
    print("正在获取历史上的今天...")
    # 使用一个公开的免费接口，或者直接爬取百度百科
    # 这里使用 60s api 的历史接口 (如果失效可以换其他源)
    url = "https://60s.viki.moe/v2/history" 
    try:
        resp = requests.get(url, timeout=5)
        data = resp.json()
        
        if data.get('code') == 200:
            events = data.get('data', [])
            # 格式化一下
            event_list = []
            for item in events[:5]: # 取前5个大事件
                event_list.append(f"📜 **{item}**")
            
            return "**⏳ 历史上的今天**\n" + "\n".join(event_list)
        return None
    except:
        # 备用方案：简单的写死测试，实际建议换稳定API
        return "**⏳ 历史上的今天**\n获取失败，请检查 API 源"

def send_to_feishu(content_list):
    if not FEISHU_WEBHOOK: return
    timestamp = str(int(time.time()))
    sign = gen_sign(timestamp, FEISHU_SECRET)
    
    valid_contents = [c for c in content_list if c]
    if not valid_contents: return

    final_content = "\n\n----------------\n\n".join(valid_contents)
    
    payload = {
        "timestamp": timestamp,
        "sign": sign,
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": "🌈 每日趋势 & 灵感"},
                "template": "orange" # 橙色代表活力
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
    msgs.append(get_weibo_hot())    # 吃瓜/热点
    msgs.append(get_product_hunt()) # 产品灵感
    msgs.append(get_history_today())# 历史底蕴
    
    send_to_feishu(msgs)