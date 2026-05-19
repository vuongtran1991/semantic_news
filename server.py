from flask import Flask, request, jsonify
from flask_cors import CORS
import pandas as pd
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

print("Đang load database...")
df = pd.read_csv("news.csv")

print("Đang load AI model...")
model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')

print("Đang tạo vector cho bài báo...")
news_vectors = model.encode(df["title"].tolist())

app = Flask(__name__)
CORS(app)

@app.route("/search", methods=["POST"])
def search():
    data = request.json
    query = data["query"]

    query_vector = model.encode([query])
    scores = cosine_similarity(query_vector, news_vectors)[0]

    top_indices = scores.argsort()[-5:][::-1]

    results = []
    for idx in top_indices:
        results.append({
            "title": df.iloc[idx]["title"],
            "link": df.iloc[idx]["link"],
            "source": df.iloc[idx]["source"]
        })

    return jsonify({"results": results})

print("Server ready!")

app.run(host="0.0.0.0", port=5000)