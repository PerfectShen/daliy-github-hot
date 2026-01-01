import requests
import feedparser
import os
import time
import hmac
import hashlib
import base64
import re
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
    """
    获取历史上的今天 (稳定版 - 数据源: 百度百科)
    """
    print("正在获取历史上的今天...")
    try:
        # 1. 获取当前月、日
        now = datetime.now()
        month = now.strftime("%m") # 例如 "01"
        day = now.strftime("%d")   # 例如 "01"
        date_key = month + day     # 例如 "0101"

        # 2. 请求百度百科官方接口 (按月存储的静态JSON，速度快且稳定)
        url = f"https://baike.baidu.com/cms/home/eventsOnHistory/{month}.json"
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        
        resp = requests.get(url, headers=headers, timeout=5)
        resp.encoding = 'utf-8' # 强制编码，防止中文乱码
        all_data = resp.json()
        
        # 3. 定位到“今天”的数据
        # 百度的数据结构是: { "01": { "0101": [ ...events... ] } }
        today_events = all_data.get(month, {}).get(date_key, [])
        
        if not today_events:
            return "**⏳ 历史上的今天**\n暂无数据"

        # 4. 清洗和筛选数据
        # 定义一个去除 HTML 标签的小函数
        def clean_text(text):
            text = re.sub(r'<.*?>', '', text) # 去掉 <a href...> 这种标签
            text = text.replace('&nbsp;', ' ').strip()
            return text

        display_list = []
        # 百度数据通常按年份排序。
        # 策略：取最后 5 条（也就是离现在最近的年份），或者反转列表取最著名的
        # 这里我们取倒数5条，通常是近代史，大家比较熟悉
        for item in today_events[-5:]:
            year = item.get('year')
            title = clean_text(item.get('title'))
            # 简单排版
            display_list.append(f"📜 **{year}年**: {title}")
            
        # 再反转一下，让最近的年份在最上面
        display_list.reverse()

        return f"**⏳ 历史上的今天 ({month}月{day}日)**\n" + "\n".join(display_list)

    except Exception as e:
        print(f"History Error: {e}")
        # 返回错误信息，这样你能在飞书看到是哪里错了，而不是什么都没有
        return f"**⏳ 历史上的今天**\n数据获取异常: {str(e)[:50]}"

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