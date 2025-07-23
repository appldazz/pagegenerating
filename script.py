import os
import re
import html
import requests
import urllib3
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urlunparse, urljoin, unquote
from tqdm import tqdm
from typing import Optional

# -------------------- Konfigurasi --------------------
BASE_URL = "https://ec2-47-129-150-75.ap-southeast-1.compute.amazonaws.com/"  # Ganti dengan domain target
SITEMAP_URL = f"{BASE_URL}/sitemap.xml"
DOWNLOAD_DIR = "downloaded_site"
SKIP_SCHEMES = ("javascript:", "mailto:", "tel:", "data:", "sms:")
visited_urls = set()

# Nonaktifkan warning SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Setup session
session = requests.Session()
session.headers.update({'User-Agent': 'Mozilla/5.0'})


# -------------------- Utilitas --------------------
def sanitize_url(url):
    url = html.unescape(url)
    parsed = urlparse(url)
    clean_path = parsed.path
    return urlunparse((parsed.scheme, parsed.netloc, clean_path, '', '', ''))


def url_to_path(url):
    path = urlparse(url).path
    if path.endswith("/"):
        path += "index.html"
    elif not os.path.splitext(path)[1]:  # Tanpa ekstensi
        path += "/index.html"
    full_path = os.path.join(DOWNLOAD_DIR, unquote(path.lstrip("/")))
    return full_path


def save_file(url, content):
    path = url_to_path(url)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(content)


def is_internal(url):
    p = urlparse(url)
    if p.scheme not in ("http", "https", ""):
        return False
    base_netloc = urlparse(BASE_URL).netloc
    return not p.netloc or p.netloc == base_netloc


def clean_link(raw_link: str) -> Optional[str]:
    if not raw_link:
        return None
    link = html.unescape(raw_link).strip()
    if link.startswith("#"):
        return None
    l_lower = link.lower()
    if l_lower.startswith(SKIP_SCHEMES):
        return None
    if "javascript" in l_lower and "(" in l_lower:
        return None
    return link


# -------------------- Main Downloader --------------------
def extract_urls_from_sitemap(xml_text):
    soup = BeautifulSoup(xml_text, "xml")
    urls = [sanitize_url(loc.text) for loc in soup.find_all("loc")]
    return urls


def download_url(url):
    url = sanitize_url(url)
    if url in visited_urls:
        return
    visited_urls.add(url)

    try:
        response = session.get(url, verify=False, timeout=10)
        response.raise_for_status()
        content_type = response.headers.get("Content-Type", "")

        save_file(url, response.content)

        if 'text/html' in content_type:
            extract_and_download_links(url, response.text)

    except Exception as e:
        print(f"[✗] Failed to download {url}: {e}")


def extract_and_download_links(base_url, html_text):
    soup = BeautifulSoup(html_text, "lxml")
    attrs = ["href", "src", "data-src", "data-bg"]

    for tag in soup.find_all(True):
        for attr in attrs:
            raw_link = tag.get(attr)
            cleaned = clean_link(raw_link)
            if not cleaned:
                continue
            full_url = urljoin(base_url, cleaned)
            if is_internal(full_url):
                download_url(full_url)

        # inline CSS url("...") detection
        style = tag.get("style", "")
        matches = re.findall(r"url\([\"']?([^\"')]+)[\"']?\)", style)
        for raw in matches:
            cleaned = clean_link(raw)
            if not cleaned:
                continue
            full_url = urljoin(base_url, cleaned)
            if is_internal(full_url):
                download_url(full_url)


# -------------------- Main Entry --------------------
def main():
    try:
        print(f"[~] Mengunduh sitemap dari {SITEMAP_URL}")
        response = session.get(SITEMAP_URL, verify=False)
        response.raise_for_status()
        sitemap_urls = extract_urls_from_sitemap(response.text)

        print(f"[✓] {len(sitemap_urls)} URL ditemukan.\nMulai crawling...\n")
        for url in tqdm(sitemap_urls):
            download_url(url)

        print("\n[✓] Selesai.")

    except Exception as e:
        print(f"[✗] Gagal mengunduh sitemap: {e}")


if __name__ == "__main__":
    main()
