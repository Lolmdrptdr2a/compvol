import requests
import streamlit as st
from datetime import datetime
import pydeck as pdk
import os
import json

# -----------------------------
# Configuration
# -----------------------------
LOCAL_IATA_FILE = "C://Users//Rosas//Desktop//Anglais//Vol//programmes//airports.json"

def recherche(token, depart, arrivee, ar, adultes, enfant, esc, classe, date_dep, date_ret):
    headers = {"Authorization": f"Bearer {token}"}
    params = {
        "originLocationCode": depart,
        "destinationLocationCode": arrivee,
        "departureDate": date_dep,
        "adults": adultes,
        "children": enfant,
        "travelClass": classe,
        "nonStop": esc,
        "currencyCode": "EUR",
        "max": 100
    }
    if ar == "Aller-Retour":
        params["returnDate"] = date_ret
    search_url = "https://test.api.amadeus.com/v2/shopping/flight-offers"
    response = requests.get(search_url, headers=headers, params=params)
    return response.json()



# -----------------------------
# Utilitaires d'affichage
# -----------------------------

def parse_duration(duration_str):
    duration_str = duration_str.replace('PT', '')
    hours = 0
    minutes = 0
    if 'H' in duration_str:
        parts = duration_str.split('H')
        hours = int(parts[0])
        if 'M' in parts[1]:
            minutes = int(parts[1].replace('M', ''))
    elif 'M' in duration_str:
        minutes = int(duration_str.replace('M', ''))
    if hours > 0 and minutes > 0:
        return f"{hours}h {minutes}m"
    elif hours > 0:
        return f"{hours}h"
    else:
        return f"{minutes}m"

def format_datetime(datetime_str):
    dt = datetime.fromisoformat(datetime_str.replace('Z', '+00:00'))
    return dt.strftime("%d/%m/%Y %H:%M")

def get_airline_name(carrier_code, dictionaries):
    carriers = dictionaries.get('carriers', {})
    return carriers.get(carrier_code, carrier_code)

def get_aircraft_name(aircraft_code, dictionaries):
    aircraft = dictionaries.get('aircraft', {})
    return aircraft.get(aircraft_code, aircraft_code)

def trier_vols_par_prix(data):
    if 'data' in data:
        data['data'] = sorted(data['data'], key=lambda x: float(x['price']['total']))
    return data

# -----------------------------
# Récupération des coordonnées d'un aéroport (IATA code)
# -----------------------------
_COORDS_CACHE = {}

def _load_local_iata():
    try:
        with open(LOCAL_IATA_FILE, encoding='utf-8') as f:
            data = json.load(f)
            mapping = {}
            for icao, info in data.items():
                mapping[info['iata']] = {
                    'lat': info.get('lat'),
                    'lon': info.get('lon')
                }
            return mapping
    except Exception as e:
        print("Erreur chargement fichier IATA:", e)
        return {}

_LOCAL_IATA_MAPPING = _load_local_iata()

def get_airport_coords(iata_code):
    iata_code = iata_code.upper()
    if iata_code in _COORDS_CACHE:
        return _COORDS_CACHE[iata_code]
    if iata_code in _LOCAL_IATA_MAPPING:
        coords = _LOCAL_IATA_MAPPING[iata_code]
        if coords['lat'] and coords['lon']:
            _COORDS_CACHE[iata_code] = (coords['lat'], coords['lon'])
            return _COORDS_CACHE[iata_code]
    _COORDS_CACHE[iata_code] = (None, None)
    return (None, None)

# -----------------------------
# Affichage : carte interactive
# -----------------------------

def afficher_carte_vol(itineraires, initial_view=None):
    paths = []
    points_depart = []
    points_arrivee = []
    points_escales = []

    for itineraire in itineraires:
        for idx, segment in enumerate(itineraire['segments']):
            dep_iata = segment['departure']['iataCode']
            arr_iata = segment['arrival']['iataCode']
            dep_lat, dep_lon = get_airport_coords(dep_iata)
            arr_lat, arr_lon = get_airport_coords(arr_iata)

            if dep_lat and dep_lon and arr_lat and arr_lon:
                paths.append({
                    'path': [[dep_lon, dep_lat], [arr_lon, arr_lat]],
                    'label': f"{segment['carrierCode']} {segment['number']}"
                })
                if idx == 0:
                    points_depart.append({'position': [dep_lon, dep_lat], 'iata': dep_iata})
                elif idx == len(itineraire['segments']) - 1:
                    points_arrivee.append({'position': [arr_lon, arr_lat], 'iata': arr_iata})
                else:
                    points_escales.append({'position': [dep_lon, dep_lat], 'iata': dep_iata})
                    points_escales.append({'position': [arr_lon, arr_lat], 'iata': arr_iata})

    if not paths:
        st.info("ℹ️ Coordinates for this flight's airports are missing; map cannot be displayed.")
        return

    if initial_view is None:
        lon0, lat0 = paths[0]['path'][0]
        initial_view = pdk.ViewState(latitude=lat0, longitude=lon0, zoom=3)

    layer_paths = pdk.Layer(
        "PathLayer",
        data=paths,
        get_path='path',
        get_width=4,
        get_color=[255, 0, 0],  # Rouge
        width_min_pixels=2,
        pickable=True,
        auto_highlight=True,
    )

    layer_depart = pdk.Layer(
        "ScatterplotLayer",
        data=points_depart,
        get_position='position',
        get_radius=30000,
        get_color=[0, 255, 0],  # Vert pour départ
        pickable=True,
    )

    layer_arrivee = pdk.Layer(
        "ScatterplotLayer",
        data=points_arrivee,
        get_position='position',
        get_radius=30000,
        get_color=[0, 0, 255],  # Bleu pour arrivée
        pickable=True,
    )

    layer_escales = pdk.Layer(
        "ScatterplotLayer",
        data=points_escales,
        get_position='position',
        get_radius=20000,
        get_color=[255, 165, 0],  # Orange pour escales
        pickable=True,
    )

    deck = pdk.Deck(layers=[layer_paths, layer_depart, layer_arrivee, layer_escales], initial_view_state=initial_view)
    st.pydeck_chart(deck)


# -----------------------------
# Affichage du bloc vol amélioré (logo + carte)
# -----------------------------

def afficher_bloc_vol(vol, dictionaries, index):
    with st.container():
        st.markdown(f"""<div style=\"border: 2px solid #e1e5e9; border-radius: 15px; padding: 20px; margin: 15px 0; background: linear-gradient(135deg, #f8f9fa 0%, #ffffff 100%); box-shadow: 0 4px 6px rgba(0,0,0,0.05);\"></div>""", unsafe_allow_html=True)
        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            st.markdown(f"### ✈️ **Offre #{vol['id']}**")
        with col2:
            prix = float(vol['price']['total'])
            devise = vol['price']['currency']
            st.markdown(f"### **{prix:.2f} {devise}**")
            st.markdown("💰 *Prix total*")
        with col3:
            nb_voyageurs = len(vol['travelerPricings'])
            st.markdown(f"### **{nb_voyageurs} voyageur(s)**")
            st.markdown("👥 *Passagers*")
        st.markdown("---")
        for idx, itineraire in enumerate(vol['itineraries']):
            st.markdown("#### 🛫 **Aller**" if idx == 0 else "#### 🛬 **Retour**")
            duree_totale = parse_duration(itineraire['duration'])
            nb_escales = len(itineraire['segments']) - 1
            c_info1, c_info2 = st.columns(2)
            with c_info1:
                st.markdown(f"⏱️ **Durée:** {duree_totale}")
            with c_info2:
                st.markdown("✅ **Vol direct**" if nb_escales == 0 else f"🔄 **{nb_escales} escale(s)**")
            for seg_idx, segment in enumerate(itineraire['segments']):
                dep = segment['departure']
                arr = segment['arrival']
                compagnie = get_airline_name(segment['carrierCode'], dictionaries)
                numero_vol = f"{segment['carrierCode']} {segment['number']}"
                avion = get_aircraft_name(segment['aircraft']['code'], dictionaries) if 'aircraft' in segment and segment['aircraft'] else ''
                duree_segment = parse_duration(segment['duration'])
                logo_url = f"https://airlabs.co/img/airline/m/{segment['carrierCode']}.png"
                st.markdown(f"""<div style=\"background: #f1f3f4; border-radius: 10px; padding: 15px; margin: 10px 0; border-left: 4px solid #1f77b4;\"><div style=\"display: flex; justify-content: space-between; align-items: center;\"><div style=\"display:flex; align-items:center; gap:10px;\"><img src=\"{logo_url}\" alt=\"{compagnie}\" style=\"height:28px; width:auto; border-radius:4px;\"><div><strong style=\"font-size: 18px; color: #1f77b4;\">{dep['iataCode']} → {arr['iataCode']}</strong><br><span style=\"color: #666;\">{format_datetime(dep['at'])} → {format_datetime(arr['at'])}</span></div></div><div style=\"text-align:right;\"><strong>{numero_vol}</strong><br><span style=\"color: #666; font-size: 12px;\">{compagnie}</span></div></div><div style=\"margin-top: 10px; font-size: 14px; color: #666;\">✈️ {avion} | ⏱️ {duree_segment}</div></div>""", unsafe_allow_html=True)
        afficher_carte_vol(vol['itineraries'])
        st.markdown("#### 💳 **Détail des prix**")
        devise = vol['price']['currency']
        for traveler in vol['travelerPricings']:
            traveler_type = "Adulte" if traveler['travelerType'] == 'ADULT' else "Enfant"
            prix_voyageur = float(traveler['price']['total'])
            tcol1, tcol2 = st.columns([3, 1])
            with tcol1:
                st.markdown(f"👤 **{traveler_type}** (ID: {traveler['travelerId']})")
            with tcol2:
                st.markdown(f"**{prix_voyageur:.2f} {devise}**")
        if st.button(f"Sélectionner cette offre", key=f"select_{vol['id']}_{index}"):
            st.success(f"✅ Offre #{vol['id']} sélectionnée!")
            st.balloons()

# -----------------------------
# Page résultats
# -----------------------------

def page_resultats_vols(data):
    st.markdown("""<div style=\"text-align: center; padding: 20px;\"><h1 style=\"color: #1f77b4; margin-bottom: 10px;\">✈️ Résultats de recherche de vols</h1><p style=\"color: #666; font-size: 18px;\">Voici les meilleures offres pour votre voyage</p></div>""", unsafe_allow_html=True)
    if not data or 'data' not in data or not data['data']:
        st.error("❌ Aucun résultat trouvé pour votre recherche.")
        if st.button("🔙 Nouvelle recherche"):
            st.session_state.page = "recherche"
            st.rerun()
        return
    data_triee = trier_vols_par_prix(data.copy())
    vols = data_triee['data']
    dictionaries = data_triee.get('dictionaries', {})
    nb_resultats = len(vols)
    prix_min = min(float(vol['price']['total']) for vol in vols)
    prix_max = max(float(vol['price']['total']) for vol in vols)
    devise = vols[0]['price']['currency'] if vols else 'EUR'
    col_stat1, col_stat2, col_stat3, col_stat4 = st.columns(4)
    with col_stat1:
        st.metric("📊 Résultats", nb_resultats)
    with col_stat2:
        st.metric("💰 Prix minimum", f"{prix_min:.2f} {devise}")
    with col_stat3:
        st.metric("💸 Prix maximum", f"{prix_max:.2f} {devise}")
    with col_stat4:
        if st.button("🔙 Nouvelle recherche"):
            st.session_state.page = "recherche"
            st.rerun()
    st.markdown("---")
    vols_a_afficher = vols[:10]
    if len(vols) > 10:
        st.info(f"ℹ️ Affichage des 10 meilleures offres sur {nb_resultats} résultats disponibles.")
    for index, vol in enumerate(vols_a_afficher):
        afficher_bloc_vol(vol, dictionaries, index)
