import requests
import feedparser
import json
import os
import time
import hmac
import hashlib
import base64

# ================= 配置区域 =================
# 建议从环境变量读取，本地测试可以直接填字符串
FEISHU_WEBHOOK = os.getenv("FEISHU_WEBHOOK")
FEISHU_SECRET = os.getenv("FEISHU_SECRET")
# ===========================================

def gen_sign(timestamp, secret):
    """
    飞书签名生成算法 (HMAC-SHA256)
    """
    string_to_sign = '{}\n{}'.format(timestamp, secret)
    hmac_code = hmac.new(string_to_sign.encode("utf-8"), digestmod=hashlib.sha256).digest()
    sign = base64.b64encode(hmac_code).decode('utf-8')
    return sign

def get_reddit_prompts():
    """
    抓取 Reddit (r/ChatGPTPromptGenius) 每日热门
    """
    url = "https://www.reddit.com/r/ChatGPTPromptGenius/top.rss?t=day"
    # Reddit 必须伪装 User-Agent，否则报错 429
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    print(f"🧠 正在抓取 Reddit: {url} ...")
    try:
        # feedparser 支持直接传 headers 并不是所有版本都行，建议用 requests 下载内容再解析
        resp = requests.get(url, headers=headers, timeout=15)
        feed = feedparser.parse(resp.content)
        
        prompts = []
        for entry in feed.entries[:3]: # 只取前3个
            # 清洗描述，去除 HTML 标签
            summary = entry.summary.replace('<br>', '\n').replace('<p>', '').replace('</p >', '')
            
            prompts.append({
                "source": "🧠 ChatGPT / Reddit",
                "title": entry.title[:50], # 标题限制长度
                "url": entry.link,
                "desc": summary[:120] + "..." # 截取摘要
            })
        print(f"✅ Reddit 获取到 {len(prompts)} 条")
        return prompts
    except Exception as e:
        print(f"❌ Reddit 抓取失败: {e}")
        return []

def get_civitai_prompts():
    """
    抓取 Civitai (C站) 每日最热图片 Prompt
    """
    url = "https://civitai.com/api/v1/images"
    params = {
        "sort": "Most Reactions", # 点赞最多
        "period": "Day",          # 24小时内
        "limit": 3,               # 取3个
        "nsfw": "false"           # 过滤成人内容
    }
    
    print(f"🎨 正在抓取 Civitai ...")
    try:
        resp = requests.get(url, params=params, timeout=15)
        data = resp.json()
        
        prompts = []
        for item in data.get('items', []):
            meta = item.get('meta', {})
            prompt_text = meta.get('prompt', '无 Prompt 数据')
            
            # 简单的清洗
            clean_prompt = str(prompt_text).replace('\n', ' ')[:120]
            
            prompts.append({
                "source": "🎨 Midjourney/SD (Civitai)",
                "title": f"今日热图 (ID: {item['id']})",
                "url": f"https://civitai.com/images/{item['id']}",
                "desc": f"Prompt: {clean_prompt}..."
            })
        print(f"✅ Civitai 获取到 {len(prompts)} 条")
        return prompts
    except Exception as e:
        print(f"❌ Civitai 抓取失败: {e}")
        return []

def send_to_feishu(content_list):
    """
    发送到飞书 (带签名)
    """
    if not FEISHU_WEBHOOK:
        print("❌ 未配置飞书 Webhook")
        return

    print(f"📨 正在推送 {len(content_list)} 条 Prompt...")

    # 1. 生成签名
    timestamp = str(int(time.time()))
    sign = gen_sign(timestamp, FEISHU_SECRET)

    # 2. 拼接卡片内容
    card_elements = []
    for item in content_list:
        # 使用 Markdown 格式
        text = f"**【{item['source']}】**\n[{item['title']}]({item['url']})\n> {item['desc']}"
        card_elements.append(text)

    final_content = "\n\n----------------\n\n".join(card_elements)

    # 3. 构建 Payload
    payload = {
        "timestamp": timestamp,
        "sign": sign,
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": "🔥 每日热门 AI Prompts"
                },
                "template": "purple" # 紫色代表创造力
            },
            "elements": [
                {
                    "tag": "markdown",
                    "content": final_content
                },
                {
                    "tag": "note",
                    "elements": [
                        {"tag": "plain_text", "content": "数据来源: Reddit & Civitai"}
                    ]
                }
            ]
        }
    }

    # 4. 发送
    try:
        resp = requests.post(FEISHU_WEBHOOK, json=payload)
        result = resp.json()
        if result.get("code") == 0:
            print("✅ 推送成功！")
        else:
            print(f"❌ 推送失败: {result}")
    except Exception as e:
        print(f"❌ 网络请求出错: {e}")

def save_to_local(content_list):
    """
    将抓取到的 Prompt 追加保存到本地 JSON 文件中
    """
    file_path = "prompts_history.json"
    
    # 1. 如果文件不存在，创建一个空的列表
    if not os.path.exists(file_path):
        existing_data = []
    else:
        # 2. 如果文件存在，先读取旧数据
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
        except json.JSONDecodeError:
            existing_data = []

    # 3. 简单的去重逻辑（防止同一条数据存两遍）
    # 我们用 URL 作为唯一标识
    existing_urls = {item['url'] for item in existing_data}
    new_items = [item for item in content_list if item['url'] not in existing_urls]

    if new_items:
        # 4. 追加新数据
        # 把新数据放在最前面（倒序），方便查看最新
        updated_data = new_items + existing_data
        
        # 5. 写入文件
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(updated_data, f, ensure_ascii=False, indent=2)
        print(f"💾 已保存 {len(new_items)} 条新 Prompt 到 {file_path}")
    else:
        print("💾 没有新数据需要保存")

if __name__ == "__main__":
    # 1. 抓取数据
    all_prompts = []
    
    # 抓取 Reddit
    all_prompts.extend(get_reddit_prompts())
    
    # 抓取 Civitai
    all_prompts.extend(get_civitai_prompts())
    
    # 2. 推送
    if all_prompts:
        # 1. 先发飞书
        send_to_feishu(all_prompts)
        # 2. 【新增】再存本地
        save_to_local(all_prompts) 
    else:
        print("今日无数据抓取成功")