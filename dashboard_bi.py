import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import os

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

    if not st.session_state["password_correct"]:
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
# METAS
# =============================

METAS_CLARO_BRASIL = {
"01/2026":94.45,"02/2026":94.65,"03/2026":94.63,"04/2026":94.93
}

METAS_NET = {"01/2026":90,"02/2026":90,"03/2026":90}
METAS_CLARO_TV = {"01/2026":85.02,"02/2026":85.11,"03/2026":85.19}
METAS_EMBRATEL = {"01/2026":80,"02/2026":80,"03/2026":80}
METAS_CLARO_MOVEL = {"01/2026":99.5,"02/2026":99.5,"03/2026":99.5}

def obter_meta(mes, empresa):

    empresa=str(empresa).upper()

    if "NET" in empresa:
        return METAS_NET.get(mes,85)

    if "TV" in empresa:
        return METAS_CLARO_TV.get(mes,85)

    if "EMBRATEL" in empresa:
        return METAS_EMBRATEL.get(mes,85)

    if "MOVEL" in empresa:
        return METAS_CLARO_MOVEL.get(mes,85)

    return METAS_CLARO_BRASIL.get(mes,85)

# =============================
# CARGA DE DADOS XLSB
# =============================

@st.cache_data
def load_data():

    arquivos=[f for f in os.listdir() if f.lower().endswith(".xlsb")]

    if len(arquivos)==0:
        st.error("Arquivo XLSB não encontrado no repositório")
        st.stop()

    arquivo=arquivos[0]

    df=pd.read_excel(arquivo,engine="pyxlsb")

    df.columns=df.columns.str.strip()

    # =============================
    # CORRIGIR DATA XLSB
    # =============================

    if pd.api.types.is_numeric_dtype(df["Data NF"]):

        df["Data NF"]=pd.to_datetime("1899-12-30")+pd.to_timedelta(df["Data NF"],unit="D")

    else:

        df["Data NF"]=pd.to_datetime(df["Data NF"],errors="coerce")

    df=df.dropna(subset=["Data NF"])

    df["Mes_Ano"]=df["Data NF"].dt.strftime("%m/%Y")

    df["Mes_Ano_dt"]=pd.to_datetime(df["Mes_Ano"],format="%m/%Y")

    aging=df["Aging_Ajustado_D+"].astype(str)

    df["flag_d0"]=aging.str.contains("D+0")
    df["flag_d1"]=aging.str.contains("D+1")
    df["flag_d2"]=aging.str.contains("D+2")

    return df

df=load_data()

# =============================
# SIDEBAR
# =============================

with st.sidebar:

    if os.path.exists("logo_claro.png"):
        st.image("logo_claro.png",use_container_width=True)

    aba=st.radio("Visualização",["Visão Diária","Evolução Mensal"])

    lista_meses=(
        df.sort_values("Mes_Ano_dt",ascending=False)["Mes_Ano"].unique()
    )

    mes_selecionado=st.selectbox("Mês",lista_meses)

    filtros=["Operador","CD Origem","Empresa","Canal","Unidade de Negocio","Canal de Atuacao"]

    mask=np.ones(len(df),dtype=bool)

    for col in filtros:

        if col in df.columns:

            valores=st.multiselect(col,sorted(df[col].dropna().unique()))

            if valores:

                mask &= df[col].isin(valores)

df=df[mask]

# =============================
# BASE
# =============================

if aba=="Visão Diária":

    base=df[df["Mes_Ano"]==mes_selecionado]

else:

    periodo=st.sidebar.radio("Período",[3,6,9,12],index=3)

    meses=df.sort_values("Mes_Ano_dt")["Mes_Ano"].unique()

    base=df[df["Mes_Ano"].isin(meses[-periodo:])]

# =============================
# KPIs
# =============================

total=len(base)

p0=base["flag_d0"].sum()
p1=(base["flag_d0"]|base["flag_d1"]).sum()
p2=(base["flag_d0"]|base["flag_d1"]|base["flag_d2"]).sum()

c1,c2,c3,c4=st.columns(4)

c1.metric("Até D+0",f"{p0/total*100:.2f}%")
c2.metric("Até D+1",f"{p1/total*100:.2f}%")
c3.metric("Até D+2",f"{p2/total*100:.2f}%")
c4.metric("Total Pedidos",f"{total:,}".replace(",","."))

# =============================
# AGRUPAMENTO
# =============================

if aba=="Visão Diária":

    res=base.groupby("Data NF").agg(
    Pedido=("Pedido","count"),
    D0=("flag_d0","sum"),
    D1=("flag_d1","sum"),
    D2=("flag_d2","sum")
    ).reset_index()

    res["Até D+0"]=res["D0"]/res["Pedido"]*100
    res["Até D+1"]=(res["D0"]+res["D1"])/res["Pedido"]*100
    res["Até D+2"]=(res["D0"]+res["D1"]+res["D2"])/res["Pedido"]*100

    res["Mês"]=res["Data NF"].dt.strftime("%d/%m")

else:

    res=base.groupby("Mes_Ano").agg(
    Pedido=("Pedido","count"),
    D0=("flag_d0","sum"),
    D1=("flag_d1","sum"),
    D2=("flag_d2","sum")
    ).reset_index()

    res["Até D+0"]=res["D0"]/res["Pedido"]*100
    res["Até D+1"]=(res["D0"]+res["D1"])/res["Pedido"]*100
    res["Até D+2"]=(res["D0"]+res["D1"]+res["D2"])/res["Pedido"]*100

    res["Mês"]=res["Mes_Ano"]

# =============================
# GRÁFICO
# =============================

fig=go.Figure()

for col in ["Até D+0","Até D+1","Até D+2"]:

    fig.add_trace(go.Scatter(
    x=res["Mês"],
    y=res[col],
    mode="lines+markers",
    name=col
    ))

st.plotly_chart(fig,use_container_width=True)

# =============================
# RANKING CD
# =============================

st.subheader("Ranking CD Origem (SLA D+1)")

rank=base.groupby("CD Origem").agg(
Pedido=("Pedido","count"),
D0=("flag_d0","sum"),
D1=("flag_d1","sum")
).reset_index()

rank["SLA"]=(rank["D0"]+rank["D1"])/rank["Pedido"]*100

rank=rank.sort_values("SLA")

fig_bar=px.bar(
rank,
x="CD Origem",
y="SLA",
text=rank["SLA"].apply(lambda x:f"{x:.2f}%"),
color="SLA",
color_continuous_scale=["red","yellow","green"]
)

st.plotly_chart(fig_bar,use_container_width=True)
