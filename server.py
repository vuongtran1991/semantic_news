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
    "Vietnamnet": "https://vietnamnet.vn/rss/home.rss"
}

# =========================
# GIẬT GÂN
# =========================

CLICKBAIT_WORDS = [
    "sốc", "kinh hoàng", "gây bão", "không thể tin", "chấn động"
]

# =========================
# PHỦ ĐỊNH
# =========================

NEGATIVE_WORDS = [
    "không", "không có", "không phải", "chưa", "bác bỏ", "phủ nhận"
]

def has_negative(text):
    text = text.lower()
    return any(w in text for w in NEGATIVE_WORDS)

# =========================
# 🔥 FIX: BẮT SỐ - % - NGÀY - THỜI GIAN
# =========================

def extract_numbers(text):
    text = text.lower()

    pattern = r'''
        \d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?   |   # ngày 12/05/2026
        \d+\s?(ngày|tuần|tháng|năm|giờ)      |   # thời gian
        \d+[.,]?\d*\s?%                      |   # phần trăm
        \d+                                   # số thường
    '''

    results = re.findall(pattern, text, re.VERBOSE)

    # 🔥 FIX: loại tuple rỗng do group
    clean = []
    for r in results:
        if isinstance(r, tuple):
            r = next((x for x in r if x), "")
        if r:
            clean.append(r)

    return clean

# =========================
# CLICKBAIT
# =========================

def detect_clickbait(text):
    text = text.lower()
    return next((w for w in CLICKBAIT_WORDS if w in text), None)

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
                all_articles.append({
                    "source": source,
                    "title": getattr(entry, "title", ""),
                    "summary": getattr(entry, "summary", ""),
                    "link": getattr(entry, "link", "")
                })

        except Exception as e:
            print("RSS ERROR:", e)

    df = pd.DataFrame(all_articles)

    if not df.empty:
        texts = (df["title"].fillna("") + " " + df["summary"].fillna("")).tolist()
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
    return "Semantic News API running"

# =========================
# NEWS (đã format đẹp hơn)
# =========================

@app.route("/news")
def news():

    if df.empty:
        return "<h3>Chưa có dữ liệu</h3>"

    html = """
    <html>
    <head>
    <meta charset="utf-8">
    <style>
        body {font-family: Arial; margin:20px;}
        .card {border:1px solid #ddd; padding:10px; margin:10px; border-radius:10px;}
        .source {color:green; font-weight:bold;}
        .title {font-size:18px; font-weight:bold;}
    </style>
    </head>
    <body>
    <h2>NEWS DASHBOARD</h2>
    """

    for _, r in df.iterrows():
        html += f"""
        <div class="card">
            <div class="source">{r['source']}</div>
            <div class="title">{r['title']}</div>
            <p>{r['summary']}</p>
            <a href="{r['link']}" target="_blank">Read</a>
        </div>
        """

    html += "</body></html>"
    return html

# =========================
# SEARCH (FIX LOGIC MẠNH)
# =========================

@app.route("/search", methods=["POST"])
def search():

    global news_vectors

    query = request.json["query"]

    if detect_clickbait(query):
        return jsonify({"status": "fake", "results": []})

    if df.empty or news_vectors is None:
        return jsonify({"status": "empty", "results": []})

    query_vec = vectorizer.transform([query])
    scores = cosine_similarity(query_vec, news_vectors)[0]

    top = scores.argsort()[-5:][::-1]

    results = []

    query_nums = extract_numbers(query)
    query_neg = has_negative(query)

    for i in top:

        title = df.iloc[i]["title"]
        summary = df.iloc[i]["summary"]
        link = df.iloc[i]["link"]
        source = df.iloc[i]["source"]

        text = title + " " + summary

        score = float(scores[i])

        # =========================
        # 🔥 FIX PHỦ ĐỊNH LOGIC
        # =========================
        if query_neg != has_negative(text):
            score *= 0.2

        article_nums = extract_numbers(text)

        mismatches = []

        # =========================
        # 🔥 FIX SO SÁNH SỐ LIỆU
        # =========================
        for q in query_nums:
            if not any(q == a for a in article_nums):
                mismatches.append({
                    "query": q,
                    "article": article_nums[0] if article_nums else "none"
                })

        results.append({
            "title": title,
            "summary": summary,
            "link": link,
            "source": source,
            "score": round(score, 2),
            "mismatches": mismatches
        })

    results = sorted(results, key=lambda x: x["score"], reverse=True)

    best = results[0]

    # =========================
    # DECISION
    # =========================

    if best["score"] < 0.3:
        return jsonify({"status": "not_found", "results": []})

    if len(best["mismatches"]) > 0:
        return jsonify({"status": "mismatch", "results": results})

    if best["score"] < 0.6:
        return jsonify({"status": "low_confidence", "results": results})

    return jsonify({"status": "success", "results": results})

# =========================
# START
# =========================

crawl_news()

threading.Thread(target=auto_update, daemon=True).start()

app.run(host="0.0.0.0", port=5000)