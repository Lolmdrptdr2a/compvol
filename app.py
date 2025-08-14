import json
import streamlit as st
from amadeus import Client, ResponseError
from vols import client_id,client_secret,token
from traitement_info import *

# Chargement des données aéroports
with open("C://Users//Rosas//Desktop//Anglais//Vol//programmes//Code-IATA-villes.json", encoding="utf-8") as f:
    airports = json.load(f)

amadeus = Client(client_id = client_id,client_secret = client_secret)
st.set_page_config(layout="wide")
st.markdown("""
    <style>
        .block-container {
            max-width: 1000px !important;
            padding-left: 3rem;
            padding-right: 3rem;
        }
    </style>
""", unsafe_allow_html=True)

airport_dict = {f"({a['iata']}) {a['airport']}": a['iata'] for a in airports}
options = list(airport_dict.keys())

# Titre de la page
st.title("🛫 Comparateur de Vols")

# Première rangée
ar_col, bm_col, bs_col, _, _ = st.columns(5)
with ar_col:
    allee_retour = st.selectbox("Type de vol", ["Aller-Retour", "Aller-simple"], label_visibility="hidden")
with bm_col:
    bagage_main = st.selectbox("Bagage à main", [0, 1])
with bs_col:
    bagage_soute = st.selectbox("Bagages en soute", [0, 1, 2, 3])

# Deuxième rangée
col1, col2, col3, col4 = st.columns(4)
with col1:
    depart = st.selectbox("Aéroport de départ", [""] + options)
with col2:
    arrivee = st.selectbox("Aéroport d'arrivée", [""] + options)
with col3:
    date_depart = st.date_input("Date Aller")
if allee_retour == "Aller-Retour":
    with col4:
        date_retour = st.date_input("Date Retour", value=date_depart)

a1,a2,_,a3,a4 = st.columns(5)

with a1:
    adultes = st.selectbox("adultes",[0,1,2,3,4,5,6,7,8,9])
with a2:
    enfants = st.selectbox("enfants",[0,1,2,3,4,5,6,7,8,9])
    
with a3:
    escale = st.checkbox("Sans Escale")
        
with a4:
    cl_liste = ["Economique","Première Économique","Business","Première Classe"]
    cl = st.selectbox("classe",cl_liste)
    cc = ["ECONOMY","PREMIUM_ECONOMY","BUSINESS","FIRST"]
    classe = cc[cl_liste.index(cl)]
    
# Bouton (en bas)
if st.button("🔍 Rechercher"):
    if escale:
        escale = 'true'
    else:
        escale = 'false'
    if allee_retour == "Aller-Retour":
        L = recherche(token(),depart[1:4],arrivee[1:4],allee_retour,adultes,enfants,escale,classe,date_depart,date_retour)
    else:
        L = recherche(token(),depart[1:4],arrivee[1:4],allee_retour,adultes,enfants,escale,classe,date_depart,date_depart)

    st.session_state.resultats_vols = L
    st.session_state.page = "resultats"
    st.rerun()

# Gestion des pages
if 'page' not in st.session_state:
    st.session_state.page = "recherche"

if 'resultats_vols' not in st.session_state:
    st.session_state.resultats_vols = None

# Affichage de la page correspondante
if st.session_state.page == "resultats":
    page_resultats_vols(st.session_state.resultats_vols)
