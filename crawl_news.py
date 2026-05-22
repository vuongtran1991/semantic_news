import feedparser
import pandas as pd
from datetime import datetime

rss_urls = {
    "VnExpress": "https://vnexpress.net/rss/tin-moi-nhat.rss",
    "TuoiTre": "https://tuoitre.vn/rss/tin-moi-nhat.rss",
    "ThanhNien": "https://thanhnien.vn/rss/home.rss",
    "BaoChinhPhu": "https://baochinhphu.vn/rss/home.rss",
    "BaoNhanDan": "https://nhandan.vn/rss/home.rss",
}

all_articles = []

for source, url in rss_urls.items():

    print(f"Đang lấy: {source}")

    feed = feedparser.parse(url)

    print("Số bài:", len(feed.entries))

    for entry in feed.entries:

        title = entry.get("title", "")
        link = entry.get("link", "")
        summary = entry.get("summary", "")

        all_articles.append({
            "source": source,
            "title": title,
            "link": link,
            "summary": summary,
            "created_at": datetime.now()
        })

df = pd.DataFrame(all_articles)

df.drop_duplicates(
    subset=["title"],
    inplace=True
)

df.to_csv(
    "news.csv",
    index=False,
    encoding="utf-8-sig"
)

print("Đã tạo database:", len(df), "bài báo")