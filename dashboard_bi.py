import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from datetime import datetime
import pytz
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
# HORA BRASIL
# =============================

brasil = pytz.timezone("America/Sao_Paulo")
agora = datetime.now(brasil)

st.title("Dashboard SLA Separação e Faturamento")
st.caption(f"Atualizado em {agora.strftime('%d/%m/%Y %H:%M')}")

# =============================
# METAS
# =============================

METAS_CLARO_BRASIL = {
"01/2025":76.09,"02/2025":74.38,"03/2025":79.52,"04/2025":72.28,"05/2025":81.73,"06/2025":88.07,
"07/2025":82.91,"08/2025":89.19,"09/2025":92.77,"10/2025":88.68,"11/2025":82.47,"12/2025":85.94,
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
# LEITURA XLSB
# =============================

@st.cache_data
def load_data():

    arquivos=[f for f in os.listdir() if f.lower().endswith(".xlsb")]

    if len(arquivos)==0:
        st.error("Arquivo XLSB não encontrado")
        st.stop()

    arquivo=arquivos[0]

    df=pd.read_excel(arquivo,engine="pyxlsb")

    df.columns=df.columns.str.strip()

    # corrigir data

    if pd.api.types.is_numeric_dtype(df["Data NF"]):

        df["Data NF"]=pd.to_datetime("1899-12-30")+pd.to_timedelta(df["Data NF"],unit="D")

    else:

        df["Data NF"]=pd.to_datetime(df["Data NF"],errors="coerce")

    df=df.dropna(subset=["Data NF"])

    df["Mes_Ano"]=df["Data NF"].dt.strftime("%m/%Y")

    df["Mes_Ano_dt"]=pd.to_datetime(df["Mes_Ano"],format="%m/%Y")

    # SLA

    aging=df["Aging_Ajustado_D+"].astype(str).str.upper().str.strip()

    aging_num=aging.str.extract(r'(\d+)').astype(float)

    df["D0"]=aging_num[0]==0
    df["D1"]=aging_num[0]==1
    df["D2"]=aging_num[0]==2
    df["D3"]=aging_num[0]==3

    return df

df=load_data()

# =============================
# SIDEBAR
# =============================

with st.sidebar:

    if os.path.exists("logo_claro.png"):
        st.image("logo_claro.png")

    aba=st.radio("Visualização",["Visão Diária","Evolução Mensal"])

    meses=df.sort_values("Mes_Ano_dt",ascending=False)["Mes_Ano"].unique()

    mes=st.selectbox("Mês",meses)

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

base=df[df["Mes_Ano"]==mes]

total=len(base)

p0=base["D0"].sum()
p1=(base["D0"]|base["D1"]).sum()
p2=(base["D0"]|base["D1"]|base["D2"]).sum()
p3=(base["D0"]|base["D1"]|base["D2"]|base["D3"]).sum()

c1,c2,c3,c4=st.columns(4)

c1.metric("Até D+0",f"{p0/total*100:.2f}%")
c2.metric("Até D+1",f"{p1/total*100:.2f}%")
c3.metric("Até D+2",f"{p2/total*100:.2f}%")
c4.metric("Até D+3",f"{p3/total*100:.2f}%")

# =============================
# VISÃO DIÁRIA
# =============================

res=base.groupby("Data NF").agg(
D0=("D0","sum"),
D1=("D1","sum"),
D2=("D2","sum"),
D3=("D3","sum"),
Pedidos=("Pedido","count")
).reset_index()

res["Até D+0"]=res["D0"]/res["Pedidos"]*100
res["Até D+1"]=(res["D0"]+res["D1"])/res["Pedidos"]*100
res["Até D+2"]=(res["D0"]+res["D1"]+res["D2"])/res["Pedidos"]*100

res["Dia"]=res["Data NF"].dt.strftime("%d/%m")

fig=px.line(res,x="Dia",y=["Até D+0","Até D+1","Até D+2"],markers=True)

st.plotly_chart(fig,use_container_width=True)

# =============================
# RANKING CD
# =============================

st.subheader("Ranking CD Origem (SLA D+1)")

rank=base.groupby("CD Origem").agg(
D0=("D0","sum"),
D1=("D1","sum"),
Pedidos=("Pedido","count")
).reset_index()

rank["SLA"]=(rank["D0"]+rank["D1"])/rank["Pedidos"]*100

rank=rank.sort_values("SLA")

fig2=px.bar(
rank,
x="CD Origem",
y="SLA",
text=rank["SLA"].apply(lambda x:f"{x:.2f}%"),
color="SLA",
color_continuous_scale=["red","yellow","green"]
)

st.plotly_chart(fig2,use_container_width=True)
