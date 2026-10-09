"""
ИИ-агент: ежедневное напоминание о днях рождения.
Читает данные из birthdays.json, проверяет даты,
отправляет уведомление в Telegram через Bot API.
"""

import json
import os
import sys
from datetime import date, timedelta
import requests


# ---------- 1. Загрузка данных ----------
def load_birthdays(filepath="birthdays.json"):
    """Читает JSON-файл с контактами. Возвращает список словарей."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("dates", [])
    except FileNotFoundError:
        print(f"Ошибка: файл {filepath} не найден.")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Ошибка в JSON: {e}")
        sys.exit(1)


# ---------- 2. Проверка: у кого сегодня ДР ----------
def get_todays_birthdays(people):
    """
    Возвращает список людей, у кого сегодня день рождения.
    Сравниваем только месяц и день (ММ-ДД), игнорируя год.
    """
    today = date.today()
    today_str = today.strftime("%m-%d")
    celebrating = []

    for person in people:
        # "1965-08-20" -> "08-20"
        birthday_md = person["date"][5:]
        if birthday_md == today_str:
            celebrating.append(person)
    return celebrating


# ---------- 3. Проверка: у кого ДР на этой неделе ----------
def get_upcoming_birthdays(people, days_ahead=7):
    """
    Возвращает список людей, у кого ДР в ближайшие N дней.
    Полезно, чтобы успеть купить подарок.
    """
    today = date.today()
    upcoming = []

    for person in people:
        # Собираем дату ДР в текущем году
        bd_this_year = date(
            today.year,
            int(person["date"][5:7]),  # месяц
            int(person["date"][8:10]),  # день
        )
        # Если ДР уже прошёл в этом году — берём следующий год
        if bd_this_year < today:
            bd_this_year = bd_this_year.replace(year=today.year + 1)

        delta = (bd_this_year - today).days
        if 0 < delta <= days_ahead:
            person_copy = person.copy()
            person_copy["days_until"] = delta
            upcoming.append(person_copy)

    return upcoming


# ---------- 4. Расчёт возраста ----------
def get_age(person):
    """Считает, сколько лет исполняется сегодня."""
    today = date.today()
    birth_year = int(person["date"][:4])
    return today.year - birth_year


# ---------- 5. Генерация сообщения ----------
#def generate_message(person):
    """
    Формирует текст уведомления.
    Здесь можно подключить LLM (OpenAI, Anthropic, Groq) для
    генерации персонализированного поздравления — просто замените
    этот блок на вызов API.
    """
    name = person["name"]
    age = get_age(person)
    interests = person.get("interests", "")

    msg = f"🎂 <b>Сегодня день рождения у {name}!</b>\n"
    msg += f"Исполняется: {age} лет\n"

    if interests:
        msg += f"\n💡 Интересы: {interests}\n"
        msg += "Самое время подобрать подарок!"

    return msg


# ---------- 5,6. Сборка блоков под каждого человека и генерация общего
def format_person_block(person):
    """Формирует блок текста для одного именинника (без отправки)."""
    name = person["name"]
    age = get_age(person)
    interests = person.get("interests", "")

    block = f"🎂 <b>{name}</b> — исполняется {age} лет"
    if interests:
        block += f"\n   💡 Интересы: {interests}"
    return block


def build_daily_message(celebrating, upcoming):
    """
    Собирает одно сообщение из всех поводов:
    - сегодняшние именинники
    - именинники на неделе
    Возвращает строку или None, если поводов нет.
    """
    parts = []

    if celebrating:
        parts.append("🎉 <b>Сегодня день рождения:</b>")
        for person in celebrating:
            parts.append(format_person_block(person))

    if upcoming:
        if parts:
            parts.append("")  # пустая строка-разделитель
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
        print("Проверьте файл .env и launch.json.")
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


# ---------- 7. Главная логика ----------
def main():
    people = load_birthdays()
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
    send_telegram(message)


if __name__ == "__main__":
    main()