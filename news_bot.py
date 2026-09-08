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

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")
COHERE_API_KEY = os.environ.get("COHERE_API_KEY")

if not TELEGRAM_TOKEN or not CHANNEL_ID:
    raise ValueError("TELEGRAM_TOKEN and CHANNEL_ID must be set as environment variables")

# ---------- سرویس‌های AI ----------
ai_services = []
if OPENAI_API_KEY:
    ai_services.append(("openai", OPENAI_API_KEY))
if DEEPSEEK_API_KEY:
    ai_services.append(("deepseek", DEEPSEEK_API_KEY))
if COHERE_API_KEY:
    ai_services.append(("cohere", COHERE_API_KEY))

if not ai_services:
    print("No AI API keys found, falling back to deep-translator.")

# ---------- فیدها ----------
RSS_FEEDS = [
    # خارجی
    ("CNN", "http://rss.cnn.com/rss/edition.rss"),
    ("BBC", "http://feeds.bbci.co.uk/news/world/rss.xml"),
    ("Reuters", "http://feeds.reuters.com/Reuters/worldNews"),
    ("Al Jazeera", "https://www.aljazeera.com/xml/rss/all.xml"),
    ("RT", "https://www.rt.com/rss/"),
    ("Associated Press", "https://apnews.com/rss"),
    ("The Guardian", "https://www.theguardian.com/world/rss"),
    ("Deutsche Welle", "https://rss.dw.com/rdf/rss-en-world"),
    ("France 24", "https://www.france24.com/en/rss"),
    ("New York Times", "https://rss.nytimes.com/services/xml/rss/nyt/World.xml"),

    # ایرانی
    ("Tasnim", "https://www.tasnimnews.com/fa/rss/feed/0/8/0/%D8%AA%D9%85%D8%A7%D9%85-%D8%A7%D8%AE%D8%A8%D8%A7%D8%B1"),
    ("IRNA", "https://www.irna.ir/rss/"),
    ("Fars", "https://www.farsnews.ir/rss"),
    ("Mehr", "https://www.mehrnews.com/rss"),
    ("ISNA", "https://www.isna.ir/rss"),
    ("Tabnak", "https://www.tabnak.ir/fa/rss/allnews"),
    ("Eghtesadonline", "https://www.eghtesadonline.com/fa/rss/allnews"),
]

SENT_LINKS_FILE = "sent_links.txt"
SENT_TITLES_FILE = "sent_titles.txt"

# ---------- کلمات فوری ----------
URGENT_KEYWORDS = [
    "جنگ", "حمله", "انفجار", "زلزله", "سیل", "آتش", "تحریم", "موشک",
    "هسته‌ای", "قتل", "ترور", "کودتا", "جنگنده", "اورژانس", "فوری",
    "سکه", "ارز", "بانک مرکزی",
    "تعطیلی مدارس", "تعطیلی ادارات", "کالابرگ", "یارانه", "سهام عدالت",
    "وام", "کمک معیشتی", "بسته معیشتی"
]

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
    "سکه", "اوراق", "عرضه اولیه", "بانک مرکزی", "ارز", "ریال", "سهام",
    "بازار سرمایه", "بازار مالی", "سپرده", "وام", "اعتبار", "مالیات",
    "یارانه", "بودجه",
    "تعطیلی مدارس", "کالابرگ", "یارانه", "سهام عدالت", "کمک معیشتی",
    "بسته معیشتی", "تعطیلی ادارات"
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

# کلمات محلی/استانی که باید رد شوند
LOCAL_BLACKLIST = [
    "استاندار", "فرماندار", "فرمانداری", "شهردار", "شورای شهر", "بخشدار",
    "استان", "شهرستان", "روستا", "پروژه‌های عمرانی", "عمرانی", "زیرگذر",
    "پل", "جاده", "کلنگ‌زنی", "بهره‌برداری", "افتتاح", "بسیج سازندگی",
    "دادستان", "پلیس", "شهر", "بخش", "دهیاری", "آبفا", "تعهدات جهادی"
]

# ---------- تنظیمات اهمیت ----------
IMPORTANCE_THRESHOLD = 4  # حداقل امتیاز برای ارسال

# ---------- متغیرهای دیگر ----------
SOURCE_HASHTAGS = {
    "CNN": "#سی_ان_ان",
    "BBC": "#بی_بی_سی",
    "Reuters": "#رویترز",
    "Al Jazeera": "#الجزیره",
    "RT": "#راشا_تودی",
    "Tasnim": "#تسنیم",
    "IRNA": "#ایرنا",
    "Associated Press": "#آسوشیتدپرس",
    "The Guardian": "#گاردین",
    "Deutsche Welle": "#دویچه_وله",
    "France 24": "#فرانس_۲۴",
    "New York Times": "#نیویورک_تایمز",
    "Fars": "#فارس",
    "Mehr": "#مهر",
    "ISNA": "#ایسنا",
    "Tabnak": "#تابناک",
    "Eghtesadonline": "#اقتصادآنلاین",
}

CHANNEL_LINK = f"https://t.me/{CHANNEL_ID.lstrip('@')}"
SLOGAN = "🔔 نبض دنیا؛ اخبار فوری، مستند و قابل اعتماد از خبرگزاری‌های معتبر"

translator = GoogleTranslator(source='auto', target='fa')
shortener = pyshorteners.Shortener()

# ---------- توابع کمکی ----------
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

def clean_html(raw_html):
    cleanr = re.compile('<.*?>')
    cleantext = re.sub(cleanr, '', raw_html)
    return cleantext.strip()

def normalize_title(title):
    title = re.sub(r'[^\w\s]', '', title, flags=re.UNICODE)
    title = re.sub(r'\s+', ' ', title).strip().lower()
    return title[:60]

def is_unwanted(title, translated_title="", translated_summary=""):
    lower_title = title.lower()
    lower_summary = translated_summary.lower()
    for word in EN_BLACKLIST:
        if word in lower_title:
            return True
    for word in FA_BLACKLIST:
        if word in title or word in translated_title or word in translated_summary:
            return True
    return False

def is_local_news(title, translated_title="", translated_summary=""):
    """بررسی وجود کلمات محلی/استانی در عنوان یا خلاصه"""
    combined = (title + " " + translated_title + " " + translated_summary).lower()
    for word in LOCAL_BLACKLIST:
        if word in combined:
            return True
    return False

def calculate_importance(title, translated_title, summary=""):
    """محاسبه امتیاز اهمیت خبر"""
    score = 0
    title_text = (title + " " + translated_title).lower()
    summary_text = summary.lower()
    for keyword in IMPORTANT_KEYWORDS:
        if keyword in title_text:
            score += 3
        elif keyword in summary_text:
            score += 1
    for keyword in URGENT_KEYWORDS:
        if keyword in title_text:
            score += 5
    return score

def is_duplicate_title(new_title, existing_titles, threshold=0.85):
    for old_title in existing_titles:
        similarity = difflib.SequenceMatcher(None, new_title, old_title).ratio()
        if similarity >= threshold:
            return True
    return False

def classify_news(title, summary=""):
    text = (title + " " + summary).lower()
    categories = {
        "conflict": ["جنگ", "حمله", "درگیری", "موشک", "انفجار", "ارتش", "نظامی", "تهاجم"],
        "economy": ["اقتصاد", "تورم", "نفت", "دلار", "بورس", "قیمت", "تجارت", "سهام", "بودجه"],
        "politics": ["انتخابات", "رئیس‌جمهور", "دولت", "مجلس", "سیاست", "قانون", "تحریم", "مذاکره"],
        "sports": ["ورزش", "فوتبال", "بسکتبال", "المپیک", "لیگ", "جام"],
        "technology": ["فناوری", "هوش مصنوعی", "اینترنت", "ربات", "نرم‌افزار", "استارتاپ", "دیجیتال"],
        "health": ["سلامت", "بهداشت", "کرونا", "ویروس", "واکسن", "بیمارستان", "دارو"],
        "environment": ["محیط زیست", "آب و هوا", "اقلیم", "آلودگی", "حیات وحش", "جنگل"],
        "other": []
    }
    for cat, keywords in categories.items():
        for kw in keywords:
            if kw in text:
                return cat
    return "other"

CATEGORY_EMOJIS = {
    "politics": "🏛️",
    "economy": "💰",
    "sports": "🏆",
    "technology": "💻",
    "health": "🏥",
    "environment": "🌍",
    "conflict": "⚔️",
    "other": "📰",
}

def extract_image_url(entry):
    if 'media_content' in entry:
        for media in entry.media_content:
            url = media.get('url', '')
            if url:
                if media.get('medium') == 'image' or media.get('type', '').startswith('image'):
                    return url
                return url
    if 'media_thumbnail' in entry:
        for media in entry.media_thumbnail:
            if 'url' in media:
                return media['url']
    if 'enclosures' in entry:
        for enc in entry.enclosures:
            if enc.get('type', '').startswith('image'):
                return enc.get('url', '')
    summary = entry.get('summary', entry.get('description', ''))
    img_patterns = [
        r'<img[^>]+src=["\'](.*?)["\']',
        r'<img[^>]+data-src=["\'](.*?)["\']',
        r'<img[^>]+data-lazy-src=["\'](.*?)["\']',
        r'<img[^>]+data-original=["\'](.*?)["\']',
        r'<img[^>]+srcset=["\'](.*?)["\']',
    ]
    for pattern in img_patterns:
        match = re.search(pattern, summary)
        if match:
            url = match.group(1)
            if 'srcset' in pattern and url:
                parts = url.split(',')
                if parts:
                    url = parts[0].strip().split(' ')[0]
            if url:
                return url
    return None

def extract_video_url(entry):
    if 'media_content' in entry:
        for media in entry.media_content:
            if 'url' in media and media.get('type', '').startswith('video'):
                return media['url']
            if 'url' in media and 'video' in media.get('medium', ''):
                return media['url']
    if 'enclosures' in entry:
        for enc in entry.enclosures:
            if 'url' in enc and enc.get('type', '').startswith('video'):
                return enc['url']
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
        response = requests.post(api_url, json=payload)
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
        response = requests.post(api_url, json=payload)
        response.raise_for_status()
        return True
    except Exception as e:
        print(f"Error sending photo: {e}")
        return False

def send_telegram_video(video_url, caption):
    api_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendVideo"
    payload = {
        "chat_id": CHANNEL_ID,
        "video": video_url,
        "caption": caption,
        "parse_mode": "HTML",
    }
    try:
        response = requests.post(api_url, json=payload)
        response.raise_for_status()
        return True
    except Exception as e:
        print(f"Error sending video: {e}")
        return False

# ---------- توابع AI ----------
def ai_translate_and_summarize(title, content, service_name, api_key):
    prompt = f"""
You are an expert news summarizer. I give you a news title and its content (may be partial). Your task is to produce a **detailed but concise summary** in Persian (about 4-5 sentences, or 80-120 words) that captures all the important facts. Follow these rules strictly:

1. Translate the title to Persian if needed.
2. In the summary:
   - Include ALL specific numbers, prices, amounts, percentages, dates, names, conditions, and any table data if mentioned.
   - If the title contains key details (e.g., amounts, dates, lists), you MUST include them in the summary.
   - Do not use generic phrases like "جزئیات را بخوانید" or "اطلاعات بیشتر در گزارش". Instead, state the facts directly.
   - If a necessary detail is missing from both title and content, write "جزئیات بیشتر اعلام نشده است" at the end.
   - The summary should be longer than a typical headline: about 4-5 sentences, providing a good overview without being the full article.

3. Output exactly in this format, with no extra commentary:
TITLE: <translated title>
SUMMARY: <summary>

Example of a good detailed summary:
Title: "آغاز شارژ کالابرگ از فردا ۱۵ شهریور ۱۴۰۵ / به حساب این خانوارها ۵.۰۰۰.۰۰۰ تومان واریز می‌شود"
Summary: "شارژ کالابرگ از فردا ۱۵ شهریور ۱۴۰۵ آغاز می‌شود. مبلغ ۵,۰۰۰,۰۰۰ تومان به حساب خانوارهای مشمول واریز خواهد شد. این مبلغ برای خرید کالاهای اساسی قابل استفاده است. جزئیات بیشتر در مورد شرایط و مشمولان اعلام نشده است."

Now process the following:
Title: {title}
Content: {content[:3000]}
"""

Return exactly in this format:
TITLE: <translated title>
SUMMARY: <summary>
"""
    try:
        if service_name == "openai":
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            payload = {
                "model": "gpt-3.5-turbo",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
            }
            resp = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload, timeout=15)
            if resp.status_code != 200:
                raise Exception(f"OpenAI API error: {resp.status_code}")
            text = resp.json()["choices"][0]["message"]["content"]

        elif service_name == "deepseek":
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            payload = {
                "model": "deepseek-chat",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
            }
            resp = requests.post("https://api.deepseek.com/v1/chat/completions", headers=headers, json=payload, timeout=15)
            if resp.status_code != 200:
                raise Exception(f"DeepSeek API error: {resp.status_code}")
            text = resp.json()["choices"][0]["message"]["content"]

        elif service_name == "cohere":
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
            payload = {
                "model": "command-r",
                "message": prompt,
                "temperature": 0.3,
                "preamble": "You are a helpful news assistant that translates and summarizes news.",
            }
            resp = requests.post("https://api.cohere.ai/v1/chat", headers=headers, json=payload, timeout=15)
            if resp.status_code != 200:
                raise Exception(f"Cohere API error: {resp.status_code}")
            text = resp.json()["text"]
        else:
            return None

        translated_title = ""
        summary = ""
        for line in text.split('\n'):
            line = line.strip()
            if line.startswith("TITLE:"):
                translated_title = line.replace("TITLE:", "").strip()
            elif line.startswith("SUMMARY:"):
                summary = line.replace("SUMMARY:", "").strip()
        if not translated_title:
            translated_title = title
        return translated_title, summary
    except Exception as e:
        print(f"{service_name} error: {e}")
        return None

def fallback_translate_and_summarize(title, content):
    try:
        translated_title = translator.translate(title) if title else ""
        summary_clean = clean_html(content)
        if len(summary_clean) > 600:
            summary_clean = summary_clean[:600] + "..."
        translated_summary = translator.translate(summary_clean) if summary_clean else ""
        return translated_title, translated_summary
    except Exception as e:
        print(f"Fallback error: {e}")
        return title, content[:200]

def process_with_ai(title, content):
    for service_name, key in ai_services:
        result = ai_translate_and_summarize(title, content, service_name, key)
        if result:
            return result
    return fallback_translate_and_summarize(title, content)

# ---------- ارسال خبر ----------
def send_news_item(item):
    title = item.get("title", "")
    summary = item.get("summary", "")
    link = item.get("link", "")
    source = item.get("source", "")
    category = item.get("category", "other")
    image_url = item.get("image_url", None)
    video_url = item.get("video_url", None)

    category_emoji = CATEGORY_EMOJIS.get(category, "📰")
    source_hashtag = SOURCE_HASHTAGS.get(source, f"#{source.replace(' ', '_')}")

    title_escaped = escape_html(title)
    summary_escaped = escape_html(summary) if summary else ""

    caption = f"{category_emoji} <b>{title_escaped}</b>\n\n"
    if summary_escaped:
        caption += f"📝 {summary_escaped}\n\n"
    caption += f"{source_hashtag}\n"
    caption += f"🔗 {CHANNEL_LINK}\n\n"
    caption += SLOGAN

    if video_url:
        success = send_telegram_video(video_url, caption)
        if not success:
            if image_url:
                success = send_telegram_photo(image_url, caption)
            else:
                success = send_telegram_message(caption)
    elif image_url:
        success = send_telegram_photo(image_url, caption)
        if not success:
            success = send_telegram_message(caption)
    else:
        success = send_telegram_message(caption)

    return success

def fetch_and_send():
    sent_links = load_set_from_file(SENT_LINKS_FILE)
    sent_titles = load_list_from_file(SENT_TITLES_FILE)

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

        count_from_source = 0
        for entry in feed.entries:
            if count_from_source >= 5:  # حداکثر ۵ خبر از هر منبع
                break

            link = entry.get("link", "")
            title = entry.get("title", "بدون عنوان")
            if not link:
                continue

            if any(keyword in title.lower() for keyword in error_keywords):
                print(f"Skipped (error-like title): {title}")
                continue

            translated_title, translated_summary = process_with_ai(title, entry.get("summary", entry.get("description", "")))
            if not translated_title:
                translated_title = title

            if is_unwanted(title, translated_title, translated_summary):
                print(f"Skipped (unwanted): {title}")
                continue

            if is_local_news(title, translated_title, translated_summary):
                print(f"Skipped (local): {title}")
                continue

            importance_score = calculate_importance(title, translated_title, translated_summary)
            if importance_score < IMPORTANCE_THRESHOLD:
                print(f"Skipped (low importance, score {importance_score}): {title}")
                continue

            norm_title = normalize_title(translated_title if translated_title else title)

            if is_duplicate_title(norm_title, sent_titles):
                print(f"Skipped (duplicate): {title}")
                continue

            news_item = {
                "title": translated_title,
                "summary": translated_summary,
                "link": link,
                "source": source_name,
                "category": classify_news(title, translated_summary),
                "image_url": extract_image_url(entry),
                "video_url": extract_video_url(entry),
            }

            success = send_news_item(news_item)
            if success:
                print(f"Sent: {translated_title}")
                sent_links.add(link)
                sent_titles.append(norm_title)
                count_from_source += 1
                time.sleep(1)
            else:
                print(f"Failed to send: {title}")

    save_set_to_file(SENT_LINKS_FILE, sent_links)
    save_list_to_file(SENT_TITLES_FILE, sent_titles)
    print("Finished.")

if __name__ == "__main__":
    fetch_and_send()
