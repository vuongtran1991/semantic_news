from flask import Flask, request, jsonify
from flask_cors import CORS
import pandas as pd
import os

# =========================
# FLASK
# =========================
app = Flask(__name__)
CORS(app)

# =========================
# LOAD DATABASE
# =========================
print("Loading database...")

df = pd.read_csv("news.csv")

# chống lỗi dữ liệu rỗng
df["title"] = df["title"].fillna("")
df["summary"] = df["summary"].fillna("")
df["link"] = df["link"].fillna("")
df["source"] = df["source"].fillna("")

# =========================
# AI CHƯA LOAD NGAY
# =========================
model = None
news_vectors = None

# =========================
# LOAD AI KHI CẦN
# =========================
def load_ai():
    global model, news_vectors

    if model is None:

        print("Loading AI model (first request only)...")

        from sentence_transformers import SentenceTransformer

        # model nhẹ cho Render free
        model = SentenceTransformer(
            'paraphrase-multilingual-MiniLM-L12-v2',
            device='cpu'
        )

        print("Creating vectors...")

        # AI tìm theo title + summary
        combined_texts = (
            df["title"] + " " + df["summary"]
        ).tolist()

        # tạo vector
        news_vectors = model.encode(
            combined_texts,
            batch_size=8,
            show_progress_bar=False
        )

        print("AI ready!")

# =========================
# HOME
# =========================
@app.route("/")
def home():
    return "Semantic News API is running!"

# =========================
# SEARCH API
# =========================
@app.route("/search", methods=["POST"])
def search():

    load_ai()

    from sklearn.metrics.pairwise import cosine_similarity

    try:

        data = request.json

        # kiểm tra query
        if not data or "query" not in data:
            return jsonify({
                "error": "Missing query"
            }), 400

        query = data["query"]

        # vector câu hỏi user
        query_vector = model.encode([query])

        # tính độ giống
        scores = cosine_similarity(
            query_vector,
            news_vectors
        )[0]

        # lấy top 5 bài gần nhất
        top_indices = scores.argsort()[-5:][::-1]

        results = []

        for idx in top_indices:

            results.append({
                "title": df.iloc[idx]["title"],
                "summary": df.iloc[idx]["summary"],
                "link": df.iloc[idx]["link"],
                "source": df.iloc[idx]["source"],
                "score": float(scores[idx])
            })

        return jsonify({
            "results": results
        })

    except Exception as e:

        return jsonify({
            "error": str(e)
        }), 500

# =========================
# RUN SERVER
# =========================
if __name__ == "__main__":

    port = int(os.environ.get("PORT", 5000))

    app.run(
        host="0.0.0.0",
        port=port
    )