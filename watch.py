import json
import os
import requests
from bs4 import BeautifulSoup


# -------------------------
# Nastavení
# -------------------------
ISBN = "9781111307301"
PRICE_LIMIT_CZK = 5000
USD_TO_CZK = 23
EMAIL_TO = "mandoral@seznam.cz"


# -------------------------
# Stav (paměť mezi běhy)
# -------------------------
def load_state():
    try:
        with open("state.json", "r") as f:
            return json.load(f)
    except Exception:
        return {"alerted_urls": []}


def save_state(state):
    with open("state.json", "w") as f:
        json.dump(state, f, indent=4)


# -------------------------
# Stažení nabídek z AbeBooks
# -------------------------
def get_abebooks_offers():
    search_url = f"https://www.abebooks.com/servlet/SearchResults?isbn={ISBN}"
    response = requests.get(
        search_url,
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=20
    )
    print("AbeBooks status:", response.status_code)
    soup = BeautifulSoup(response.text, "html.parser")

    offers = []
    for offer in soup.find_all("h2", itemprop="offers"):
        price_tag = offer.find("meta", itemprop="price")
        url_tag = offer.find("a", itemprop="url")
        if not price_tag or not url_tag:
            continue
        try:
            offers.append({
                "price_usd": float(price_tag["content"]),
                "url": "https://www.abebooks.com" + url_tag["href"]
            })
        except Exception:
            pass
    return offers


# -------------------------
# Email přes Resend
# -------------------------
def send_email(offer):
    api_key = os.environ["RESEND_API_KEY"]
    price_usd = offer["price_usd"]
    price_czk = round(price_usd * USD_TO_CZK)

    response = requests.post(
        "https://api.resend.com/emails",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        },
        json={
            "from": "onboarding@resend.dev",
            "to": [EMAIL_TO],
            "subject": "Kniha nalezena pod limitem",
            "html": f"""
                <h2>An Illustrated Guide to Pruning (3rd edition)</h2>
                <p><b>Cena:</b> {price_usd} USD</p>
                <p><b>Přibližně:</b> {price_czk} Kč</p>
                <p><a href="{offer['url']}">Otevřít nabídku</a></p>
            """
        }
    )
    print("Email status:", response.status_code)
    print(response.text)


# -------------------------
# Hlavní program
# -------------------------
offers = get_abebooks_offers()
print("Nalezeno nabídek:", len(offers))

if not offers:
    print("Žádné nabídky nebyly nalezeny.")
else:
    cheapest_offer = min(offers, key=lambda x: x["price_usd"])
    lowest_usd = cheapest_offer["price_usd"]
    lowest_czk = round(lowest_usd * USD_TO_CZK)

    print("Nejnižší cena USD:", lowest_usd)
    print("Nejnižší cena CZK:", lowest_czk)
    print("URL:", cheapest_offer["url"])

    state = load_state()
    alerted_urls = state.get("alerted_urls", [])
    current_url = cheapest_offer["url"]

    if lowest_czk <= PRICE_LIMIT_CZK:
        if current_url not in alerted_urls:
            print("Nová nabídka pod limitem.")
            send_email(cheapest_offer)
            alerted_urls.append(current_url)
            state["alerted_urls"] = alerted_urls
            save_state(state)
        else:
            print("Stejná nabídka už byla oznámena.")
    else:
        print("Cena je nad limitem.")
