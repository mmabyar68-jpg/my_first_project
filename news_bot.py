import feedparser
import requests
import os
import time
import re
import difflib
from deep_translator import GoogleTranslator
import pyshorteners

# ---------- تنظیمات ----------
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID")

if not TELEGRAM_TOKEN or not CHANNEL_ID:
    raise ValueError("TELEGRAM_TOKEN and CHANNEL_ID must be set as environment variables")

# لیست فیدها (نام منبع، آدرس)
RSS_FEEDS = [
    ("CNN", "http://rss.cnn.com/rss/edition.rss"),
    ("BBC", "http://feeds.bbci.co.uk/news/world/rss.xml"),
    ("Reuters", "http://feeds.reuters.com/Reuters/worldNews"),
    ("Al Jazeera", "https://www.aljazeera.com/xml/rss/all.xml"),
    ("RT", "https://www.rt.com/rss/"),
    ("Tasnim", "https://www.tasnimnews.com/fa/rss/feed/0/8/0/%D8%AA%D9%85%D8%A7%D9%85-%D8%A7%D8%AE%D8%A8%D8%A7%D8%B1"),
    ("IRNA", "https://www.irna.ir/rss/"),
]

SENT_LINKS_FILE = "sent_links.txt"
SENT_TITLES_FILE = "sent_titles.txt"

# کلمات مهم برای فیلتر اخبار
IMPORTANT_KEYWORDS = [
    "جنگ", "حمله", "انفجار", "زلزله", "سیل", "آتش", "تحریم", "اقتصاد",
    "تورم", "نفت", "قیمت", "دلار", "طلا", "بورس", "انتخابات", "رئیس‌جمهور",
    "دولت", "مجلس", "قانون", "بحران", "کرونا", "ویروس", "واکسن", "صلح",
    "مذاکره", "توافق", "جنگنده", "موشک", "هسته‌ای", "آمریکا", "ایران",
    "چین", "روسیه", "اوکراین", "فلسطین", "اسرائیل", "عراق", "افغانستان",
    "پاکستان", "هند", "ترکیه", "اروپا", "انگلیس", "فرانسه", "آلمان",
    "پناهنده", "مهاجرت", "بهداشت", "آموزش", "فناوری", "هوش مصنوعی",
    "اینترنت", "فضا", "محیط زیست", "آب و هوا", "تغییر اقلیم",
    "جرم", "جنایت", "قتل", "دادگاه", "پلیس", "ارتش",
]

# کلمات نامطلوب (کم‌اهمیت)
EN_BLACKLIST = [
    "celebrity", "singer", "actor", "actress", "movie", "film", "sport",
    "entertainment", "gossip", "rumor", "music", "tv", "reality show"
]
FA_BLACKLIST = [
    "خواننده", "سلبریتی", "بازیگر", "سینما", "فیلم", "ورزش", "موسیقی",
    "تلویزیون", "شایعه", "هنرمند", "کنسرت", "آلبوم", "سریال"
]

# نگاشت نام منبع به هشتگ فارسی
SOURCE_HASHTAGS = {
    "CNN": "#سی_ان_ان",
    "BBC": "#بی_بی_سی",
    "Reuters": "#رویترز",
    "Google News": "#گوگل_نیوز",
    "Al Jazeera": "#الجزیره",
    "RT": "#راشا_تودی",
    "Tasnim": "#تسنیم",
    "IRNA": "#ایرنا",
}

# لینک کانال (جایگزین لینک خبر)
CHANNEL_LINK = f"https://t.me/{CHANNEL_ID.lstrip('@')}"

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

def load_list_from_file(filename):
    if not os.path.exists(filename):
        return []
    with open(filename, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]

def save_list_to_file(filename, data_list):
    with open(filename, "w", encoding="utf-8") as f:
        for item in data_list:
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
    cleanr = re.compile('<.*?>')
    cleantext = re.sub(cleanr, '', raw_html)
    return cleantext.strip()

def normalize_title(title):
    title = re.sub(r'[^\w\s]', '', title, flags=re.UNICODE)
    title = re.sub(r'\s+', ' ', title).strip().lower()
    return title[:60]

def is_unwanted(title, translated_title=""):
    lower_title = title.lower()
    for word in EN_BLACKLIST:
        if word in lower_title:
            return True
    for word in FA_BLACKLIST:
        if word in title or word in translated_title:
            return True
    return False

def is_duplicate_title(new_title, existing_titles, threshold=0.85):
    for old_title in existing_titles:
        similarity = difflib.SequenceMatcher(None, new_title, old_title).ratio()
        if similarity >= threshold:
            return True
    return False

def is_important(title, translated_title, summary=""):
    combined_text = (title + " " + translated_title + " " + summary).lower()
    for keyword in IMPORTANT_KEYWORDS:
        if keyword in combined_text:
            return True
    return False

def extract_image_url(entry):
    if 'media_content' in entry:
        for media in entry.media_content:
            if 'url' in media:
                return media['url']
    if 'media_thumbnail' in entry:
        for media in entry.media_thumbnail:
            if 'url' in media:
                return media['url']
    if 'enclosures' in entry:
        for enc in entry.enclosures:
            if 'url' in enc and enc.get('type', '').startswith('image'):
                return enc['url']
    summary = entry.get('summary', entry.get('description', ''))
    img_pattern = r'<img[^>]+src=["\'](.*?)["\']'
    match = re.search(img_pattern, summary)
    if match:
        return match.group(1)
    return None

def escape_html(text):
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def send_telegram_message(text):
    api_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHANNEL_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }
    try:
        response = requests.post(api_url, data=payload)
        response.raise_for_status()
        return True
    except Exception as e:
        print(f"Error sending message: {e}")
        return False

def send_telegram_photo(photo_url, caption):
    api_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
    payload = {
        "chat_id": CHANNEL_ID,
        "photo": photo_url,
        "caption": caption,
        "parse_mode": "HTML",
    }
    try:
        response = requests.post(api_url, data=payload)
        response.raise_for_status()
        return True
    except Exception as e:
        print(f"Error sending photo: {e}")
        return False

def fetch_and_send():
    sent_links = load_set_from_file(SENT_LINKS_FILE)
    sent_titles = load_list_from_file(SENT_TITLES_FILE)
    new_links = set()
    new_titles = []

    error_keywords = ["error", "500", "server", "not found", "404", "خطا", "مشکل"]

    for source_name, feed_url in RSS_FEEDS:
        print(f"Checking feed: {source_name} - {feed_url}")
        try:
            feed = feedparser.parse(feed_url)
        except Exception as e:
            print(f"Feed parse error for {source_name}: {e}")
            continue

        if feed.bozo:
            print(f"Feed {source_name} has bozo error, skipping.")
            continue

        if not feed.entries:
            print(f"Feed {source_name} returned no entries.")
            continue

        count_sent_from_source = 0
        for entry in feed.entries:
            if count_sent_from_source >= 2:
                break

            link = entry.get("link", "")
            title = entry.get("title", "بدون عنوان")
            if not link:
                continue

            if any(keyword in title.lower() for keyword in error_keywords):
                print(f"Skipped (error-like title): {title}")
                continue

            translated_title = translate_text(title)

            if is_unwanted(title, translated_title):
                print(f"Skipped (unwanted): {title}")
                continue

            summary = entry.get("summary", entry.get("description", ""))
            summary = clean_html(summary)
            if len(summary) > 300:
                summary = summary[:300] + "..."
            translated_summary = translate_text(summary) if summary else ""

            if not is_important(title, translated_title, translated_summary):
                print(f"Skipped (not important): {title}")
                continue

            norm_title = normalize_title(translated_title if translated_title else title)

            if is_duplicate_title(norm_title, sent_titles):
                print(f"Skipped (duplicate): {title}")
                continue

            image_url = extract_image_url(entry)

            # هشتگ منبع
            source_hashtag = SOURCE_HASHTAGS.get(source_name, f"#{source_name.replace(' ', '_')}")

            # ساخت کپشن
            title_escaped = escape_html(translated_title)
            summary_escaped = escape_html(translated_summary) if translated_summary else ""

            caption = f"<b>📰 {title_escaped}</b>\n\n"
            if summary_escaped:
                caption += f"📝 {summary_escaped}\n\n"
            caption += f"{source_hashtag}\n"
            caption += f"🔗 {CHANNEL_LINK}"

            # ارسال
            if image_url:
                if send_telegram_photo(image_url, caption):
                    print(f"Sent photo: {translated_title}")
                    new_links.add(link)
                    new_titles.append(norm_title)
                    count_sent_from_source += 1
                    time.sleep(2)
                else:
                    if send_telegram_message(caption):
                        print(f"Sent text (photo failed): {translated_title}")
                        new_links.add(link)
                        new_titles.append(norm_title)
                        count_sent_from_source += 1
                        time.sleep(1)
            else:
                if send_telegram_message(caption):
                    print(f"Sent text: {translated_title}")
                    new_links.add(link)
                    new_titles.append(norm_title)
                    count_sent_from_source += 1
                    time.sleep(1)

    sent_links.update(new_links)
    sent_titles.extend(new_titles)
    save_set_to_file(SENT_LINKS_FILE, sent_links)
    save_list_to_file(SENT_TITLES_FILE, sent_titles)
    print("Finished.")

if __name__ == "__main__":
    fetch_and_send()
