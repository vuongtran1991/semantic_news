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

CLICKBAIT_WORDS = ["sốc", "kinh hoàng", "gây bão", "không thể tin", "chấn động", "ngã ngửa"]

NEGATIVE_WORDS = ["không", "không có", "không phải", "chưa", "bác bỏ", "phủ nhận"]

def has_negative(text):
    text = text.lower()
    return any(w in text for w in NEGATIVE_WORDS)

# =========================
# CRAWL
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
# UTIL
# =========================

def extract_numbers(text):
    pattern = r'\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?|\d+[.,]?\d*%?'
    return re.findall(pattern, text)

def detect_clickbait(text):
    text = text.lower()
    for w in CLICKBAIT_WORDS:
        if w in text:
            return w
    return None

# =========================
# HOME
# =========================

@app.route("/")
def home():
    return "Semantic News API is running!"

# =========================
# ⭐ FIX /NEWS (ĐẸP HƠN)
# =========================

@app.route("/news")
def get_news():

    if df.empty:
        return """
        <h2>Chưa có dữ liệu</h2>
        """

    html = """
    <html>
    <head>
        <meta charset="utf-8">
        <title>Semantic News</title>
        <style>
            body { font-family: Arial; background:#f5f5f5; padding:20px; }
            h1 { text-align:center; }

            .card {
                background:white;
                padding:15px;
                margin:15px auto;
                border-radius:12px;
                box-shadow:0 2px 8px rgba(0,0,0,0.1);
                max-width:900px;
            }

            .source {
                color:green;
                font-weight:bold;
                font-size:14px;
            }

            a {
                color:#1a73e8;
                text-decoration:none;
            }

            .title {
                font-size:18px;
                font-weight:bold;
                margin:10px 0;
            }

            .summary {
                color:#444;
            }
        </style>
    </head>
    <body>

    <h1>📰 DANH SÁCH BÀI BÁO (REALTIME RSS)</h1>
    """

    for _, row in df.iterrows():
        html += f"""
        <div class="card">
            <div class="source">{row['source']}</div>
            <div class="title">{row['title']}</div>
            <div class="summary">{row['summary']}</div>
            <br>
            <a href="{row['link']}" target="_blank">👉 Đọc bài gốc</a>
        </div>
        """

    html += "</body></html>"
    return html

# =========================
# COUNT
# =========================

@app.route("/count")
def count_news():
    return jsonify({"total": len(df)})

# =========================
# SEARCH (GIỮ NGUYÊN LOGIC CỦA BẠN)
# =========================

@app.route("/search", methods=["POST"])
def search():

    global news_vectors

    data = request.json
    query = data["query"]

    clickbait = detect_clickbait(query)
    if clickbait:
        return jsonify({
            "status": "fake",
            "message": f"❌ Phát hiện từ giật gân: {clickbait}",
            "results": []
        })

    if df.empty or news_vectors is None:
        return jsonify({
            "status": "empty",
            "message": "⚠ Server chưa tải xong dữ liệu",
            "results": []
        })

    query_vector = vectorizer.transform([query])
    scores = cosine_similarity(query_vector, news_vectors)[0]

    top_indices = scores.argsort()[-5:][::-1]

    results = []
    query_numbers = extract_numbers(query)
    query_negative = has_negative(query)

    for idx in top_indices:

        title = str(df.iloc[idx]["title"])
        summary = str(df.iloc[idx]["summary"])
        link = str(df.iloc[idx]["link"])
        source = str(df.iloc[idx]["source"])

        score = float(scores[idx])

        article_text = title + " " + summary
        article_negative = has_negative(article_text)

        if query_negative != article_negative:
            score *= 0.3

        results.append({
            "title": title,
            "summary": summary,
            "link": link,
            "source": source,
            "score": round(score, 2)
        })

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