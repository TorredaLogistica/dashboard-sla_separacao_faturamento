import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
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
        st.text_input("Senha", type="password", on_change=password_entered, key="password")
        st.stop()
    if not st.session_state["password_correct"]:
        st.text_input("Senha", type="password", on_change=password_entered, key="password")
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
METAS = {
    "CLARO_BRASIL": {"01/2025":76.09,"02/2025":74.38,"03/2025":79.52,"04/2025":72.28,"05/2025":81.73,"06/2025":88.07,
                      "07/2025":82.91,"08/2025":89.19,"09/2025":92.77,"10/2025":88.68,"11/2025":82.47,"12/2025":85.94,
                      "01/2026":94.45,"02/2026":94.65,"03/2026":94.63,"04/2026":94.93,"05/2026":94.31,"06/2026":94.21,
                      "07/2026":94.36,"08/2026":95.80,"09/2026":95.36,"10/2026":95.47,"11/2026":95.56,"12/2026":95.47},
    "NET": {"01/2025":54.98,"02/2025":47.34,"03/2025":55.80,"04/2025":36.50,"05/2025":57.16,"06/2025":73.98,
            "07/2025":67.22,"08/2025":76.42,"09/2025":85.52,"10/2025":75.33,"11/2025":65.79,"12/2025":70.59,
            "01/2026":90,"02/2026":90,"03/2026":90,"04/2026":90,"05/2026":90,"06/2026":90,
            "07/2026":90,"08/2026":92,"09/2026":92,"10/2026":92,"11/2026":92,"12/2026":92},
    "CLARO_TV": {"01/2025":26.91,"02/2025":31.21,"03/2025":58.02,"04/2025":38.19,"05/2025":54.97,"06/2025":78.13,
                 "07/2025":82.01,"08/2025":73.10,"09/2025":66.67,"10/2025":64.25,"11/2025":63.69,"12/2025":48.48,
                 "01/2026":85.02,"02/2026":85.11,"03/2026":85.19,"04/2026":85.04,"05/2026":84.80,"06/2026":84.90,
                 "07/2026":85.19,"08/2026":84.77,"09/2026":84.97,"10/2026":84.97,"11/2026":85.05,"12/2026":84.97},
    "EMBRATEL": {"01/2025":43.25,"02/2025":40.31,"03/2025":51.70,"04/2025":27.42,"05/2025":65.94,"06/2025":73.60,
                 "07/2025":55.06,"08/2025":69.74,"09/2025":82.46,"10/2025":64.27,"11/2025":41.33,"12/2025":67.61,
                 "01/2026":80,"02/2026":80,"03/2026":80.01,"04/2026":80.02,"05/2026":80.01,"06/2026":79.99,
                 "07/2026":79.99,"08/2026":82,"09/2026":81.98,"10/2026":82.01,"11/2026":82,"12/2026":82},
    "CLARO_MOVEL": {"01/2025":97.94,"02/2025":98.17,"03/2025":98.22,"04/2025":97.46,"05/2025":98.39,"06/2025":98.21,
                    "07/2025":99.05,"08/2025":98.75,"09/2025":98.73,"10/2025":99.46,"11/2025":96.98,"12/2025":98.28,
                    "01/2026":99.50,"02/2026":99.50,"03/2026":99.50,"04/2026":99.50,"05/2026":99.50,"06/2026":99.50,
                    "07/2026":99.50,"08/2026":99.50,"09/2026":99.50,"10/2026":99.50,"11/2026":99.50,"12/2026":99.50},
}

def obter_meta(mes, empresa):
    empresa = str(empresa).upper()
    if "NET" in empresa: return METAS["NET"].get(mes,0)
    if "TV" in empresa: return METAS["CLARO_TV"].get(mes,0)
    if "EMBRATEL" in empresa: return METAS["EMBRATEL"].get(mes,0)
    if "MOVEL" in empresa: return METAS["CLARO_MOVEL"].get(mes,0)
    return METAS["CLARO_BRASIL"].get(mes,0)

# =============================
# LEITURA XLSB
# =============================
@st.cache_data
def load_data():
    arquivo = [f for f in os.listdir() if f.endswith(".xlsb")]
    if not arquivo:
        st.error("Nenhum arquivo .xlsb encontrado na pasta.")
        st.stop()
    arquivo = arquivo[0]
    df = pd.read_excel(arquivo, engine="pyxlsb")
    
    # Verifica colunas essenciais
    for col in ["Data NF","Aging_Ajustado_D+","Pedido","Empresa","CD"]:
        if col not in df.columns:
            df[col] = np.nan

    # Converter Data NF corretamente
    def parse_date(x):
        try: return pd.to_datetime(x)
        except: return pd.NaT
    df["Data NF"] = df["Data NF"].apply(parse_date)
    df = df[df["Data NF"].notna()]
    df["Mes_Ano"] = df["Data NF"].dt.strftime("%m/%Y")

    # D0, D1, D2
    df["Aging_Ajustado_D+"] = df["Aging_Ajustado_D+"].astype(str)
    aging_num = df["Aging_Ajustado_D+"].str.extract(r'(\d+)').astype(float)
    df["D0"] = aging_num[0] == 0
    df["D1"] = aging_num[0] == 1
    df["D2"] = aging_num[0] == 2
    return df

df = load_data()

# =============================
# FILTROS
# =============================
with st.sidebar:
    aba = st.radio("Visualização", ["Visão Diária","Evolução Mensal"])
    meses = sorted(df["Mes_Ano"].dropna().unique(), reverse=True)
    mes = st.selectbox("Mês", meses)
    if aba=="Evolução Mensal":
        periodo = st.selectbox("Meses acumulados",[3,6,9,12,24],index=3)

# =============================
# BASE
# =============================
if aba=="Visão Diária":
    base = df[df["Mes_Ano"]==mes].copy()
else:
    meses_ord = sorted(df["Mes_Ano"].dropna().unique())
    meses_periodo = meses_ord[-periodo:]
    base = df[df["Mes_Ano"].isin(meses_periodo)].copy()

empresa = base["Empresa"].iloc[0] if len(base)>0 else ""

# =============================
# AGRUPAMENTO
# =============================
if aba=="Visão Diária":
    res = base.groupby("Data NF").agg(
        D0=("D0","sum"),
        D1=("D1","sum"),
        D2=("D2","sum"),
        Pedidos=("Pedido","count")
    ).reset_index()
    res["Periodo"] = res["Data NF"].dt.strftime("%d/%m")
else:
    res = base.groupby("Mes_Ano").agg(
        D0=("D0","sum"),
        D1=("D1","sum"),
        D2=("D2","sum"),
        Pedidos=("Pedido","count")
    ).reset_index()
    res["Periodo"] = res["Mes_Ano"]

res["Até D+0"] = res["D0"]/res["Pedidos"]*100
res["Até D+1"] = (res["D0"]+res["D1"])/res["Pedidos"]*100
res["Até D+2"] = (res["D0"]+res["D1"]+res["D2"])/res["Pedidos"]*100
res["Meta"] = res["Periodo"].apply(lambda x: obter_meta(x if aba!="Visão Diária" else mes,empresa))

# =============================
# KPIs
# =============================
kpi_d0 = res["Até D+0"].mean()
kpi_d1 = res["Até D+1"].mean()
kpi_d2 = res["Até D+2"].mean()
meta_kpi = obter_meta(mes,empresa)

c1,c2,c3,c4 = st.columns(4)
c1.metric("SLA D+0",f"{kpi_d0:.2f}%")
c2.metric("SLA D+1",f"{kpi_d1:.2f}%")
c3.metric("SLA D+2",f"{kpi_d2:.2f}%")
c4.metric("Meta",f"{meta_kpi:.2f}%")

# =============================
# GRÁFICOS
# =============================
fig = go.Figure()
# Linha SLA
fig.add_scatter(x=res["Periodo"], y=res["Até D+0"], mode="lines+markers", name="D+0")
fig.add_scatter(x=res["Periodo"], y=res["Até D+1"], mode="lines+markers", name="D+1")
fig.add_scatter(x=res["Periodo"], y=res["Até D+2"], mode="lines+markers", name="D+2")
fig.add_scatter(x=res["Periodo"], y=res["Meta"], mode="lines", name="Meta", line=dict(dash="dash"))

# Barra Volume
fig.add_bar(x=res["Periodo"], y=res["Pedidos"], name="Volume", opacity=0.4, yaxis="y2")

fig.update_layout(
    yaxis=dict(title="SLA (%)", range=[0,100]),
    yaxis2=dict(title="Volume", overlaying="y", side="right"),
    barmode="overlay"
)
st.plotly_chart(fig,use_container_width=True)

# =============================
# TABELA
# =============================
tabela = res[["Periodo","Meta","Até D+0","Até D+1","Até D+2","Pedidos"]]
st.dataframe(
    tabela.style.format({
        "Meta":"{:.2f}%",
        "Até D+0":"{:.2f}%",
        "Até D+1":"{:.2f}%",
        "Até D+2":"{:.2f}%"
    }),
    use_container_width=True
)

# =============================
# RANKING CD
# =============================
if "CD" in base.columns:
    ranking = base.groupby("CD").agg(
        Pedidos=("Pedido","count"),
        D0=("D0","sum"),
        D1=("D1","sum")
    ).reset_index()
    ranking["SLA D+1"] = (ranking["D0"]+ranking["D1"])/ranking["Pedidos"]*100
    ranking = ranking.sort_values("SLA D+1", ascending=False)
    st.subheader("Ranking CDs")
    st.dataframe(ranking.style.format({"SLA D+1":"{:.2f}%"}), use_container_width=True)
else:
    st.warning("Coluna 'CD' não encontrada. Ranking CD não pode ser exibido.")
