import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
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
st.title("Dashboard SLA Separação e Faturamento")
st.caption(f"Atualizado em {datetime.now().strftime('%d/%m/%Y %H:%M')}")

# =============================
# CARGA DE DADOS (ZIP GITHUB)
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

    df["flag_d0"] = aging.str.contains("D+0", na=False)
    df["flag_d1"] = aging.str.contains("D+1", na=False)
    df["flag_d2"] = aging.str.contains("D+2", na=False)

    return df


df = load_data()

# =============================
# SIDEBAR
# =============================
with st.sidebar:

    if os.path.exists("logo_claro.png"):
        st.image("logo_claro.png", use_container_width=True)
    else:
        st.markdown("<h2 style='text-align:center;color:#e1261c'>CLARO</h2>", unsafe_allow_html=True)

    aba = st.radio("Visualização", ["📅 Visão Diária", "📊 Evolução Mensal"])

    lista_meses = (
        pd.to_datetime(df["Mes_Ano"], format="%m/%Y", errors="coerce")
        .dropna()
        .sort_values(ascending=False)
        .dt.strftime("%m/%Y")
        .unique()
    )

    mes_selecionado = st.selectbox("Mês de Referência", lista_meses)

    filtros = ["Operador","CD Origem","Empresa","Canal","Unidade de Negocio","Canal de Atuacao"]

    mask = np.ones(len(df), dtype=bool)
    filtros_selecionados = {}

    for col in filtros:

        if col in df.columns:

            vals = st.multiselect(col, sorted(df[col].dropna().unique()))

            filtros_selecionados[col] = vals

            if vals:
                mask &= df[col].isin(vals)

dff_global = df[mask].copy()

# =============================
# DASHBOARD
# =============================

if aba == "📅 Visão Diária":

    st.subheader(f"Indicadores Consolidados - {mes_selecionado}")

    base = dff_global[dff_global["Mes_Ano"] == mes_selecionado].copy()

else:

    periodo = st.radio("Período acumulado", [3,6,9,12,24], index=3)

    meses_disponiveis = (
        pd.to_datetime(dff_global["Mes_Ano"], format="%m/%Y", errors="coerce")
        .dropna()
        .sort_values()
        .dt.strftime("%m/%Y")
        .unique()
    )

    meses_filtrados = meses_disponiveis[-periodo:]

    base = dff_global[dff_global["Mes_Ano"].isin(meses_filtrados)].copy()

    st.subheader(f"Evolução mensal ({periodo} meses)")


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

    res["Mês"] = res["Data NF"].dt.strftime("%d/%m")

else:

    res = base.groupby("Mes_Ano").agg(
        Pedido=("Pedido","count"),
        D0=("flag_d0","sum"),
        D1=("flag_d1","sum"),
        D2=("flag_d2","sum")
    ).reset_index()

    res["data_sort"] = pd.to_datetime(res["Mes_Ano"], format="%m/%Y")

    res = res.sort_values("data_sort")

    res["Até D+0"] = res["D0"]/res["Pedido"]*100
    res["Até D+1"] = (res["D0"]+res["D1"])/res["Pedido"]*100
    res["Até D+2"] = (res["D0"]+res["D1"]+res["D2"])/res["Pedido"]*100

    res["Mês"] = res["Mes_Ano"]

# =============================
# GRÁFICO
# =============================

fig = go.Figure()

for col in ["Até D+0","Até D+1","Até D+2"]:

    fig.add_trace(
        go.Scatter(
            x=res["Mês"],
            y=res[col],
            mode="lines+markers",
            name=col
        )
    )

fig.update_layout(
    hovermode="x unified",
    legend=dict(orientation="h", y=1.02)
)

st.plotly_chart(fig, use_container_width=True)

# =============================
# TABELA
# =============================

view = res[["Mês","Pedido","Até D+0","Até D+1","Até D+2"]].copy()

for c in ["Até D+0","Até D+1","Até D+2"]:
    view[c] = view[c].apply(lambda x: f"{x:.2f}%")

st.dataframe(view, use_container_width=True, hide_index=True)

# =============================
# RANKING CD
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
    text=rank["Até D+1"].round(2),
    color="Até D+1",
    color_continuous_scale="RdYlGn"
)

st.plotly_chart(fig_bar, use_container_width=True)
