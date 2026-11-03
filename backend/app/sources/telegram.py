"""Public Telegram channels, read from their web view (t.me/s/<channel>)."""

from bs4 import BeautifulSoup

from app.scraping.fetcher import FetchError, fetch_html
from app.sources.base import Post, Source, SourceResult, posts_result, to_day

MAX_POSTS = 20


class TelegramSource(Source):
    name = "telegram"

    def read(self, url: str) -> SourceResult:
        page = fetch_html(url)
        soup = BeautifulSoup(page.content, "lxml")
        posts = []
        for message in soup.select(".tgme_widget_message[data-post]"):
            body = message.select_one(".tgme_widget_message_text")
            text = body.get_text("\n") if body else ""
            if not text.strip():
                continue  # photos or stickers without a caption
            stamp = message.select_one("time[datetime]")
            posts.append(Post(
                day=to_day(stamp["datetime"]) if stamp else "",
                text=text,
                link=f"https://t.me/{message['data-post']}",
            ))
        if not posts:
            raise FetchError("No public posts found: is this a public Telegram channel?")
        # the web view lists oldest first
        return posts_result(page.url, posts[-MAX_POSTS:][::-1], self.name)
