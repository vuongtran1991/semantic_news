from flask import Flask, request, jsonify
from flask_cors import CORS

import pandas as pd
import feedparser
import re
import threading
import time

app = Flask(__name__)
CORS(app)

# =========================
# DATA
# =========================

model = None
news_vectors = None
df = pd.DataFrame()

# =========================
# RSS CHÍNH THỐNG
# =========================

rss_urls = {

    "VnExpress":
    "https://vnexpress.net/rss/tin-moi-nhat.rss",

    "TuoiTre":
    "https://tuoitre.vn/rss/tin-moi-nhat.rss",

    "ThanhNien":
    "https://thanhnien.vn/rss/home.rss",

    "DanTri":
    "https://dantri.com.vn/rss/home.rss",

    "Vietnamnet":
    "https://vietnamnet.vn/rss/home.rss",

    "TienPhong":
    "https://tienphong.vn/rss/home.rss",

    "LaoDong":
    "https://laodong.vn/rss/home.rss",

    "NguoiLaoDong":
    "https://nld.com.vn/rss/home.rss",

    "BaoChinhPhu":
    "https://baochinhphu.vn/rss/home.rss",

    "BaoNhanDan":
    "https://nhandan.vn/rss/home.rss",

    "BoYTe":
    "https://moh.gov.vn/rss/-/asset_publisher/7ng11fEWgASC/rss",

    "BoGiaoDuc":
    "https://moet.gov.vn/rss/Pages/index.aspx",

    "QuocHoi":
    "https://quochoi.vn/rss/default.aspx"
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
    "ngã ngửa"
]

# =========================
# LOAD AI
# =========================

def load_ai():

    global model

    if model is None:

        print("Loading AI model...")

        from sentence_transformers import SentenceTransformer

        model = SentenceTransformer(
            'all-MiniLM-L6-v2'
        )

        print("AI ready!")

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

            feed = feedparser.parse(url)

            # mỗi báo chỉ lấy 10 bài
            for entry in feed.entries[:10]:

                all_articles.append({

                    "source": source,

                    "title":
                    getattr(entry, 'title', ''),

                    "summary":
                    getattr(entry, 'summary', ''),

                    "link":
                    getattr(entry, 'link', '')
                })

        except Exception as e:

            print("RSS ERROR:", source, e)

    # cập nhật mới hoàn toàn
    df = pd.DataFrame(all_articles)

    print("Loaded", len(df), "articles")

    # tạo vector semantic

    if model is not None and not df.empty:

        texts = (

            df["title"].fillna('') + " " +
            df["summary"].fillna('')

        ).tolist()

        news_vectors = model.encode(texts)

        print("Vectors updated!")

# =========================
# AUTO UPDATE
# =========================

def auto_update():

    while True:

        crawl_news()

        # 30 phút cập nhật 1 lần
        time.sleep(1800)

# =========================
# TÁCH SỐ / % / NGÀY
# =========================

def extract_numbers(text):

    pattern = r'\d{1,2}/\d{1,2}/\d{2,4}|\d+%?'

    return re.findall(pattern, text)

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
# HOME
# =========================

@app.route("/")
def home():

    return "Semantic News API is running!"

# =========================
# DEBUG XEM BÀI BÁO
# =========================

@app.route("/news")
def get_news():

    return jsonify(
        df.to_dict(orient="records")
    )

# =========================
# DEBUG ĐẾM BÀI
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
    # LOAD AI
    # =====================

    load_ai()

    from sklearn.metrics.pairwise import cosine_similarity

    # nếu chưa có vector
    if news_vectors is None:

        crawl_news()

    query_vector = model.encode([query])

    scores = cosine_similarity(
        query_vector,
        news_vectors
    )[0]

    top_indices = scores.argsort()[-5:][::-1]

    results = []

    query_numbers = extract_numbers(query)

    # =====================
    # TOP 5
    # =====================

    for idx in top_indices:

        title = str(df.iloc[idx]["title"])

        summary = str(df.iloc[idx]["summary"])

        link = str(df.iloc[idx]["link"])

        source = str(df.iloc[idx]["source"])

        score = float(scores[idx])

        article_text = title + " " + summary

        article_numbers = extract_numbers(
            article_text
        )

        mismatches = []

        # check số liệu

        for q in query_numbers:

            if q not in article_numbers:

                correct_value = (

                    article_numbers[0]
                    if article_numbers
                    else "Không có"
                )

                mismatches.append({

                    "user": q,
                    "official": correct_value
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
    # KHÔNG KHỚP HOÀN TOÀN
    # =====================

    if results[0]["score"] < 0.30:

        return jsonify({

            "status": "not_found",

            "message":
            "⚠ Không tìm thấy bài khớp hoàn toàn. Dưới đây là các bài gần đúng.",

            "results": results
        })

    # =====================
    # SUCCESS
    # =====================

    return jsonify({

        "status": "success",

        "message":
        "✅ Đã tìm thấy bài báo phù hợp",

        "results": results
    })

# =========================
# START
# =========================

crawl_news()

threading.Thread(
    target=auto_update,
    daemon=True
).start()

app.run(
    host="0.0.0.0",
    port=5000
)