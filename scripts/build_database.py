import json
import re
import sys
import requests

WIKIDATA_ENDPOINT = "https://query.wikidata.org/sparql"

# Palettes couleurs respectant la DA éditoriale sobre
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

QUERY = """
SELECT ?player ?playerLabel ?countryLabel ?positionLabel ?clubLabel ?startTime ?endTime WHERE {
  ?player wdt:P106 wd:Q937857;          # Métier : footballeur
          wdt:P27 ?country;            # Nationalité
          p:P54 ?statement.            # Passage en club
  
  # Joueurs majeurs (ayant disputé des compétitions de premier rang)
  ?statement ps:P54 ?club.
  OPTIONAL { ?statement pq:P580 ?startTime. }
  OPTIONAL { ?statement pq:P582 ?endTime. }
  OPTIONAL { ?player wdt:P413 ?position. }

  # Exclusion des sélections nationales
  MINUS { ?club wdt:P31 wd:Q6979593. }

  SERVICE wikibase:label { bd:serviceParam wikibase:language "fr,en". }
}
LIMIT 15000
"""

HEADERS = {
    "User-Agent": "FootCareerDailyBot/2.0 (GitHub Educational Project; contact@footcareer.local)",
    "Accept": "application/sparql-results+json"
}

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
    print("Extraction Wikidata en cours...")
    res = requests.get(WIKIDATA_ENDPOINT, params={"query": QUERY, "format": "json"}, headers=HEADERS, timeout=90)
    res.raise_for_status()
    raw = res.json().get("results", {}).get("bindings", [])

    players_map = {}

    for row in raw:
        p_name = row.get("playerLabel", {}).get("value", "")
        p_uri = row.get("player", {}).get("value", "")
        wikidata_id = p_uri.split("/")[-1].lower()

        if not p_name or p_name.startswith("Q") and p_name[1:].isdigit():
            continue

        club_name = row.get("clubLabel", {}).get("value", "")
        if not club_name or (club_name.startswith("Q") and club_name[1:].isdigit()):
            continue
        if any(ign in club_name.lower() for ign in ["réserves", "u19", "u21", "b team", "jugend", "ii"]):
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

    formatted = []
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

    output_path = "data/players.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(formatted, f, ensure_ascii=False, indent=2)

    print(f"Extraction réussie : {len(formatted)} carrières exportées dans {output_path}")

if __name__ == "__main__":
    main()
