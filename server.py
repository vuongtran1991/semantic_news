from flask import Flask, request, jsonify
from flask_cors import CORS
import pandas as pd
import re

app = Flask(__name__)
CORS(app)

print("Loading database...")

df = pd.read_csv("news.csv")

model = None
news_vectors = None


# =========================
# LOAD AI
# =========================
def load_ai():

    global model, news_vectors

    if model is None:

        print("Loading AI model...")

        from sentence_transformers import SentenceTransformer

        model = SentenceTransformer(
            'paraphrase-multilingual-MiniLM-L12-v2'
        )

        # TITLE + SUMMARY
        texts = (
            df["title"].fillna('') + " " +
            df["summary"].fillna('')
        ).tolist()

        news_vectors = model.encode(texts)

        print("AI ready!")


# =========================
# CLICKBAIT
# =========================
CLICKBAIT_WORDS = [
    "sốc",
    "kinh hoàng",
    "gây bão",
    "không thể tin",
    "chấn động",
    "ngã ngửa"
]


def detect_clickbait(text):

    lower = text.lower()

    for word in CLICKBAIT_WORDS:

        if word in lower:
            return word

    return None


# =========================
# EXTRACT NUMBER
# =========================
def extract_numbers(text):

    pattern = r'\d{1,2}/\d{1,2}/\d{2,4}|\d+%?'

    return re.findall(pattern, text)


# =========================
# HOME
# =========================
@app.route("/")
def home():
    return "Semantic News API is running!"


# =========================
# SEARCH
# =========================
@app.route("/search", methods=["POST"])
def search():

    data = request.json

    query = data["query"]

    # =====================
    # B1 CLICKBAIT
    # =====================

    clickbait = detect_clickbait(query)

    if clickbait:

        return jsonify({
            "status": "fake",
            "message":
                f"❌ Phát hiện từ giật gân: '{clickbait}'",
            "results": []
        })

    # =====================
    # B2 LOAD AI
    # =====================

    load_ai()

    from sklearn.metrics.pairwise import cosine_similarity

    query_vector = model.encode([query])

    scores = cosine_similarity(
        query_vector,
        news_vectors
    )[0]

    top_indices = scores.argsort()[-5:][::-1]

    results = []

    query_numbers = extract_numbers(query)

    # =====================
    # B3 BUILD RESULT
    # =====================

    for idx in top_indices:

        title = str(df.iloc[idx]["title"])
        summary = str(df.iloc[idx]["summary"])
        link = str(df.iloc[idx]["link"])
        source = str(df.iloc[idx]["source"])

        score = float(scores[idx])

        article_text = title + " " + summary

        article_numbers = extract_numbers(article_text)

        mismatches = []

        for q in query_numbers:

            if q not in article_numbers:

                correct_value = (
                    article_numbers[0]
                    if len(article_numbers) > 0
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
    # B4 NOT FOUND
    # =====================

    if results[0]["score"] < 0.25:

        return jsonify({

            "status": "not_found",

            "message":
                "⚠ Không tìm thấy bài báo khớp hoàn toàn. "
                "Dưới đây là các bài gần đúng.",

            "results": results
        })

    # =====================
    # B5 SUCCESS
    # =====================

    return jsonify({

        "status": "success",

        "message":
            "✅ Đã tìm thấy bài báo phù hợp",

        "results": results
    })


# =========================
# RUN
# =========================
app.run(
    host="0.0.0.0",
    port=5000
)