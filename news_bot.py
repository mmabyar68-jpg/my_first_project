import feedparser
import requests
import os
import time
import re
from deep_translator import GoogleTranslator
import pyshorteners
import difflib

# ---------- تنظیمات ----------
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID")

if not TELEGRAM_TOKEN or not CHANNEL_ID:
    raise ValueError("TELEGRAM_TOKEN and CHANNEL_ID must be set as environment variables")

# لیست فیدها با نام منبع
RSS_FEEDS = [
    ("CNN", "http://rss.cnn.com/rss/edition.rss"),
    ("BBC", "http://feeds.bbci.co.uk/news/world/rss.xml"),
    ("Reuters", "http://feeds.reuters.com/Reuters/worldNews"),
    ("Google News", "https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en"),
    ("Al Jazeera", "https://www.aljazeera.com/xml/rss/all.xml"),
    ("RT", "https://www.rt.com/rss/"),
    ("Tasnim", "https://www.tasnimnews.com/fa/rss/feed/0/8/0/%D8%AA%D9%85%D8%A7%D9%85-%D8%A7%D8%AE%D8%A8%D8%A7%D8%B1"),
    ("IRNA", "https://www.irna.ir/rss/"),
]

SENT_LINKS_FILE = "sent_links.txt"
SENT_TITLES_FILE = "sent_titles.txt"

# لیست کلمات نامطلوب (انگلیسی و فارسی)
EN_BLACKLIST = [
    "celebrity", "singer", "actor", "actress", "movie", "film", "sport",
    "entertainment", "gossip", "rumor", "music", "tv", "reality show"
]
FA_BLACKLIST = [
    "خواننده", "سلبریتی", "بازیگر", "سینما", "فیلم", "ورزش", "موسیقی",
    "تلویزیون", "شایعه", "هنرمند", "کنسرت", "آلبوم", "سریال"
]

translator = GoogleTranslator(source='auto', target='fa')
shortener = pyshorteners.Shortener()

def load_set_from_file(filename):
    if not os.path.exists(filename):
        return set()
    with open(filename, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip())

def save_set_to_file(filename, data_set):
    with open(filename, "w", encoding="utf-8") as f:
        for item in data_set:
            f.write(item + "\n")

def translate_text(text):
    try:
        if not text:
            return ""
        return translator.translate(text)
    except Exception as e:
        print(f"Translation error: {e}")
        return text

def shorten_url(url):
    try:
        return shortener.tinyurl.short(url)
    except Exception as e:
        print(f"Shortening error: {e}")
        return url

def clean_html(raw_html):
    """حذف تگ‌های HTML از متن"""
    cleanr = re.compile('<.*?>')
    cleantext = re.sub(cleanr, '', raw_html)
    return cleantext.strip()

def normalize_title(title):
    """نرمال‌سازی عنوان برای تشخیص تکراری‌ها"""
    # حذف علائم نگارشی و فاصله‌های اضافی
    title = re.sub(r'[^\w\s]', '', title, flags=re.UNICODE)
    title = re.sub(r'\s+', ' ', title).strip().lower()
    # برای دقت بیشتر، فقط ۶۰ کاراکتر اول
    return title[:60]

def is_unwanted(title, translated_title=""):
    """بررسی وجود کلمات نامطلوب در عنوان اصلی و ترجمه‌شده"""
    lower_title = title.lower()
    for word in EN_BLACKLIST:
        if word in lower_title:
            return True
    for word in FA_BLACKLIST:
        if word in title or word in translated_title:
            return True
    return False

def send_telegram_message(text):
    api_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHANNEL_ID,
        "text": text,
        "disable_web_page_preview": False,
    }
    try:
        response = requests.post(api_url, data=payload)
        response.raise_for_status()
        return True
    except Exception as e:
        print(f"Error sending message: {e}")
        return False

def fetch_and_send():
    sent_links = load_set_from_file(SENT_LINKS_FILE)
    sent_titles = load_set_from_file(SENT_TITLES_FILE)
    new_links = set()
    new_titles = set()

    # کلماتی که نشان‌دهنده خطا هستند
    error_keywords = ["error", "500", "server", "not found", "404", "خطا", "مشکل"]

    for source_name, feed_url in RSS_FEEDS:
        print(f"Checking feed: {source_name} - {feed_url}")
        try:
            feed = feedparser.parse(feed_url)
        except Exception as e:
            print(f"Feed parse error for {source_name}: {e}")
            continue

        # اگر فید خطای ساختاری داشته باشد (مثلاً HTML باشد)
        if feed.bozo:
            print(f"Feed {source_name} has bozo error, skipping.")
            continue

        # اگر هیچ خبری در فید نبود
        if not feed.entries:
            print(f"Feed {source_name} returned no entries.")
            continue

        for entry in feed.entries[:5]:
            link = entry.get("link", "")
            title = entry.get("title", "بدون عنوان")
            if not link:
                continue

            # بررسی عنوان برای تشخیص خطا
            if any(keyword in title.lower() for keyword in error_keywords):
                print(f"Skipped (error-like title): {title}")
                continue

            # ترجمه عنوان
            translated_title = translate_text(title)

            # فیلتر اخبار نامطلوب (همان کلمات قبلی)
            if is_unwanted(title, translated_title):
                print(f"Skipped (unwanted): {title}")
                continue

            # تشخیص تکراری
            norm_title = normalize_title(translated_title if translated_title else title)
            if norm_title in sent_titles:
                print(f"Skipped (duplicate): {title}")
                continue

            # گرفتن خلاصه
            summary = entry.get("summary", entry.get("description", ""))
            summary = clean_html(summary)
            if len(summary) > 300:
                summary = summary[:300] + "..."
            translated_summary = translate_text(summary) if summary else ""

            # ساخت پیام
            message = f"📰 [{source_name}] {translated_title}\n"
            if translated_summary:
                message += f"📝 {translated_summary}\n"
            short_link = shorten_url(link)
            message += f"🔗 {short_link}"

            # ارسال
            if send_telegram_message(message):
                print(f"Sent: {translated_title}")
                new_links.add(link)
                new_titles.add(norm_title)
                time.sleep(1)
            else:
                print(f"Failed to send: {title}")

    # ذخیره
    sent_links.update(new_links)
    sent_titles.update(new_titles)
    save_set_to_file(SENT_LINKS_FILE, sent_links)
    save_set_to_file(SENT_TITLES_FILE, sent_titles)
    print("Finished.")

if __name__ == "__main__":
    fetch_and_send()
