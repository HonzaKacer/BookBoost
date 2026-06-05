import requests
from bs4 import BeautifulSoup
from PIL import Image
import imagehash
import io
import json
import os

# -------------------------
# Nastavení
# -------------------------
REFERENCE_IMAGE = "cover.png"
HASH_THRESHOLD = 15        # 0 = identické, 64 = zcela jiné; doporučuju začít na 15
BAZOS_SEARCH_URL = "https://www.bazos.cz/search.php?hledat=pruning+gilman&rubriky=www&hlokalita=&humkreis=25&cenaod=&cenado=&Submit=Hledat&kitx=ano"
EMAIL_TO = "mandoral@seznam.cz"
STATE_FILE = "state_bazos.json"


# -------------------------
# Stav
# -------------------------
def load_state():
    try:
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {"alerted_urls": []}


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=4)


# -------------------------
# Referenční hash obálky
# -------------------------
def get_reference_hash():
    return imagehash.phash(Image.open(REFERENCE_IMAGE))


# -------------------------
# Stažení výsledků z Bazoše
# -------------------------
def get_bazos_listings():
    response = requests.get(
        BAZOS_SEARCH_URL,
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=20
    )
    print("Bazoš status:", response.status_code)
    soup = BeautifulSoup(response.text, "html.parser")

    listings = []
    for item in soup.find_all("div", class_="inzeraty"):
        # Název a odkaz
        title_tag = item.find("h2")
        if not title_tag:
            continue
        link_tag = title_tag.find("a")
        if not link_tag:
            continue

        title = link_tag.text.strip()
        url = link_tag["href"]
        if not url.startswith("http"):
            url = "https://www.bazos.cz" + url

        # Obrázek náhledu
        img_tag = item.find("img")
        img_url = img_tag["src"] if img_tag and "src" in img_tag.attrs else None
        if img_url and not img_url.startswith("http"):
            img_url = "https://www.bazos.cz" + img_url

        # Cena
        price_tag = item.find("div", class_="inzeratycena")
        price_text = price_tag.text.strip() if price_tag else "?"

        listings.append({
            "title": title,
            "url": url,
            "img_url": img_url,
            "price": price_text
        })

    return listings


# -------------------------
# Porovnání obrázku inzerátu s obálkou
# -------------------------
def image_matches(img_url, ref_hash, threshold=HASH_THRESHOLD):
    if not img_url:
        return False
    try:
        response = requests.get(
            img_url,
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=10
        )
        img = Image.open(io.BytesIO(response.content)).convert("RGB")
        listing_hash = imagehash.phash(img)
        diff = ref_hash - listing_hash
        print(f"  Hash rozdíl: {diff}")
        return diff <= threshold
    except Exception as e:
        print(f"  Chyba při stahování obrázku: {e}")
        return False


# -------------------------
# Email přes Resend
# -------------------------
def send_email(listing):
    api_key = os.environ["RESEND_API_KEY"]
    response = requests.post(
        "https://api.resend.com/emails",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        },
        json={
            "from": "onboarding@resend.dev",
            "to": [EMAIL_TO],
            "subject": "Možná shoda na Bazoši!",
            "html": f"""
                <h2>An Illustrated Guide to Pruning – možná shoda</h2>
                <p><b>Název inzerátu:</b> {listing['title']}</p>
                <p><b>Cena:</b> {listing['price']}</p>
                <p><a href="{listing['url']}">Otevřít inzerát</a></p>
                <p><img src="{listing['img_url']}" style="max-width:300px"></p>
            """
        }
    )
    print("Email status:", response.status_code)


# -------------------------
# Hlavní program
# -------------------------
ref_hash = get_reference_hash()
print("Referenční hash načten.")

listings = get_bazos_listings()
print(f"Nalezeno inzerátů: {len(listings)}")

state = load_state()
alerted_urls = state.get("alerted_urls", [])

for listing in listings:
    print(f"Kontroluji: {listing['title']} ({listing['url']})")
    if listing["url"] in alerted_urls:
        print("  Již oznámeno, přeskakuji.")
        continue
    if image_matches(listing["img_url"], ref_hash):
        print("  SHODA! Odesílám email.")
        send_email(listing)
        alerted_urls.append(listing["url"])

state["alerted_urls"] = alerted_urls
save_state(state)
print("Hotovo.")
