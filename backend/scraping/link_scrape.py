import os
import re
import sys
import argparse
from datetime import datetime
from typing import List, Tuple

import requests
from bs4 import BeautifulSoup

DOCS_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "mitre_enterprise_techniques.txt"
)
techniques = "MITRE/techniques"
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), techniques)


def parse_links_from_docs(path: str) -> List[Tuple[str, str]]:
    """
    Parse lines of format: "TXXXX - Name - URL" and return [(technique_id, url)].
    Fallback: find first URL on a line and derive ID from URL.
    """
    links: List[Tuple[str, str]] = []
    if not os.path.isfile(path):
        print(f"Input file not found: {path}")
        return links

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("Source:") or line.startswith("Terms:"):
                continue
            # Expected format
            parts = [p.strip() for p in line.split(" - ")]
            url = None
            technique_id = None
            if len(parts) >= 3 and parts[2].startswith("http"):
                technique_id = parts[0]
                url = parts[2]
            else:
                # Fallback: URL anywhere in line
                m = re.search(r"https?://\S+", line)
                if m:
                    url = m.group(0)
                    technique_id = derive_id_from_url(url)
            if technique_id and url:
                links.append((technique_id, url))
    return links


def derive_id_from_url(url: str) -> str:
    # https://attack.mitre.org/techniques/T1548/ or /techniques/T1548/001/
    m = re.search(r"/techniques/(T\d+)(?:/(\d{3})/?)?", url)
    if not m:
        return "unknown"
    base = m.group(1)
    sub = m.group(2)
    return f"{base}.{sub}" if sub else base


def fetch_page(url: str) -> str:
    resp = requests.get(
        url, timeout=30, headers={"User-Agent": "Mozilla/5.0 (compatible; scraper/1.0)"}
    )
    resp.raise_for_status()
    return resp.text


def extract_title_and_paragraphs(
    html: str, max_paragraphs: int | None = None
) -> Tuple[str, List[str]]:
    soup = BeautifulSoup(html, "html.parser")

    # Title: prefer first h1; fallback to page <title>
    title = ""
    h1 = soup.find("h1")
    if h1 and h1.get_text(strip=True):
        title = h1.get_text(strip=True)
    else:
        ttag = soup.find("title")
        title = ttag.get_text(strip=True) if ttag else "(no title)"

    # Try preferred container: all text under .col-md-8 > .description-body
    container = soup.select_one(".col-md-8 .description-body")
    if container:
        body_text = container.get_text(" ", strip=True)
        return title, [body_text]

    # Fallback: collect first meaningful paragraphs under main/content
    def paragraph_texts(root):
        texts = []
        for p in root.find_all("p"):
            txt = p.get_text(" ", strip=True)
            if not txt:
                continue
            # Skip cookie banners or miscellaneous noise
            if "cookies" in txt.lower() and "privacy" in txt.lower():
                continue
            texts.append(txt)
        return texts

    main = soup.find("main") or soup.find("div", attrs={"role": "main"}) or soup
    paragraphs = paragraph_texts(main)
    # Return up to max_paragraphs, without truncating paragraph content
    selected = paragraphs if max_paragraphs is None else paragraphs[:max_paragraphs]
    return title, selected


def write_txt(
    technique_id: str, title: str, url: str, paragraphs: List[str], out_dir: str
) -> str:
    os.makedirs(out_dir, exist_ok=True)
    filename = f"{technique_id}.txt"
    path = os.path.join(out_dir, filename)
    header = [
        f"ID: {technique_id}",
        f"Title: {title}",
        f"URL: {url}",
    ]
    # Flatten all summary paragraphs into a single paragraph (no internal newlines)
    if paragraphs:
        normalized = [re.sub(r"\s+", " ", p).strip() for p in paragraphs]
        body = " ".join(normalized).strip()
    else:
        body = "(no summary)"
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(header) + "\n" + body + "\n")
    return path


def run(input_file: str, out_dir: str, limit: int | None = None):
    links = parse_links_from_docs(input_file)
    if not links:
        print("No links parsed.")
        return

    count = 0
    for technique_id, url in links:
        try:
            html = fetch_page(url)
            title, paragraphs = extract_title_and_paragraphs(html)
            path = write_txt(technique_id, title, url, paragraphs, out_dir)
            print(f"Saved: {path}")
            count += 1
            if limit and count >= limit:
                break
        except Exception as e:
            print(f"Failed for {technique_id} {url}: {e}")

    print(f"Total saved: {count}")


def main():
    parser = argparse.ArgumentParser(
        description="Scrape MITRE technique pages into per-technique .txt files."
    )
    parser.add_argument(
        "--input", default=DOCS_FILE, help="Path to mitre_enterprise_techniques.txt"
    )
    parser.add_argument(
        "--out",
        default=OUTPUT_DIR,
        help="Output directory (defaults to backend/scraping)",
    )
    parser.add_argument(
        "--limit", type=int, default=None, help="Limit number of pages to scrape"
    )
    args = parser.parse_args()

    run(args.input, args.out, args.limit)


if __name__ == "__main__":
    main()
