import os
import re
import argparse
import logging
import time
from typing import List, Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

BASE_URL = "https://www.darkreading.com"
HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_OUTPUT_DIR = os.path.join(HERE, "darkreader")

REQUEST_DELAY = 1.5
MAX_RETRIES = 3
REQUEST_TIMEOUT = 30

TOPICS = [
    "application-security",
    "cybersecurity-careers",
    "cloud-security",
    "cyber-risk",
    "cyberattacks-data-breaches",
    "cybersecurity-analytics",
    "cybersecurity-operations",
    "data-privacy",
    "endpoint-security",
    "ics-ot-security",
    "identity-access-mgmt-security",
    "insider-threats",
    "iot",
    "mobile-security",
    "perimeter",
    "physical-security",
    "remote-workforce",
    "threat-intelligence",
    "vulnerabilities-threats",
    "dr-global",
    "dr-technology",
    "the-edge",
]


def _make_request(url: str) -> Optional[str]:
    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.get(
                url,
                timeout=REQUEST_TIMEOUT,
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; DarkReaderScraper/1.0)"
                },
            )
            resp.raise_for_status()
            return resp.text
        except requests.RequestException as e:
            logger.warning(
                "Attempt %d/%d failed for %s: %s",
                attempt + 1,
                MAX_RETRIES,
                url,
                e,
            )
            if attempt < MAX_RETRIES - 1:
                time.sleep(2**attempt)
    return None


_NON_ARTICLE_PREFIXES = {"author", "keyword", "program", "series", "topic", "tag", "category"}


def _is_article_path(path: str) -> bool:
    parts = path.strip("/").split("/")
    if len(parts) < 2:
        return False
    if parts[0] in _NON_ARTICLE_PREFIXES:
        return False
    slug_re = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
    return all(re.match(slug_re, p) for p in parts)


def discover_topics() -> List[str]:
    topics = []
    html = _make_request(BASE_URL)
    if not html:
        logger.warning("Could not fetch homepage, falling back to known topics")
        return [f"{BASE_URL}/{t}" for t in TOPICS]

    soup = BeautifulSoup(html, "html.parser")
    seen = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        m = re.match(r"^/([a-z0-9]+(?:-[a-z0-9]+)*)$", href)
        if m and m.group(1) not in seen:
            seen.add(m.group(1))
            topics.append(urljoin(BASE_URL, href))

    if not topics:
        topics = [f"{BASE_URL}/{t}" for t in TOPICS]

    return topics


def discover_article_urls(topic_url: str, max_pages: int = 0) -> List[str]:
    article_urls: List[str] = []
    seen = set()

    page_num = 1
    while True:
        if max_pages > 0 and page_num > max_pages:
            break
        url = topic_url if page_num == 1 else f"{topic_url}?page={page_num}"
        logger.info("Discovering articles from page %d: %s", page_num, url)

        html = _make_request(url)
        if not html:
            break

        soup = BeautifulSoup(html, "html.parser")
        found = False

        for a in soup.find_all("a", href=True):
            href = a["href"]
            if not _is_article_path(href):
                continue
            full_url = urljoin(BASE_URL, href)
            if full_url not in seen:
                seen.add(full_url)
                article_urls.append(full_url)
                found = True

        if not found:
            break

        page_num += 1
        time.sleep(REQUEST_DELAY)

    return article_urls


def extract_article(html: str, url: str) -> Optional[dict]:
    soup = BeautifulSoup(html, "html.parser")

    # Title
    title = ""
    h1 = soup.find("h1")
    if h1 and h1.get_text(strip=True):
        title = h1.get_text(strip=True)
    else:
        ttag = soup.find("title")
        if ttag:
            title = re.sub(
                r"\s*\| Dark Reading.*$", "", ttag.get_text(strip=True)
            ).strip()

    if not title:
        logger.warning("No title found for %s", url)
        return None

    # Author
    author = ""
    for sel in [
        ".author-name",
        ".byline",
        "[rel='author']",
        ".article-author",
        ".contributor",
    ]:
        el = soup.select_one(sel)
        if el:
            author = el.get_text(strip=True)
            break

    if not author:
        for tag in soup.find_all(["p", "span", "div"]):
            text = tag.get_text(strip=True)
            m = re.match(r"^by\s+(.+)$", text, re.IGNORECASE)
            if m:
                author = m.group(1).strip()
                break

    if not author:
        author = "(unknown)"

    # Date
    date_str = ""
    for sel in ["time", "[datetime]", ".article-date", ".published-date", ".date"]:
        el = soup.select_one(sel)
        if el:
            date_str = el.get_text(strip=True)
            if el.has_attr("datetime"):
                date_str = el["datetime"]
            break

    if not date_str:
        date_str = "(unknown)"

    # Topic from URL
    topic = ""
    parsed = urlparse(url)
    path_parts = parsed.path.strip("/").split("/")
    if path_parts:
        topic = path_parts[0]

    # Paragraphs
    STOP_HEADINGS = re.compile(
        r"about\s+the\s+(author|contributor|writer)", re.I
    )
    STOP_PARAGRAPHS = re.compile(
        r"about\s+the\s+(author|contributor|writer)|"
        r"more\s+(from|recently|in)\b|"
        r"now\s+playing|"
        r"want\s+more\s+dark\s+reading|"
        r"copyright|"
        r"all\s+rights\s+reserved|"
        r"cookie|privacy\s+policy|terms\s+of\s+use|"
        r"subscribe|newsletter|"
        r"follow\s+us|sign\s+up|"
        r"your\s+privacy\s+choices|"
        r"use\s+code|get\s+your\s+pass|discover\s+more|"
        r"see\s+more\s+from|"
        r"related\s+topics?|"
        r"recent\s+in\s+.*topics?|"
        r"\btopic\b|"
        r"\bauthor\b",
        re.I,
    )

    container = (
        soup.find("article")
        or soup.find("main")
        or soup.find("div", class_=re.compile(r"(article|content|story|body)", re.I))
        or soup.find("div", role="main")
    )

    paragraphs = []
    source = container if container else soup

    for el in source.find_all(["p", "h2", "h3", "h4"]):
        text = el.get_text(" ", strip=True)
        if not text:
            continue
        lower = text.lower()

        # Stop at "About the Author" or similar section headers
        if el.name in ("h2", "h3", "h4") and STOP_HEADINGS.search(lower):
            break

        if el.name == "p":
            if STOP_PARAGRAPHS.search(lower):
                continue
            if len(text) < 20:
                continue
            paragraphs.append(text)

    if not paragraphs:
        return None

    return {
        "title": title,
        "url": url,
        "author": author,
        "date": date_str,
        "topic": topic,
        "paragraphs": paragraphs,
    }


def save_article(article: dict, output_dir: str) -> str:
    topic = article.get("topic", "uncategorized")
    topic_dir = os.path.join(output_dir, topic)
    os.makedirs(topic_dir, exist_ok=True)
    safe = re.sub(r"[^\w\s-]", "", article["title"]).strip()
    safe = re.sub(r"[-\s]+", "_", safe)[:100]
    filename = f"{safe}.txt"
    path = os.path.join(topic_dir, filename)

    lines = [
        f"Title: {article['title']}",
        f"URL: {article['url']}",
        f"Author: {article['author']}",
        f"Date: {article['date']}",
        f"Topic: {article['topic']}",
        "",
    ]
    for p in article["paragraphs"]:
        lines.append(p)
        lines.append("")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return path


def save_url_list(urls: List[str], path: str):
    with open(path, "w", encoding="utf-8") as f:
        for url in sorted(urls):
            f.write(url + "\n")


def load_url_list(path: str) -> List[str]:
    urls = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                urls.append(line)
    return urls


def run(
    max_pages: int = 0,
    max_articles: Optional[int] = None,
    topics: Optional[List[str]] = None,
    output_dir: Optional[str] = None,
    url_list_path: Optional[str] = None,
    discover_only: bool = False,
    skip_discover: bool = False,
    delay: float = 1.5,
):
    global REQUEST_DELAY
    REQUEST_DELAY = delay

    if output_dir is None:
        output_dir = DEFAULT_OUTPUT_DIR
    os.makedirs(output_dir, exist_ok=True)

    # Phase 1: Discover article URLs
    all_urls: List[str] = []

    if skip_discover and url_list_path and os.path.exists(url_list_path):
        all_urls = load_url_list(url_list_path)
        logger.info("Loaded %d URLs from %s", len(all_urls), url_list_path)

    if not all_urls:
        if topics:
            topic_urls = [
                url if url.startswith("http") else urljoin(BASE_URL, url)
                for url in topics
            ]
        else:
            topic_urls = discover_topics()

        logger.info("Discovered %d topics", len(topic_urls))
        seen = set()
        for topic_url in topic_urls:
            logger.info("Crawling topic: %s", topic_url)
            article_urls = discover_article_urls(topic_url, max_pages)
            for u in article_urls:
                if u not in seen:
                    seen.add(u)
                    all_urls.append(u)
            logger.info("Found %d unique article URLs so far", len(all_urls))

        logger.info("Total unique article URLs discovered: %d", len(all_urls))

    if url_list_path:
        save_url_list(all_urls, url_list_path)
        logger.info("Saved URL list to %s", url_list_path)

    if discover_only:
        return

    # Phase 2: Scrape articles
    if not all_urls:
        logger.error("No article URLs to scrape.")
        return

    count = 0
    errors = 0
    to_scrape = all_urls[:max_articles] if max_articles else all_urls

    for i, url in enumerate(to_scrape):
        try:
            logger.info("Scraping [%d/%d]: %s", i + 1, len(to_scrape), url)
            html = _make_request(url)
            if not html:
                errors += 1
                continue

            article = extract_article(html, url)
            if article:
                path = save_article(article, output_dir)
                logger.info("Saved: %s", path)
                count += 1
            else:
                errors += 1

            time.sleep(REQUEST_DELAY)
        except Exception as e:
            logger.error("Failed for %s: %s", url, e)
            errors += 1

    logger.info("Done. Saved %d articles, %d errors", count, errors)


def main():
    parser = argparse.ArgumentParser(
        description="Dark Reading article scraper — discover endpoints and extract content paragraph-by-paragraph.",
    )
    parser.add_argument(
        "--discover-only",
        action="store_true",
        help="Only discover article URLs, do not scrape content",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=0,
        help="Max listing pages to crawl per topic (0 = unlimited, default: 0)",
    )
    parser.add_argument(
        "--max-articles",
        type=int,
        default=None,
        help="Max articles to scrape (default: all discovered)",
    )
    parser.add_argument(
        "--topics",
        nargs="*",
        help="Specific topic slugs to crawl (e.g., cyberattacks-data-breaches)",
    )
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT_DIR,
        help=f"Output directory for article files (default: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--url-list",
        default=None,
        help="Path to save/load article URL list (auto-detects: loads if exists, creates if not)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.5,
        help="Delay between requests in seconds (default: 1.5)",
    )
    parser.add_argument(
        "--skip-discover",
        action="store_true",
        help="Skip discovery (requires --url-list with existing file)",
    )

    args = parser.parse_args()

    skip_discover = args.skip_discover
    if skip_discover and not (args.url_list and os.path.exists(args.url_list)):
        parser.error(
            "--skip-discover requires --url-list pointing to an existing file."
        )

    run(
        max_pages=args.max_pages,
        max_articles=args.max_articles,
        topics=args.topics,
        output_dir=args.output,
        url_list_path=args.url_list,
        discover_only=args.discover_only,
        skip_discover=skip_discover,
        delay=args.delay,
    )


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    main()
