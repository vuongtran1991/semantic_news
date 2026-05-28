from flask import Flask, request, jsonify
from flask_cors import CORS

import pandas as pd
import feedparser
import re
import threading
import time

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

app = Flask(__name__)
CORS(app)

# =========================
# DATA
# =========================

df = pd.DataFrame()
vectorizer = TfidfVectorizer()
news_vectors = None

# =========================
# RSS
# =========================

rss_urls = {
    "VnExpress": "https://vnexpress.net/rss/home.rss",
    "TuoiTre": "https://tuoitre.vn/rss/home.rss",
    "ThanhNien": "https://thanhnien.vn/rss/home.rss",
    "DanTri": "https://dantri.com.vn/rss/home.rss",
    "Vietnamnet": "https://vietnamnet.vn/rss/home.rss",
    "BaoChinhPhu": "https://baochinhphu.vn/rss/home.rss",
    "BaoNhanDan": "https://nhandan.vn/rss/home.rss",
    "BoYTe": "https://moh.gov.vn/rss/-/asset_publisher/7ng11fEWgASC/rss",
    "BoGiaoDuc": "https://moet.gov.vn/rss/Pages/index.aspx",
    "QuocHoi": "https://quochoi.vn/rss/default.aspx"
}

# =========================
# KEYWORDS
# =========================

CLICKBAIT_WORDS = ["sốc", "kinh hoàng", "gây bão", "không thể tin", "chấn động", "ngã ngửa"]

NEGATIVE_WORDS = ["không", "không có", "không phải", "chưa", "bác bỏ", "phủ nhận"]

# =========================
# UTIL AI LAYER
# =========================

def has_negative(text):
    text = text.lower()
    return any(w in text for w in NEGATIVE_WORDS)

def extract_numbers(text):
    pattern = r'\d+[\.,]?\d*\s?%?|\d+'
    return re.findall(pattern, text)

def extract_time(text):
    pattern = r'\b(\d{1,2}[/-]\d{1,2}([/-]\d{2,4})?|ngày\s*\d+|tháng\s*\d+|năm\s*\d+|\d+\s*(ngày|tháng|năm))\b'
    return re.findall(pattern, text.lower())

def detect_trend(text):
    text = text.lower()

    up_words = ["tăng", "leo", "bứt phá", "tăng mạnh", "vọt"]
    down_words = ["giảm", "tụt", "rơi", "sụt", "giảm mạnh"]

    return {
        "up": any(w in text for w in up_words),
        "down": any(w in text for w in down_words)
    }

def detect_clickbait(text):
    text = text.lower()
    for w in CLICKBAIT_WORDS:
        if w in text:
            return w
    return None

# =========================
# CRAWL RSS
# =========================

def crawl_news():
    global df, news_vectors

    all_articles = []

    for source, url in rss_urls.items():
        try:
            feed = feedparser.parse(url)

            for entry in feed.entries[:5]:
                link = getattr(entry, 'link', '').replace('%22','').replace('"','').strip()

                all_articles.append({
                    "source": source,
                    "title": getattr(entry, 'title', ''),
                    "summary": getattr(entry, 'summary', ''),
                    "link": link
                })

        except Exception as e:
            print("RSS ERROR:", e)

    df = pd.DataFrame(all_articles)

    if not df.empty:
        texts = (df["title"].fillna('') + " " + df["summary"].fillna('')).tolist()
        news_vectors = vectorizer.fit_transform(texts)

# =========================
# AUTO UPDATE
# =========================

def auto_update():
    while True:
        crawl_news()
        time.sleep(1800)

# =========================
# HOME
# =========================

@app.route("/")
def home():
    return "Semantic News API is running!"

# =========================
# NEWS VIEW
# =========================

@app.route("/news")
def get_news():

    if df.empty:
        return "<h2>Chưa có dữ liệu</h2>"

    html = """
    <html>
    <head>
        <meta charset="utf-8">
        <title>Semantic News</title>
        <style>
            body { font-family: Arial; background:#f4f4f4; padding:20px; }
            .card {
                background:white;
                padding:15px;
                margin:10px auto;
                border-radius:10px;
                max-width:900px;
                box-shadow:0 2px 8px rgba(0,0,0,0.1);
            }
            .source { color:green; font-weight:bold; }
            .title { font-size:18px; font-weight:bold; }
            a { color:blue; }
        </style>
    </head>
    <body>
    <h1>📰 NEWS</h1>
    """

    for _, row in df.iterrows():
        html += f"""
        <div class="card">
            <div class="source">{row['source']}</div>
            <div class="title">{row['title']}</div>
            <p>{row['summary']}</p>
            <a href="{row['link']}" target="_blank">Đọc bài</a>
        </div>
        """

    html += "</body></html>"
    return html

# =========================
# SEARCH (AI FACT CHECK UPGRADE)
# =========================

@app.route("/search", methods=["POST"])
def search():

    global news_vectors

    data = request.json
    query = data["query"]

    if detect_clickbait(query):
        return jsonify({"status": "fake", "message": "Clickbait detected", "results": []})

    if df.empty or news_vectors is None:
        return jsonify({"status": "empty", "results": []})

    query_vector = vectorizer.transform([query])
    scores = cosine_similarity(query_vector, news_vectors)[0]

    top_indices = scores.argsort()[-5:][::-1]

    results = []

    query_numbers = extract_numbers(query)
    query_negative = has_negative(query)
    query_time = extract_time(query)
    query_trend = detect_trend(query)

    for idx in top_indices:

        title = str(df.iloc[idx]["title"])
        summary = str(df.iloc[idx]["summary"])
        link = str(df.iloc[idx]["link"])
        source = str(df.iloc[idx]["source"])

        score = float(scores[idx])

        text = title + " " + summary

        # =========================
        # AI CHECK LAYER
        # =========================

        article_negative = has_negative(text)
        article_numbers = extract_numbers(text)
        article_time = extract_time(text)
        article_trend = detect_trend(text)

        # ❌ PHỦ ĐỊNH
        if query_negative != article_negative:
            score *= 0.25

        # ❌ SỐ LIỆU
        for q in query_numbers:
            for a in article_numbers:
                try:
                    if float(q.replace('%','')) != float(a.replace('%','')):
                        score *= 0.7
                except:
                    pass

        # ❌ THỜI GIAN
        if query_time and article_time:
            if query_time[0][0] != article_time[0][0]:
                score *= 0.5

        # ❌ TREND
        if query_trend["up"] != article_trend["up"] or query_trend["down"] != article_trend["down"]:
            score *= 0.3

        results.append({
            "title": title,
            "summary": summary,
            "link": link,
            "source": source,
            "score": round(score, 2)
        })

    # =========================
    # FILTER
    # =========================

    results = sorted(results, key=lambda x: x["score"], reverse=True)

    if results[0]["score"] < 0.3:
        return jsonify({"status": "not_found", "results": []})

    return jsonify({
        "status": "success",
        "results": results
    })

# =========================
# START
# =========================

crawl_news()

threading.Thread(target=auto_update, daemon=True).start()

app.run(host="0.0.0.0", port=5000)