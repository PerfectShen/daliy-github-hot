import requests
import feedparser
import os
import time
import hmac
import hashlib
import base64
import random

# ================= 配置区域 =================
FEISHU_WEBHOOK = os.getenv("FEISHU_WEBHOOK")
FEISHU_SECRET = os.getenv("FEISHU_SECRET")

# 【关注名单】你想监控的大佬 (填他们的推特 ID，不带 @)
TARGET_USERS = [
    {"id": "_akhaliq", "tag": "🤖 AI前沿", "name": "AK"},
    {"id": "levelsio", "tag": "💰 独立开发", "name": "Levelsio"},
    {"id": "OpenAI", "tag": "🧠 官方", "name": "OpenAI"},
    {"id": "karpathy", "tag": "💡 观点", "name": "Karpathy"}
]

# 【Nitter 节点池】
# X 的反爬很严，Nitter 节点经常轮流挂，这里多备几个
NITTER_INSTANCES = [
    "https://nitter.privacydev.net",
    "https://nitter.poast.org",
    "https://nitter.soopy.moe",
    "https://nitter.uni-sonia.com"
]
# ===========================================

def gen_sign(timestamp, secret):
    string_to_sign = '{}\n{}'.format(timestamp, secret)
    hmac_code = hmac.new(string_to_sign.encode("utf-8"), digestmod=hashlib.sha256).digest()
    sign = base64.b64encode(hmac_code).decode('utf-8')
    return sign

def get_working_instance():
    """随机选择一个能用的 Nitter 节点"""
    random.shuffle(NITTER_INSTANCES)
    for url in NITTER_INSTANCES:
        try:
            # 简单测试一下连通性
            requests.get(url, timeout=3)
            print(f"✅ 选中节点: {url}")
            return url
        except:
            continue
    return None

def fetch_user_tweets(base_url, user):
    """抓取单个用户的最新推文"""
    # Nitter 的 RSS 地址格式: https://nitter.net/username/rss
    rss_url = f"{base_url}/{user['id']}/rss"
    
    print(f"正在抓取 {user['name']} (@{user['id']})...")
    try:
        # 必须带 Header，否则有些 Nitter 会拒绝
        headers = {'User-Agent': 'Mozilla/5.0 (Compatible; RSS Bot)'}
        feed = feedparser.parse(rss_url, request_headers=headers)
        
        if not feed.entries:
            return None

        # 只取最新的一条
        latest_tweet = feed.entries[0]
        
        # 简单的去重/时间判断逻辑 (实际使用建议存文件比对 ID)
        # 这里演示：直接获取内容
        content = latest_tweet.summary.replace('<br>', '\n')
        # 去掉 HTML 标签 (简单处理)
        import re
        content = re.sub(r'<.*?>', '', content)
        
        # 截取前 150 字
        if len(content) > 150:
            content = content[:150] + "..."
            
        return {
            "author": user['name'],
            "tag": user['tag'],
            "content": content,
            "link": latest_tweet.link,
            "date": latest_tweet.published
        }
        
    except Exception as e:
        print(f"❌ {user['name']} 抓取失败: {e}")
        return None

def send_to_feishu(tweets):
    if not FEISHU_WEBHOOK: return
    timestamp = str(int(time.time()))
    sign = gen_sign(timestamp, FEISHU_SECRET)
    
    if not tweets: return

    # 拼接卡片
    card_elements = []
    for t in tweets:
        text = f"**【{t['tag']}】{t['author']}**\n> {t['content']}\n[查看原文]({t['link']})"
        card_elements.append(text)

    final_content = "\n\n----------------\n\n".join(card_elements)
    
    payload = {
        "timestamp": timestamp,
        "sign": sign,
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": "🐦 X (Twitter) 重点监控"},
                "template": "blue"
            },
            "elements": [
                {"tag": "markdown", "content": final_content}
            ]
        }
    }
    requests.post(FEISHU_WEBHOOK, json=payload)
    print("推送成功")

if __name__ == "__main__":
    base_url = get_working_instance()
    
    if base_url:
        all_tweets = []
        for user in TARGET_USERS:
            tweet = fetch_user_tweets(base_url, user)
            if tweet:
                all_tweets.append(tweet)
            # 礼貌抓取，避免对节点造成太大压力
            time.sleep(1)
            
        send_to_feishu(all_tweets)
    else:
        print("❌ 所有 Nitter 节点都无法连接，请稍后再试")