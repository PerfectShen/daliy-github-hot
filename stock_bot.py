import akshare as ak
import requests
import os
import time
import pandas as pd
import hmac
import hashlib
import base64
import csv
from datetime import datetime

# ================= 配置区域 =================
FEISHU_WEBHOOK = os.getenv("FEISHU_WEBHOOK")
FEISHU_SECRET = os.getenv("FEISHU_SECRET")
CSV_FILE = "trade_history.csv" # 交易记录文件名
# ===========================================

def gen_sign(timestamp, secret):
    string_to_sign = '{}\n{}'.format(timestamp, secret)
    hmac_code = hmac.new(string_to_sign.encode("utf-8"), digestmod=hashlib.sha256).digest()
    sign = base64.b64encode(hmac_code).decode('utf-8')
    return sign

def format_number(num):
    try:
        n = float(num)
        if abs(n) > 100000000:
            return f"{n/100000000:.1f}亿"
        elif abs(n) > 10000:
            return f"{n/10000:.0f}万"
        return f"{n:.2f}"
    except:
        return str(num)

def save_to_csv(record_list):
    """
    将选股记录保存到 CSV 文件
    record_list item format: {Date, Time, Board, Type, Code, Name, Price, Change}
    """
    file_exists = os.path.isfile(CSV_FILE)
    
    # utf-8-sig 是为了让 Excel 打开时不乱码
    with open(CSV_FILE, mode='a', newline='', encoding='utf-8-sig') as f:
        fieldnames = ['日期', '时间', '板块', '类型', '代码', '名称', '买入价', '涨跌幅', '成交额']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        
        # 如果文件是新建的，先写表头
        if not file_exists:
            writer.writeheader()
        
        writer.writerows(record_list)
    print(f"💾 已保存 {len(record_list)} 条回测记录到 {CSV_FILE}")

def get_hot_stocks_strategy():
    print("🚀 正在执行选股策略...")
    trade_records = [] # 用于存储要写入 CSV 的数据
    feishu_results = [] # 用于飞书推送的数据
    
    current_date = datetime.now().strftime("%Y-%m-%d")
    current_time = datetime.now().strftime("%H:%M")

    try:
        # 1. 获取资金流向板块
        df_flow = ak.stock_fund_flow_concept(symbol="即时")
        flow_col = "主力净流入-净额" if "主力净流入-净额" in df_flow.columns else "主力净流入"
        df_flow.sort_values(by=flow_col, ascending=False, inplace=True)
        top_5_boards = df_flow.head(5)
        
        for _, row in top_5_boards.iterrows():
            board_name = row['行业']
            net_inflow = row[flow_col]
            board_change = row['涨跌幅']
            
            try:
                df_cons = ak.stock_board_concept_cons_em(symbol=board_name)
                df_cons['涨跌幅'] = pd.to_numeric(df_cons['涨跌幅'], errors='coerce')
                df_cons['成交额'] = pd.to_numeric(df_cons['成交额'], errors='coerce')
                
                # === A组: 龙头 ===
                df_leaders = df_cons.sort_values(by="涨跌幅", ascending=False).head(3)
                leaders_list = []
                for _, stock in df_leaders.iterrows():
                    leaders_list.append(f"🔥 {stock['名称']} (`{stock['涨跌幅']}%`)")
                    # 记录到 CSV 数据列表
                    trade_records.append({
                        '日期': current_date,
                        '时间': current_time,
                        '板块': board_name,
                        '类型': '龙头',
                        '代码': stock['代码'],
                        '名称': stock['名称'],
                        '买入价': stock['最新价'],
                        '涨跌幅': f"{stock['涨跌幅']}%",
                        '成交额': format_number(stock['成交额'])
                    })

                # === B组: 补涨 ===
                df_potential = df_cons[(df_cons['涨跌幅'] > 0) & (df_cons['涨跌幅'] <= 3)].copy()
                df_potential.sort_values(by="成交额", ascending=False, inplace=True)
                top_potential = df_potential.head(3)
                
                potential_list = []
                for _, stock in top_potential.iterrows():
                    amt = format_number(stock['成交额'])
                    potential_list.append(f"🌱 {stock['名称']} (`{stock['涨跌幅']}%`) 额:{amt}")
                    # 记录到 CSV 数据列表
                    trade_records.append({
                        '日期': current_date,
                        '时间': current_time,
                        '板块': board_name,
                        '类型': '补涨',
                        '代码': stock['代码'],
                        '名称': stock['名称'],
                        '买入价': stock['最新价'],
                        '涨跌幅': f"{stock['涨跌幅']}%",
                        '成交额': amt
                    })

                if leaders_list:
                    feishu_results.append({
                        "board_name": board_name,
                        "board_info": f"流入: {format_number(net_inflow)}",
                        "leaders": leaders_list,
                        "potentials": potential_list if potential_list else ["(无符合标的)"]
                    })
                
                time.sleep(0.5)
                
            except Exception as e:
                print(f"⚠️ {board_name} 出错: {e}")
                continue
        
        # 循环结束后，统一保存 CSV
        if trade_records:
            save_to_csv(trade_records)

        return feishu_results

    except Exception as e:
        print(f"❌ 策略执行失败: {e}")
        return []

def send_to_feishu(data):
    if not FEISHU_WEBHOOK: return
    timestamp = str(int(time.time()))
    sign = gen_sign(timestamp, FEISHU_SECRET)
    
    content_elements = []
    for i, item in enumerate(data):
        section = f"**{i+1}. {item['board_name']}** *{item['board_info']}*\n" + \
                  "**【龙头】**\n" + "\n".join(item['leaders']) + "\n" + \
                  "**【补涨】**\n" + "\n".join(item['potentials'])
        content_elements.append(section)
    
    final_content = "\n\n----------------\n\n".join(content_elements)
    payload = {
        "timestamp": timestamp, "sign": sign, "msg_type": "interactive",
        "card": {
            "header": {"title": {"tag": "plain_text", "content": f"📈 选股策略已归档"}, "template": "turquoise"},
            "elements": [{"tag": "markdown", "content": final_content}]
        }
    }
    requests.post(FEISHU_WEBHOOK, json=payload)

if __name__ == "__main__":
    strategy_data = get_hot_stocks_strategy()
    if strategy_data:
        send_to_feishu(strategy_data)
    else:
        print("今日无数据")
