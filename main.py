import streamlit as st
import pandas as pd
import pymysql
import time
from datetime import date, timedelta
import altair as alt

# ---------- Configuration de la page ----------
st.set_page_config(
    page_title="Dashboard Boutique - Gestion Complète",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ---------- Style personnalisé (optionnel) ----------
st.markdown("""
<style>
    .kpi-box {
        background-color: #f0f2f6;
        padding: 20px;
        border-radius: 10px;
        text-align: center;
        box-shadow: 2px 2px 10px rgba(0,0,0,0.05);
    }
    .kpi-value {
        font-size: 28px;
        font-weight: bold;
        color: #1f77b4;
    }
    .kpi-label {
        font-size: 14px;
        color: #444;
    }
</style>
""", unsafe_allow_html=True)

# ---------- Fonctions de connexion et de lecture ----------
def get_connection():
    """Retourne une connexion pymysql avec les secrets Streamlit."""
    return pymysql.connect(
        host=st.secrets["mysql"]["host"],
        port=st.secrets["mysql"]["port"],
        user=st.secrets["mysql"]["user"],
        password=st.secrets["mysql"]["password"],
        database=st.secrets["mysql"]["database"],
        ssl={"ca": "ca.pem"}
    )

def read_query(query, params=None):
    """Exécute une requête et retourne un DataFrame pandas."""
    conn = get_connection()
    try:
        df = pd.read_sql(query, conn, params=params)
        return df
    finally:
        conn.close()

# ---------- Chargement des données de référence ----------
@st.cache_data(ttl=0, show_spinner=False)
def load_reference_data():
    """Charge les listes de fournisseurs, clients, produits pour les filtres."""
    fournisseurs = read_query("SELECT id_fournisseur, nom_fournisseur FROM fournisseur ORDER BY nom_fournisseur")
    clients = read_query("SELECT id_client, nom_client FROM client ORDER BY nom_client")
    produits = read_query("SELECT id_produit, designation FROM produit ORDER BY designation")
    return fournisseurs, clients, produits

fournisseurs_df, clients_df, produits_df = load_reference_data()

# ---------- Sidebar : Filtres ----------
st.sidebar.title("🔍 Filtres")

# Période commune pour les ventes et les livraisons
st.sidebar.subheader("Période d'analyse")
default_start = date.today() - timedelta(days=365)
default_end = date.today()
date_range = st.sidebar.date_input(
    "Du *au*",
    value=(default_start, default_end),
    min_value=date(2020, 1, 1),
    max_value=date.today()
)
if len(date_range) == 2:
    start_date, end_date = date_range
else:
    st.sidebar.warning("Veuillez sélectionner une plage de dates complète.")
    start_date = default_start
    end_date = default_end

# Filtres optionnels
with st.sidebar.expander("Fournisseur", expanded=False):
    selected_fournisseur = st.selectbox(
        "Choisir un fournisseur",
        options=["Tous"] + list(fournisseurs_df['nom_fournisseur']),
        index=0
    )
with st.sidebar.expander("Client", expanded=False):
    selected_client = st.selectbox(
        "Choisir un client",
        options=["Tous"] + list(clients_df['nom_client']),
        index=0
    )
with st.sidebar.expander("Produit", expanded=False):
    selected_produit = st.selectbox(
        "Choisir un produit",
        options=["Tous"] + list(produits_df['designation']),
        index=0
    )

# ---------- En-tête principal et bouton d'actualisation ----------
col_title, col_btn = st.columns([3, 1])
with col_title:
    st.title("📊 Statistiques de la Boutique")
with col_btn:
    st.button("🔄 Actualiser manuellement")
st.markdown("---")

# ---------- Préparation des clauses WHERE pour les requêtes ----------
# On construit dynamiquement les filtres SQL
where_conditions = []
params = {}

# Filtre période (sur commande.date_commande pour les ventes, sur livrer.date_livraison pour les livraisons)
where_date_commande = "c.date_commande BETWEEN %(start_date)s AND %(end_date)s"
where_date_livraison = "l.date_livraison BETWEEN %(start_date)s AND %(end_date)s"
params['start_date'] = start_date
params['end_date'] = end_date

if selected_client != "Tous":
    client_id = clients_df.loc[clients_df['nom_client'] == selected_client, 'id_client'].iloc[0]
    where_conditions.append("c.id_client = %(client_id)s")
    params['client_id'] = int(client_id)  # conversion pour paramètre SQL

if selected_fournisseur != "Tous":
    frn_id = fournisseurs_df.loc[fournisseurs_df['nom_fournisseur'] == selected_fournisseur, 'id_fournisseur'].iloc[0]
    where_conditions.append("l.id_fournisseur = %(frn_id)s")
    params['frn_id'] = int(frn_id)

if selected_produit != "Tous":
    prod_id = produits_df.loc[produits_df['designation'] == selected_produit, 'id_produit'].iloc[0]
    where_conditions.append("ct.id_produit = %(prod_id)s")
    params['prod_id'] = int(prod_id)

# Construction des sous-chaînes WHERE pour les requêtes ventes et livraisons
where_sales_extra = " AND " + " AND ".join(where_conditions) if where_conditions else ""
where_liv_extra = " AND " + " AND ".join(where_conditions) if where_conditions else ""

# ---------- Requêtes pour les KPI et graphiques ----------
# 1. Nombre total de produits, fournisseurs, clients (non filtrés par période)
total_produits = read_query("SELECT COUNT(*) AS nb FROM produit")['nb'][0]
total_fournisseurs = read_query("SELECT COUNT(*) AS nb FROM fournisseur")['nb'][0]
total_clients = read_query("SELECT COUNT(*) AS nb FROM client")['nb'][0]

# 2. Nombre de commandes dans la période
query_cmd_count = f"""
SELECT COUNT(DISTINCT c.id_commande) AS nb
FROM commande c
JOIN contenir ct ON c.id_commande = ct.id_commande
WHERE {where_date_commande} {where_sales_extra}
"""
total_commandes = read_query(query_cmd_count, params)['nb'][0]

# 3. Chiffre d'affaires HT (somme des lignes de commande)
query_ca = f"""
SELECT SUM(ct.quantite_commandee * p.prix_unitaire) AS ca
FROM commande c
JOIN contenir ct ON c.id_commande = ct.id_commande
JOIN produit p ON ct.id_produit = p.id_produit
WHERE {where_date_commande} {where_sales_extra}
"""
ca = read_query(query_ca, params)['ca'][0]
ca = ca if ca is not None else 0

# 4. Total versé (paiements) pour les factures dont la commande est dans la période
query_paiements = f"""
SELECT SUM(v.somme) AS total_verse
FROM versement v
JOIN facture f ON v.id_facture = f.id_facture
JOIN commande c ON f.id_commande = c.id_commande
WHERE {where_date_commande} {where_sales_extra.replace('c.', 'c.')}  # c. déjà présent
"""
total_paye = read_query(query_paiements, params)['total_verse'][0]
total_paye = total_paye if total_paye is not None else 0

# 5. Montant restant dû (total facturé - total versé) pour les commandes de la période
# On considère le montant facturé comme stocké dans facture.montant_ht (s'il existe) sinon on le calcule
# Pour simplifier, on utilise le montant calculé à partir des lignes (le même que le CA ci-dessus)
# mais les factures peuvent avoir des montants différents. On va utiliser le montant calculé pour le reste dû global.
# Pour plus de précision, on pourrait faire une somme des factures.
# Ici, nous calculons le reste à payer global comme ca - total_paye (en supposant que toutes les commandes sont facturées)
reste_a_payer = ca - total_paye

# 6. Évolution du CA quotidien
query_ca_daily = f"""
SELECT c.date_commande AS date, SUM(ct.quantite_commandee * p.prix_unitaire) AS ca
FROM commande c
JOIN contenir ct ON c.id_commande = ct.id_commande
JOIN produit p ON ct.id_produit = p.id_produit
WHERE c.date_commande BETWEEN %(start_date)s AND %(end_date)s {where_sales_extra}
GROUP BY c.date_commande
ORDER BY c.date_commande
"""
df_ca_daily = read_query(query_ca_daily, params)

# 7. Top 10 produits par quantité vendue
query_top_produits = f"""
SELECT p.designation, SUM(ct.quantite_commandee) AS qte_vendue
FROM commande c
JOIN contenir ct ON c.id_commande = ct.id_commande
JOIN produit p ON ct.id_produit = p.id_produit
WHERE c.date_commande BETWEEN %(start_date)s AND %(end_date)s {where_sales_extra}
GROUP BY p.id_produit, p.designation
ORDER BY qte_vendue DESC
LIMIT 10
"""
df_top_produits = read_query(query_top_produits, params)

# 8. Top 10 clients par CA
query_top_clients = f"""
SELECT cl.nom_client, SUM(ct.quantite_commandee * p.prix_unitaire) AS ca_client
FROM commande c
JOIN contenir ct ON c.id_commande = ct.id_commande
JOIN produit p ON ct.id_produit = p.id_produit
JOIN client cl ON c.id_client = cl.id_client
WHERE c.date_commande BETWEEN %(start_date)s AND %(end_date)s {where_sales_extra}
GROUP BY cl.id_client, cl.nom_client
ORDER BY ca_client DESC
LIMIT 10
"""
df_top_clients = read_query(query_top_clients, params)

# 9. Livraisons par fournisseur (quantité livrée)
query_livraisons = f"""
SELECT f.nom_fournisseur, SUM(l.quantite_livree) AS qte_livree
FROM livrer l
JOIN fournisseur f ON l.id_fournisseur = f.id_fournisseur
WHERE {where_date_livraison} {where_liv_extra}
GROUP BY f.id_fournisseur, f.nom_fournisseur
ORDER BY qte_livree DESC
"""
df_livraisons = read_query(query_livraisons, params)

# 10. Dernières commandes avec statut de paiement
query_last_orders = f"""
SELECT 
    c.id_commande,
    c.date_commande,
    cl.nom_client,
    SUM(ct.quantite_commandee * p.prix_unitaire) AS total_ht,
    COALESCE(SUM(v.somme), 0) AS paye,
    SUM(ct.quantite_commandee * p.prix_unitaire) - COALESCE(SUM(v.somme), 0) AS reste_a_payer
FROM commande c
JOIN contenir ct ON c.id_commande = ct.id_commande
JOIN produit p ON ct.id_produit = p.id_produit
JOIN client cl ON c.id_client = cl.id_client
LEFT JOIN facture f ON c.id_commande = f.id_commande
LEFT JOIN versement v ON f.id_facture = v.id_facture
WHERE c.date_commande BETWEEN %(start_date)s AND %(end_date)s {where_sales_extra}
GROUP BY c.id_commande, c.date_commande, cl.nom_client
ORDER BY c.date_commande DESC
LIMIT 100
"""
df_orders = read_query(query_last_orders, params)

# ---------- Affichage du tableau de bord ----------

# ---- KPI en haut ----
st.subheader("📌 Indicateurs clés")
kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
with kpi1:
    st.markdown(f"<div class='kpi-box'><div class='kpi-value'>{total_produits}</div><div class='kpi-label'>Produits</div></div>", unsafe_allow_html=True)
with kpi2:
    st.markdown(f"<div class='kpi-box'><div class='kpi-value'>{total_fournisseurs}</div><div class='kpi-label'>Fournisseurs</div></div>", unsafe_allow_html=True)
with kpi3:
    st.markdown(f"<div class='kpi-box'><div class='kpi-value'>{total_clients}</div><div class='kpi-label'>Clients</div></div>", unsafe_allow_html=True)
with kpi4:
    st.markdown(f"<div class='kpi-box'><div class='kpi-value'>{total_commandes}</div><div class='kpi-label'>Commandes ({start_date} - {end_date})</div></div>", unsafe_allow_html=True)
with kpi5:
    st.markdown(f"<div class='kpi-box'><div class='kpi-value'>{ca:,.0f} FCFA</div><div class='kpi-label'>CA HT</div></div>", unsafe_allow_html=True)

kpi6, kpi7, kpi8 = st.columns(3)
with kpi6:
    st.markdown(f"<div class='kpi-box'><div class='kpi-value'>{total_paye:,.0f} FCFA</div><div class='kpi-label'>Paiements reçus</div></div>", unsafe_allow_html=True)
with kpi7:
    st.markdown(f"<div class='kpi-box'><div class='kpi-value'>{reste_a_payer:,.0f} FCFA</div><div class='kpi-label'>Reste à payer</div></div>", unsafe_allow_html=True)
with kpi8:
    ratio = (total_paye/ca*100) if ca > 0 else 0
    st.markdown(f"<div class='kpi-box'><div class='kpi-value'>{ratio:.1f}%</div><div class='kpi-label'>Taux de recouvrement</div></div>", unsafe_allow_html=True)

st.markdown("---")

# ---- Graphiques ----
col_left, col_right = st.columns(2)

with col_left:
    st.subheader("📈 Évolution du chiffre d'affaires quotidien")
    if not df_ca_daily.empty:
        chart = alt.Chart(df_ca_daily).mark_area(
            color='lightblue',
            line={'color':'darkblue'}
        ).encode(
            x=alt.X('date:T', title='Date'),
            y=alt.Y('ca:Q', title='CA (FCFA)')
        ).properties(height=300)
        st.altair_chart(chart, use_container_width=True)
    else:
        st.info("Aucune vente sur la période.")

with col_right:
    st.subheader("🏆 Top 10 des produits les plus vendus")
    if not df_top_produits.empty:
        chart = alt.Chart(df_top_produits).mark_bar(color='orange').encode(
            x=alt.X('qte_vendue:Q', title='Quantité vendue'),
            y=alt.Y('designation:N', sort='-x', title='Produit')
        ).properties(height=300)
        st.altair_chart(chart, use_container_width=True)
    else:
        st.info("Aucune vente pour ce filtre.")

st.markdown("---")

col_left2, col_right2 = st.columns(2)

with col_left2:
    st.subheader("👥 Top 10 clients par chiffre d'affaires")
    if not df_top_clients.empty:
        chart = alt.Chart(df_top_clients).mark_bar(color='green').encode(
            x=alt.X('ca_client:Q', title='CA (FCFA)'),
            y=alt.Y('nom_client:N', sort='-x', title='Client')
        ).properties(height=300)
        st.altair_chart(chart, use_container_width=True)
    else:
        st.info("Aucune donnée client sur la période.")

with col_right2:
    st.subheader("🚚 Livraisons par fournisseur (quantité)")
    if not df_livraisons.empty:
        chart = alt.Chart(df_livraisons).mark_bar(color='purple').encode(
            x=alt.X('qte_livree:Q', title='Quantité livrée'),
            y=alt.Y('nom_fournisseur:N', sort='-x', title='Fournisseur')
        ).properties(height=300)
        st.altair_chart(chart, use_container_width=True)
    else:
        st.info("Aucune livraison sur la période.")

st.markdown("---")

# ---- Tableau des commandes avec statut de paiement ----
st.subheader("📋 Dernières commandes et soldes")
if not df_orders.empty:
    # Formatage des colonnes monétaires
    df_display = df_orders.copy()
    df_display['total_ht'] = df_display['total_ht'].apply(lambda x: f"{x:,.0f} FCFA")
    df_display['paye'] = df_display['paye'].apply(lambda x: f"{x:,.0f} FCFA")
    df_display['reste_a_payer'] = df_display['reste_a_payer'].apply(lambda x: f"{x:,.0f} FCFA")
    df_display.rename(columns={
        'id_commande': 'N° Commande',
        'date_commande': 'Date',
        'nom_client': 'Client',
        'total_ht': 'Total HT',
        'paye': 'Payé',
        'reste_a_payer': 'Reste à payer'
    }, inplace=True)
    st.dataframe(df_display, use_container_width=True, hide_index=True, height=400)
else:
    st.info("Aucune commande sur la période sélectionnée.")

# ---- Pied de page ----
st.markdown("---")
st.caption(f"Dashboard actualisé le {time.strftime('%d/%m/%Y à %H:%M:%S')} • Données filtrées du {start_date} au {end_date}")
