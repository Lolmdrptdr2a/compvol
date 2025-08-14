import json
import streamlit as st
from amadeus import Client, ResponseError
from vols import client_id,client_secret,token
from traitement_info import *
import time
from page_flighty import page_flighty


@st.dialog("Erreur")
def erreur():
    st.write("Vous avez oublier d'entrer votre lieu de départ,d'arrivé ou le nombre de passagers")
    if st.button("OK"):
        st.rerun()


with open("Code-IATA-villes.json", encoding="utf-8") as f:
    airports = json.load(f)

amadeus = Client(client_id = client_id,client_secret = client_secret)
st.set_page_config(layout="wide")
st.markdown("""
    <style>
        .block-container {
            max-width: 1000px !important;
            padding-left: 2rem;
            padding-right: 2rem;
        }
    </style>
""", unsafe_allow_html=True)

# Si on est sur la page Flighty → afficher uniquement Flighty
if st.session_state.get("page") == "flighty":
    page_flighty()
    st.stop()  # Empêche l'exécution du reste du script


# Titre de la page
st.title("🛫 Comparateur de Vols")



airport_dict = {f"{a['airport']}  ({a['iata']})": a['iata'] for a in airports}
iata_dict = { f"{a['iata']}": f"{a['airport']}  ({a['iata']})" for a in airports}
options = list(airport_dict.keys())
liste = []
for cle in airport_dict:
    liste.append(airport_dict[cle])
options += liste


a1,a2,a3,a4,a5 = st.columns(5)

with a1:
    allee_retour = st.selectbox("Type de vol", ["Aller-Retour", "Aller-simple"], label_visibility="hidden")
with a3:
    bagage_soute = st.slider("Bagages en soute",0,3,0)
with a4:
    bagage_main = st.slider("Bagages à main",1,3,1)
    
b1,b2,b3,b4 = st.columns(4)

with b1:
    liste = [""] + options
    depart = st.selectbox("Aéroport de départ",liste)
    if len(depart)==3:
       dep = iata_dict[depart]
    else:
        dep = depart
with b2:
    liste = [""] + options
    if depart != "":
        liste.pop(liste.index(dep))
        liste.pop(liste.index(airport_dict[dep]))
    arrivee = st.selectbox("Aéroport d'arrivée",liste)
    #if len(arrivee)==3:
    #    arrivee = iata_dict[arrivee]
with b3:
    date_depart = st.date_input("Date Aller",value=time.strftime("%Y-%m-%d"),min_value=time.strftime("%Y-%m-%d"))
if allee_retour == "Aller-Retour":
    with b4:
        date_retour = st.date_input("Date Retour", value=date_depart,min_value=date_depart)

c1,c2,c3,c4,c5 = st.columns(5)

with c1:
    adultes = st.slider("Adultes",0,10,1)
with c2:
    enfants = st.slider("Enfants",0,10,0)
    
with c4:
    escale = st.checkbox("Sans Escale")
        
with c5:
    cl_liste = ["Economique","Première Économique","Business","Première Classe"]
    cl = st.selectbox("classe",cl_liste)
    cc = ["ECONOMY","PREMIUM_ECONOMY","BUSINESS","FIRST"]
    classe = cc[cl_liste.index(cl)]

if st.button("🔍 Rechercher"):
    if depart=="" or arrivee=="" or (adultes==0 and enfants==0):
        erreur()
    else:
        if len(depart)!=3:
            depart = airport_dict[depart]
        
        if escale:
            escale = 'true'
        else:
            escale = 'false'
        if allee_retour == "Aller-Retour":
            L = recherche(token(),depart,arrivee,allee_retour,adultes,enfants,escale,classe,date_depart,date_retour)
        else:
            L = recherche(token(),depart,arrivee,allee_retour,adultes,enfants,escale,classe,date_depart,date_depart)
            
        st.session_state.resultats_vols = L
        print(L)
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
    


if st.button("📡 Mode Flighty", key="btn_mode_flighty"):
    st.session_state.page = "flighty"
    st.rerun()







