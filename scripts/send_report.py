import os
import requests
import json
from datetime import datetime
from anthropic import Anthropic

SUPERMETRICS_API_KEY = os.environ["SUPERMETRICS_API_KEY"]
ANTHROPIC_API_KEY    = os.environ["ANTHROPIC_API_KEY"]
TELEGRAM_BOT_TOKEN   = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID     = os.environ["TELEGRAM_CHAT_ID"]

ACCOUNTS = [
    {"id": "act_2474323176012939", "name": "VIET CORNER RK"},
]

def fetch_campaign_data(account_id):
    today = datetime.utcnow().strftime("%Y-%m-%d")
    url = "https://api.supermetrics.com/enterprise/v2/query/data/json"
    params = {
        "json": json.dumps({
            "ds_id": "FA",
            "ds_accounts": account_id,
            "ds_user": "948296091374934",
            "ds_start_date": today,
            "ds_end_date": today,
          "fields": "adcampaign_name,action_link_click,cost,impressions,clicks,ctr,cpc,cpm",
            "settings": {"report_type": "campaign"},
            "api_key": SUPERMETRICS_API_KEY,
        })
    }
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    data = r.json()
    rows = data.get("data", [])
    if rows and isinstance(rows[0], list) and isinstance(rows[0][0], str) and "name" in rows[0][0].lower():
        rows = rows[1:]
    return [
        {
            "campaign":    row[0],
            "result":      int(float(row[1] or 0)),
            "cost":        float(row[2] or 0),
            "impressions": int(float(row[3] or 0)),
            "clicks":      int(float(row[4] or 0)),
            "ctr":         float(row[5] or 0),
            "cpc":         float(row[6] or 0),
            "cpm":         float(row[7] or 0),
        }
        for row in rows if row and row[0]
    ]

def generate_report(account_name, campaigns):
    client = Anthropic(api_key=ANTHROPIC_API_KEY)
    today  = datetime.utcnow().strftime("%d.%m.%Y")
    data_str = json.dumps(campaigns, ensure_ascii=False, indent=2)
    prompt = f"""Ти асистент з аналізу Meta Ads. Сформуй утренній звіт для Telegram.

Клієнт: {account_name}
Дата: {today}
Дані: {data_str}

Правила:
1. Заголовок: "📊 Утренній звіт Meta Ads / Клієнт: {account_name} / Дата: {today}"
2. По кожній кампанії: Назва | Результат | Витрати | Покази | CTR | CPC | CPM
3. Рядок "Разом"
4. Статус: 🟢 добре / 🟡 слідкувати / 🔴 терміново
5. Plain text, українська мова."""
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text

def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    r = requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": text}, timeout=15)
    r.raise_for_status()
    print(f"Sent {len(text)} chars")

def main():
    for account in ACCOUNTS:
        try:
            campaigns = fetch_campaign_data(account["id"])
            if not campaigns:
                send_telegram(f"⚠️ {account['name']}: немає даних за сьогодні.")
                continue
            report = generate_report(account["name"], campaigns)
            send_telegram(report)
        except Exception as e:
            send_telegram(f"❌ Помилка: {e}")

if __name__ == "__main__":
    main()
