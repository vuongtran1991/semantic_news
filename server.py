from flask import Flask, request, jsonify
from flask_cors import CORS

import pandas as pd
import feedparser
import re
import threading
import time
from datetime import datetime, timedelta

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
# CLICKBAIT
# =========================

CLICKBAIT_WORDS = ["sốc", "kinh hoàng", "gây bão", "không thể tin", "chấn động"]

NEGATIVE_WORDS = ["không", "không có", "không phải", "chưa", "bác bỏ", "phủ nhận"]


def detect_clickbait(text):
    text = text.lower()
    return any(w in text for w in CLICKBAIT_WORDS)


def has_negative(text):
    text = text.lower()
    return any(w in text for w in NEGATIVE_WORDS)

# =========================
# 🔥 AI: NORMALIZE NUMBER
# =========================

def normalize_number(x):
    return x.lower().replace(" ", "").replace(",", ".")

# =========================
# 🔥 AI: EXTRACT SMART NUMBERS
# =========================

def extract_numbers(text):
    text = text.lower()

    patterns = [
        r"\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?",   # date 12/05/2026
        r"\d+[.,]?\d*\s?%",                      # percent
        r"\d+\s?(ngày|tuần|tháng|năm|giờ)",      # time units
        r"\d+"                                    # number
    ]

    results = []
    for p in patterns:
        results += re.findall(p, text)

    clean = []
    for r in results:
        if isinstance(r, tuple):
            r = "".join([x for x in r if x])
        if r:
            clean.append(r.strip())

    return clean

# =========================
# 🔥 AI: PARSE DATE INTELLIGENT
# =========================

def parse_date(text):
    text = text.lower()

    # hôm qua
    if "hôm qua" in text:
        return (datetime.now() - timedelta(days=1)).date()

    # hôm nay
    if "hôm nay" in text:
        return datetime.now().date()

    # dd/mm/yyyy
    m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{2,4})", text)
    if m:
        d, mth, y = m.groups()
        y = int(y)
        if y < 100:
            y += 2000
        return datetime(y, int(mth), int(d)).date()

    return None

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
# NEWS
# =========================

@app.route("/news")
def news():
    if df.empty:
        return "<h3>Chưa có dữ liệu</h3>"

    html = "<html><body><h2>NEWS</h2>"

    for _, r in df.iterrows():
        html += f"""
        <div>
            <h3>{r['title']}</h3>
            <p>{r['summary']}</p>
            <a href="{r['link']}">Read</a>
        </div>
        <hr>
        """

    html += "</body></html>"
    return html

# =========================
# SEARCH AI UPGRADED
# =========================

@app.route("/search", methods=["POST"])
def search():

    global news_vectors

    query = request.json.get("query", "")

    if detect_clickbait(query):
        return jsonify({"status": "fake", "results": []})

    if df.empty or news_vectors is None:
        return jsonify({"status": "empty", "results": []})

    query_vec = vectorizer.transform([query])
    scores = cosine_similarity(query_vec, news_vectors)[0]

    top = scores.argsort()[-5:][::-1]

    query_nums = extract_numbers(query)
    query_date = parse_date(query)
    query_neg = has_negative(query)

    results = []

    for i in top:

        title = df.iloc[i]["title"]
        summary = df.iloc[i]["summary"]
        link = df.iloc[i]["link"]
        source = df.iloc[i]["source"]

        text = title + " " + summary
        score = float(scores[i])

        # =========================
        # NEGATIVE LOGIC FIX
        # =========================
        if query_neg != has_negative(text):
            score *= 0.3

        article_nums = extract_numbers(text)

        mismatches = []

        # =========================
        # NUMBER COMPARISON AI FIX
        # =========================
        for q in query_nums:
            if not any(normalize_number(q) == normalize_number(a) for a in article_nums):
                mismatches.append({
                    "query": q,
                    "article": article_nums[:3]
                })

        # =========================
        # DATE COMPARISON AI FIX
        # =========================
        article_date = parse_date(text)
        if query_date and article_date and query_date != article_date:
            score *= 0.5
            mismatches.append({
                "date_query": str(query_date),
                "date_article": str(article_date)
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