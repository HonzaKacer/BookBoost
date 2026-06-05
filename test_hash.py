"""
Testovací skript – porovná referenční obálku s obrázky z AbeBooks nabídek.
Vypíše hash rozdíl pro každou nabídku, abychom věděli jaký HASH_THRESHOLD nastavit.
"""

import requests
from bs4 import BeautifulSoup
from PIL import Image
import imagehash
import io


# -------------------------
# Nastavení
# -------------------------
ISBN = "9781111307301"
REFERENCE_IMAGE = "cover.jpg"
MAX_OFFERS_TO_TEST = 5  # kolik nabídek otestovat


# -------------------------
# Referenční hash
# -------------------------
def get_reference_hash():
    h = imagehash.phash(Image.open(REFERENCE_IMAGE))
    print(f"Referenční hash: {h}\n")
    return h


# -------------------------
# Stažení seznamu nabídek z AbeBooks
# -------------------------
def get_abebooks_offers():
    url = f"https://www.abebooks.com/servlet/SearchResults?isbn={ISBN}"
    response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
    print(f"AbeBooks seznam status: {response.status_code}")
    soup = BeautifulSoup(response.text, "html.parser")

    offers = []
    for offer in soup.find_all("h2", itemprop="offers"):
        url_tag = offer.find("a", itemprop="url")
        if url_tag:
            offers.append("https://www.abebooks.com" + url_tag["href"])
    return offers


# -------------------------
# Stažení obrázku obálky z detailu nabídky
# -------------------------
def get_cover_image_url(offer_url):
    response = requests.get(
        offer_url,
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=20
    )
    soup = BeautifulSoup(response.text, "html.parser")

    # AbeBooks má obrázek obálky v <img id="main-image"> nebo itemprop="image"
    for selector in [
        {"id": "main-image"},
        {"itemprop": "image"},
        {"class": "book-image"},
    ]:
        img = soup.find("img", selector)
        if img and img.get("src"):
            return img["src"]
    return None


# -------------------------
# Porovnání hashe
# -------------------------
def compare_image(img_url, ref_hash):
    if not img_url:
        print("  Obrázek nenalezen na stránce.")
        return

    response = requests.get(
        img_url,
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=10
    )
    img = Image.open(io.BytesIO(response.content)).convert("RGB")
    h = imagehash.phash(img)
    diff = ref_hash - h
    match = "✓ SHODA" if diff <= 15 else "✗"
    print(f"  Hash: {h}  |  Rozdíl: {diff}  |  {match}")


# -------------------------
# Hlavní program
# -------------------------
ref_hash = get_reference_hash()

offer_urls = get_abebooks_offers()
print(f"Nalezeno nabídek: {len(offer_urls)}, testuji prvních {MAX_OFFERS_TO_TEST}\n")

for i, url in enumerate(offer_urls[:MAX_OFFERS_TO_TEST]):
    print(f"[{i+1}] {url}")
    try:
        img_url = get_cover_image_url(url)
        print(f"  Obrázek: {img_url}")
        compare_image(img_url, ref_hash)
    except Exception as e:
        print(f"  Chyba: {e}")
    print()
