import os
import re
import json
import requests
import lxml.etree
import urllib3
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin, urlunparse, quote, unquote
import html  # for HTML unescape

# -------- CONFIG --------
BASE_URL = ""
SITEMAP_URL = f"{BASE_URL}/sitemap.xml"
DOWNLOAD_DIR = "downloaded_site"
REPORT_PATH = "crawl_report.md"
HTML_EXTENSIONS = ('.html', '', '/')

visited_pages = set()
visited_assets = set()
to_visit_pages = set()

success_pages = []
failed_pages = []
success_assets = []
failed_assets = []

# -------- INIT --------
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# -------- UTILS --------
def clean_url(url):
    url = html.unescape(url)
    parsed = urlparse(url)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, '', '', ''))

def is_internal(url):
    parsed = urlparse(url)
    return not parsed.netloc or parsed.netloc == urlparse(BASE_URL).netloc

def safe_path_from_url(url):
    parsed = urlparse(url)
    path = parsed.path.lstrip("/")
    if path.endswith("/") or path == "":
        path = os.path.join(path, "index.html")
    safe_path = quote(path, safe="/")
    return os.path.join(DOWNLOAD_DIR, safe_path)

def save_response_content(url, content):
    save_path = safe_path_from_url(url)
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    with open(save_path, "wb") as f:
        f.write(content)
    print(f"    └── Saved: {save_path}")

def extract_links(html_content, base_url):
    html_content = html.unescape(html_content)
    soup = BeautifulSoup(html_content, "html.parser")
    html_links = set()
    asset_links = set()

    tags_attrs = {
        "a": "href",
        "link": "href",
        "script": "src",
        "img": ["src", "data-src", "data-bg"],
        "source": "src",
        "iframe": "src",
    }

    for tag, attrs in tags_attrs.items():
        for element in soup.find_all(tag):
            if isinstance(attrs, list):
                for attr in attrs:
                    raw = element.get(attr)
                    if raw:
                        full_url = urljoin(base_url, html.unescape(raw))
                        if is_internal(full_url):
                            (html_links if full_url.endswith(HTML_EXTENSIONS) else asset_links).add(clean_url(full_url))
            else:
                raw = element.get(attrs)
                if raw:
                    full_url = urljoin(base_url, html.unescape(raw))
                    if is_internal(full_url):
                        (html_links if full_url.endswith(HTML_EXTENSIONS) else asset_links).add(clean_url(full_url))

    css_urls = re.findall(r'url\(["\']?(.*?)["\']?\)', html_content)
    for raw in css_urls:
        if raw.startswith('data:'):
            continue
        full_url = urljoin(base_url, html.unescape(raw))
        if is_internal(full_url):
            asset_links.add(clean_url(full_url))

    return html_links, asset_links

# -------- LOAD SITEMAP --------
print("📡 Loading sitemap...")
try:
    response = requests.get(SITEMAP_URL, verify=False, timeout=10)
    response.encoding = 'utf-8'
    sitemap_tree = lxml.etree.fromstring(response.content)
    sitemap_urls = sitemap_tree.xpath("//ns:url/ns:loc/text()", namespaces={
        "ns": "http://www.sitemaps.org/schemas/sitemap/0.9"
    })
    to_visit_pages = {clean_url(url) for url in sitemap_urls if is_internal(url)}
    print(f"[✓] Loaded {len(to_visit_pages)} URLs from sitemap")
except Exception as e:
    print(f"[✗] Failed to load sitemap: {e}")
    to_visit_pages = {BASE_URL}
    sitemap_urls = list(to_visit_pages)

# -------- MAIN LOOP --------
while to_visit_pages:
    url = to_visit_pages.pop()
    if url in visited_pages:
        continue
    visited_pages.add(url)

    try:
        print(f"\nDownloading page: {url}")
        resp = requests.get(url, verify=False, timeout=10)
        resp.raise_for_status()
        resp.encoding = 'utf-8'
        save_response_content(url, resp.content)
        success_pages.append(url)

        html_links, asset_links = extract_links(resp.text, url)
        to_visit_pages.update(html_links - visited_pages)

        for asset_url in asset_links:
            if asset_url in visited_assets:
                continue
            visited_assets.add(asset_url)
            try:
                print(f"    ⤷ Downloading asset: {asset_url}")
                asset_resp = requests.get(asset_url, verify=False, timeout=10)
                asset_resp.raise_for_status()
                save_response_content(asset_url, asset_resp.content)
                success_assets.append(asset_url)
            except Exception as e:
                print(f"    [✗] Failed to download asset {asset_url}: {e}")
                failed_assets.append(asset_url)

    except Exception as e:
        print(f"[✗] Failed to download page {url}: {e}")
        failed_pages.append(url)

# Count and print
url_count = len(sitemap_urls)
print(f"Total URLs found: {url_count}")

# -------- FINAL REPORT --------
print("\nWriting crawl report...")

with open(REPORT_PATH, "w", encoding="utf-8") as f:
    f.write("#Crawl Report\n\n")
    f.write(f"**Base URL:** {BASE_URL}\n")
    f.write(f"**Total Success Pages:** {len(success_pages)}\n")
    f.write(f"**Total Failed Pages:** {len(failed_pages)}\n")
    f.write(f"**Total Success Assets:** {len(success_assets)}\n")
    f.write(f"**Total Failed Assets:** {len(failed_assets)}\n\n")

    f.write("##Successful Pages:\n")
    for url in success_pages:
        f.write(f"- {url}\n")
    f.write("\n##Failed Pages:\n")
    for url in failed_pages:
        f.write(f"- {url}\n")
    f.write("\n##Successful Assets:\n")
    for url in success_assets:
        f.write(f"- {url}\n")
    f.write("\n##Failed Assets:\n")
    for url in failed_assets:
        f.write(f"- {url}\n")

# Save failed pages to JSON
with open("failed_pages.json", "w", encoding="utf-8") as f:
    json.dump(failed_pages, f, ensure_ascii=False, indent=2)

print(f"[✓] Report saved to {REPORT_PATH}")
print(f"[✓] Failed pages JSON saved to failed_pages.json")