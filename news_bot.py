import feedparser
import requests
import os
import time
import re
import difflib
import html as html_module
from deep_translator import GoogleTranslator
import pyshorteners

# ---------- تنظیمات ----------
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID")

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
COHERE_API_KEY = os.environ.get("COHERE_API_KEY")
MISTRAL_API_KEY = os.environ.get("MISTRAL_API_KEY")

if not TELEGRAM_TOKEN or not CHANNEL_ID:
    raise ValueError("TELEGRAM_TOKEN and CHANNEL_ID must be set")

ai_services = []
if GROQ_API_KEY:
    ai_services.append(("groq", GROQ_API_KEY))
if OPENROUTER_API_KEY:
    ai_services.append(("openrouter", OPENROUTER_API_KEY))
if MISTRAL_API_KEY:
    ai_services.append(("mistral", MISTRAL_API_KEY))
if DEEPSEEK_API_KEY:
    ai_services.append(("deepseek", DEEPSEEK_API_KEY))
if OPENAI_API_KEY:
    ai_services.append(("openai", OPENAI_API_KEY))
if COHERE_API_KEY:
    ai_services.append(("cohere", COHERE_API_KEY))

if not ai_services:
    print("No AI API keys found, will use fallback translators.")

# ---------- منابع ایرانی ----------
IRANIAN_SOURCES = [
    "Tasnim", "IRNA", "Fars", "Mehr", "ISNA", "Tabnak", "Eghtesadonline",
    "Hamshahri", "KhabarOnline", "IMNA"
]

# ---------- منابعی که هر ران حداقل ۱ خبر بدن ----------
REQUIRED_SOURCES = [
    "France 24",
    "Associated Press",
    "CNN",
    "RT",
    "Al Jazeera",
    "Al Mayadeen",
]

# ---------- فیدها ----------
RSS_FEEDS = [
    # خارجی
    ("CNN", "http://rss.cnn.com/rss/edition.rss"),
    ("BBC", "http://feeds.bbci.co.uk/news/world/rss.xml"),
    ("Reuters", "http://feeds.reuters.com/Reuters/worldNews"),
    ("Al Jazeera", "https://www.aljazeera.com/xml/rss/all.xml"),
    ("RT", "https://www.rt.com/rss/"),
    ("Al Mayadeen", "https://english.almayadeen.net/feed.rss"),
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
    ("Hamshahri", "https://www.hamshahrionline.ir/rss"),
    ("KhabarOnline", "https://www.khabaronline.ir/rss"),
    ("IMNA", "https://www.imna.ir/rss"),
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

URGENT_KEYWORDS_EN = [
    "war", "attack", "explosion", "earthquake", "flood", "fire",
    "emergency", "breaking", "urgent", "killed", "dead", "died",
    "missile", "strike", "invasion", "bombing", "assassination"
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

IMPORTANT_KEYWORDS_EN = [
    "war", "attack", "explosion", "earthquake", "flood", "fire",
    "sanction", "missile", "nuclear", "kill", "assassination", "terror",
    "economy", "inflation", "oil", "price", "dollar", "gold", "stock",
    "election", "president", "government", "parliament", "law", "minister",
    "crisis", "virus", "vaccine", "peace", "negotiation", "deal", "agreement",
    "america", "iran", "china", "russia", "ukraine", "israel", "trump",
    "palestine", "iraq", "afghanistan", "europe", "germany", "france",
    "britain", "japan", "india", "turkey", "egypt", "saudi", "nato", "un",
    "brics", "gaza", "lebanon", "syria", "yemen", "hormuz", "putin",
    "netanyahu", "zelensky", "khamenei"
]

# ---------- کلمات کلیدی خاورمیانه و ایران (امتیاز بالا) ----------
MIDDLE_EAST_KEYWORDS = [
    # فارسی
    "ایران", "تهران", "جمهوری اسلامی", "خامنه‌ای", "پزشکیان", "عراقچی",
    "فلسطین", "غزه", "اسرائیل", "نتانیاهو", "لبنان", "حزب‌الله", "سوریه",
    "یمن", "انصارالله", "حوثی", "عربستان", "امارات", "قطر", "عمان",
    "بحرین", "کویت", "اردن", "مصر", "ترکیه", "اردوغان", "روسیه", "پوتین",
    "اوکراین", "زلنسکی", "مسکو", "کرملین", "تنگه هرمز", "خلیج فارس",
    "دریای سرخ", "باب‌المندب", "بریکس", "مقاومت", "سپاه", "قدس",
    # انگلیسی
    "iran", "tehran", "khamenei", "pezeshkian", "araghchi", "islamic republic",
    "palestine", "gaza", "israel", "netanyahu", "lebanon", "hezbollah",
    "syria", "yemen", "houthi", "saudi", "emirates", "qatar", "oman",
    "bahrain", "kuwait", "jordan", "egypt", "turkey", "erdogan",
    "russia", "putin", "ukraine", "zelensky", "moscow", "kremlin",
    "hormuz", "persian gulf", "red sea", "bab el-mandeb", "brics",
    "resistance", "irgc", "jerusalem", "middle east", "west asia"
]

# ---------- کلمات نامطلوب ----------
EN_BLACKLIST = [
    "celebrity", "singer", "actor", "actress", "movie", "film", "sport",
    "entertainment", "gossip", "rumor", "music", "tv", "reality show",
    "sex", "sexy", "porn", "nude", "erotic"
]
FA_BLACKLIST = [
    "خواننده", "سلبریتی", "بازیگر", "سینما", "فیلم", "ورزش", "موسیقی",
    "تلویزیون", "شایعه", "هنرمند", "کنسرت", "آلبوم", "سریال",
    "سکسی", "پورن", "برهنه", "فحش", "مستهجن"
]

LOCAL_BLACKLIST = [
    "استاندار", "فرماندار", "فرمانداری", "شهردار", "شورای شهر", "بخشدار",
    "استان", "شهرستان", "روستا", "پروژه‌های عمرانی", "عمرانی", "زیرگذر",
    "پل", "جاده", "کلنگ‌زنی", "بهره‌برداری", "افتتاح", "بسیج سازندگی",
    "دادستان", "پلیس", "شهر", "بخش", "دهیاری", "آبفا", "تعهدات جهادی"
]

IMPORTANCE_THRESHOLD = 6

CATEGORY_LIMITS = {
    "sports": 1, "art": 1, "satiere": 2, "economy": 4,
    "politics": 4, "conflict": 5, "technology": 2,
    "health": 1, "environment": 1, "other": 2,
}

SOURCE_TYPE_LIMITS = {
    "iranian": 3,
    "foreign": 5,
}

MAX_POSTS_PER_RUN = 10
POST_DELAY_SECONDS = 10

# ---------- هشتگ‌ها با نام کامل ----------
SOURCE_HASHTAGS = {
    "CNN": "#خبرگزاری_سی_ان_ان",
    "BBC": "#خبرگزاری_بی_بی_سی",
    "Reuters": "#خبرگزاری_رویترز",
    "Al Jazeera": "#خبرگزاری_الجزیره",
    "RT": "#خبرگزاری_راشا_تودی",
    "Al Mayadeen": "#خبرگزاری_المیادین",
    "Associated Press": "#خبرگزاری_آسوشیتدپرس",
    "The Guardian": "#خبرگزاری_گاردین",
    "Deutsche Welle": "#خبرگزاری_دویچه_وله",
    "France 24": "#خبرگزاری_فرانس_۲۴",
    "New York Times": "#خبرگزاری_نیویورک_تایمز",
    "Tasnim": "#خبرگزاری_تسنیم",
    "IRNA": "#خبرگزاری_ایرنا",
    "Fars": "#خبرگزاری_فارس",
    "Mehr": "#خبرگزاری_مهر",
    "ISNA": "#خبرگزاری_ایسنا",
    "Tabnak": "#تابناک",
    "Eghtesadonline": "#اقتصادآنلاین",
    "Hamshahri": "#همشهری",
    "KhabarOnline": "#خبرآنلاین",
    "IMNA": "#ایمنا",
}

CHANNEL_LINK = f"https://t.me/{CHANNEL_ID.lstrip('@')}"
SLOGAN = "🔔 با دوز خبر، اخبار برجسته و مهم خبرگزاری‌های فرانس ۲۴، راشا تودی، سی‌ان‌ان، الجزیره و دیگر منابع معتبر جهانی را دنبال کنید."

translator = GoogleTranslator(source='auto', target='fa')
shortener = pyshorteners.Shortener()

ai_failure_count = 0
AI_FAILURE_LIMIT = 3


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
    if not raw_html:
        return ""
    cleanr = re.compile('<.*?>')
    cleantext = re.sub(cleanr, '', raw_html)
    cleantext = html_module.unescape(cleantext)
    return cleantext.strip()


def normalize_title(title):
    title = re.sub(r'[^\w\s]', '', title, flags=re.UNICODE)
    title = re.sub(r'\s+', ' ', title).strip().lower()
    return title[:60]


def is_error_text(text):
    if not text:
        return True
    error_patterns = [
        "error 500", "error 404", "error 403", "error 502", "error 503",
        "server error", "internal server error", "that's an error",
        "that’s an error", "please try again later", "that's all we know",
        "that’s all we know", "service unavailable", "bad gateway",
        "no translation", "translation error", "!!1500"
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


def is_mostly_english(text):
    if not text:
        return False
    alpha_chars = [c for c in text if c.isalpha()]
    if not alpha_chars:
        return False
    english = sum(1 for c in alpha_chars if ord(c) < 128)
    return (english / len(alpha_chars)) > 0.5


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


def calculate_importance(title, translated_title, summary="", source=""):
    """محاسبه امتیاز با تأکید بر اخبار ایران، روسیه و خاورمیانه"""
    score = 0
    title_text = (title + " " + translated_title).lower()
    summary_text = summary.lower()

    # کلمات فارسی
    for keyword in IMPORTANT_KEYWORDS:
        if keyword in title_text:
            score += 3
        elif keyword in summary_text:
            score += 1

    for keyword in URGENT_KEYWORDS:
        if keyword in title_text:
            score += 5

    # کلمات انگلیسی (فقط برای منابع خارجی)
    if source not in IRANIAN_SOURCES:
        for keyword in IMPORTANT_KEYWORDS_EN:
            if keyword in title_text:
                score += 3
            elif keyword in summary_text:
                score += 1

        for keyword in URGENT_KEYWORDS_EN:
            if keyword in title_text:
                score += 5

    # امتیاز بالا برای اخبار ایران، روسیه، خاورمیانه
    for keyword in MIDDLE_EAST_KEYWORDS:
        kw = keyword.lower()
        if kw in title_text:
            score += 8
        elif kw in summary_text:
            score += 3

    return score


def is_duplicate_title(new_title, existing_titles, threshold=0.85):
    for old_title in existing_titles:
        similarity = difflib.SequenceMatcher(None, new_title, old_title).ratio()
        if similarity >= threshold:
            return True
    return False


def is_duplicate_keywords(new_title, existing_titles, min_common=3):
    stop_words = {
        "از", "به", "در", "با", "را", "که", "این", "آن", "یک", "دو", "بر",
        "برای", "شده", "کرد", "است", "هست", "بود", "شد", "می", "های", "ها",
        "دیگر", "بار", "طی", "پس", "قبل", "روی", "بین", "هم", "یا", "و",
        "اگر", "نیز", "خود", "همه", "هر", "چند", "بیش", "کم", "چه", "چی",
        "the", "and", "for", "with", "from", "that", "this", "have", "has",
        "was", "were", "are", "is", "will", "would", "could", "should"
    }

    def get_keywords(text):
        words = normalize_title(text).split()
        return set(w for w in words if len(w) > 3 and w not in stop_words)

    new_words = get_keywords(new_title)
    if len(new_words) < 3:
        return False

    for old_title in existing_titles:
        old_words = get_keywords(old_title)
        common = new_words & old_words
        if len(common) >= min_common:
            if len(common) / max(len(new_words), 1) >= 0.5:
                return True
    return False


def classify_news(title, summary=""):
    text = (title + " " + summary).lower()
    categories = {
        "conflict": ["جنگ", "حمله", "درگیری", "موشک", "انفجار", "ارتش", "نظامی", "تهاجم",
                     "war", "attack", "strike", "conflict", "military"],
        "economy": ["اقتصاد", "تورم", "نفت", "دلار", "بورس", "قیمت", "تجارت", "سهام", "بودجه",
                    "economy", "inflation", "oil", "price", "dollar", "stock"],
        "politics": ["انتخابات", "رئیس‌جمهور", "دولت", "مجلس", "سیاست", "قانون", "تحریم", "مذاکره",
                     "election", "president", "government", "parliament", "politics"],
        "sports": ["ورزش", "فوتبال", "بسکتبال", "المپیک", "لیگ", "جام",
                   "sport", "football", "basketball", "olympic"],
        "technology": ["فناوری", "هوش مصنوعی", "اینترنت", "ربات", "نرم‌افزار", "استارتاپ", "دیجیتال",
                       "technology", "ai", "artificial intelligence", "internet"],
        "health": ["سلامت", "بهداشت", "کرونا", "ویروس", "واکسن", "بیمارستان", "دارو",
                   "health", "virus", "vaccine", "hospital"],
        "environment": ["محیط زیست", "آب و هوا", "اقلیم", "آلودگی", "حیات وحش", "جنگل",
                        "environment", "climate", "pollution"],
        "art": ["فیلم", "سریال", "بازیگر", "سینما", "کارگردان", "جشنواره", "تئاتر", "هنرمند",
                "film", "movie", "actor", "cinema"],
        "satiere": ["طنز", "نقد", "کلیپ", "ویدیو", "پربازدید", "کمدی", "شصت‌چی", "مدیری",
                    "video", "clip", "viral"],
        "other": []
    }
    for cat, keywords in categories.items():
        for kw in keywords:
            if kw in text:
                return cat
    return "other"


CATEGORY_EMOJIS = {
    "politics": "🏛️", "economy": "💰", "sports": "🏆",
    "technology": "💻", "health": "🏥", "environment": "🌍",
    "conflict": "⚔️", "art": "🎬", "satiere": "🎭", "other": "📰",
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
    for pattern in [r'<img[^>]+src=["\'](.*?)["\']', r'<img[^>]+data-src=["\'](.*?)["\']']:
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

    summary = entry.get('summary', entry.get('description', ''))
    ap_match = re.search(r'aparat\.com/(?:v|embed/v)/([a-zA-Z0-9]+)', summary)
    if ap_match:
        return f"APARAT:{ap_match.group(1)}"

    yt_match = re.search(r'(?:youtube\.com/embed/|youtu\.be/)([a-zA-Z0-9_-]+)', summary)
    if yt_match:
        return f"YOUTUBE:{yt_match.group(1)}"

    for pattern in [
        r'<video[^>]+src=["\'](.*?)["\']',
        r'<source[^>]+src=["\'](.*?)["\']',
        r'https?://[^\s"\']+\.(?:mp4|m3u8|webm|mov)(?:\?[^\s"\']*)?',
    ]:
        match = re.search(pattern, summary, re.IGNORECASE)
        if match:
            return match.group(1) if match.groups() else match.group(0)

    return None


def get_aparat_mp4(video_hash):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        api_url = f"https://www.aparat.com/etc/api/video/videohash/{video_hash}"
        r = requests.get(api_url, timeout=8, headers=headers)
        if r.status_code == 200:
            video = r.json().get("video", {})
            return video.get("file_url")
        return None
    except Exception:
        return None


def fetch_video_from_page(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, timeout=10, headers=headers)
        if r.status_code != 200:
            return None
        html = r.text

        ap_match = re.search(r'aparat\.com/(?:v|embed/v)/([a-zA-Z0-9]+)', html)
        if ap_match:
            video_hash = ap_match.group(1)
            mp4 = get_aparat_mp4(video_hash)
            return mp4 if mp4 else f"APARAT:{video_hash}"

        yt_match = re.search(r'(?:youtube\.com/embed/|youtu\.be/)([a-zA-Z0-9_-]+)', html)
        if yt_match:
            return f"YOUTUBE:{yt_match.group(1)}"

        mp4_match = re.search(r'https?://[^\s"\'<>]+\.mp4(?:\?[^\s"\'<>]*)?', html)
        if mp4_match:
            return mp4_match.group(0)

        return None
    except Exception:
        return None


def escape_html(text):
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def send_telegram_message(text):
    api_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHANNEL_ID, "text": text, "parse_mode": "HTML", "disable_web_page_preview": False}
    try:
        r = requests.post(api_url, json=payload, timeout=15)
        r.raise_for_status()
        return True
    except Exception as e:
        print(f"Error sending message: {e}")
        return False


def send_telegram_photo(photo_url, caption):
    api_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
    payload = {"chat_id": CHANNEL_ID, "photo": photo_url, "caption": caption, "parse_mode": "HTML"}
    try:
        r = requests.post(api_url, json=payload, timeout=20)
        r.raise_for_status()
        return True
    except Exception as e:
        print(f"Error sending photo: {e}")
        return False


def send_telegram_video(video_url, caption):
    api_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendVideo"
    payload = {"chat_id": CHANNEL_ID, "video": video_url, "caption": caption, "parse_mode": "HTML", "supports_streaming": True}
    try:
        r = requests.post(api_url, json=payload, timeout=30)
        r.raise_for_status()
        return True
    except Exception as e:
        print(f"Error sending video: {e}")
        return False


def send_video_from_link(video_url, caption):
    if video_url.startswith("APARAT:"):
        video_hash = video_url.replace("APARAT:", "")
        mp4 = get_aparat_mp4(video_hash)
        if mp4 and send_telegram_video(mp4, caption):
            return True
        caption += f"\n\n🎬 <a href='https://www.aparat.com/v/{video_hash}'>تماشا در آپارات</a>"
        return send_telegram_message(caption)

    if video_url.startswith("YOUTUBE:"):
        video_id = video_url.replace("YOUTUBE:", "")
        caption += f"\n\n🎬 <a href='https://youtu.be/{video_id}'>تماشا در یوتیوب</a>"
        return send_telegram_message(caption)

    if video_url.startswith("http"):
        if send_telegram_video(video_url, caption):
            return True
        caption += f"\n\n🎬 <a href='{video_url}'>تماشای ویدیو</a>"
        return send_telegram_message(caption)

    return False


def translate_via_mymemory(text, target_lang='fa'):
    if not text or len(text) < 2:
        return text
    try:
        text_short = text[:500]
        url = "https://api.mymemory.translated.net/get"
        params = {"q": text_short, "langpair": f"en|{target_lang}"}
        r = requests.get(url, params=params, timeout=10)
        if r.status_code == 200:
            data = r.json()
            translated = data.get("responseData", {}).get("translatedText", "")
            if translated and not is_error_text(translated):
                return translated
        return text
    except Exception:
        return text


# ---------- توابع AI ----------
def ai_translate_and_summarize(title, content, service_name, api_key):
    prompt = (
        "You are an expert Persian news editor. Translate to Persian and write a 4-5 sentence summary.\n\n"
        "RULES:\n"
        "- Use formal Persian only. No English words. Translate EVERYTHING to Persian.\n"
        "- Include ALL numbers, prices, dates, names.\n"
        "- Answer the question in the title directly.\n"
        "- Never use vague phrases. State facts directly.\n"
        "- If content is too short, write: 'جزئیات بیشتر اعلام نشده است'\n\n"
        "Output format:\nTITLE: <Persian title>\nSUMMARY: <Persian summary>\n\n"
        f"Title: {title}\nContent: {content[:2500]}\n"
    )
    try:
        if service_name == "groq":
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            payload = {
                "model": "llama-3.3-70b-versatile",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": 500,
            }
            r = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload, timeout=10)
            if r.status_code != 200:
                raise Exception(f"Groq error: {r.status_code}")
            text = r.json()["choices"][0]["message"]["content"]
        elif service_name == "openrouter":
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            payload = {
                "model": "meta-llama/llama-3.1-8b-instruct:free",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
            }
            r = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=10)
            if r.status_code != 200:
                raise Exception(f"OpenRouter error: {r.status_code}")
            text = r.json()["choices"][0]["message"]["content"]
        elif service_name == "mistral":
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            payload = {
                "model": "mistral-small-latest",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
            }
            r = requests.post("https://api.mistral.ai/v1/chat/completions", headers=headers, json=payload, timeout=10)
            if r.status_code != 200:
                raise Exception(f"Mistral error: {r.status_code}")
            text = r.json()["choices"][0]["message"]["content"]
        elif service_name == "deepseek":
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            payload = {
                "model": "deepseek-chat",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
            }
            r = requests.post("https://api.deepseek.com/v1/chat/completions", headers=headers, json=payload, timeout=10)
            if r.status_code != 200:
                raise Exception(f"DeepSeek error: {r.status_code}")
            text = r.json()["choices"][0]["message"]["content"]
        elif service_name == "openai":
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            payload = {
                "model": "gpt-3.5-turbo",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
            }
            r = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload, timeout=10)
            if r.status_code != 200:
                raise Exception(f"OpenAI error: {r.status_code}")
            text = r.json()["choices"][0]["message"]["content"]
        elif service_name == "cohere":
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            payload = {"model": "command-r", "message": prompt, "temperature": 0.3}
            r = requests.post("https://api.cohere.ai/v1/chat", headers=headers, json=payload, timeout=10)
            if r.status_code != 200:
                raise Exception(f"Cohere error: {r.status_code}")
            text = r.json()["text"]
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
    translated_title = title
    translated_summary = ""

    if title:
        try:
            t = translator.translate(title)
            if t and not is_error_text(t) and not is_mostly_english(t):
                translated_title = t
        except Exception:
            pass

    if is_mostly_english(translated_title):
        mm = translate_via_mymemory(title, 'fa')
        if mm and not is_mostly_english(mm):
            translated_title = mm

    summary_clean = clean_html(content)
    if summary_clean and len(summary_clean) > 50:
        try:
            t = translator.translate(summary_clean[:1000])
            if t and not is_error_text(t) and not is_mostly_english(t):
                translated_summary = t
        except Exception:
            pass

        if is_mostly_english(translated_summary) or not translated_summary:
            mm = translate_via_mymemory(summary_clean[:500], 'fa')
            if mm and not is_mostly_english(mm):
                translated_summary = mm

    if not translated_summary and summary_clean and len(summary_clean) > 30:
        translated_summary = summary_clean[:300]

    return translated_title, translated_summary


def process_with_ai(title, content):
    global ai_failure_count

    if ai_failure_count >= AI_FAILURE_LIMIT:
        result = fallback_translate_and_summarize(title, content)
        return result[0], result[1], False

    for service_name, key in ai_services:
        result = ai_translate_and_summarize(title, content, service_name, key)
        if result:
            ai_failure_count = 0
            t_title, t_summary = result
            if is_error_text(t_summary):
                t_summary = ""
            if not t_title or is_error_text(t_title):
                t_title = title
            return t_title, t_summary, True
        else:
            ai_failure_count += 1

    result = fallback_translate_and_summarize(title, content)
    return result[0], result[1], False


# ---------- ارسال خبر ----------
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
    caption += f"{source_hashtag}  #دوز_خبر\n"
    caption += f"📎 <a href='{link}'>منبع خبر را اینجا ببینید</a>\n"
    caption += f"🔗 {CHANNEL_LINK}\n\n"
    caption += SLOGAN

    # سلب مسئولیت برای منابع خارجی
    if source not in IRANIAN_SOURCES:
        caption += (
            f"\n\n📎 <b>منبع: {source}</b>\n"
            f"<i>⚠️ این خبر صرفاً از منبع فوق نقل شده است. "
            f"مسئولیت صحت یا سقم محتوای آن بر عهده منبع اصلی است "
            f"و دوز خبر در قبال آن مسئولیتی ندارد.</i>"
        )

    if video_url:
        success = send_video_from_link(video_url, caption)
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


# ---------- پردازش یک entry و ارسال ----------
def process_entry(entry, source_name, sent_links, sent_titles, category_counts,
                  iranian_count, foreign_count, total_sent):
    """پردازش یک entry و ارسال در صورت تأیید. مقادیر جدید رو برمی‌گردونه"""
    link = entry.get("link", "")
    title = entry.get("title", "")
    if not link or not title:
        return sent_links, sent_titles, category_counts, iranian_count, foreign_count, total_sent, False

    error_keywords = ["error", "500", "server", "not found", "404"]

    if link in sent_links:
        return sent_links, sent_titles, category_counts, iranian_count, foreign_count, total_sent, False

    if any(kw in title.lower() for kw in error_keywords):
        return sent_links, sent_titles, category_counts, iranian_count, foreign_count, total_sent, False

    raw_content = entry.get("summary", entry.get("description", ""))
    clean_content = clean_html(raw_content)

    if len(clean_content.split()) < 8:
        return sent_links, sent_titles, category_counts, iranian_count, foreign_count, total_sent, False

    is_iranian_source = source_name in IRANIAN_SOURCES

    if not is_iranian_source:
        if is_unwanted(title, "", ""):
            return sent_links, sent_titles, category_counts, iranian_count, foreign_count, total_sent, False
        if is_local_news(title, "", ""):
            return sent_links, sent_titles, category_counts, iranian_count, foreign_count, total_sent, False
    else:
        lower_title = title.lower()
        if any(w in lower_title for w in EN_BLACKLIST):
            return sent_links, sent_titles, category_counts, iranian_count, foreign_count, total_sent, False

    importance_score = calculate_importance(title, "", clean_content, source=source_name)
    if importance_score < IMPORTANCE_THRESHOLD:
        print(f"Skipped low importance ({importance_score}): {title[:50]}")
        return sent_links, sent_titles, category_counts, iranian_count, foreign_count, total_sent, False

    category = classify_news(title, clean_content)
    if category_counts.get(category, 0) >= CATEGORY_LIMITS.get(category, 3):
        print(f"Skipped category limit ({category}): {title[:50]}")
        return sent_links, sent_titles, category_counts, iranian_count, foreign_count, total_sent, False

    if is_iranian_source and iranian_count >= SOURCE_TYPE_LIMITS["iranian"]:
        return sent_links, sent_titles, category_counts, iranian_count, foreign_count, total_sent, False
    if not is_iranian_source and foreign_count >= SOURCE_TYPE_LIMITS["foreign"]:
        return sent_links, sent_titles, category_counts, iranian_count, foreign_count, total_sent, False

    norm_title_orig = normalize_title(title)
    if is_duplicate_title(norm_title_orig, sent_titles):
        return sent_links, sent_titles, category_counts, iranian_count, foreign_count, total_sent, False
    if is_duplicate_keywords(title, sent_titles):
        return sent_links, sent_titles, category_counts, iranian_count, foreign_count, total_sent, False

    print(f"→ Translating: {title[:60]}...")
    translated_title, translated_summary, used_ai = process_with_ai(title, clean_content)

    if is_error_text(translated_title) or is_error_text(translated_summary):
        return sent_links, sent_titles, category_counts, iranian_count, foreign_count, total_sent, False

    if not is_iranian_source:
        if is_mostly_english(translated_title):
            return sent_links, sent_titles, category_counts, iranian_count, foreign_count, total_sent, False

    if is_short_summary(translated_summary):
        if clean_content and len(clean_content) > 30:
            translated_summary = clean_content[:300]
        else:
            return sent_links, sent_titles, category_counts, iranian_count, foreign_count, total_sent, False

    video_url = extract_video_url(entry)
    image_url = extract_image_url(entry)
    if not video_url:
        video_url = fetch_video_from_page(link)

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
        print(f"✓ Sent: {translated_title[:50]}")
        sent_links.add(link)
        sent_titles.append(normalize_title(translated_title))
        category_counts[category] = category_counts.get(category, 0) + 1
        if is_iranian_source:
            iranian_count += 1
        else:
            foreign_count += 1
        total_sent += 1
        return sent_links, sent_titles, category_counts, iranian_count, foreign_count, total_sent, True
    return sent_links, sent_titles, category_counts, iranian_count, foreign_count, total_sent, False


def fetch_and_send():
    sent_links = load_set_from_file(SENT_LINKS_FILE)
    sent_titles = load_list_from_file(SENT_TITLES_FILE)

    total_sent_this_run = 0
    category_counts = {}
    iranian_count = 0
    foreign_count = 0

    # ==========================================
    # مرحله 1: تضمین حداقل ۱ خبر از خبرگزاری‌های مهم
    # ==========================================
    print("\n=== Phase 1: Required Sources ===")
    for required_source in REQUIRED_SOURCES:
        if total_sent_this_run >= MAX_POSTS_PER_RUN:
            break

        # فید مربوطه رو پیدا کن
        feed_url = None
        for src_name, url in RSS_FEEDS:
            if src_name == required_source:
                feed_url = url
                break

        if not feed_url:
            print(f"Required source not found: {required_source}")
            continue

        print(f"\n→ Checking required source: {required_source}")
        try:
            feed = feedparser.parse(feed_url)
        except Exception as e:
            print(f"Feed error: {e}")
            continue

        if feed.bozo or not feed.entries:
            continue

        sent_from_this_source = False
        # تلاش از ۱۰ خبر اول
        for entry in feed.entries[:10]:
            if sent_from_this_source:
                break
            if total_sent_this_run >= MAX_POSTS_PER_RUN:
                break

            sent_links, sent_titles, category_counts, iranian_count, foreign_count, total_sent_this_run, was_sent = process_entry(
                entry, required_source, sent_links, sent_titles, category_counts,
                iranian_count, foreign_count, total_sent_this_run
            )
            if was_sent:
                sent_from_this_source = True
                time.sleep(POST_DELAY_SECONDS)

        if not sent_from_this_source:
            print(f"✗ No valid news from {required_source}")

    # ==========================================
    # مرحله 2: بقیه اخبار (به ترتیب عادی)
    # ==========================================
    print("\n=== Phase 2: Regular Sources ===")
    for source_name, feed_url in RSS_FEEDS:
        if total_sent_this_run >= MAX_POSTS_PER_RUN:
            break

        print(f"\nChecking feed: {source_name}")
        try:
            feed = feedparser.parse(feed_url)
        except Exception as e:
            print(f"Feed parse error for {source_name}: {e}")
            continue

        if feed.bozo or not feed.entries:
            continue

        for entry in feed.entries[:5]:
            if total_sent_this_run >= MAX_POSTS_PER_RUN:
                break

            sent_links, sent_titles, category_counts, iranian_count, foreign_count, total_sent_this_run, was_sent = process_entry(
                entry, source_name, sent_links, sent_titles, category_counts,
                iranian_count, foreign_count, total_sent_this_run
            )
            if was_sent:
                time.sleep(POST_DELAY_SECONDS)

    save_set_to_file(SENT_LINKS_FILE, sent_links)
    save_list_to_file(SENT_TITLES_FILE, sent_titles)
    print(f"\nFinished. Iranian: {iranian_count}, Foreign: {foreign_count}, Total: {total_sent_this_run}")


if __name__ == "__main__":
    fetch_and_send()
