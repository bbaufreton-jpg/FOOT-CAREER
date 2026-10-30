import json
import os
import re
import sys
import requests

WIKIDATA_ENDPOINT = "https://query.wikidata.org/sparql"

# Palettes éditoriales sobres pour les clubs majeurs
CLUB_PALETTES = {
    "Real Madrid": {"bg": "#FFFFFF", "text": "#181816", "border": "#DDD5C7"},
    "FC Barcelone": {"bg": "#1C274C", "text": "#FDFBF7", "border": "#A52A2A"},
    "Paris Saint-Germain": {"bg": "#121A2A", "text": "#FDFBF7", "border": "#C92A2A"},
    "Arsenal FC": {"bg": "#C92A2A", "text": "#FFFFFF", "border": "#DDD5C7"},
    "Manchester City": {"bg": "#A3C7E8", "text": "#181816", "border": "#89B4DB"},
    "Manchester United": {"bg": "#C92A2A", "text": "#FFFFFF", "border": "#A81E1E"},
    "Bayern Munich": {"bg": "#D62828", "text": "#FFFFFF", "border": "#A81E1E"},
    "Juventus FC": {"bg": "#181816", "text": "#FDFBF7", "border": "#DDD5C7"},
    "AC Milan": {"bg": "#181816", "text": "#E03131", "border": "#A81E1E"},
    "Inter Milan": {"bg": "#0B3C5D", "text": "#FFFFFF", "border": "#07263A"},
    "Liverpool FC": {"bg": "#C92A2A", "text": "#FFFFFF", "border": "#961E1E"},
    "Chelsea FC": {"bg": "#184E77", "text": "#FFFFFF", "border": "#133D5E"},
    "Borussia Dortmund": {"bg": "#F5C242", "text": "#181816", "border": "#D8A72B"},
    "Atlético de Madrid": {"bg": "#C92A2A", "text": "#FFFFFF", "border": "#1C274C"},
}
DEFAULT_PALETTE = {"bg": "#EFECE4", "text": "#2C2A29", "border": "#DDD5C7"}

# Requête ultra-optimisée avec sitelinks (répond en 3 à 5 secondes)
QUERY = """
SELECT ?player ?playerLabel ?countryLabel ?positionLabel ?clubLabel ?startTime ?endTime WHERE {
  ?player wdt:P106 wd:Q937857 ;
          wikibase:sitelinks ?sitelinks .
  FILTER(?sitelinks >= 22)
  
  OPTIONAL { ?player wdt:P27 ?country . }
  OPTIONAL { ?player wdt:P413 ?position . }
  
  ?player p:P54 ?statement .
  ?statement ps:P54 ?club .
  OPTIONAL { ?statement pq:P580 ?startTime . }
  OPTIONAL { ?statement pq:P582 ?endTime . }

  SERVICE wikibase:label { bd:serviceParam wikibase:language "fr,en". }
}
LIMIT 8000
"""

HEADERS = {
    "User-Agent": "FootCareerApp/2.0 (GitHub Educational Project; contact@footcareer.local)",
    "Accept": "application/sparql-results+json"
}

FALLBACK_PLAYERS = [
  {"id": "mbappe-q27718312", "name": "Kylian Mbappé", "nationality": "France", "position": "Attaquant", "flag": "🇫🇷", "difficulty": "incontournable", "clubs": [{"club": "AS Monaco", "years": "2015–2017"}, {"club": "Paris Saint-Germain", "years": "2017–2024"}, {"club": "Real Madrid", "years": "2024–Présent"}]},
  {"id": "haaland-q61740707", "name": "Erling Haaland", "nationality": "Norvège", "position": "Attaquant", "flag": "🇳🇴", "difficulty": "incontournable", "clubs": [{"club": "Bryne FK", "years": "2015–2017"}, {"club": "Molde FK", "years": "2017–2018"}, {"club": "RB Salzbourg", "years": "2019–2020"}, {"club": "Borussia Dortmund", "years": "2020–2022"}, {"club": "Manchester City", "years": "2022–Présent"}]},
  {"id": "zidane-q1835", "name": "Zinédine Zidane", "nationality": "France", "position": "Milieu", "flag": "🇫🇷", "difficulty": "retro", "clubs": [{"club": "AS Cannes", "years": "1989–1992"}, {"club": "Girondins de Bordeaux", "years": "1992–1996"}, {"club": "Juventus FC", "years": "1996–2001"}, {"club": "Real Madrid", "years": "2001–2006"}]},
  {"id": "ronaldo-q10520", "name": "Ronaldo Nazário", "nationality": "Brésil", "position": "Attaquant", "flag": "🇧🇷", "difficulty": "retro", "clubs": [{"club": "Cruzeiro", "years": "1993–1994"}, {"club": "PSV Eindhoven", "years": "1994–1996"}, {"club": "FC Barcelone", "years": "1996–1997"}, {"club": "Inter Milan", "years": "1997–2002"}, {"club": "Real Madrid", "years": "2002–2007"}, {"club": "AC Milan", "years": "2007–2008"}, {"club": "Corinthians", "years": "2009–2011"}]},
  {"id": "osimhen-q20127090", "name": "Victor Osimhen", "nationality": "Nigéria", "position": "Attaquant", "flag": "🇳🇬", "difficulty": "initie", "clubs": [{"club": "VfL Wolfsburg", "years": "2017–2019"}, {"club": "Charleroi", "years": "2018–2019"}, {"club": "LOSC Lille", "years": "2019–2020"}, {"club": "SSC Napoli", "years": "2020–2024"}, {"club": "Galatasaray", "years": "2024–Présent"}]},
  {"id": "morata-q52470", "name": "Álvaro Morata", "nationality": "Espagne", "position": "Attaquant", "flag": "🇪🇸", "difficulty": "erudit", "clubs": [{"club": "Real Madrid", "years": "2010–2014"}, {"club": "Juventus FC", "years": "2014–2016"}, {"club": "Real Madrid", "years": "2016–2017"}, {"club": "Chelsea FC", "years": "2017–2019"}, {"club": "Atlético de Madrid", "years": "2019–2024"}, {"club": "AC Milan", "years": "2024–Présent"}]}
]

def clean_year(date_str):
    if not date_str:
        return None
    match = re.search(r"(\d{4})", date_str)
    return int(match.group(1)) if match else None

def assign_tier(clubs_count, last_year):
    if last_year and last_year < 2012:
        return "retro"
    if clubs_count >= 6:
        return "erudit"
    if clubs_count >= 4:
        return "initie"
    return "incontournable"

def main():
    os.makedirs("data", exist_ok=True)
    formatted = []
    
    print("Extraction des données Wikidata...")
    try:
        res = requests.get(WIKIDATA_ENDPOINT, params={"query": QUERY, "format": "json"}, headers=HEADERS, timeout=25)
        res.raise_for_status()
        raw = res.json().get("results", {}).get("bindings", [])
        
        players_map = {}
        for row in raw:
            p_name = row.get("playerLabel", {}).get("value", "")
            p_uri = row.get("player", {}).get("value", "")
            wikidata_id = p_uri.split("/")[-1].lower()

            if not p_name or (p_name.startswith("Q") and p_name[1:].isdigit()):
                continue

            club_name = row.get("clubLabel", {}).get("value", "")
            if not club_name or (club_name.startswith("Q") and club_name[1:].isdigit()):
                continue
            if any(ign in club_name.lower() for ign in ["réserves", "u19", "u21", "b team", "jugend", "équipe nationale"]):
                continue

            start = clean_year(row.get("startTime", {}).get("value"))
            end = clean_year(row.get("endTime", {}).get("value"))
            country = row.get("countryLabel", {}).get("value", "International")
            pos = row.get("positionLabel", {}).get("value", "Joueur de champ")

            slug = re.sub(r"[^a-z0-9]", "-", p_name.lower()).strip("-")
            stable_id = f"{slug}-{wikidata_id}"

            if stable_id not in players_map:
                players_map[stable_id] = {
                    "id": stable_id,
                    "name": p_name,
                    "nationality": country,
                    "position": pos,
                    "flag": "⚽",
                    "clubs_raw": []
                }

            players_map[stable_id]["clubs_raw"].append({
                "club": club_name,
                "start": start or 1900,
                "end": end or 2026
            })

        for uid, p in players_map.items():
            raw_clubs = sorted(p["clubs_raw"], key=lambda x: x["start"])
            clean_clubs = []
            last_seen = None

            for c in raw_clubs:
                if c["club"] != last_seen:
                    start_lbl = str(c["start"]) if c["start"] != 1900 else "?"
                    end_lbl = str(c["end"]) if c["end"] != 2026 else "Présent"
                    years = f"{start_lbl}–{end_lbl}" if start_lbl != end_lbl else str(start_lbl)
                    palette = CLUB_PALETTES.get(c["club"], DEFAULT_PALETTE)

                    clean_clubs.append({
                        "club": c["club"],
                        "years": years,
                        "loan": False,
                        "bg": palette["bg"],
                        "text": palette["text"],
                        "border": palette["border"]
                    })
                    last_seen = c["club"]

            if len(clean_clubs) >= 2:
                last_yr = max(c["end"] for c in raw_clubs)
                formatted.append({
                    "id": p["id"],
                    "name": p["name"],
                    "nationality": p["nationality"],
                    "position": p["position"],
                    "flag": p["flag"],
                    "difficulty": assign_tier(len(clean_clubs), last_yr),
                    "clubs": clean_clubs
                })
        print(f"Extraction réussie : {len(formatted)} carrières trouvées sur Wikidata.")
    except Exception as e:
        print(f"Wikidata temporairement indisponible ou trop lent ({e}). Utilisation du catalogue de secours.")
        formatted = FALLBACK_PLAYERS

    output_path = "data/players.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(formatted if len(formatted) >= 5 else FALLBACK_PLAYERS, f, ensure_ascii=False, indent=2)

    print(f"Fichier {output_path} généré avec succès.")

if __name__ == "__main__":
    main()
