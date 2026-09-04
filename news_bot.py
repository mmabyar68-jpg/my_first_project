import feedparser
import requests
import os
import time

# ---------- تنظیمات از متغیرهای محیطی ----------
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID")

if not TELEGRAM_TOKEN or not CHANNEL_ID:
    raise ValueError("TELEGRAM_TOKEN and CHANNEL_ID must be set as environment variables")

# لیست فیدهای خبری
RSS_FEEDS = [
    "http://rss.cnn.com/rss/edition.rss",
    "http://feeds.bbci.co.uk/news/world/rss.xml",
    "http://feeds.reuters.com/Reuters/worldNews",
    "https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en",
]

# فایل ذخیره لینک‌های ارسال‌شده (در همان مخزن)
SENT_LINKS_FILE = "sent_links.txt"

def load_sent_links():
    if not os.path.exists(SENT_LINKS_FILE):
        return set()
    with open(SENT_LINKS_FILE, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip())

def save_sent_links(links):
    with open(SENT_LINKS_FILE, "w", encoding="utf-8") as f:
        for link in links:
            f.write(link + "\n")

def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHANNEL_ID,
        "text": text,
        "disable_web_page_preview": False,
    }
    try:
        response = requests.post(url, data=payload)
        response.raise_for_status()
        return True
    except Exception as e:
        print(f"Error sending message: {e}")
        return False

def fetch_and_send():
    sent_links = load_sent_links()
    new_links = set()

    for feed_url in RSS_FEEDS:
        print(f"Checking feed: {feed_url}")
        feed = feedparser.parse(feed_url)
        for entry in feed.entries[:3]:  # ۳ خبر اول هر فید
            link = entry.get("link", "")
            title = entry.get("title", "بدون عنوان")
            if link and link not in sent_links:
                message = f"📰 {title}\n🔗 {link}"
                if send_telegram_message(message):
                    print(f"Sent: {title}")
                    new_links.add(link)
                time.sleep(1)
            else:
                if link in sent_links:
                    print(f"Skipped (already sent): {title}")

    sent_links.update(new_links)
    save_sent_links(sent_links)
    print("Finished.")

if __name__ == "__main__":
    fetch_and_send()
