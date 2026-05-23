import os
import requests
import json
from datetime import datetime, timedelta
from anthropic import Anthropic
from PIL import Image, ImageDraw, ImageFont
import io

SUPERMETRICS_API_KEY = os.environ["SUPERMETRICS_API_KEY"]
ANTHROPIC_API_KEY    = os.environ["ANTHROPIC_API_KEY"]
TELEGRAM_BOT_TOKEN   = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID     = os.environ["TELEGRAM_CHAT_ID"]

ACCOUNTS = [
    {"id": "act_2474323176012939", "name": "VIET CORNER RK"},
]

def fetch_data(account_id, date_range):
    url = "https://api.supermetrics.com/enterprise/v2/query/data/json"
    today = datetime.utcnow()

    if date_range == "today":
        start = today.strftime("%Y-%m-%d")
        end = today.strftime("%Y-%m-%d")
    elif date_range == "yesterday":
        yesterday = today - timedelta(days=1)
        start = yesterday.strftime("%Y-%m-%d")
        end = yesterday.strftime("%Y-%m-%d")
    else:
        start = today.strftime("%Y-%m-%d")
        end = today.strftime("%Y-%m-%d")

    query = json.dumps({
        "ds_id": "FA",
        "ds_accounts": account_id,
        "ds_user": "948296091374934",
        "date_range_type": "custom",
        "start_date": start,
        "end_date": end,
        "max_rows": 100,
        "fields": "adcampaign_name,action_link_click,cost,impressions,clicks,ctr,cpc,cpm",
        "api_key": SUPERMETRICS_API_KEY,
    }, separators=(",", ":"))
    r = requests.get(f"{url}?json={requests.utils.quote(query)}", timeout=60)
    r.raise_for_status()
    result = r.json()
    rows = result.get("data", [])
    if rows and isinstance(rows[0], list) and isinstance(rows[0][0], str) and "name" in rows[0][0].lower():
        rows = rows[1:]
    return [
        {
            "campaign":    row[0],
            "result":      int(float(row[1] or 0)),
            "cost":        float(row[2] or 0),
            "impressions": int(float(row[3] or 0)),
            "clicks":      int(float(row[4] or 0)),
            "ctr":         float(row[5] or 0) * 100,
            "cpc":         float(row[6] or 0),
            "cpm":         float(row[7] or 0),
            "cpr":         float(row[2] or 0) / int(float(row[1] or 1)) if float(row[1] or 0) > 0 else 0,
        }
        for row in rows if row and row[0]
    ]

def fetch_data_custom(account_id, start_date, end_date):
    url = "https://api.supermetrics.com/enterprise/v2/query/data/json"
    query = json.dumps({
        "ds_id": "FA",
        "ds_accounts": account_id,
        "ds_user": "948296091374934",
        "date_range_type": "custom",
        "start_date": start_date,
        "end_date": end_date,
        "max_rows": 100,
        "fields": "adcampaign_name,action_link_click,cost,impressions,clicks,ctr,cpc,cpm",
        "api_key": SUPERMETRICS_API_KEY,
    }, separators=(",", ":"))
    r = requests.get(f"{url}?json={requests.utils.quote(query)}", timeout=60)
    r.raise_for_status()
    result = r.json()
    rows = result.get("data", [])
    if rows and isinstance(rows[0], list) and isinstance(rows[0][0], str) and "name" in rows[0][0].lower():
        rows = rows[1:]
    return [
        {
            "campaign":    row[0],
            "result":      int(float(row[1] or 0)),
            "cost":        float(row[2] or 0),
            "impressions": int(float(row[3] or 0)),
            "clicks":      int(float(row[4] or 0)),
            "ctr":         float(row[5] or 0) * 100,
            "cpc":         float(row[6] or 0),
            "cpm":         float(row[7] or 0),
            "cpr":         float(row[2] or 0) / int(float(row[1] or 1)) if float(row[1] or 0) > 0 else 0,
        }
        for row in rows if row and row[0]
    ]

def get_status(campaigns, is_weekly=False):
    client = Anthropic(api_key=ANTHROPIC_API_KEY)
    data_str = json.dumps(campaigns, ensure_ascii=False)
    period = "тиждень" if is_weekly else "сьогодні"
    prompt = f"""Проаналізуй Meta Ads кампанії за {period} і дай статус кожній. Відповідай ТІЛЬКИ JSON масивом без пояснень.

Дані: {data_str}

Формат відповіді (масив об'єктів, порядок як у вхідних даних):
[{{"emoji": "🟢", "name": "назва кампанії", "desc": "коротка конкретна рекомендація"}}, ...]

Правила:
- CTR норма: для трафику >= 1.5% — добре, для доставки >= 1.0% — добре, нижче — слідкувати
- 🟢 якщо CTR >= 2.5% і CPC <= 0.15 — що саме добре і що тримати
- 🟡 якщо середні показники — що саме перевірити
- 🔴 тільки якщо result <= 2 або CTR < 0.8% — що терміново зробити
- desc максимум 80 символів, конкретно: цифри, дії
- Мова: українська"""

    message = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}],
    )
    try:
        text = message.content[0].text.strip()
        if "```" in text:
            text = text.split("```")[1].replace("json", "").strip()
        data = json.loads(text)
        return [(d["emoji"], d["name"], d["desc"]) for d in data]
    except:
        statuses = []
        for c in campaigns:
            if c["ctr"] >= 2.5 and c["cpc"] <= 0.15:
                statuses.append(("🟢", c["campaign"], "все потужно, тримаємо"))
            elif c["result"] <= 2 or c["ctr"] < 0.8:
                statuses.append(("🔴", c["campaign"], "терміново перевірити / перезапустити"))
            else:
                statuses.append(("🟡", c["campaign"], "слідкувати за динамікою"))
        return statuses

def get_overall_status(campaigns):
    red = sum(1 for c in campaigns if c["result"] <= 2 or c["ctr"] < 0.8)
    green = sum(1 for c in campaigns if c["ctr"] >= 2.5 and c["cpc"] <= 0.15)
    total = len(campaigns)
    if red == 0 and green >= total // 2:
        return ("🟢", "Загальний підсумок: все працює добре. Тримаємо курс!")
    elif red >= total // 2:
        return ("🔴", f"Загальний підсумок: {red} з {total} кампаній потребують термінової уваги!")
    else:
        return ("🟡", "Загальний підсумок: є моменти для покращення, слідкуємо за динамікою.")

def generate_image(account_name, campaigns, yesterday_campaigns, title="Утренній звіт Meta Ads", period=None):
    today = period if period else datetime.utcnow().strftime("%d.%m.%Y")
    yesterday = (datetime.utcnow() - timedelta(days=1)).strftime("%d.%m.%Y")
    is_weekly = period is not None
    statuses = get_status(campaigns, is_weekly=is_weekly)
    overall_emoji, overall_text = get_overall_status(campaigns)

    if not is_weekly and yesterday_campaigns:
        y_cost = sum(c["cost"] for c in yesterday_campaigns)
        y_results = sum(c["result"] for c in yesterday_campaigns)
        y_cpr = y_cost / y_results if y_results else 0
        summary_text = f"Вчора ({yesterday})   Витрачено: ${y_cost:.2f}   Отримано: {y_results} результатів   Ціна результату: ${y_cpr:.2f}"
    else:
        summary_text = ""

    BG = (28, 28, 30)
    BG2 = (38, 38, 40)
    BG3 = (48, 48, 52)
    WHITE = (255, 255, 255)
    GRAY = (160, 160, 170)
    GREEN = (52, 199, 89)
    YELLOW = (255, 204, 0)
    RED = (255, 69, 58)
    BORDER = (60, 60, 65)

    W = 1200
    ROW_H = 56
    TABLE_TOP = 160
    cols = ["Кампанія", "Результат", "Ціна/рез.", "Витрати", "Покази", "Кліки", "CTR", "CPC", "CPM"]
    col_w = [250, 100, 105, 95, 95, 75, 85, 85, 85]
    STATUS_H = 80 + len(statuses) * 44
    OVERALL_H = 60
    SUMMARY_H = 50 if summary_text else 10
    H = TABLE_TOP + ROW_H + (len(campaigns) + 1) * ROW_H + SUMMARY_H + STATUS_H + OVERALL_H + 40

    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    try:
        font_b = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 18)
