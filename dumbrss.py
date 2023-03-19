#! /usr/bin/env python3

import argparse
import shutil
import tomllib
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from xml.etree.ElementTree import Element

import requests
from defusedxml import ElementTree as xml

CODE_DIR = Path(__file__).parent
HTML_FMT = """
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>RSS</title>
    <link rel="stylesheet" href="./style.css">
    <link rel="icon" href="./favicon.ico" type="image/x-icon">
  </head>
  <body>
    <main>
        {}
    </main>
  </body>
</html>
"""

ARTICLE_FMT = """
<li class="article">
    {date} - <a href="{link}" target="new">{title}</a>
    <br/>
    <div class="article-description">{description}</div>
</li>
"""

FEED_FMT = """
<div class="feed">
    <a href="{link}" target="new"><h2>{title}</h2></a>
    <ul class="article-list">
        {articles}
    </ul>
</div>
"""

CATEGORY_FMT = """
<div class="category">
    <h1 class="category-title">{title}</h1>
    {feeds}
</div>
"""


@dataclass
class Article:
    title: str = ""
    link: str = ""
    description: str | None = ""
    date: datetime | None = None

    @staticmethod
    def parse_dt(s: str) -> datetime:
        return datetime.strptime(" ".join(s.split(" ")[1:4]), "%d %b %Y")

    @staticmethod
    def parse_description(s: str) -> str:
        bad = "appeared first on"
        return "\n".join(ln for ln in s.splitlines() if ln and bad not in ln)

    @classmethod
    def parse(cls, item: Element) -> "Article":
        article = cls()
        for el in item:
            match el.tag:
                case "pubDate":
                    article.date = cls.parse_dt(el.text) if el.text else None
                case "description":
                    article.description = cls.parse_description(el.text) if el.text else None

                case _:
                    if hasattr(article, el.tag):
                        setattr(article, el.tag, el.text)
        return article

    def format(self):
        kwargs = asdict(self)
        if self.date:
            kwargs["date"] = datetime.strftime(self.date, "%x")
        return ARTICLE_FMT.format(**kwargs)


@dataclass
class Feed:
    title: str = ""
    link: str = ""
    articles: list[Article] = field(default_factory=list)

    @classmethod
    def parse(cls, url: str) -> "Feed":
        resp = requests.get(url)
        if not resp.ok:
            raise RuntimeError(f"Failed to fetch: {url}")

        data = xml.fromstring(resp.text)
        feed = cls()
        for el in data[0]:
            match el.tag:
                case "item":
                    feed.articles.append(Article.parse(el))
                case _:
                    if hasattr(feed, el.tag):
                        setattr(feed, el.tag, el.text)

        print("Fetched", feed.title)
        return feed

    def format(self):
        kwargs = asdict(self)
        kwargs["articles"] = "<br/>".join(a.format() for a in self.articles)
        return FEED_FMT.format(**kwargs)


def main(args):
    assert args.output.is_dir()
    categories = []
    for category, urls in tomllib.load(args.config.open("rb")).items():
        feeds = []
        for url in urls:
            feeds.append(Feed.parse(url).format())

        categories.append(CATEGORY_FMT.format(title=category, feeds="\n".join(feeds)))

    html_file = args.output / "index.html"
    html_file.write_text(HTML_FMT.format("\n".join(categories)))
    if args.output != CODE_DIR:
        shutil.copy(CODE_DIR / "style.css", args.output / "style.css")


def path_arg(s: str):
    return Path(s).expanduser()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-c",
        "--config",
        type=path_arg,
        default="config.toml",
        help="Config file holding categories of feeds",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=path_arg,
        default=CODE_DIR,
        help="Directory in which to output web assets",
    )

    main(parser.parse_args())
