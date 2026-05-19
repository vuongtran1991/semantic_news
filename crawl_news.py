import feedparser
import pandas as pd

rss_urls = {
    "VnExpress": "https://vnexpress.net/rss/tin-moi-nhat.rss",
    "TuoiTre": "https://tuoitre.vn/rss/tin-moi-nhat.rss",
    "ThanhNien": "https://thanhnien.vn/rss/home.rss",
    "BaoChinhPhu": "https://baochinhphu.vn/rss/home.rss",
    "BaoNhanDan": "https://nhandan.vn/rss/home.rss",
}

all_articles = []

for source, url in rss_urls.items():
    feed = feedparser.parse(url)
    for entry in feed.entries:
        all_articles.append({
            "source": source,
            "title": entry.title,
            "link": entry.link,
            "summary": entry.summary
        })

df = pd.DataFrame(all_articles)
df.to_csv("news.csv", index=False)

print("Đã tạo database:", len(df), "bài báo")