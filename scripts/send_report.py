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
TELEGRAM_CHAT_ID_2   = os.environ.get("TELEGRAM_CHAT_ID_2", "")

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
    for attempt in range(3):
        try:
            r = requests.get(f"{url}?json={requests.utils.quote(query)}", timeout=90)
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
        except requests.exceptions.Timeout:
            if attempt < 2:
                import time
                time.sleep(10)
                continue
            raise

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
    for attempt in range(3):
        try:
            r = requests.get(f"{url}?json={requests.utils.quote(query)}", timeout=90)
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
        except requests.exceptions.Timeout:
            if attempt < 2:
                import time
                time.sleep(10)
                continue
            raise

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
        font_sm = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
        font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 26)
    except:
        font_b = font_sm = font_title = ImageFont.load_default()

    draw.text((40, 28), title, font=font_title, fill=WHITE)
    draw.text((40, 64), f"Клієнт: {account_name}", font=font_sm, fill=GRAY)
    date_label = f"Період: {today}" if is_weekly else f"Дата: {today}"
    date_w = int(draw.textlength(date_label, font=font_sm))
    draw.text((W - date_w - 40, 28), date_label, font=font_sm, fill=GRAY)

    x = 40
    draw.rectangle([x, TABLE_TOP, W - 40, TABLE_TOP + ROW_H], fill=BG3)
    for i, col in enumerate(cols):
        align_x = x + 10 if i == 0 else x + col_w[i] // 2 - int(draw.textlength(col, font=font_b)) // 2
        draw.text((align_x, TABLE_TOP + 18), col, font=font_b, fill=GRAY)
        x += col_w[i]

    totals = {"result": 0, "cost": 0, "impressions": 0, "clicks": 0}
    for ri, c in enumerate(campaigns):
        y = TABLE_TOP + ROW_H + ri * ROW_H
        row_bg = BG if ri % 2 == 0 else BG2
        draw.rectangle([40, y, W - 40, y + ROW_H], fill=row_bg)
        draw.line([40, y + ROW_H, W - 40, y + ROW_H], fill=BORDER, width=1)

        totals["result"] += c["result"]
        totals["cost"] += c["cost"]
        totals["impressions"] += c["impressions"]
        totals["clicks"] += c["clicks"]

        name = c["campaign"][:28] + "..." if len(c["campaign"]) > 28 else c["campaign"]
        values = [
            name,
            str(c["result"]),
            f"${c['cpr']:.2f}",
            f"${c['cost']:.2f}",
            f"{c['impressions']:,}",
            str(c["clicks"]),
            f"{c['ctr']:.2f}%",
            f"${c['cpc']:.2f}",
            f"${c['cpm']:.2f}",
        ]
        x = 40
        for i, val in enumerate(values):
            color = WHITE
            if i == 6 and c["ctr"] >= 2.5:
                color = GREEN
            elif i == 6 and c["ctr"] < 1.5:
                color = RED
            elif i == 7 and c["cpc"] <= 0.12:
                color = GREEN
            elif i == 8 and c["cpm"] <= 2.0:
                color = GREEN
            if i == 0:
                draw.text((x + 10, y + 18), val, font=font_sm, fill=color)
            else:
                tw = int(draw.textlength(val, font=font_sm))
                draw.text((x + col_w[i] // 2 - tw // 2, y + 18), val, font=font_sm, fill=color)
            x += col_w[i]

    y = TABLE_TOP + ROW_H + len(campaigns) * ROW_H
    draw.rectangle([40, y, W - 40, y + ROW_H], fill=BG3)
    avg_ctr = sum(c["ctr"] for c in campaigns) / len(campaigns) if campaigns else 0
    avg_cpc = totals["cost"] / totals["clicks"] if totals["clicks"] else 0
    avg_cpm = totals["cost"] / totals["impressions"] * 1000 if totals["impressions"] else 0
    total_cpr = totals["cost"] / totals["result"] if totals["result"] else 0
    total_vals = ["Разом", str(totals["result"]), f"${total_cpr:.2f}",
                  f"${totals['cost']:.2f}", f"{totals['impressions']:,}",
                  str(totals["clicks"]), f"{avg_ctr:.2f}%",
                  f"${avg_cpc:.2f}", f"${avg_cpm:.2f}"]
    x = 40
    for i, val in enumerate(total_vals):
        if i == 0:
            draw.text((x + 10, y + 18), val, font=font_b, fill=WHITE)
        else:
            tw = int(draw.textlength(val, font=font_b))
            draw.text((x + col_w[i] // 2 - tw // 2, y + 18), val, font=font_b, fill=WHITE)
        x += col_w[i]

    ys = y + ROW_H + 16
    if summary_text:
        draw.text((40, ys), summary_text, font=font_sm, fill=GRAY)

    sy = ys + (40 if summary_text else 10)
    draw.rectangle([40, sy, W - 40, sy + 36 + len(statuses) * 44 + 16], fill=BG2, outline=BORDER)
    draw.text((56, sy + 10), "Статус кампаній", font=font_b, fill=WHITE)
    sy += 46
    for emoji, name, desc in statuses:
        color = GREEN if emoji == "🟢" else (YELLOW if emoji == "🟡" else RED)
        draw.ellipse([56, sy + 2, 70, sy + 16], fill=color)
        short = name[:42] + "..." if len(name) > 42 else name
        draw.text((82, sy), f"{short} — {desc}", font=font_sm, fill=WHITE)
        sy += 44

    sy += 16
    overall_color = GREEN if overall_emoji == "🟢" else (YELLOW if overall_emoji == "🟡" else RED)
    draw.rectangle([40, sy, W - 40, sy + 44], fill=BG3, outline=overall_color)
    draw.ellipse([56, sy + 14, 70, sy + 28], fill=overall_color)
    draw.text((82, sy + 13), overall_text, font=font_b, fill=WHITE)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.getvalue()

def send_telegram_photo(photo_bytes):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    chat_ids = [TELEGRAM_CHAT_ID]
    if TELEGRAM_CHAT_ID_2:
        chat_ids.append(TELEGRAM_CHAT_ID_2)
    print(f"Chat IDs: {chat_ids}")
    print(f"Photo bytes length: {len(photo_bytes)}")
    for chat_id in chat_ids:
        print(f"Sending to {chat_id}...")
        r = requests.post(
            url,
            data={"chat_id": chat_id},
            files={"photo": ("report.png", photo_bytes, "image/png")},
            timeout=30
        )
        print(f"Response: {r.status_code} {r.text}")
        r.raise_for_status()
        print(f"Photo sent to {chat_id}!")

def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    r = requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": text}, timeout=15)
    r.raise_for_status()

def main():
    report_type = os.environ.get("REPORT_TYPE", "daily")

    for account in ACCOUNTS:
        try:
            if report_type == "weekly":
                today = datetime.utcnow()
                last_monday = today - timedelta(days=today.weekday() + 7)
                last_sunday = last_monday + timedelta(days=6)
                start = last_monday.strftime("%Y-%m-%d")
                end = last_sunday.strftime("%Y-%m-%d")
                campaigns = fetch_data_custom(account["id"], start, end)
                if not campaigns:
                    send_telegram(f"⚠️ {account['name']}: немає даних за тиждень.")
                    continue
                photo = generate_image(
                    account["name"],
                    campaigns,
                    [],
                    title="Тижневий звіт Meta Ads",
                    period=f"{last_monday.strftime('%d.%m.%Y')} – {last_sunday.strftime('%d.%m.%Y')}"
                )
            else:
                campaigns = fetch_data(account["id"], "today")
                yesterday_campaigns = fetch_data(account["id"], "yesterday")
                if not campaigns:
                    send_telegram(f"⚠️ {account['name']}: немає даних за сьогодні.")
                    continue
                photo = generate_image(account["name"], campaigns, yesterday_campaigns)

            send_telegram_photo(photo)
        except Exception as e:
            send_telegram(f"❌ Помилка: {e}")

if __name__ == "__main__":
    main()
