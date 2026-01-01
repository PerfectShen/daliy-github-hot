import requests
import feedparser
import time
import os
import hmac
import hashlib
import base64

# ================= 配置 =================
FEISHU_WEBHOOK = os.getenv("FEISHU_WEBHOOK")
FEISHU_SECRET = os.getenv("FEISHU_SECRET")
# =======================================

def gen_sign(timestamp, secret):
    string_to_sign = '{}\n{}'.format(timestamp, secret)
    hmac_code = hmac.new(string_to_sign.encode("utf-8"), digestmod=hashlib.sha256).digest()
    sign = base64.b64encode(hmac_code).decode('utf-8')
    return sign

def get_crypto_price():
    """获取 BTC/ETH 简报"""
    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {
        "ids": "bitcoin,ethereum",
        "vs_currencies": "usd",
        "include_24hr_change": "true"
    }
    try:
        # Coingecko 免费版有时候会限流，加个超时处理。
        resp = requests.get(url, params=params, timeout=5)
        if resp.status_code != 200:
            return None
            
        data = resp.json()
        btc_price = data['bitcoin']['usd']
        btc_change = data['bitcoin']['usd_24h_change']
        eth_price = data['ethereum']['usd']
        eth_change = data['ethereum']['usd_24h_change']
        
        btc_icon = "🔺" if btc_change > 0 else "🔻"
        eth_icon = "🔺" if eth_change > 0 else "🔻"
        
        return (f"🪙 **Crypto Market**\n"
                f"**BTC**: ${btc_price:,.0f} ({btc_icon}{btc_change:.2f}%)\n"
                f"**ETH**: ${eth_price:,.0f} ({eth_icon}{eth_change:.2f}%)")
    except:
        return None # 获取失败就不显示这一块了

def get_hacker_news():
    """获取 Hacker News Top 5"""
    print("正在获取 Hacker News...")
    try:
        top_url = "https://hacker-news.firebaseio.com/v0/topstories.json"
        ids = requests.get(top_url, timeout=5).json()[:5]
        
        stories = []
        for i, item_id in enumerate(ids):
            item_url = f"https://hacker-news.firebaseio.com/v0/item/{item_id}.json"
            item = requests.get(item_url, timeout=3).json()
            
            title = item.get('title')
            url = item.get('url', f"https://news.ycombinator.com/item?id={item_id}")
            score = item.get('score', 0)
            
            stories.append(f"**{i+1}. {title}**\n🔥 {score} pts | [Read]({url})")
            
        return "**🍊 Hacker News Top 5**\n" + "\n".join(stories)
    except Exception as e:
        print(f"HN Error: {e}")
        return "Hacker News 获取失败"

def get_arxiv_papers():
    """获取 ArXiv 最新 AI 论文 (CS.CL/LG/AI)"""
    print("正在获取 ArXiv...")
    try:
        # 查询策略：
        # cat:cs.CL (计算语言学/LLM) OR cat:cs.LG (机器学习) OR cat:cs.AI (人工智能)
        # sortBy=submittedDate (按提交时间倒序)
        query = "cat:cs.CL+OR+cat:cs.LG+OR+cat:cs.AI"
        url = f"http://export.arxiv.org/api/query?search_query={query}&sortBy=submittedDate&sortOrder=descending&max_results=3"
        
        data = feedparser.parse(url)
        
        papers = []
        for entry in data.entries:
            title = entry.title.replace('\n', ' ')
            link = entry.link
            
            # 处理摘要：去掉换行符，截取前100个字符
            summary = entry.summary.replace('\n', ' ')[:100] + "..."
            
            # 获取第一作者
            author = entry.authors[0].name if entry.authors else "Unknown"
            
            papers.append(f"📄 **{title}**\n👤 {author} et al.\n> {summary}\n[PDF]({link})")
            
        return "**🎓 ArXiv AI Daily (Latest)**\n" + "\n\n".join(papers)
    except Exception as e:
        print(f"ArXiv Error: {e}")
        return "ArXiv 获取失败"

def send_to_feishu(content_list):
    if not FEISHU_WEBHOOK: 
        print("未配置 Webhook")
        return
    
    timestamp = str(int(time.time()))
    sign = gen_sign(timestamp, FEISHU_SECRET)
    
    # 过滤掉 None (获取失败的模块)
    valid_contents = [c for c in content_list if c]
    
    if not valid_contents:
        print("所有模块都获取失败，取消推送")
        return

    # 用分割线拼接
    final_content = "\n\n----------------\n\n".join(valid_contents)
    
    payload = {
        "timestamp": timestamp,
        "sign": sign,
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": "🌍 每日科技 & 金融全览"},
                "template": "blue"
            },
            "elements": [
                {"tag": "markdown", "content": final_content},
                {
                    "tag": "note",
                    "elements": [{"tag": "plain_text", "content": "Source: Coingecko | HackerNews | ArXiv"}]
                }
            ]
        }
    }
    requests.post(FEISHU_WEBHOOK, json=payload)
    print("推送成功")

if __name__ == "__main__":
    msgs = []
    
    # 1. Crypto (如果不想要可以注释掉)
    msgs.append(get_crypto_price())
    
    # 2. Hacker News
    msgs.append(get_hacker_news())
    
    # 3. ArXiv Papers
    msgs.append(get_arxiv_papers())
    
    send_to_feishu(msgs)