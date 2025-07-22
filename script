#!/bin/bash

# ====== CONFIGURATION ======
SITEMAP_URL="https://example.com/sitemap.xml"
PAGES_DIR="pages"
SITEMAP_FILE="sitemap.xml"
URL_LIST="urls.txt"
ASSETS_FILE="assets.txt"

# ====== STEP 1: Download Sitemap ======
echo "[1] Downloading sitemap..."
curl -s "$SITEMAP_URL" -o "$SITEMAP_FILE"

if [ ! -s "$SITEMAP_FILE" ]; then
  echo "Failed to download sitemap."
  exit 1
fi

# ====== STEP 2: Extract URLs ======
echo "[2] Extracting URLs from sitemap..."
xmllint --xpath "//url/loc/text()" "$SITEMAP_FILE" > "$URL_LIST"

URL_COUNT=$(wc -l < "$URL_LIST")
echo "Found $URL_COUNT URLs."

# ====== STEP 3: Download Webpages ======
echo "[3] Downloading HTML pages..."
mkdir -p "$PAGES_DIR"

while read -r url; do
  filename=$(echo "$url" | sed 's|https\?://||; s|/|_|g')
  curl -s "$url" -o "$PAGES_DIR/${filename}.html"
  echo "Saved $url to $PAGES_DIR/${filename}.html"
done < "$URL_LIST"

# ====== STEP 4: Extract Asset URLs ======
echo "[4] Extracting asset URLs..."
> "$ASSETS_FILE"

for file in "$PAGES_DIR"/*.html; do
  grep -Eo 'src="[^"]+"|href="[^"]+"' "$file" \
    | sed -E 's/(src|href)="([^"]+)"/\2/' \
    | grep -E '^https?://' >> "$ASSETS_FILE"
done

sort -u "$ASSETS_FILE" -o "$ASSETS_FILE"

ASSET_COUNT=$(wc -l < "$ASSETS_FILE")
echo "Found $ASSET_COUNT unique asset URLs."
