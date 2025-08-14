import streamlit as st
import requests
import pydeck as pdk
from datetime import datetime
import re
from traitement_info import get_airport_coords
from vols import token
import math
import os
import json

# ------------------------------------------------------------
# Config
# ------------------------------------------------------------
st.set_page_config(page_title="Flighty", layout="wide", initial_sidebar_state="collapsed")

# Chemin de la base aéroports (json   format: { "ICAO": { "iata": "...", "city": "...", "lat": ..., "lon": ... } })
AIRPORTS_JSON = os.getenv("AIRPORTS_JSON", "airports.json")  # change si besoin

# ------------------------------------------------------------
# Utilitaires: aéroports, date/heure, durées
# ------------------------------------------------------------
@st.cache_data(show_spinner=False)
def load_airports_db(path):
    if not os.path.exists(path):
        return {}, {}
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    by_iata, by_icao = {}, {}
    for icao, rec in raw.items():
        iata = (rec.get("iata") or "").upper()
        if iata:
            by_iata[iata] = {
                "iata": iata,
                "icao": (rec.get("icao") or "").upper(),
                "city": rec.get("city") or "",
                "name": rec.get("name") or "",
                "country": rec.get("country") or "",
                "lat": rec.get("lat"),
                "lon": rec.get("lon"),
            }
        by_icao[icao.upper()] = {
            "iata": iata,
            "icao": icao.upper(),
            "city": rec.get("city") or "",
            "name": rec.get("name") or "",
            "country": rec.get("country") or "",
            "lat": rec.get("lat"),
            "lon": rec.get("lon"),
        }
    return by_iata, by_icao

AIRPORTS_BY_IATA, AIRPORTS_BY_ICAO = load_airports_db(AIRPORTS_JSON)

def get_airport_info(iata: str):
    """Retourne (lat, lon, city, name) pour un IATA. Fallback sur IATA si manquant."""
    if not iata:
        return None, None, iata or "", ""
    rec = AIRPORTS_BY_IATA.get(iata.upper())
    if not rec:
        return None, None, iata.upper(), ""
    return rec["lat"], rec["lon"], rec["city"] or rec["iata"], rec["name"]

def parse_datetime(dt_str):
    """Transforme un datetime ISO en jour + heure, et renvoie aussi l'objet datetime aware."""
    dt = datetime.fromisoformat(dt_str)  # garde le fuseau contenu dans la chaîne ISO
    day = dt.strftime("%a %d %b")        # ex: "Thu 14 Aug"
    hour = dt.strftime("%H:%M")          # ex: "10:30"
    return day, hour, dt

def parse_duration(iso_str):
    """Convertit une durée ISO8601 (PT8H10M, PT-21M) -> ('8h10', 490) minutes (signé)."""
    if not iso_str:
        return "N/A", 0
    negative = "-" in iso_str
    iso_str = iso_str.replace("-", "")
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?", iso_str)
    if not m:
        return iso_str, 0
    h = int(m.group(1)) if m.group(1) else 0
    mn = int(m.group(2)) if m.group(2) else 0
    total = h * 60 + mn
    if h and mn:
        s = f"{h}h{mn:02d}"
    elif h:
        s = f"{h}h"
    else:
        s = f"{mn} min"
    if negative:
        return f"-{s}", -total
    return s, total

def fraction_progress(dep_time_dt: datetime, duration_min: int) -> float:
    """Fraction du vol écoulée en fonction de l'heure locale du départ (0..1)."""
    if duration_min <= 0:
        return 0.0
    now = datetime.now(dep_time_dt.tzinfo)
    elapsed = (now - dep_time_dt).total_seconds() / 60.0
    return max(0.0, min(1.0, elapsed / duration_min))

def interpolate_position(lat1, lon1, lat2, lon2, t):
    """Interpolation linéaire simple entre départ et arrivée (0..1)."""
    if lat1 is None or lon1 is None or lat2 is None or lon2 is None:
        return None, None
    return lat1 + (lat2 - lat1) * t, lon1 + (lon2 - lon1) * t

# ------------------------------------------------------------
# Amadeus
# ------------------------------------------------------------
# ⚠️ Remplace l'import si ta fonction token() est ailleurs

def get_flight_status_amadeus(access_token, carrier_code, flight_number, date):
    """On-Demand Flight Status (Schedule)"""
    url = "https://test.api.amadeus.com/v2/schedule/flights"
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {"carrierCode": carrier_code, "flightNumber": flight_number, "scheduledDepartureDate": date}
    r = requests.get(url, headers=headers, params=params, timeout=20)
    if r.status_code == 200:
        return r.json()
    st.error(f"Erreur Amadeus : {r.status_code} – {r.text}")
    return {}

# ------------------------------------------------------------
# Carte
# ------------------------------------------------------------
def afficher_carte(dep_iata, arr_iata, dep_dt, duration_min):
    """Carte avec: arc bleu clair, labels villes, points départ/arrivée (rouge à l'arrivée), avion estimé."""
    dep_lat, dep_lon, dep_city, _ = get_airport_info(dep_iata)
    arr_lat, arr_lon, arr_city, _ = get_airport_info(arr_iata)

    if dep_lat is None or arr_lat is None:
        st.warning("Coordonnées aéroport non trouvées dans airports.json.")
        return

    # 1) Grande trajectoire (GreatCircleLayer) en BLEU CLAIR + largeur en PIXELS
    great_circle_data = [{
        "from": [dep_lon, dep_lat],
        "to": [arr_lon, arr_lat]
    }]
    arc_layer = pdk.Layer(
        "GreatCircleLayer",
        data=great_circle_data,
        get_source_position="from",
        get_target_position="to",
        get_width=0.5,
        width_units="pixels",
        get_source_color=[0, 191, 255],
        get_target_color=[0, 191, 255],
        opacity=0.85,
        pickable=False,
    )

    # 2) Labels villes (TextLayer)
    text_data = [
        {"pos": [dep_lon, dep_lat - 0.5], "label": dep_city or dep_iata, "color": [0, 200, 0]},
        {"pos": [arr_lon, arr_lat - 0.5], "label": arr_city or arr_iata, "color": [220, 0, 0]},
    ]
    text_layer = pdk.Layer(
        "TextLayer",
        data=text_data,
        get_position="pos",
        get_text="label",
        get_size=18,
        get_color="color",
        get_text_anchor='"middle"',
        get_alignment_baseline='"top"',
    )

    # 3) Points départ (vert) & arrivée (rouge) — en pixels pour rester visibles
    departure_layer = pdk.Layer(
        "ScatterplotLayer",
        data=[{"pos": [dep_lon, dep_lat]}],
        get_position="pos",
        radius_units="pixels",
        get_radius=8,
        get_color=[0, 255, 0],
    )
    arrival_layer = pdk.Layer(
        "ScatterplotLayer",
        data=[{"pos": [arr_lon, arr_lat]}],
        get_position="pos",
        radius_units="pixels",
        get_radius=8,
        get_color=[255, 0, 0],
    )

    # 4) Position estimée de l'avion (emoji ✈︎ pour compatibilité maximale)
    frac = fraction_progress(dep_dt, duration_min)
    plane_lat, plane_lon = interpolate_position(dep_lat, dep_lon, arr_lat, arr_lon, frac)
    print(plane_lat,plane_lon)
    plane_layer = None
    if plane_lat is not None and plane_lon is not None:
        plane_layer = pdk.Layer(
            "TextLayer",
            data=[{"pos": [plane_lon, plane_lat], "label": "✈︎"}],
            get_position="pos",
            get_icon="https://upload.wikimedia.org/wikipedia/commons/d/d2/White_plane_icon.svg", # URL d'une icône d'avion
            get_size=24,
            get_color=[255, 255, 255],
            get_text_anchor='"middle"',
            get_alignment_baseline='"center"',
            pickable=True,
        )
            

    # Centrage: milieu du segment
    center_lat = (dep_lat + arr_lat) / 2
    center_lon = (dep_lon + arr_lon) / 2

    view_state = pdk.ViewState(latitude=center_lat, longitude=center_lon, zoom=3)

    layers = [arc_layer, departure_layer, arrival_layer, text_layer]
    if plane_layer:
        layers.append(plane_layer)

    st.pydeck_chart(pdk.Deck(
        initial_view_state=view_state,
        layers=layers,
        map_style=None  # garde le style par défaut de Streamlit; mets "mapbox://styles/mapbox/dark-v9" si besoin
    ))

# ------------------------------------------------------------
# UI principale
# ------------------------------------------------------------
def page_flighty():
    st.title("📡 Suivi de vol (type Flighty – Amadeus)")

    carrier_code = st.text_input("Code compagnie (ex: AF)", key="page_flighty_code").upper()
    flight_number = st.text_input("Numéro de vol (ex: 0004)", key="page_flighty_numero")
    date_depart = st.date_input("Date de départ", key="page_flighty_date")

    # Recherche
    if st.button("🔍 Rechercher", key="page_flighty_recherche"):
        if not carrier_code or not flight_number or not date_depart:
            st.error("Veuillez remplir tous les champs.")
            return

        access_token = token()
        date_str = date_depart.strftime("%Y-%m-%d")
        data = get_flight_status_amadeus(access_token, carrier_code, flight_number, date_str)

        if not data or "data" not in data or not data["data"]:
            st.error("Aucun vol trouvé.")
            return

        vol = data["data"][0]

        # Identification du vol
        numero_vol = f"{vol['flightDesignator']['carrierCode']}{vol['flightDesignator']['flightNumber']}"

        # Départ
        dep = vol["flightPoints"][0]
        dep_iata = dep["iataCode"]
        dep_terminal = dep["departure"].get("terminal", {}).get("code", "N/A")
        dep_gate = dep["departure"].get("gate", {}).get("mainGate", "N/A")
        dep_time_iso = dep["departure"]["timings"][0]["value"]

        # Arrivée
        arr = vol["flightPoints"][-1]
        arr_iata = arr["iataCode"]
        arr_terminal = arr["arrival"].get("terminal", {}).get("code", "N/A")
        arr_time_iso = arr["arrival"]["timings"][0]["value"]
        delay_iso = arr["arrival"]["timings"][0].get("delays", [{}])[0].get("duration", "")

        # Horaires lisibles
        dep_day, dep_hour, dep_dt = parse_datetime(dep_time_iso)
        arr_day, arr_hour, _ = parse_datetime(arr_time_iso)
        extra = " +1" if dep_day != arr_day else ""

        # Durées lisibles
        delay_text, _ = parse_duration(delay_iso) if delay_iso else ("On Time", 0)
        duration_text, duration_min = parse_duration(vol["segments"][0].get("scheduledSegmentDuration", ""))

        # Avion & codeshare
        aircraft = vol["legs"][0].get("aircraftEquipment", {}).get("aircraftType", "N/A")
        operating = vol["segments"][0].get("partnership", {}).get("operatingFlight", {})

        # --- Affichage info ---
        st.subheader(f"✈️ Vol {numero_vol}")
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Départ", dep_iata)
            st.write(f"**Jour** : {dep_day}")
            st.write(f"**Heure** : {dep_hour}")
            st.write(f"**Terminal** : {dep_terminal}")
            st.write(f"**Gate** : {dep_gate}")
        with col2:
            st.metric("Arrivée", arr_iata)
            st.write(f"**Jour** : {arr_day}")
            st.write(f"**Heure** : {arr_hour}{extra}")
            st.write(f"**Terminal** : {arr_terminal}")
            st.write(f"**Retard** : {delay_text}")

        st.write(f"**Durée prévue** : {duration_text}")
        st.write(f"**Avion** : {aircraft}")
        if operating:
            st.write(f"**Opéré par** : {operating['carrierCode']}{operating['flightNumber']}")

        # --- Carte enrichie ---
        afficher_carte(dep_iata, arr_iata, dep_dt, duration_min)
        # Code HTML pour le bouton. L'attribut 'target="_blank"' est la clé pour ouvrir dans un nouvel onglet.
        html_code = f'<a href="https://www.flightradar24.com/{carrier_code+flight_number}" target="_blank" style="display: inline-block; padding: 12px 20px; background-color: #4CAF50; color: white; text-align: center; text-decoration: none; font-size: 16px; border-radius: 8px;">Ouvrir Flightradar24</a>'
        # Affiche le bouton dans l'application Streamlit
        st.markdown(html_code, unsafe_allow_html=True)
                