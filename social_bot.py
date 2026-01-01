import requests
import os
import time
import hmac
import hashlib
import base64
import json

# ================= 配置区域 =================
FEISHU_WEBHOOK = os.getenv("FEISHU_WEBHOOK")
FEISHU_SECRET = os.getenv("FEISHU_SECRET")
# ===========================================

def gen_sign(timestamp, secret):
    string_to_sign = '{}\n{}'.format(timestamp, secret)
    hmac_code = hmac.new(string_to_sign.encode("utf-8"), digestmod=hashlib.sha256).digest()
    sign = base64.b64encode(hmac_code).decode('utf-8')
    return sign

def fetch_hot_list(source_name, api_url, type_key="title"):
    """
    通用的聚合 API 抓取函数
    """
    print(f"正在抓取 {source_name} ...")
    try:
        # 使用韩小韩(vvhan)的免费聚合接口
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        resp = requests.get(api_url, headers=headers, timeout=15)
        data = resp.json()
        
        if not data.get('success'):
            print(f"⚠️ {source_name} API 返回失败: {data}")
            return None

        items = data.get('data', [])[:5] # 取前5条
        
        lines = []
        for i, item in enumerate(items):
            title = item.get('title')
            link = item.get('url') # 或者 mobileUrl
            hot = item.get('hot', '🔥')
            
            # 简单的格式化
            lines.append(f"{i+1}. [{title}]({link}) `{hot}`")
            
        return f"**{source_name}**\n" + "\n".join(lines)
        
    except Exception as e:
        print(f"❌ {source_name} 抓取异常: {e}")
        return None

def get_bilibili_hot():
    # 接口文档参考: https://api.vvhan.com/
    return fetch_hot_list("📺 B站热门", "https://api.vvhan.com/api/hotlist/bili")

def get_zhihu_hot():
    return fetch_hot_list("🧠 知乎热榜", "https://api.vvhan.com/api/hotlist/zhihu")

def get_douyin_hot():
    return fetch_hot_list("🎵 抖音热搜", "https://api.vvhan.com/api/hotlist/douyin")

def get_weibo_hot():
    return fetch_hot_list("🍉 微博热搜", "https://api.vvhan.com/api/hotlist/wb")

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
                "title": {"tag": "plain_text", "content": "🔥 全网热榜 (API版)"},
                "template": "red"
            },
            "elements": [
                {"tag": "markdown", "content": final_content},
                {
                    "tag": "note",
                    "elements": [{"tag": "plain_text", "content": "数据源: vvhan API"}]
                }
            ]
        }
    }
    requests.post(FEISHU_WEBHOOK, json=payload)
    print("推送成功")

if __name__ == "__main__":
    msgs = []
    
    # 依次调用聚合接口
    msgs.append(get_bilibili_hot())
    msgs.append(get_zhihu_hot())
    msgs.append(get_douyin_hot())
    msgs.append(get_weibo_hot())
    
    send_to_feishu(msgs)