import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

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
# LINK DO EXCEL (ONEDRIVE / SHAREPOINT)
# =============================

url_excel = "https://corpclarobr.sharepoint.com/:x:/s/USER-IndicadoresemPowerBI/IQBahNLMGezRT5ak1HteRYqCAUgUkkeW68ge9Rtus46WstE?e=Zn4B2Q&download=1"

# =============================
# CARGA DE DADOS OTIMIZADA
# =============================

@st.cache_data(ttl=900)
def load_data(path):

    df = pd.read_excel(
        path,
        usecols=[
            "Data NF",
            "Aging_Ajustado_D+",
            "Pedido",
            "Operador",
            "CD Origem",
            "Empresa",
            "Canal",
            "Unidade de Negocio",
            "Canal de Atuacao"
        ]
    )

    df.columns = df.columns.str.strip()

    df["Data NF"] = pd.to_datetime(df["Data NF"])

    df["Mes_Ano"] = df["Data NF"].dt.strftime("%m/%Y")

    df["flag_d0"] = df["Aging_Ajustado_D+"].astype(str).str.contains("D\+0")

    df["flag_d1"] = df["Aging_Ajustado_D+"].astype(str).str.contains("D\+1")

    df["flag_d2"] = df["Aging_Ajustado_D+"].astype(str).str.contains("D\+2")

    return df


with st.spinner("Carregando dados do OneDrive..."):
    df = load_data(url_excel)

# =============================
# METAS
# =============================

METAS_CLARO_BRASIL = {
"01/2025":76.09,"02/2025":74.38,"03/2025":79.52,"04/2025":72.28,
"05/2025":81.73,"06/2025":88.07,"07/2025":82.91,"08/2025":89.19,
"09/2025":92.77,"10/2025":88.68,"11/2025":82.47,"12/2025":85.94,
"01/2026":94.45,"02/2026":94.65,"03/2026":94.63,"04/2026":94.93,
"05/2026":94.31,"06/2026":94.21,"07/2026":94.36,"08/2026":95.80,
"09/2026":95.36,"10/2026":95.47,"11/2026":95.56,"12/2026":95.47
}

# =============================
# SIDEBAR
# =============================

with st.sidebar:

    st.markdown("## Filtros")

    aba = st.radio(
        "Visualização",
        ["📅 Visão Diária","📊 Evolução Mensal"]
    )

    lista_meses = sorted(
        df["Mes_Ano"].unique(),
        key=lambda x: datetime.strptime(x,"%m/%Y"),
        reverse=True
    )

    mes_selecionado = st.selectbox(
        "Mês de Referência",
        lista_meses
    )

    filtros = [
        "Operador",
        "CD Origem",
        "Empresa",
        "Canal",
        "Unidade de Negocio",
        "Canal de Atuacao"
    ]

    mask = np.ones(len(df), dtype=bool)

    filtros_selecionados = {}

    for col in filtros:

        if col in df.columns:

            vals = st.multiselect(
                col,
                sorted(df[col].dropna().unique())
            )

            filtros_selecionados[col] = vals

            if vals:

                mask &= df[col].isin(vals)

dff_global = df[mask].copy()

# =============================
# DASHBOARD
# =============================

if aba == "📅 Visão Diária":

    st.subheader(f"Indicadores - {mes_selecionado}")

    base = dff_global[dff_global["Mes_Ano"] == mes_selecionado].copy()

else:

    periodo = st.radio(
        "Período acumulado",
        [3,6,9,12,24],
        index=3
    )

    meses = sorted(
        dff_global["Mes_Ano"].unique(),
        key=lambda x: datetime.strptime(x,"%m/%Y")
    )

    base = dff_global[
        dff_global["Mes_Ano"].isin(meses[-periodo:])
    ].copy()

total = len(base)

if total > 0:

    p0 = base["flag_d0"].sum()

    p1 = (base["flag_d0"] | base["flag_d1"]).sum()

    p2 = (base["flag_d0"] | base["flag_d1"] | base["flag_d2"]).sum()

    c1,c2,c3,c4 = st.columns(4)

    c1.metric("Até D+0", f"{(p0/total*100):.2f}%")

    c2.metric("Até D+1", f"{(p1/total*100):.2f}%")

    c3.metric("Até D+2", f"{(p2/total*100):.2f}%")

    c4.metric("Total Pedidos", f"{total:,}")

    # AGRUPAMENTO

    if aba == "📅 Visão Diária":

        res = base.groupby("Data NF").agg(
            {
                "flag_d0":"sum",
                "flag_d1":"sum",
                "flag_d2":"sum",
                "Pedido":"count"
            }
        ).reset_index()

        res["Até D+1"] = (
            (res["flag_d0"]+res["flag_d1"])
            /res["Pedido"]*100
        )

        res["Data"] = res["Data NF"].dt.strftime("%d/%m")

    else:

        res = base.groupby("Mes_Ano").agg(
            {
                "flag_d0":"sum",
                "flag_d1":"sum",
                "flag_d2":"sum",
                "Pedido":"count"
            }
        ).reset_index()

        res["Até D+1"] = (
            (res["flag_d0"]+res["flag_d1"])
            /res["Pedido"]*100
        )

        res["Data"] = res["Mes_Ano"]

    # GRAFICO

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=res["Data"],
            y=res["Até D+1"],
            mode="lines+markers",
            name="Até D+1"
        )
    )

    fig.add_hline(
        y=85,
        line_dash="dash",
        line_color="black",
        annotation_text="Meta 85%"
    )

    st.plotly_chart(fig, use_container_width=True)

else:

    st.warning("Nenhum dado encontrado.")
