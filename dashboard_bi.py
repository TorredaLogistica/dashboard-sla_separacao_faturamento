import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import pytz
import os
import zipfile

st.set_page_config(layout="wide", page_title="Dashboard SLA Faturamento")

# =============================
# LOGIN
# =============================
def check_password():

    def password_entered():
        if st.session_state["password"] == "claro2026":
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.title("🔒 Acesso Restrito")
        st.text_input("Digite a senha", type="password", on_change=password_entered, key="password")
        st.stop()

    elif not st.session_state["password_correct"]:
        st.text_input("Digite a senha", type="password", on_change=password_entered, key="password")
        st.error("Senha incorreta")
        st.stop()

check_password()

# =============================
# CABEÇALHO
# =============================

fuso = pytz.timezone("America/Sao_Paulo")
agora = datetime.now(fuso)

st.title("Dashboard SLA Separação e Faturamento")
st.caption(f"Atualizado em {agora.strftime('%d/%m/%Y %H:%M')}")

# =============================
# DICIONÁRIOS DE METAS
# =============================
METAS_CLARO_BRASIL = {
    "01/2025": 76.09, "02/2025": 74.38, "03/2025": 79.52, "04/2025": 72.28, "05/2025": 81.73, "06/2025": 88.07,
    "07/2025": 82.91, "08/2025": 89.19, "09/2025": 92.77, "10/2025": 88.68, "11/2025": 82.47, "12/2025": 85.94,
    "01/2026": 94.45, "02/2026": 94.65, "03/2026": 94.63, "04/2026": 94.93, "05/2026": 94.31, "06/2026": 94.21,
    "07/2026": 94.36, "08/2026": 95.80, "09/2026": 95.36, "10/2026": 95.47, "11/2026": 95.56, "12/2026": 95.47
}

METAS_NET = {
    "01/2025": 54.98, "02/2025": 47.34, "03/2025": 55.80, "04/2025": 36.50, "05/2025": 57.16, "06/2025": 73.98,
    "07/2025": 67.22, "08/2025": 76.42, "09/2025": 85.52, "10/2025": 75.33, "11/2025": 65.79, "12/2025": 70.59,
    "01/2026": 90.00, "02/2026": 90.00, "03/2026": 90.00, "04/2026": 90.00, "05/2026": 90.00, "06/2026": 90.00,
    "07/2026": 90.00, "08/2026": 92.00, "09/2026": 92.00, "10/2026": 92.00, "11/2026": 92.00, "12/2026": 92.00
}

METAS_CLARO_TV = {
    "01/2025": 26.91, "02/2025": 31.21, "03/2025": 58.02, "04/2025": 38.19, "05/2025": 54.97, "06/2025": 78.13,
    "07/2025": 82.01, "08/2025": 73.10, "09/2025": 66.67, "10/2025": 64.25, "11/2025": 63.69, "12/2025": 48.48,
    "01/2026": 85.02, "02/2026": 85.11, "03/2026": 85.19, "04/2026": 85.04, "05/2026": 84.80, "06/2026": 84.90,
    "07/2026": 85.19, "08/2026": 84.77, "09/2026": 84.97, "10/2026": 84.97, "11/2026": 85.05, "12/2026": 84.97
}

METAS_EMBRATEL = {
    "01/2025": 43.25, "02/2025": 40.31, "03/2025": 51.70, "04/2025": 27.42, "05/2025": 65.94, "06/2025": 73.60,
    "07/2025": 55.06, "08/2025": 69.74, "09/2025": 82.46, "10/2025": 64.27, "11/2025": 41.33, "12/2025": 67.61,
    "01/2026": 80.00, "02/2026": 80.00, "03/2026": 80.01, "04/2026": 80.02, "05/2026": 80.01, "06/2026": 79.99,
    "07/2026": 79.99, "08/2026": 82.00, "09/2026": 81.98, "10/2026": 82.01, "11/2026": 82.00, "12/2026": 82.00
}

METAS_CLARO_MOVEL = {
    "01/2025": 97.94, "02/2025": 98.17, "03/2025": 98.22, "04/2025": 97.46, "05/2025": 98.39, "06/2025": 98.21,
    "07/2025": 99.05, "08/2025": 98.75, "09/2025": 98.73, "10/2025": 99.46, "11/2025": 96.98, "12/2025": 98.28,
    "01/2026": 99.50, "02/2026": 99.50, "03/2026": 99.50, "04/2026": 99.50, "05/2026": 99.50, "06/2026": 99.50,
    "07/2026": 99.50, "08/2026": 99.50, "09/2026": 99.50, "10/2026": 99.50, "11/2026": 99.50, "12/2026": 99.50
}

# =============================
# FUNÇÕES DE APOIO
# =============================
def estilo_tabela(row):
    try:
        m = float(str(row['Meta']).replace('%','').replace(',', '.'))
        v = float(str(row['Até D+1']).replace('%','').replace(',', '.'))
        return [f"color: {'green' if v >= m else 'red'}; font-weight: bold" if name == 'Até D+1' else "" for name in row.index]
    except:
        return ["" for _ in row.index]

def obter_meta_dinamica(mes, empresas_selecionadas):
    if empresas_selecionadas and len(empresas_selecionadas) == 1:
        emp = empresas_selecionadas[0]
        if emp == 'NET': return METAS_NET.get(mes, 85.0)
        if emp == 'Claro TV': return METAS_CLARO_TV.get(mes, 85.0)
        if emp == 'Embratel': return METAS_EMBRATEL.get(mes, 85.0)
        if emp == 'Claro Movel': return METAS_CLARO_MOVEL.get(mes, 85.0)
    return METAS_CLARO_BRASIL.get(mes, 85.0)

# =============================
# CARGA DE DADOS
# =============================

@st.cache_data(ttl=3600)
def load_data():

    caminho_zip = "Faturamento SLA 2025 - Novo Ajuste.zip"

    if not os.path.exists(caminho_zip):
        st.error("Arquivo ZIP não encontrado no repositório.")
        st.stop()

    with zipfile.ZipFile(caminho_zip) as z:

        nome_csv = z.namelist()[0]

        with z.open(nome_csv) as f:

            df = pd.read_csv(
                f,
                sep=";",
                low_memory=False
            )

    df.columns = df.columns.str.strip()

    df["Data NF"] = pd.to_datetime(df["Data NF"], errors="coerce")

    df = df.dropna(subset=["Data NF"])

    df["Mes_Ano"] = df["Data NF"].dt.strftime("%m/%Y")

    aging = df["Aging_Ajustado_D+"].astype(str)

    df["flag_d0"] = aging.str.contains(r"D\+0", regex=True, na=False)
    df["flag_d1"] = aging.str.contains(r"D\+1", regex=True, na=False)
    df["flag_d2"] = aging.str.contains(r"D\+2", regex=True, na=False)

    return df

df = load_data()

# =============================
# SIDEBAR
# =============================

with st.sidebar:

    logo_path = "logo_claro.png"

    if os.path.exists(logo_path):
        st.image(logo_path, width=180)

    aba = st.radio("Visualização", ["📅 Visão Diária", "📊 Evolução Mensal"])

    lista_meses = sorted(df["Mes_Ano"].unique(), reverse=True)

    mes_selecionado = st.selectbox("Mês de Referência", lista_meses)

    filtros = ["Operador","CD Origem","Empresa","Canal","Unidade de Negocio","Canal de Atuacao"]

    mask = np.ones(len(df), dtype=bool)

    for col in filtros:

        if col in df.columns:

            vals = st.multiselect(col, sorted(df[col].dropna().unique()))

            if vals:
                mask &= df[col].isin(vals)

dff = df[mask].copy()

# =============================
# BASE
# =============================

if aba == "📅 Visão Diária":

    base = dff[dff["Mes_Ano"] == mes_selecionado]

else:

    periodo = st.radio("Período acumulado", [3,6,9,12], index=3)

    meses = sorted(dff["Mes_Ano"].unique())

    base = dff[dff["Mes_Ano"].isin(meses[-periodo:])]

# =============================
# KPIs
# =============================

total = len(base)

if total > 0:

    p0 = base["flag_d0"].sum()
    p1 = (base["flag_d0"] | base["flag_d1"]).sum()
    p2 = (base["flag_d0"] | base["flag_d1"] | base["flag_d2"]).sum()

    c1,c2,c3,c4 = st.columns(4)

    c1.metric("Até D+0", f"{p0/total*100:.2f}%")
    c2.metric("Até D+1", f"{p1/total*100:.2f}%")
    c3.metric("Até D+2", f"{p2/total*100:.2f}%")
    c4.metric("Total Pedidos", f"{total:,}".replace(",", "."))

# =============================
# AGRUPAMENTO
# =============================

if aba == "📅 Visão Diária":

    res = base.groupby("Data NF").agg(
        Pedido=("Pedido","count"),
        D0=("flag_d0","sum"),
        D1=("flag_d1","sum"),
        D2=("flag_d2","sum")
    ).reset_index()

    res["Até D+0"] = res["D0"]/res["Pedido"]*100
    res["Até D+1"] = (res["D0"]+res["D1"])/res["Pedido"]*100
    res["Até D+2"] = (res["D0"]+res["D1"]+res["D2"])/res["Pedido"]*100

    res["Meta"] = obter_meta(mes_selecionado)

    res["Data"] = res["Data NF"].dt.strftime("%d/%m/%Y")

    eixo = "Data"

else:

    res = base.groupby("Mes_Ano").agg(
        Pedido=("Pedido","count"),
        D0=("flag_d0","sum"),
        D1=("flag_d1","sum"),
        D2=("flag_d2","sum")
    ).reset_index()

    res["Até D+0"] = res["D0"]/res["Pedido"]*100
    res["Até D+1"] = (res["D0"]+res["D1"])/res["Pedido"]*100
    res["Até D+2"] = (res["D0"]+res["D1"]+res["D2"])/res["Pedido"]*100

    res["Meta"] = res["Mes_Ano"].apply(obter_meta)

    eixo = "Mes_Ano"

# =============================
# GRÁFICO
# =============================

fig = go.Figure()

for col in ["Até D+0","Até D+1","Até D+2"]:

    fig.add_trace(
        go.Scatter(
            x=res[eixo],
            y=res[col],
            mode="lines+markers",
            name=col
        )
    )

fig.add_trace(
    go.Scatter(
        x=res[eixo],
        y=res["Meta"],
        name="Meta",
        line=dict(dash="dash", color="black")
    )
)

st.plotly_chart(fig, use_container_width=True)

# =============================
# TABELA
# =============================

view = res[[eixo,"Meta","Até D+0","Até D+1","Até D+2","Pedido"]]

for c in ["Até D+0","Até D+1","Até D+2","Meta"]:
    view[c] = view[c].apply(lambda x: f"{x:.2f}%")

st.dataframe(view, use_container_width=True, hide_index=True)

# =============================
# RANKING
# =============================

st.markdown("---")
st.subheader("Ranking CD Origem (SLA D+1)")

rank = base.groupby("CD Origem").agg(
    Pedido=("Pedido","count"),
    D0=("flag_d0","sum"),
    D1=("flag_d1","sum")
).reset_index()

rank["Até D+1"] = (rank["D0"]+rank["D1"])/rank["Pedido"]*100

rank = rank.sort_values("Até D+1")

fig_bar = px.bar(
    rank,
    x="CD Origem",
    y="Até D+1",
    text=rank["Até D+1"].apply(lambda x: f"{x:.2f}%"),
    color="Até D+1",
    color_continuous_scale=["red","yellow","green"]
)

fig_bar.update_traces(textposition="outside")

st.plotly_chart(fig_bar, use_container_width=True)
