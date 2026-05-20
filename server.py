from flask import Flask, request, jsonify
from flask_cors import CORS
import pandas as pd

app = Flask(__name__)
CORS(app)

# chỉ load file csv (nhẹ)
print("Loading database...")
df = pd.read_csv("news.csv")

# chưa load AI vội
model = None
news_vectors = None

def load_ai():
    global model, news_vectors
    if model is None:
        print("Loading AI model (first request only)...")
        from sentence_transformers import SentenceTransformer
        from sklearn.metrics.pairwise import cosine_similarity
        
        model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
        news_vectors = model.encode(df["title"].tolist())
        print("AI ready!")

@app.route("/")
def home():
    return "Semantic News API is running!"

@app.route("/search", methods=["POST"])
def search():
    load_ai()  # chỉ load AI khi có request đầu tiên
    
    from sklearn.metrics.pairwise import cosine_similarity

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

app.run(host="0.0.0.0", port=5000)