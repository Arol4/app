import streamlit as st
import pandas as pd
import pymysql
import time

st.set_page_config(page_title="Dashboard MySQL Aiven", layout="wide")
st.title("Statistiques en Temps Réel 📊")

# 1. Panneau de contrôle de l'actualisation
# On utilise des colonnes pour aligner l'interrupteur et le bouton côte à côte
col1, col2 = st.columns([1, 1])

with col1:
    # L'interrupteur est activé (True) par défaut
    auto_refresh = st.toggle("Activer l'actualisation automatique (5s)", value=True)

with col2:
    # Dans Streamlit, cliquer sur un bouton relance automatiquement tout le script.
    # On n'a donc pas besoin d'écrire de logique complexe ici, le simple clic suffit à rafraîchir !
    st.button("🔄 Actualiser manuellement")

st.markdown("---") # Ligne de séparation visuelle

# 2. Fonction sécurisée pour récupérer les données
def get_data():
    # On ouvre la connexion à l'intérieur de la fonction (plus de cache)
    conn = pymysql.connect(
        host=st.secrets["mysql"]["host"],
        port=st.secrets["mysql"]["port"],
        user=st.secrets["mysql"]["user"],
        password=st.secrets["mysql"]["password"],
        database=st.secrets["mysql"]["database"],
        ssl={"ca": "ca.pem"} 
    )
    
    try:
        # On exécute la requête
        query = "SELECT date_enregistrement, valeur FROM mes_statistiques"
        df = pd.read_sql(query, conn)
        return df
    finally:
        # Le bloc 'finally' garantit que la connexion sera TOUJOURS fermée,
        # même si une erreur survient pendant la lecture des données.
        # Cela évite de saturer la limite de connexions de ton serveur Aiven.
        conn.close()

# 3. Affichage du graphique
try:
    df = get_data()
    # ... la suite de ton code (if not df.empty: etc...)
except Exception as e:
    st.error(f"Impossible de récupérer les données : {e}")
    st.stop()

# 4. Affichage du graphique
df = get_data()

if not df.empty:
    df = df.set_index("date_enregistrement")
    
    st.subheader("Évolution des valeurs")
    st.line_chart(df)
    st.write("Données brutes :", df)
    # Optionnel : Afficher l'heure de la dernière mise à jour
    st.caption(f"Dernière mise à jour des données : {time.strftime('%H:%M:%S')}")
else:
    st.info("La table est vide. Ajoute des données via DBeaver/Workbench !")

# 5. Logique d'actualisation automatique (placée tout à la fin)
if auto_refresh:
    time.sleep(5)
    st.rerun()