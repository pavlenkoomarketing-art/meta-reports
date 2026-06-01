import os
import requests
import json
import time
from datetime import datetime, timedelta
from anthropic import Anthropic
from PIL import Image, ImageDraw, ImageFont
import io

ANTHROPIC_API_KEY  = os.environ["ANTHROPIC_API_KEY"]
FB_APP_ID          = os.environ["FB_APP_ID"]
FB_APP_SECRET      = os.environ["FB_APP_SECRET"]
FB_ACCESS_TOKEN    = os.environ["FB_ACCESS_TOKEN"]

ACCOUNTS = [
    {
        "id": "act_2474323176012939",
        "name": "VIET CORNER RK",
        "bot_token": os.environ.get("TELEGRAM_BOT_TOKEN", ""),
        "chat_ids": [
            os.environ.get("TELEGRAM_CHAT_ID", ""),
            os.environ.get("TELEGRAM_CHAT_ID_2", ""),
        ],
        "context": """
            Ресторан в'єтнамської кухні в Одесі.
            Ціль реклами: доставка їжі та відвідування ресторану.
            Цільова аудиторія: 21-54 роки, Одеса.
            Нормальний CPR: до $0.15
            Нормальний CTR: від 1.5%
            Головні кампанії: доставка, контент (дописи), відео UGC.
        """
    },
    {
        "id": "act_707464865220616",
        "name": "Затока Готель",
        "bot_token": os.environ.get("TELEGRAM_BOT_TOKEN_2", ""),
        "chat_ids": [
            os.environ.get("TELEGRAM_CHAT_ID", ""),
            os.environ.get("TELEGRAM_CHAT_ID_4", ""),
        ],
        "context": """
            Готельний комплекс в Затоці, Одеська область.
            Є басейн на даху та вихід до моря.
            Ціль реклами: бронювання номерів та залучення гостей.
            Цільова аудиторія: сім'ї та пари, 25-55 років.
            Нормальний CPR: до $0.50
            Нормальний CTR: від 1.5%
        """
    },
]

def get_long_lived_token():
    url = "https://graph.facebook.com/oauth/access_token"
    r = requests.get(url, params={
        "grant_type": "fb_exchange_token",
        "client_id": FB_APP_ID,
        "client_secret": FB_APP_SECRET,
        "fb_exchange_token": FB_ACCESS_TOKEN,
    }, timeout=30)
    r.raise_for_status()
    return r.json().get("access_token", FB_ACCESS_TOKEN)

def fetch_meta_data(account_id, start_date, end_date):
    token = get_long_lived_token()
    url = f"https://graph.facebook.com/v19.0/{account_id}/insights"
    params = {
        "access_token": token,
        "level": "campaign",
        "fields": "campaign_name,impressions,clicks,ctr,cpc,cpm,spend,actions,objective",
        "time_range": json.dumps({"since": start_date, "until": end_date}),
        "limit": 100,
    }
    for attempt in range(3):
        try:
            r = requests.get(url, params=params, timeout=60)
            r.raise_for_status()
            data = r.json().get("data", [])
            results = []
            for row in data:
                spend = float(row.get("spend", 0))
                impressions = int(row.get("impressions", 0))
                clicks = int(row.get("clicks", 0))
                ctr = float(row.get("ctr", 0))
                cpc = float(row.get("cpc", 0))
                cpm = float(row.get("cpm", 0))
                objective = row.get("objective", "")
                actions = row.get("actions", [])
                result = 0
                for action in actions:
                    if action.get("action_type") == "link_click":
                        result = int(float(action.get("value", 0)))
                        break
                cpr = spend / result if result > 0 else 0
                results.append({
                    "campaign":    row.get("campaign_name", ""),
                    "objective":   objective,
                    "result":      result,
                    "cost":        spend,
                    "impressions": impressions,
                    "clicks":      clicks,
                    "ctr":         ctr,
                    "cpc":         cpc,
                    "cpm":         cpm,
                    "cpr":         cpr,
                })
            return results
        except requests.exceptions.HTTPError as e:
            if "429" in str(e) and attempt < 2:
                time.sleep(30)
                continue
            raise
        except requests.exceptions.Timeout:
            if attempt < 2:
                time.sleep(10)
                continue
            raise

def fetch_best_creative(account_id):
    try:
        token = get_long_lived_token()
        url = f"https://graph.facebook.com/v19.0/{account_id}/insights"
        today = datetime.utcnow()
        start = (today - timedelta(days=7)).strftime("%Y-%m-%d")
        end = today.strftime("%Y-%m-%d")
        params = {
            "access_token": token,
            "level": "ad",
            "fields": "ad_name,impressions,clicks,ctr,spend,actions",
            "time_range": json.dumps({"since": start, "until": end}),
            "limit": 50,
            "sort": "impressions_descending",
        }
        for attempt in range(3):
            try:
                r = requests.get(url, params=params, timeout=60)
                r.raise_for_status()
                break
            except requests.exceptions.HTTPError as e:
                if "429" in str(e) and attempt < 2:
                    time.sleep(30)
                    continue
                return None
        data = r.json().get("data", [])
        if not data:
            return None
        best = None
        best_result = 0
        for ad in data:
            actions = ad.get("actions", [])
            result = 0
            for action in actions:
                if action.get("action_type") == "link_click":
                    result = int(float(action.get("value", 0)))
                    break
            if result > best_result:
                best_result = result
                best = ad
        if best:
            spend = float(best.get("spend", 0))
            cpr = spend / best_result if best_result > 0 else 0
            return {
                "name": best.get("ad_name", ""),
                "result": best_result,
                "ctr": float(best.get("ctr", 0)),
                "spend": spend,
                "cpr": cpr,
            }
    except:
        return None

def fetch_data(account_id, date_range):
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
    time.sleep(2)
    return fetch_meta_data(account_id, start, end)

def fetch_data_custom(account_id, start_date, end_date):
    time.sleep(2)
    return fetch_meta_data(account_id, start_date, end_date)

def get_arrow(curr, prev, reverse=False):
    if prev == 0:
        return ""
    diff = ((curr - prev) / prev) * 100
    if abs(diff) < 5:
        return "→"
    if diff > 0:
        return "↑" if not reverse else "↓"
    else:
        return "↓" if not reverse else "↑"

def get_arrow_color(arrow, reverse=False):
    if arrow == "↑":
        return (52, 199, 89) if not reverse else (255, 69, 58)
    elif arrow == "↓":
        return (255, 69, 58) if not reverse else (52, 199, 89)
    return (160, 160, 170)

def get_actions_and_text(campaigns, yesterday_campaigns, client_context, is_weekly=False):
    client = Anthropic(api_key=ANTHROPIC_API_KEY)
    data_str = json.dumps(campaigns, ensure_ascii=False)
    yesterday_str = json.dumps(yesterday_campaigns, ensure_ascii=False) if yesterday_campaigns else "[]"
    period = "тиждень" if is_weekly else "сьогодні"

    prompt = f"""Проаналізуй Meta Ads кампанії за {period}.

Контекст клієнта: {client_context}
Дані за {period}: {data_str}
Дані за вчора: {yesterday_str}

Відповідай ТІЛЬКИ JSON без пояснень у форматі:
{{
  "actions": ["дія 1", "дія 2", "дія 3", "дія 4"],
  "overall": "🟢 Все добре"
}}

Правила для "actions":
- 3-5 конкретних дій по кампаніях і креативах
- Враховуй ціль кампанії (objective)
- Порівнюй з вчора — якщо є зміна >20% вкажи
- Конкретні назви кампаній і цифри
- Мова: українська

Правила для "overall":
- 🟢 якщо все добре
- 🟡 якщо є питання
- 🔴 якщо є проблеми"""

    message = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=600,
        messages=[{"role": "user", "content": prompt}],
    )
    try:
        text = message.content[0].text.strip()
        if "```" in text:
            text = text.split("```")[1].replace("json", "").strip()
        data = json.loads(text)
        return data.get("actions", []), data.get("overall", "🟢 Все добре")
    except:
        return ["Перевірити показники кампаній"], "🟡 Потребує уваги"

def generate_image(account_name, campaigns, yesterday_campaigns, title="Утренній звіт Meta Ads", period=None, best_creative=None, client_context=""):
    today = period if period else datetime.utcnow().strftime("%d.%m.%Y")
    yesterday_date = (datetime.utcnow() - timedelta(days=1)).strftime("%d.%m.%Y")
    is_weekly = period is not None

    actions, overall = get_actions_and_text(campaigns, yesterday_campaigns, client_context, is_weekly)

    if not is_weekly and yesterday_campaigns:
        y_cost = sum(c["cost"] for c in yesterday_campaigns)
        y_results = sum(c["result"] for c in yesterday_campaigns)
        y_cpr = y_cost / y_results if y_results else 0
        summary_text = f"Вчора ({yesterday_date})   Витрачено: ${y_cost:.2f}   Отримано: {y_results} результатів по ціні: ${y_cpr:.2f}"
    else:
        summary_text = ""

    yesterday_map = {c["campaign"]: c for c in yesterday_campaigns} if yesterday_campaigns else {}

    BG = (28, 28, 30)
    BG2 = (38, 38, 40)
    BG3 = (48, 48, 52)
    WHITE = (255, 255, 255)
    GRAY = (160, 160, 170)
    GREEN = (52, 199, 89)
    BORDER = (60, 60, 65)

    W = 1200
    ROW_H = 56
    TABLE_TOP = 160
    cols = ["Кампанія", "Результат", "Витрати", "Покази", "Кліки", "CTR", "CPC", "CPM", "CPL"]
    col_w = [250, 95, 95, 100, 75, 85, 85, 85, 85]

    ACTIONS_H = 50 + len(actions) * 30 + 20
    SUMMARY_H = 50 if summary_text else 10
    CREATIVE_H = 44 if best_creative else 0
    H = TABLE_TOP + ROW_H + (len(campaigns) + 1) * ROW_H + SUMMARY_H + ACTIONS_H + CREATIVE_H + 40

    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    try:
        font_b = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 18)
        font_sm = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
        font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 26)
        font_arrow = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12)
    except:
        font_b = font_sm = font_title = font_arrow = ImageFont.load_default()

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

        yest = yesterday_map.get(c["campaign"], {})
        name = c["campaign"][:28] + "..." if len(c["campaign"]) > 28 else c["campaign"]

        arr_result = get_arrow(c["result"], yest.get("result", 0))
        arr_cost = get_arrow(c["cost"], yest.get("cost", 0), reverse=True)
        arr_imp = get_arrow(c["impressions"], yest.get("impressions", 0))
        arr_clicks = get_arrow(c["clicks"], yest.get("clicks", 0))
        arr_ctr = get_arrow(c["ctr"], yest.get("ctr", 0))
        arr_cpc = get_arrow(c["cpc"], yest.get("cpc", 0), reverse=True)
        arr_cpm = get_arrow(c["cpm"], yest.get("cpm", 0), reverse=True)
        arr_cpr = get_arrow(c["cpr"], yest.get("cpr", 0), reverse=True)

        metrics = [
            (name, None, None),
            (str(c["result"]), arr_result, False),
            (f"${c['cost']:.2f}", arr_cost, True),
            (f"{c['impressions']:,}", arr_imp, False),
            (str(c["clicks"]), arr_clicks, False),
            (f"{c['ctr']:.2f}%", arr_ctr, False),
            (f"${c['cpc']:.2f}", arr_cpc, True),
            (f"${c['cpm']:.2f}", arr_cpm, True),
            (f"${c['cpr']:.2f}", arr_cpr, True),
        ]

        x = 40
        for i, (val, arrow, rev) in enumerate(metrics):
            if i == 0:
                draw.text((x + 10, y + 18), val, font=font_sm, fill=WHITE)
            else:
                tw = int(draw.textlength(val, font=font_sm))
                cx = x + col_w[i] // 2
                if arrow and arrow != "→":
                    arr_color = get_arrow_color(arrow, rev)
                    aw = int(draw.textlength(arrow, font=font_arrow))
                    total_w = tw + aw + 3
                    draw.text((cx - total_w // 2, y + 18), val, font=font_sm, fill=WHITE)
                    draw.text((cx - total_w // 2 + tw + 3, y + 20), arrow, font=font_arrow, fill=arr_color)
                else:
                    draw.text((cx - tw // 2, y + 18), val, font=font_sm, fill=WHITE)
            x += col_w[i]

    y = TABLE_TOP + ROW_H + len(campaigns) * ROW_H
    draw.rectangle([40, y, W - 40, y + ROW_H], fill=BG3)
    avg_ctr = sum(c["ctr"] for c in campaigns) / len(campaigns) if campaigns else 0
    avg_cpc = totals["cost"] / totals["clicks"] if totals["clicks"] else 0
    avg_cpm = totals["cost"] / totals["impressions"] * 1000 if totals["impressions"] else 0
    total_cpr = totals["cost"] / totals["result"] if totals["result"] else 0
    total_vals = ["Разом", str(totals["result"]), f"${totals['cost']:.2f}",
                  f"{totals['impressions']:,}", str(totals["clicks"]),
                  f"{avg_ctr:.2f}%", f"${avg_cpc:.2f}", f"${avg_cpm:.2f}", f"${total_cpr:.2f}"]
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
        ys += 36

    if best_creative:
        creative_text = f"🏆 Кращий креатив (7 днів): {best_creative['name'][:45]}   CTR: {best_creative['ctr']:.2f}%   CPR: ${best_creative['cpr']:.2f}"
        draw.text((40, ys), creative_text, font=font_sm, fill=GREEN)
        ys += 36

    sy = ys + 10
    actions_block_h = 36 + len(actions) * 30 + 16
    draw.rectangle([40, sy, W - 40, sy + actions_block_h], fill=BG2, outline=BORDER)
    draw.text((56, sy + 10), "Що зробити сьогодні", font=font_b, fill=WHITE)
    sy += 40
    for action in actions:
        short = action[:95] + "..." if len(action) > 95 else action
        draw.text((56, sy), f"- {short}", font=font_sm, fill=GRAY)
        sy += 30

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.getvalue(), overall, summary_text

def send_report(account, photo_bytes, caption):
    bot_token = account["bot_token"]
    chat_ids = [c for c in account["chat_ids"] if c]
    if not bot_token:
        print(f"No bot token for {account['name']}, skipping send")
        return
    url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
    for chat_id in chat_ids:
        try:
            r = requests.post(
                url,
                data={"chat_id": chat_id, "caption": caption, "parse_mode": "HTML"},
                files={"photo": ("report.png", photo_bytes, "image/png")},
                timeout=30
            )
            print(f"Send to {chat_id}: {r.status_code} {r.text[:100]}")
            r.raise_for_status()
            print(f"Sent to {chat_id}!")
        except Exception as e:
            print(f"Error sending to {chat_id}: {e}")

def send_error(account, text):
    bot_token = account.get("bot_token", "")
    chat_ids = [c for c in account.get("chat_ids", []) if c]
    if not bot_token or not chat_ids:
        print(f"Cannot send error for {account.get('name')} — no token or chat_ids")
        return
    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        r = requests.post(url, json={"chat_id": chat_ids[0], "text": text}, timeout=15)
        r.raise_for_status()
    except Exception as e:
        print(f"Error sending error message: {e}")

def build_caption(account_name, overall, summary_text, yesterday_campaigns, campaigns):
    today = datetime.utcnow().strftime("%d.%m.%Y")
    lines = [f"<b>Ранковий звіт · {today}</b>", f"🏢 Клієнт: {account_name}", ""]
    if summary_text:
        lines.append(f"<b>{summary_text}</b>")
    if yesterday_campaigns and campaigns:
        y_total = sum(c["result"] for c in yesterday_campaigns)
        t_total = sum(c["result"] for c in campaigns)
        diff = t_total - y_total
        sign = "+" if diff >= 0 else ""
        lines.append(f"Порівняно з вчора: {sign}{diff} результатів")
    lines.append("")
    lines.append(overall)
    return "\n".join(lines)

def main():
    report_type = os.environ.get("REPORT_TYPE", "daily")
    print(f"Report type: {report_type}")

    for account in ACCOUNTS:
        print(f"\n=== Processing: {account['name']} ===")
        print(f"Bot token: {'YES' if account.get('bot_token') else 'NO'}")
        print(f"Chat IDs: {account['chat_ids']}")
        print(f"Account ID: {account['id']}")

        try:
            if not account.get("bot_token"):
                print(f"Skipping {account['name']} — no bot token")
                continue

            client_context = account.get("context", "")
            best_creative = fetch_best_creative(account["id"])
            print(f"Best creative: {'found' if best_creative else 'not found'}")

            if report_type == "weekly":
                today = datetime.utcnow()
                last_monday = today - timedelta(days=today.weekday() + 7)
                last_sunday = last_monday + timedelta(days=6)
                campaigns = fetch_data_custom(account["id"],
                    last_monday.strftime("%Y-%m-%d"),
                    last_sunday.strftime("%Y-%m-%d"))
                print(f"Weekly campaigns: {len(campaigns) if campaigns else 0}")
                if not campaigns:
                    send_error(account, f"⚠️ {account['name']}: немає даних за тиждень.")
                    continue
                photo, overall, summary_text = generate_image(
                    account["name"], campaigns, [],
                    title="Тижневий звіт Meta Ads",
                    period=f"{last_monday.strftime('%d.%m.%Y')} – {last_sunday.strftime('%d.%m.%Y')}",
                    best_creative=best_creative,
                    client_context=client_context,
                )
                caption = build_caption(account["name"], overall, summary_text, [], campaigns)

            elif report_type == "monthly":
                today = datetime.utcnow()
                first_day = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
                last_day = today.replace(day=1) - timedelta(days=1)
                prev_first = (first_day.replace(day=1) - timedelta(days=1)).replace(day=1)
                prev_last = first_day - timedelta(days=1)
                campaigns = fetch_data_custom(account["id"],
                    first_day.strftime("%Y-%m-%d"),
                    last_day.strftime("%Y-%m-%d"))
                prev_campaigns = fetch_data_custom(account["id"],
                    prev_first.strftime("%Y-%m-%d"),
                    prev_last.strftime("%Y-%m-%d"))
                print(f"Monthly campaigns: {len(campaigns) if campaigns else 0}")
                if not campaigns:
                    send_error(account, f"⚠️ {account['name']}: немає даних за місяць.")
                    continue
                photo, overall, summary_text = generate_image(
                    account["name"], campaigns, prev_campaigns,
                    title="Місячний звіт Meta Ads",
                    period=f"{first_day.strftime('%d.%m.%Y')} – {last_day.strftime('%d.%m.%Y')}",
                    best_creative=best_creative,
                    client_context=client_context,
                )
                caption = build_caption(account["name"], overall, summary_text, prev_campaigns, campaigns)

            else:
                campaigns = fetch_data(account["id"], "today")
                yesterday_campaigns = fetch_data(account["id"], "yesterday")
                print(f"Today campaigns: {len(campaigns) if campaigns else 0}")
                print(f"Yesterday campaigns: {len(yesterday_campaigns) if yesterday_campaigns else 0}")
                if not campaigns:
                    send_error(account, f"⚠️ {account['name']}: немає даних за сьогодні.")
                    continue
                photo, overall, summary_text = generate_image(
                    account["name"], campaigns, yesterday_campaigns,
                    best_creative=best_creative,
                    client_context=client_context,
                )
                caption = build_caption(account["name"], overall, summary_text, yesterday_campaigns, campaigns)

            send_report(account, photo, caption)

        except Exception as e:
            print(f"Exception for {account['name']}: {e}")
            send_error(account, f"❌ Помилка {account['name']}: {e}")

if __name__ == "__main__":
    main()
