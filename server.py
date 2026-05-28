from flask import Flask, request, jsonify
from flask_cors import CORS

import pandas as pd
import feedparser
import requests
import re
import threading
import time
import os

from bs4 import BeautifulSoup

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

app = Flask(__name__)
CORS(app)

# =========================
# DATA
# =========================

df = pd.DataFrame()

vectorizer = TfidfVectorizer(
    stop_words=None,
    lowercase=True
)

news_vectors = None

# =========================
# RSS CHÍNH THỐNG
# =========================

rss_urls = {

    "VnExpress":
    "https://vnexpress.net/rss/home.rss",

    "TuoiTre":
    "https://tuoitre.vn/rss/home.rss",

    "ThanhNien":
    "https://thanhnien.vn/rss/home.rss",

    "DanTri":
    "https://dantri.com.vn/rss/home.rss",

    "Vietnamnet":
    "https://vietnamnet.vn/rss/home.rss"
}

# =========================
# TỪ GIẬT GÂN
# =========================

CLICKBAIT_WORDS = [

    "sốc",
    "kinh hoàng",
    "gây bão",
    "không thể tin",
    "chấn động",
    "ngã ngửa",
    "viral",
    "rúng động"
]

# =========================
# TỪ PHỦ ĐỊNH
# =========================

NEGATIVE_WORDS = [

    "không",
    "chưa",
    "không có",
    "không phải",
    "bác bỏ",
    "tin giả"
]

# =========================
# LẤY NỘI DUNG BÀI BÁO
# =========================

def get_article_content(url):

    try:

        headers = {
            "User-Agent":
            "Mozilla/5.0"
        }

        response = requests.get(
            url,
            headers=headers,
            timeout=10
        )

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

        paragraphs = soup.find_all("p")

        content = ""

        for p in paragraphs:

            text = p.get_text().strip()

            if len(text) > 40:

                content += text + " "

        return content[:4000]

    except Exception as e:

        print("CONTENT ERROR:", e)

        return ""

# =========================
# CRAWL RSS
# =========================

def crawl_news():

    global df
    global news_vectors

    print("Updating RSS news...")

    all_articles = []

    for source, url in rss_urls.items():

        try:

            print(f"\nLoading: {source}")

            feed = feedparser.parse(url)

            count = 0

            # =====================
            # MỖI BÁO 3 BÀI
            # =====================

            for entry in feed.entries[:3]:

                title = getattr(
                    entry,
                    'title',
                    ''
                )

                summary = getattr(
                    entry,
                    'summary',
                    ''
                )

                link = getattr(
                    entry,
                    'link',
                    ''
                )

                # làm sạch link
                link = (
                    link.replace('%22', '')
                        .replace('"', '')
                        .strip()
                )

                print("Reading content...")

                content = get_article_content(
                    link
                )

                print(
                    f"Content length: {len(content)}"
                )

                all_articles.append({

                    "source": source,

                    "title": title,

                    "summary": summary,

                    "content": content,

                    "link": link
                })

                count += 1

            print(
                f"{source}: {count} articles"
            )

        except Exception as e:

            print(
                f"RSS ERROR {source}: {e}"
            )

    # =====================
    # DATAFRAME
    # =====================

    df = pd.DataFrame(all_articles)

    print("\nTOTAL ARTICLES:", len(df))

    # =====================
    # TF-IDF VECTOR
    # =====================

    if not df.empty:

        texts = (

            df["title"].fillna('') + " " +
            df["summary"].fillna('') + " " +
            df["content"].fillna('')
        ).tolist()

        news_vectors = vectorizer.fit_transform(
            texts
        )

        print("Vectors updated!")

# =========================
# AUTO UPDATE
# =========================

def auto_update():

    while True:

        time.sleep(1800)

        crawl_news()

# =========================
# TÁCH SỐ / NGÀY
# =========================

def extract_numbers(text):

    pattern = (

        r'\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?'
        r'|\d+[.,]?\d*\s?(?:%|độ|°c|người|ca)?'
    )

    matches = re.findall(
        pattern,
        text.lower()
    )

    return matches

# =========================
# CHECK GIẬT GÂN
# =========================

def detect_clickbait(text):

    lower = text.lower()

    for word in CLICKBAIT_WORDS:

        if word in lower:
            return word

    return None

# =========================
# CHECK PHỦ ĐỊNH
# =========================

def has_negative(text):

    lower = text.lower()

    for word in NEGATIVE_WORDS:

        if word in lower:
            return True

    return False

# =========================
# HOME
# =========================

@app.route("/")
def home():

    return "Semantic News API is running!"

# =========================
# DEBUG XEM BÀI
# =========================

@app.route("/news")
def get_news():

    return jsonify(
        df.to_dict(orient="records")
    )

# =========================
# ĐẾM BÀI
# =========================

@app.route("/count")
def count_news():

    return jsonify({

        "total": len(df)
    })

# =========================
# SEARCH
# =========================

@app.route("/search", methods=["POST"])
def search():

    global news_vectors

    data = request.json

    query = data["query"]

    # =====================
    # CHECK GIẬT GÂN
    # =====================

    clickbait = detect_clickbait(query)

    if clickbait:

        return jsonify({

            "status": "fake",

            "message":
            f"❌ Phát hiện từ giật gân: {clickbait}",

            "results": []
        })

    # =====================
    # SERVER CHƯA LOAD
    # =====================

    if df.empty or news_vectors is None:

        return jsonify({

            "status": "empty",

            "message":
            "⚠ Server chưa tải xong dữ liệu",

            "results": []
        })

    # =====================
    # TF-IDF SEARCH
    # =====================

    query_vector = vectorizer.transform(
        [query]
    )

    scores = cosine_similarity(
        query_vector,
        news_vectors
    )[0]

    top_indices = scores.argsort()[-5:][::-1]

    results = []

    query_numbers = extract_numbers(query)

    query_has_negative = has_negative(query)

    # =====================
    # TOP RESULTS
    # =====================

    for idx in top_indices:

        title = str(df.iloc[idx]["title"])

        summary = str(df.iloc[idx]["summary"])

        content = str(df.iloc[idx]["content"])

        link = str(df.iloc[idx]["link"])

        source = str(df.iloc[idx]["source"])

        score = float(scores[idx])

        article_text = (
            title + " " +
            summary + " " +
            content
        )

        # =====================
        # CHECK PHỦ ĐỊNH
        # =====================

        article_has_negative = has_negative(
            article_text
        )

        # nếu phủ định không khớp
        if query_has_negative != article_has_negative:

            score *= 0.4

        article_numbers = extract_numbers(
            article_text
        )

        mismatches = []

        # =====================
        # CHECK SỐ / NGÀY
        # =====================

        for q in query_numbers:

            found = False

            for a in article_numbers:

                if q == a:

                    found = True
                    break

            if not found:

                correct_value = (

                    article_numbers[0]
                    if len(article_numbers) > 0
                    else "Không có"
                )

                mismatches.append({

                    "user": q,

                    "official":
                    correct_value
                })

        results.append({

            "title": title,

            "summary": summary,

            "link": link,

            "source": source,

            "score": round(score, 2),

            "mismatches": mismatches
        })

    # =====================
    # SẮP XẾP LẠI SAU KHI
    # GIẢM SCORE PHỦ ĐỊNH
    # =====================

    results = sorted(
        results,
        key=lambda x: x["score"],
        reverse=True
    )

    # =====================
    # SCORE THẤP
    # =====================

    if results[0]["score"] < 0.30:

        return jsonify({

            "status": "not_found",

            "message":
            "❌ Không tìm thấy trên báo chính thống",

            "highest_score":
            results[0]["score"],

            "results": []
        })

    # =====================
    # SAI LỆCH SỐ LIỆU
    # =====================

    if len(results[0]["mismatches"]) > 0:

        return jsonify({

            "status": "mismatch",

            "message":
            "⚠ Có sai lệch số liệu hoặc ngày tháng",

            "results": results
        })

    # =====================
    # SUCCESS
    # =====================

    return jsonify({

        "status": "success",

        "message":
        "✅ Tin đáng tin",

        "results": results
    })

# =========================
# START
# =========================

if __name__ == "__main__":

    crawl_news()

    threading.Thread(
        target=auto_update,
        daemon=True
    ).start()

    port = int(
        os.environ.get("PORT", 10000)
    )

    app.run(
        host="0.0.0.0",
        port=port
    )