import feedparser
import pandas as pd

rss_urls = {
    "VnExpress": "https://vnexpress.net/rss/tin-moi-nhat.rss",
    "TuoiTre": "https://tuoitre.vn/rss/tin-moi-nhat.rss",
    "ThanhNien": "https://thanhnien.vn/rss/home.rss",
    
    "BaoChinhPhu": "https://baochinhphu.vn/rss/home.rss",
    "BaoNhanDan": "https://nhandan.vn/rss/home.rss",
    "BaoCongAn": "https://cand.com.vn/rss/",
    
    "BoYTe": "https://moh.gov.vn/rss/home.rss",
    "BoGiaoDuc": "https://moet.gov.vn/rss/Pages/home.aspx",
    "QuocHoi": "https://quochoi.vn/rss/default.aspx"
}

all_articles = []

for source, url in rss_urls.items():
    feed = feedparser.parse(url)
    
    for entry in feed.entries:
        content = entry.summary if "summary" in entry else entry.title
        
        all_articles.append({
            "source": source,
            "title": entry.title,
            "link": entry.link,
            "content": content   # ← QUAN TRỌNG
        })

df = pd.DataFrame(all_articles)
df.to_csv("news.csv", index=False)

print("Đã tải xong", len(df), "bài báo")