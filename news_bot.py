import feedparser
import requests
import os
import time
import re
import difflib
from deep_translator import GoogleTranslator
import pyshorteners
from bs4 import BeautifulSoup

# ---------- Settings ----------
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID")

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")
COHERE_API_KEY = os.environ.get("COHERE_API_KEY")

if not TELEGRAM_TOKEN or not CHANNEL_ID:
    raise ValueError("TELEGRAM_TOKEN and CHANNEL_ID must be set")

# ---------- AI Services ----------
ai_services = []
if OPENAI_API_KEY:
    ai_services.append(("openai", OPENAI_API_KEY))
if DEEPSEEK_API_KEY:
    ai_services.append(("deepseek", DEEPSEEK_API_KEY))
if COHERE_API_KEY:
    ai_services.append(("cohere", COHERE_API_KEY))

if not ai_services:
    print("No AI API keys found, falling back to deep-translator.")

# ---------- Iranian sources (art filter NOT applied) ----------
IRANIAN_SOURCES = [
    "Tasnim", "IRNA", "Fars", "Mehr", "ISNA", "Tabnak", "Eghtesadonline",
    "Hamshahri", "KhabarOnline", "IMNA", "IBNA", "Hoze Honari", "Shada",
    "Parseek Art", "Parseek Sport", "Parseek Economic"
]

# ---------- Feeds ----------
RSS_FEEDS = [
    # Foreign sources
    ("CNN", "http://rss.cnn.com/rss/edition.rss"),
    ("BBC", "http://feeds.bbci.co.uk/news/world/rss.xml"),
    ("Reuters", "http://feeds.reuters.com/Reuters/worldNews"),
    ("Al Jazeera", "https://www.aljazeera.com/xml/rss/all.xml"),
    ("RT", "https://www.rt.com/rss/"),
    ("Al Mayadeen", "https://english.almayadeen.net/feed.rss"),
    ("The Guardian", "https://www.theguardian.com/world/rss"),
    ("Deutsche Welle", "https://rss.dw.com/rdf/rss-en-world"),
    ("France 24", "https://www.france24.com/en/rss"),
    ("New York Times", "https://rss.nytimes.com/services/xml/rss/nyt/World.xml"),
    ("Reuters Video", "https://www.reuters.com/rssFeed/videoNews"),
    ("AP Video", "https://apnews.com/apf-video"),
    ("Euronews Video", "https://www.euronews.com/rss?level=theme&name=news"),

    # Iranian sources
    ("Tasnim", "https://www.tasnimnews.com/fa/rss/feed/0/8/0/%D8%AA%D9%85%D8%A7%D9%85-%D8%A7%D8%AE%D8%A8%D8%A7%D8%B1"),
    ("IRNA", "https://www.irna.ir/rss/"),
    ("Fars", "https://www.farsnews.ir/rss"),
    ("Mehr", "https://www.mehrnews.com/rss"),
    ("ISNA", "https://www.isna.ir/rss"),
    ("Tabnak", "https://www.tabnak.ir/fa/rss/allnews"),
    ("Eghtesadonline", "https://www.eghtesadonline.com/fa/rss/allnews"),
    ("Hamshahri", "https://www.hamshahrionline.ir/rss"),
    ("KhabarOnline", "https://www.khabaronline.ir/rss"),
    ("IMNA", "https://www.imna.ir/rss"),
    ("IBNA", "https://www.ibna.ir/rss"),
    ("Hoze Honari", "https://news.hozehonari.ir/rss"),
    ("Shada", "http://shada.ir/rss"),
    ("Parseek Art", "http://www.parseek.com/rss/?type=ART"),
    ("Parseek Sport", "http://www.parseek.com/rss/?type=SPORT"),
    ("Parseek Economic", "http://www.parseek.com/rss/?type=ECONOMIC"),
]

SENT_LINKS_FILE = "sent_links.txt"
SENT_TITLES_FILE = "sent_titles.txt"
SENT_SUMMARIES_FILE = "sent_summaries.txt"

URGENT_KEYWORDS = [
    "جنگ", "حمله", "انفجار", "زلزله", "سیل", "آتش", "تحریم", "موشک",
    "هسته‌ای", "قتل", "ترور", "کودتا", "جنگنده", "اورژانس", "فوری",
    "سکه", "ارز", "بانک مرکزی",
    "تعطیلی مدارس", "تعطیلی ادارات", "کالابرگ", "یارانه", "سهام عدالت",
    "وام", "کمک معیشتی", "بسته معیشتی",
    "قهرمانی", "فینال", "دربی", "الکلاسیکو"
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
    "بسته معیشتی", "تعطیلی ادارات",
    "ورزش", "فوتبال", "لیگ", "جام", "مسی", "رونالدو", "پرسپولیس", "استقلال",
    "بایرن", "رئال", "بارسلونا", "منچستر", "لیورپول", "چلسی", "آرسنال",
    "یوونتوس", "میلان", "پاریس", "دورتموند", "مربی", "گل", "بازی", "برد",
    "باخت", "تساوی", "قهرمانی", "المپیک", "ملی", "تیم ملی",
    # Art and cinema keywords
    "فیلم", "سریال", "بازیگر", "کارگردان", "سینما", "جشنواره", "اسکار",
    "تئاتر", "نمایش", "هنرمند", "بازیگران", "موسیقی", "کنسرت", "نمایش خانگی",
    # Satire and critique keywords
    "طنز", "نقد", "کلیپ", "ویدیو", "ویدئو", "پربازدید", "کمدی",
    "شصت‌چی", "مدیری", "سکانس", "فیلم جدید", "نمایش خانگی"
]

EN_BLACKLIST = [
    "celebrity", "singer", "gossip", "rumor", "music", "tv", "reality show"
]
FA_BLACKLIST = [
    "خواننده", "سلبریتی", "شایعه", "کنسرت", "آلبوم"
]

LOCAL_BLACKLIST = [
    "استاندار", "فرماندار", "فرمانداری", "شهردار", "شورای شهر", "بخشدار",
    "استان", "شهرستان", "روستا", "پروژه‌های عمرانی", "عمرانی", "زیرگذر",
    "پل", "جاده", "کلنگ‌زنی", "بهره‌برداری", "افتتاح", "بسیج سازندگی",
    "دادستان", "پلیس", "شهر", "بخش", "دهیاری", "آبفا", "تعهدات جهادی"
]

# ---------- Sports keywords ----------
BIG_SPORTS_WORDS = [
    "رونالدو", "مسی", "دربی", "الکلاسیکو", "قهرمانی", "فینال",
    "المپیک", "جام جهانی", "لیگ قهرمانان", "پرسپولیس", "استقلال",
    "دوناروما", "مرگ", "دستگیری", "شکست سنگین", "پیروزی بزرگ",
    "رکورد", "مصدومیت شدید", "بازنشستگی", "خداحافظی"
]

IMPORTANCE_THRESHOLD = 6

# ---------- Limits per run ----------
MAX_POSTS_PER_RUN = 10
POST_DELAY_SECONDS = 10

SOURCE_HASHTAGS = {
    "CNN": "#سی_ان_ان",
    "BBC": "#بی_بی_سی",
    "Reuters": "#رویترز",
    "Al Jazeera": "#الجزیره",
    "RT": "#راشا_تودی",
    "Al Mayadeen": "#المیادین",
    "Tasnim": "#تسنیم",
    "IRNA": "#ایرنا",
    "The Guardian": "#گاردین",
    "Deutsche Welle": "#دویچه_وله",
    "France 24": "#فرانس_۲۴",
    "New York Times": "#نیویورک_تایمز",
    "Fars": "#فارس",
    "Mehr": "#مهر",
    "ISNA": "#ایسنا",
    "Tabnak": "#تابناک",
    "Eghtesadonline": "#اقتصادآنلاین",
    "Reuters Video": "#رویترز_ویدیو",
    "AP Video": "#آسوشیتدپرس_ویدیو",
    "Euronews Video": "#یورونیوز",
    "Hamshahri": "#همشهری",
    "KhabarOnline": "#خبرآنلاین",
    "IMNA": "#ایمنا",
    "IBNA": "#ایبنا",
    "Hoze Honari": "#حوزه_هنری",
    "Shada": "#شادا",
    "Parseek Art": "#پارسیک_هنر",
    "Parseek Sport": "#پارسیک_ورزش",
    "Parseek Economic": "#پارسیک_اقتصاد",
}

CHANNEL_LINK = f"https://t.me/{CHANNEL_ID.lstrip('@')}"
SLOGAN = "🔔 نبض دنیا؛ اخبار فوری، مستند و قابل اعتماد از خبرگزاری‌های معتبر"

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


def clean_html(raw_html):
    cleanr = re.compile('<.*?>')
    cleantext = re.sub(cleanr, '', raw_html)
    return cleantext.strip()


def normalize_title(title):
    title = re.sub(r'[^\w\s]', '', title, flags=re.UNICODE)
    title = re.sub(r'\s+', ' ', title).strip().lower()
    return title[:80]


def is_error_text(text):
    if not text:
        return True
    error_patterns = [
        "error 500", "error 404", "error 403", "error 502", "error 503",
        "server error", "internal server error", "that's an error",
        "that’s an error", "please try again later", "that's all we know",
        "that’s all we know", "service unavailable", "bad gateway",
        "no translation", "translation error"
    ]
    lower = text.lower()
    for pattern in error_patterns:
        if pattern in lower:
            return True
    if len(text.strip()) < 15 and ("error" in lower or "خطا" in lower):
        return True
    return False


def is_short_summary(summary):
    if not summary:
        return True
    words = summary.split()
    if len(words) < 15:
        return True
    if len(words) <= 4 and len(summary) < 40:
        return True
    return False


def is_unwanted(title, translated_title="", translated_summary=""):
    lower_title = title.lower()
    for word in EN_BLACKLIST:
        if word in lower_title:
            return True
    for word in FA_BLACKLIST:
        if word in title or word in translated_title or word in translated_summary:
            return True
    return False


def is_local_news(title, translated_title="", translated_summary=""):
    combined = (title + " " + translated_title + " " + translated_summary).lower()
    for word in LOCAL_BLACKLIST:
        if word in combined:
            return True
    return False


def calculate_importance(title, translated_title, summary="", category="other"):
    """محاسبه امتیاز اهمیت با تفکیک ورزشی مهم از بی‌ارزش"""
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

    # برای ورزشی‌ها: اگر خبر بزرگ نیست، جریمه‌ی سنگین
    if category == "sports":
        is_big_sports = any(w in title_text or w in summary_text for w in BIG_SPORTS_WORDS)
        if not is_big_sports:
            score -= 6

    return score


def is_duplicate_smart(new_title, new_summary, existing_titles, existing_summaries):
    """تشخیص تکراری با ترکیب عنوان و خلاصه"""
    new_norm = normalize_title(new_title)

    # 1) چک شباهت عنوان با عناوین قبلی
    for old_title in existing_titles:
        title_sim = difflib.SequenceMatcher(None, new_norm, old_title).ratio()
        if title_sim >= 0.70:
            return True

        # چک کلمات کلیدی مشترک
        new_words = set(new_norm.split())
        old_words = set(old_title.split())
        common = new_words & old_words
        if len(common) >= 3 and len(common) / max(len(new_words), 1) >= 0.5:
            return True

    # 2) چک شباهت خلاصه
    if new_summary:
        new_summary_norm = normalize_title(new_summary)[:100]
        for old_summary in existing_summaries:
            if not old_summary:
                continue
            summary_sim = difflib.SequenceMatcher(None, new_summary_norm, old_summary).ratio()
            if summary_sim >= 0.75:
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
        "art": ["فیلم", "سریال", "بازیگر", "سینما", "کارگردان", "جشنواره", "تئاتر", "هنرمند"],
        "satiere": ["طنز", "نقد", "کلیپ", "ویدیو", "ویدئو", "پربازدید", "کمدی", "شصت‌چی", "مدیری", "سکانس", "نمایش خانگی"],
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
    "art": "🎬",
    "satiere": "🎭",
    "other": "📰",
}


def extract_image_url(entry):
    if 'media_content' in entry:
        for media in entry.media_content:
            url = media.get('url', '')
            if url:
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
    ]
    for pattern in img_patterns:
        match = re.search(pattern, summary)
        if match:
            return match.group(1)
    return None


def extract_video_url(entry):
    if 'media_content' in entry:
        for media in entry.media_content:
            url = media.get('url', '')
            if not url:
                continue
            medium = media.get('medium', '').lower()
            type_attr = media.get('type', '').lower()
            if medium == 'video' or type_attr.startswith('video'):
                return url
            if re.search(r'\.(mp4|webm|m3u8|mov)(\?|$)', url, re.IGNORECASE):
                return url
    if 'enclosures' in entry:
        for enc in entry.enclosures:
            url = enc.get('url', '')
            type_attr = enc.get('type', '').lower()
            if url and ('video' in type_attr or 'mpeg' in type_attr):
                return url
            if re.search(r'\.(mp4|webm|m3u8|mov)(\?|$)', url, re.IGNORECASE):
                return url
    summary = entry.get('summary', entry.get('description', ''))
    patterns = [
        r'<video[^>]+src=["\'](.*?)["\']',
        r'<source[^>]+src=["\'](.*?)["\']',
        r'https?://[^\s"\']+\.(?:mp4|m3u8|webm|mov)(?:\?[^\s"\']*)?',
    ]
    for pattern in patterns:
        match = re.search(pattern, summary, re.IGNORECASE)
        if match:
            return match.group(1) if match.groups() else match.group(0)
    if 'media_group' in entry:
        for group in entry.media_group:
            if 'media_content' in group:
                for media in group.media_content:
                    url = media.get('url', '')
                    if url and (media.get('medium') == 'video' or re.search(r'\.(mp4|m3u8)', url, re.IGNORECASE)):
                        return url
    return None


def fetch_video_from_page(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        resp = requests.get(url, timeout=8, headers=headers)
        if resp.status_code != 200:
            return None
        soup = BeautifulSoup(resp.content, 'html.parser')
        for video in soup.find_all('video'):
            src = video.get('src')
            if src and src.startswith('http'):
                return src
            for source in video.find_all('source'):
                src = source.get('src')
                if src and src.startswith('http'):
                    return src
        for meta in soup.find_all('meta'):
            prop = meta.get('property', '') or meta.get('name', '')
            if prop in ('og:video', 'og:video:url', 'og:video:secure_url', 'twitter:player:stream'):
                content = meta.get('content', '')
                if content and re.search(r'\.(mp4|m3u8|webm)', content, re.IGNORECASE):
                    return content
        mp4_match = re.search(r'https?://[^\s"\'<>]+\.mp4(?:\?[^\s"\'<>]*)?', resp.text)
        if mp4_match:
            return mp4_match.group(0)
        return None
    except Exception as e:
        print(f"fetch_video_from_page error: {e}")
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
        response = requests.post(api_url, json=payload, timeout=15)
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
        response = requests.post(api_url, json=payload, timeout=20)
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
        "supports_streaming": True,
    }
    try:
        response = requests.post(api_url, json=payload, timeout=30)
        response.raise_for_status()
        return True
    except Exception as e:
        print(f"Error sending video: {e}")
        return False


def ai_translate_and_summarize(title, content, service_name, api_key):
    prompt = (
        "You are an expert news summarizer. Given a news title and content, "
        "translate the title to Persian if needed, and write a detailed summary in Persian "
        "(4 to 5 sentences) that includes all numbers, prices, dates, and names. "
        "Do not use vague phrases. If a detail is missing, add: 'جزئیات بیشتر اعلام نشده است'.\n\n"
        "Output format:\nTITLE: <translated title>\nSUMMARY: <summary>\n\n"
        f"Title: {title}\nContent: {content[:2500]}\n"
    )
    try:
        if service_name == "openai":
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            payload = {
                "model": "gpt-3.5-turbo",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
            }
            resp = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload, timeout=20)
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
            resp = requests.post("https://api.deepseek.com/v1/chat/completions", headers=headers, json=payload, timeout=20)
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
            }
            resp = requests.post("https://api.cohere.ai/v1/chat", headers=headers, json=payload, timeout=20)
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
        if not translated_title or is_error_text(translated_title):
            translated_title = title
        if is_error_text(summary):
            summary = ""
        return translated_title, summary
    except Exception as e:
        print(f"{service_name} error: {e}")
        return None


def fallback_translate_and_summarize(title, content):
    try:
        translated_title = ""
        if title:
            try:
                t = translator.translate(title)
                if t and not is_error_text(t):
                    translated_title = t
                else:
                    translated_title = title
            except Exception:
                translated_title = title

        summary_clean = clean_html(content)
        if len(summary_clean) > 1000:
            summary_clean = summary_clean[:1000] + "..."

        translated_summary = ""
        if summary_clean:
            try:
                t = translator.translate(summary_clean)
                if t and not is_error_text(t):
                    translated_summary = t
                else:
                    translated_summary = ""
            except Exception:
                translated_summary = ""

        return translated_title, translated_summary
    except Exception as e:
        print(f"Fallback error: {e}")
        return title, ""


def process_with_ai(title, content):
    for service_name, key in ai_services:
        result = ai_translate_and_summarize(title, content, service_name, key)
        if result:
            t_title, t_summary = result
            if is_error_text(t_summary):
                t_summary = ""
            if not t_title or is_error_text(t_title):
                t_title = title
            return t_title, t_summary
    return fallback_translate_and_summarize(title, content)


def send_news_item(item):
    title = item.get("title", "")
    summary = item.get("summary", "")
    link = item.get("link", "")
    source = item.get("source", "")
    category = item.get("category", "other")
    image_url = item.get("image_url", None)
    video_url = item.get("video_url", None)

    if summary and is_error_text(summary):
        summary = ""

    category_emoji = CATEGORY_EMOJIS.get(category, "📰")
    source_hashtag = SOURCE_HASHTAGS.get(source, f"#{source.replace(' ', '_')}")

    title_escaped = escape_html(title)
    summary_escaped = escape_html(summary) if summary else ""

    caption = f"{category_emoji} <b>{title_escaped}</b>\n\n"
    if summary_escaped:
        caption += f"📝 {summary_escaped}\n\n"
    caption += f"{source_hashtag}  #نبض_دنیا\n"
    caption += f"📎 <a href='{link}'>منبع خبر را اینجا ببینید</a>\n"
    caption += f"🔗 {CHANNEL_LINK}\n\n"
    caption += SLOGAN

    if video_url:
        print(f"Trying to send video: {video_url}")
        success = send_telegram_video(video_url, caption)
        if success:
            return True
        if image_url:
            success = send_telegram_photo(image_url, caption)
            if success:
                return True
        return send_telegram_message(caption)

    if image_url:
        success = send_telegram_photo(image_url, caption)
        if success:
            return True
        return send_telegram_message(caption)

    return send_telegram_message(caption)


def fetch_and_send():
    sent_links = load_set_from_file(SENT_LINKS_FILE)
    sent_titles = load_list_from_file(SENT_TITLES_FILE)
    sent_summaries = load_list_from_file(SENT_SUMMARIES_FILE)

    error_keywords = ["error", "500", "server", "not found", "404"]

    total_sent_this_run = 0

    for source_name, feed_url in RSS_FEEDS:
        if total_sent_this_run >= MAX_POSTS_PER_RUN:
            print(f"Reached max posts per run ({MAX_POSTS_PER_RUN}). Stopping.")
            break

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
            if count_from_source >= 3:
                break
            if total_sent_this_run >= MAX_POSTS_PER_RUN:
                break

            try:
                link = entry.get("link", "")
                title = entry.get("title", "")
                if not link or not title:
                    continue

                if any(keyword in title.lower() for keyword in error_keywords):
                    print(f"Skipped error-like title: {title}")
                    continue

                translated_title, translated_summary = process_with_ai(
                    title,
                    entry.get("summary", entry.get("description", ""))
                )
                if not translated_title:
                    translated_title = title

                if is_error_text(translated_summary):
                    print(f"Skipped error summary: {title}")
                    continue

                # فیلتر خلاصه‌ی کوتاه یا فقط نام منبع
                if is_short_summary(translated_summary):
                    print(f"Skipped short summary: {title}")
                    continue

                if source_name not in IRANIAN_SOURCES:
                    if is_unwanted(title, translated_title, translated_summary):
                        print(f"Skipped unwanted: {title}")
                        continue

                if is_local_news(title, translated_title, translated_summary):
                    print(f"Skipped local: {title}")
                    continue

                # تعیین دسته‌بندی قبل از محاسبه‌ی اهمیت
                category = classify_news(title, translated_summary)

                importance_score = calculate_importance(
                    title, translated_title, translated_summary, category=category
                )
                if importance_score < IMPORTANCE_THRESHOLD:
                    print(f"Skipped low importance ({importance_score}): {title}")
                    continue

                norm_title = normalize_title(translated_title if translated_title else title)

                # تشخیص تکراری هوشمند
                if is_duplicate_smart(norm_title, translated_summary, sent_titles, sent_summaries):
                    print(f"Skipped duplicate (smart): {title}")
                    continue

                video_url = extract_video_url(entry)
                image_url = extract_image_url(entry)

                if not video_url:
                    video_url = fetch_video_from_page(link)
                    if video_url:
                        print(f"Found video on page: {video_url}")

                news_item = {
                    "title": translated_title,
                    "summary": translated_summary,
                    "link": link,
                    "source": source_name,
                    "category": category,
                    "image_url": image_url,
                    "video_url": video_url,
                }

                success = send_news_item(news_item)
                if success:
                    print(f"Sent: {translated_title}")
                    sent_links.add(link)
                    sent_titles.append(norm_title)
                    sent_summaries.append(normalize_title(translated_summary)[:100])
                    count_from_source += 1
                    total_sent_this_run += 1
                    if total_sent_this_run < MAX_POSTS_PER_RUN:
                        print(f"Waiting {POST_DELAY_SECONDS} seconds before next post...")
                        time.sleep(POST_DELAY_SECONDS)
                else:
                    print(f"Failed to send: {title}")
            except Exception as e:
                print(f"Error processing entry: {e}")
                continue

    save_set_to_file(SENT_LINKS_FILE, sent_links)
    save_list_to_file(SENT_TITLES_FILE, sent_titles)
    save_list_to_file(SENT_SUMMARIES_FILE, sent_summaries)
    print(f"Finished. Total sent this run: {total_sent_this_run}")


if __name__ == "__main__":
    fetch_and_send()
