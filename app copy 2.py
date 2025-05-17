import discord
from discord.ext import commands
from discord import Option
import json
import os
import uuid
import requests
import xml.etree.ElementTree as ET
import logging
import aiohttp
import asyncio
import random


# 設置日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 意圖
intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.message_content = True

# 機器人初始化
bot = commands.Bot(command_prefix=".", intents=intents)

ALLOWED_USER_IDS = []
# 放入id限制使用者[id1, id2, id3....]

def is_allowed_user(ctx):
    return ctx.author.id in ALLOWED_USER_IDS

# bot啟動
@bot.event
async def on_ready():
    bot_run = {
        "機器人名稱": bot.user.name,
        "機器人ID": bot.user.id,
        "開發者": "Co2_tw",
        "開發者網站": "https://你的網站.com",
        "版本": "1.0.0",
        "描述": "這是一個功能強大的 Discord 機器人。",
        "狀態": f"連接至 {len(bot.guilds)} 個伺服器"
    }
    print("=== 機器人已啟動 ===")
    for key, value in bot_run.items():
        print(f"{key}: {value}")
        
json_path = "SmilePay.json"

        
def load_json():
    if os.path.exists(json_path):
        with open(json_path, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []
    return []

def save_json(data):
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def add_order(order_data):
    data = load_json()
    data.append(order_data)
    save_json(data)

@bot.slash_command(name="開付款碼", description="金額記得輸入手續費")
@commands.check(is_allowed_user)
async def pay(ctx, 金額: discord.Option(int, "金額", min_value=15, max_value=20000), 付款方式:discord.Option(str, "付款方式", choices=["7-11", "全家", "轉帳"])):
    if 付款方式 not in ["7-11", "全家", "轉帳"]:
        await ctx.respond("❌ 付款方式僅限：7-11、全家、轉帳")
        return

    # 轉換為 SmilePay 代碼
    classif_map = {
        "7-11": "4",     # ibon
        "全家": "6",     # famiport
        "轉帳": "2",     # 虛擬帳號
    }
    classif = classif_map[付款方式]

    訂單號 = f"ORD-{uuid.uuid4().hex[:8].upper()}"
    smilepay_api = "https://ssl.smse.com.tw/api/SPPayment.asp"  # API

    payload = {
        "Dcvc": "17647",# 商家代號
        "Verify_key": "",# 速買配密鑰
        "Rvg2c": "1",
        "Od_sob": 訂單號,
        "Pur_name": "",# 商城名稱
        "Mobile_number": "",# 你的手機號碼
        "Email": "",# 你的信箱
        "Remark": "",# 開單的備註，可以使用此模板：請留好收據避免查帳未收到或付款出問題
        "Roturl": "",# 配合自動查帳 http://回傳的post server
        "Pay_zg": classif,
        "Amount": 金額
    }

    try:
        response = requests.post(smilepay_api, data=payload)
        response.encoding = "utf-8"
        xml_text = response.text

        root = ET.fromstring(xml_text)

        status = root.findtext("Status")
        desc = root.findtext("Desc")
        smilepay_no = root.findtext("SmilePayNO")
        ibon_no = root.findtext("IbonNo")
        fami_no = root.findtext("FamiNO")
        atm_no = root.findtext("AtmNo")
        amount = root.findtext("Amount")
        pay_end = root.findtext("PayEndDate")

        if status != "1":
            await ctx.respond(f"❌ 建立失敗：{desc}")
            return
        
        add_order({
        "訂單號": 訂單號,
        "SmilePayNO": smilepay_no,
        "channel_id": str(ctx.channel.id),
        "user_id": str(ctx.author.id),
        "狀態": "未付款"
        })

        embed = discord.Embed(
            title="✅ 付款資訊",
            description="請使用以下資訊完成付款",
            color=discord.Color.green()
        )
        embed.add_field(name="訂單編號", value=訂單號, inline=False)
        embed.add_field(name="付款方式", value=付款方式, inline=True)
        embed.add_field(name="金額", value=f"{amount} 元", inline=True)
        embed.add_field(name="查詢代碼", value=smilepay_no or "無", inline=False)

        if ibon_no:
            embed.add_field(name="7-11 ibon 代碼", value=f"`{ibon_no}`", inline=False)
            embed.add_field(name="7-11 代碼付款教學", value="https://www.youtube.com/watch?v=dbFgeII7QX4", inline=False)
        if fami_no:
            embed.add_field(name="全家 FamiPort 代碼", value=f"`{fami_no}`", inline=False)
            embed.add_field(name="全家代碼付款教學", value=" https://www.youtube.com/watch?v=MTPEwUcoBTE&t", inline=False)
        if atm_no:
            embed.add_field(name="虛擬帳號", value=f"`{atm_no}`", inline=False)
            embed.add_field(name=">>備註<<", value="**為了防止第三方詐騙, 請務必要截圖付款記錄以及註明跟夜雀商城購買OOO商品 沒有的話不發貨也不退款**", inline=False)

        embed.add_field(name="付款期限", value=pay_end or "無", inline=False)
        embed.set_footer(text="請在時間內完成付款，避免訂單失效｜需要QRcode？自行用/條碼 <超商代碼>")
        await ctx.respond(embed=embed)

    except Exception as e:
        await ctx.respond(f"❌ 建立失敗：{str(e)}")
        
        
def load_json():
    if os.path.exists(json_path):
        with open(json_path, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []
    return []

# 儲存 JSON 資料
def save_json(data):
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
        
        
        

@bot.event
async def on_message(message):

    if message.channel.id != 這裡填寫頻道id:# 自動查帳才會用到
        return

    content = message.content.strip()

    print(f"收到訊息: {content}")

    if "查詢碼：" in content:
        query_code = content.split("查詢碼：")[1].strip()

        print(f"提取到的查詢碼: {query_code}")

        if len(query_code) > 10 and query_code.isdigit():
            print(f"簡易驗證：查詢碼長度大於10，並且是數字：{query_code}")

            data = load_json()
            updated = False

            for entry in data:
                if entry.get("SmilePayNO") == query_code:
                    print(f"找到對應的查詢碼: {query_code}")
                    if entry.get("狀態") != "已付款":
                        entry["狀態"] = "已付款"
                        updated = True
                        channel_id = int(entry["channel_id"])
                        訂單號 = entry["訂單號"]
                        channel = bot.get_channel(channel_id)
                        if channel:
                            await channel.send(f"✅ 訂單 `{訂單號}` 已完成付款，狀態已更新為：已付款\n查詢碼 `{query_code}`")
                    break

            if updated:
                save_json(data)
                print(f"付款狀態已更新，並儲存 JSON 檔案")
            else:
                print(f"未找到需要更新的訂單，或訂單狀態已經是已付款")

    await bot.process_commands(message)

    
    
# 啟動機器人
if __name__ == "__main__":
    bot.run('bot_id')