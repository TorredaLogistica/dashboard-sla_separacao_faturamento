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
# HORARIO BRASIL
# =============================

fuso = pytz.timezone("America/Sao_Paulo")
agora = datetime.now(fuso)

st.title("Dashboard SLA Separação e Faturamento")
st.caption(f"Atualizado em {agora.strftime('%d/%m/%Y %H:%M')}")

# =============================
# DICIONÁRIOS DE METAS
# =============================

METAS_CLARO_BRASIL = {
"01/2026":94.45,"02/2026":94.65,"03/2026":94.63,"04/2026":94.93,"05/2026":94.31,
"06/2026":94.21,"07/2026":94.36,"08/2026":95.80,"09/2026":95.36
}

METAS_NET = {"01/2026":90,"02/2026":90,"03/2026":90,"04/2026":90}

METAS_CLARO_TV = {"01/2026":85.02,"02/2026":85.11,"03/2026":85.19}

METAS_EMBRATEL = {"01/2026":80,"02/2026":80,"03/2026":80}

METAS_CLARO_MOVEL = {"01/2026":99.5,"02/2026":99.5,"03/2026":99.5}

def obter_meta(empresa, mes):

    empresa = str(empresa).upper()

    if "CLARO BRASIL" in empresa:
        return METAS_CLARO_BRASIL.get(mes,85)

    elif "NET" in empresa:
        return METAS_NET.get(mes,85)

    elif "CLARO TV" in empresa:
        return METAS_CLARO_TV.get(mes,85)

    elif "EMBRATEL" in empresa:
        return METAS_EMBRATEL.get(mes,85)

    elif "CLARO MOVEL" in empresa:
        return METAS_CLARO_MOVEL.get(mes,85)

    return 85

# =============================
# CARGA DE DADOS
# =============================

@st.cache_data
def load_data():

    caminho_zip = "base_sla.zip"

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

    df["Meta"] = df.apply(lambda x: obter_meta(x["Empresa"],x["Mes_Ano"]),axis=1)

    # =============================
    # CORREÇÃO SLA
    # =============================

    aging = df["Aging_Ajustado_D+"].astype(str).str.upper().str.strip()

    df["flag_d0"] = aging.str.contains(r"D\+0", regex=True, na=False)
    df["flag_d1"] = aging.str.contains(r"D\+1", regex=True, na=False)
    df["flag_d2"] = aging.str.contains(r"D\+2", regex=True, na=False)

    return df

df = load_data()

# =============================
# SIDEBAR
# =============================

with st.sidebar:

    if os.path.exists("logo_claro.png"):
        st.image("logo_claro.png", width=180)

    aba = st.radio("Visualização",["Visão Diária","Evolução Mensal"])

    meses = sorted(df["Mes_Ano"].unique(), reverse=True)

    mes_selecionado = st.selectbox("Mês", meses)

# =============================
# BASE
# =============================

if aba == "Visão Diária":

    base = df[df["Mes_Ano"] == mes_selecionado]

else:

    periodo = st.sidebar.radio("Período", [3,6,9,12], index=3)

    meses = sorted(df["Mes_Ano"].unique())

    base = df[df["Mes_Ano"].isin(meses[-periodo:])]

# =============================
# KPIs
# =============================

total = len(base)

p0 = base["flag_d0"].sum()
p1 = (base["flag_d0"] | base["flag_d1"]).sum()
p2 = (base["flag_d0"] | base["flag_d1"] | base["flag_d2"]).sum()

c1,c2,c3,c4 = st.columns(4)

c1.metric("Até D+0", f"{p0/total*100:.2f}%")
c2.metric("Até D+1", f"{p1/total*100:.2f}%")
c3.metric("Até D+2", f"{p2/total*100:.2f}%")
c4.metric("Total Pedidos", f"{total:,}".replace(",","."))

# =============================
# AGRUPAMENTO
# =============================

if aba == "Visão Diária":

    res = base.groupby("Data NF").agg(
        Pedido=("Pedido","count"),
        D0=("flag_d0","sum"),
        D1=("flag_d1","sum"),
        D2=("flag_d2","sum"),
        Meta=("Meta","mean")
    ).reset_index()

    eixo = "Data NF"

else:

    res = base.groupby("Mes_Ano").agg(
        Pedido=("Pedido","count"),
        D0=("flag_d0","sum"),
        D1=("flag_d1","sum"),
        D2=("flag_d2","sum"),
        Meta=("Meta","mean")
    ).reset_index()

    eixo = "Mes_Ano"

res["Até D+0"] = res["D0"] / res["Pedido"] * 100
res["Até D+1"] = (res["D0"] + res["D1"]) / res["Pedido"] * 100
res["Até D+2"] = (res["D0"] + res["D1"] + res["D2"]) / res["Pedido"] * 100

# =============================
# GRÁFICO
# =============================

fig = go.Figure()

for col in ["Até D+0","Até D+1","Até D+2"]:

    fig.add_trace(go.Scatter(
        x=res[eixo],
        y=res[col],
        mode="lines+markers",
        name=col
    ))

fig.add_trace(go.Scatter(
    x=res[eixo],
    y=res["Meta"],
    name="Meta",
    line=dict(dash="dash", color="black")
))

st.plotly_chart(fig, use_container_width=True)

# =============================
# TABELA
# =============================

view = res[[eixo,"Meta","Até D+0","Até D+1","Até D+2","Pedido"]]

for c in ["Meta","Até D+0","Até D+1","Até D+2"]:
    view[c] = view[c].apply(lambda x: f"{x:.2f}%")

st.dataframe(view, use_container_width=True, hide_index=True)

# =============================
# RANKING CD
# =============================

st.subheader("Ranking CD Origem (SLA D+1)")

rank = base.groupby("CD Origem").agg(
Pedido=("Pedido","count"),
D0=("flag_d0","sum"),
D1=("flag_d1","sum")
).reset_index()

rank["SLA"] = (rank["D0"] + rank["D1"]) / rank["Pedido"] * 100

rank = rank.sort_values("SLA")

fig_bar = px.bar(
rank,
x="CD Origem",
y="SLA",
text=rank["SLA"].apply(lambda x:f"{x:.2f}%"),
color="SLA",
color_continuous_scale=["red","yellow","green"]
)

fig_bar.update_traces(textposition="outside")

st.plotly_chart(fig_bar, use_container_width=True)
