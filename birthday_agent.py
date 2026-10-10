"""
ИИ-агент: ежедневное напоминание о днях рождения.
"""

import os
import sys
from datetime import date, timedelta
import requests
import pandas as pd

import csv
import io

def load_birthdays_from_google_sheets():
    """
    Читает данные о днях рождения из Google Таблицы (CSV).
    Устойчив к лишним столбцам и опечаткам в заголовках.
    """
    csv_url = os.environ.get("GOOGLE_SHEET_CSV_URL")

    if not csv_url:
        print("Ошибка: не задан GOOGLE_SHEET_CSV_URL.")
        return []

    try:
        response = requests.get(csv_url, timeout=15)
        response.raise_for_status()

        csv_content = io.StringIO(response.text)
        reader = csv.reader(csv_content)
        
        try:
            header = next(reader)
        except StopIteration:
            print("Ошибка: CSV файл пуст.")
            return []

        # Приводим заголовки к нижнему регистру и убираем пробелы
        header_lower = [h.strip().lower() for h in header]
        
        # Ищем name (обязательно)
        try:
            name_idx = header_lower.index("name")
        except ValueError:
            print(f"Ошибка: нет колонки 'name'. Найдены: {header}")
            return []

        # Ищем date ИЛИ data (на случай опечатки)
        date_idx = None
        for possible_name in ["date", "data"]:
            if possible_name in header_lower:
                date_idx = header_lower.index(possible_name)
                break
        
        if date_idx is None:
            print(f"Ошибка: нет колонки 'date' или 'data'. Найдены: {header}")
            return []

        # Ищем interests (необязательно)
        interests_idx = header_lower.index("interests") if "interests" in header_lower else None

        people = []
        for row in reader:
            # Пропускаем строки, где не хватает данных
            if len(row) <= max(name_idx, date_idx):
                continue

            name = row[name_idx].strip()
            date_str = row[date_idx].strip()
            
            interests = ""
            if interests_idx is not None and len(row) > interests_idx:
                interests = row[interests_idx].strip()

            if not name or not date_str:
                continue

            people.append({
                "name": name,
                "date": date_str,
                "interests": interests,
            })

        print(f"Загружено {len(people)} записей из Google Таблицы.")
        return people

    except requests.RequestException as e:
        print(f"Ошибка при скачивании CSV: {e}")
        return []
    except Exception as e:
        print(f"Ошибка при чтении данных: {e}")
        return []


# ---------- 2. Проверка: у кого сегодня ДР ----------
def get_todays_birthdays(people):
    """Возвращает список людей, у кого сегодня день рождения."""
    today = date.today()
    today_str = today.strftime("%m-%d")
    celebrating = []

    for person in people:
        # Поддерживаем формат "ГГГГ-ММ-ДД" и "ДД.ММ.ГГГГ"
        date_str = person["date"]
        if "-" in date_str:
            birthday_md = date_str[5:]  # "1965-08-20" -> "08-20"
        elif "." in date_str:
            # "20.08.1965" -> "08-20"
            parts = date_str.split(".")
            if len(parts) == 3:
                birthday_md = f"{parts[1]}-{parts[0]}"
            else:
                continue
        else:
            continue

        if birthday_md == today_str:
            celebrating.append(person)

    return celebrating


# ---------- 3. Проверка: у кого ДР на этой неделе ----------
def get_upcoming_birthdays(people, days_ahead=7):
    """Возвращает список людей, у кого ДР в ближайшие N дней."""
    today = date.today()
    upcoming = []

    for person in people:
        try:
            date_str = person["date"]
            if "-" in date_str:
                year, month, day = date_str.split("-")
            elif "." in date_str:
                day, month, year = date_str.split(".")
            else:
                continue

            bd_this_year = date(today.year, int(month), int(day))
            if bd_this_year < today:
                bd_this_year = bd_this_year.replace(year=today.year + 1)

            delta = (bd_this_year - today).days
            if 0 < delta <= days_ahead:
                person_copy = person.copy()
                person_copy["days_until"] = delta
                upcoming.append(person_copy)
        except (ValueError, IndexError):
            continue

    return upcoming


# ---------- 4. Расчёт возраста ----------
def get_age(person):
    """Считает, сколько лет исполняется сегодня."""
    today = date.today()
    date_str = person["date"]
    if "-" in date_str:
        birth_year = int(date_str[:4])
    elif "." in date_str:
        birth_year = int(date_str.split(".")[2])
    else:
        return "?"
    return today.year - birth_year


# ---------- 5. Формирование блоков сообщения ----------
def format_person_block(person):
    """Формирует блок текста для одного именинника."""
    name = person["name"]
    age = get_age(person)
    interests = person.get("interests", "")

    block = f"🎂 <b>{name}</b> — исполняется {age} лет"
    if interests:
        block += f"\n   💡 Интересы: {interests}"
    return block


def build_daily_message(celebrating, upcoming):
    """Собирает одно сообщение из всех поводов."""
    parts = []

    if celebrating:
        parts.append("🎉 <b>Сегодня день рождения:</b>")
        for person in celebrating:
            parts.append(format_person_block(person))

    if upcoming:
        if parts:
            parts.append("")
        parts.append("📅 <b>На этой неделе:</b>")
        for p in upcoming:
            parts.append(f"• {p['name']} — через {p['days_until']} дн.")

    if not parts:
        return None

    return "\n".join(parts)


# ---------- 6. Отправка в Telegram ----------
def send_telegram(text):
    """Отправляет сообщение через Telegram Bot API."""
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not bot_token or not chat_id:
        print("Ошибка: не заданы TELEGRAM_BOT_TOKEN и TELEGRAM_CHAT_ID.")
        return False

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            print("✅ Уведомление отправлено в Telegram.")
            return True
        else:
            print(f"❌ Ошибка отправки: {response.status_code} — {response.text}")
            return False
    except requests.RequestException as e:
        print(f"❌ Сетевая ошибка: {e}")
        return False


def send_long_message(text, limit=4000):
    """Разбивает длинный текст на части и шлёт по очереди."""
    if len(text) <= limit:
        send_telegram(text)
        return

    chunks = []
    current = ""
    for line in text.split("\n"):
        if len(current) + len(line) + 1 > limit:
            chunks.append(current)
            current = line
        else:
            current += ("\n" if current else "") + line
    if current:
        chunks.append(current)

    for chunk in chunks:
        send_telegram(chunk)


# ---------- 7. Главная логика ----------
def main():
    people = load_birthdays_from_google_sheets()

    if not people:
        print("Список пуст или произошла ошибка. Сообщение не отправлено.")
        return

    today = date.today()
    print(f"Проверка дат на {today.strftime('%d.%m.%Y')}...")

    celebrating = get_todays_birthdays(people)
    upcoming = get_upcoming_birthdays(people, days_ahead=7)

    message = build_daily_message(celebrating, upcoming)

    if message is None:
        print("Поводов нет — сообщение не отправлено.")
        return

    print("--- Сообщение ---")
    print(message)
    print("-----------------")
    send_long_message(message)


if __name__ == "__main__":
    main()
