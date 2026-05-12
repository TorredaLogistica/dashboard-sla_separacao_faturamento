import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import os

# =============================
# CONFIGURAÇÃO DA PÁGINA
# =============================
st.set_page_config(layout="wide", page_title="Dashboard SLA Faturamento")

# =============================
# CABEÇALHO
# =============================
st.title("Dashboard SLA Separação e Faturamento")

horario_brasilia = datetime.now() - timedelta(hours=3)
st.caption(f"Atualizado em {horario_brasilia.strftime('%d/%m/%Y %H:%M')}")

# =============================
# BOTÃO DE ATUALIZAÇÃO
# =============================
if st.button("🔄 Atualizar dados"):
    st.cache_data.clear()
    st.rerun()

# =============================
# CARGA DE DADOS
# =============================
@st.cache_data
def load_data(path):
    df = pd.read_excel(path, engine="pyxlsb")
    df.columns = df.columns.str.strip()
    return df

caminho_arquivo = "Faturamento SLA 2026.xlsb"
if not os.path.exists(caminho_arquivo):
    st.error("Arquivo não encontrado!")
    st.stop()

df = load_data(caminho_arquivo)

# =============================
# SIDEBAR
# =============================
with st.sidebar:

    if os.path.exists("logo_claro.png"):
        st.image("logo_claro.png", use_container_width=True)

    st.markdown("### 📊 Visualização")
    tipo_visualizacao = st.radio(
        "",
        ["Visão Diária", "Evolução Mensal"],
        index=0
    )

    st.markdown("---")

    st.markdown("### 📅 Mês de Referência")
    meses_disponiveis = sorted(df["Mes_Ano"].dropna().unique())
    meses_selecionados = st.multiselect(
        "",
        meses_disponiveis,
        default=[meses_disponiveis[-1]] if meses_disponiveis else []
    )

    st.markdown("### Operador")
    operador_sel = st.multiselect(
        "",
        sorted(df["Operador"].dropna().unique())
    )

    st.markdown("### CD Origem")
    cd_sel = st.multiselect(
        "",
        sorted(df["CD Origem"].dropna().unique())
    )

    st.markdown("### Empresa")
    empresa_sel = st.multiselect(
        "",
        sorted(df["Empresa"].dropna().unique())
    )

    st.markdown("### Unidade de Negócio")
    unidade_sel = st.multiselect(
        "",
        sorted(df["Unidade de Negocio"].dropna().unique())
    )

    st.markdown("### Canal de Atuação")
    canal_sel = st.multiselect(
        "",
        sorted(df["Canal de Atuacao"].dropna().unique())
    )

# =============================
# APLICAÇÃO DOS FILTROS
# =============================
dff = df.copy()

if meses_selecionados:
    dff = dff[dff["Mes_Ano"].isin(meses_selecionados)]

if operador_sel:
    dff = dff[dff["Operador"].isin(operador_sel)]

if cd_sel:
    dff = dff[dff["CD Origem"].isin(cd_sel)]

if empresa_sel:
    dff = dff[dff["Empresa"].isin(empresa_sel)]

if unidade_sel:
    dff = dff[dff["Unidade de Negocio"].isin(unidade_sel)]

if canal_sel:
    dff = dff[dff["Canal de Atuacao"].isin(canal_sel)]

# =============================
# CONTROLE DE VISUALIZAÇÃO
# =============================

if tipo_visualizacao == "Visão Diária":
    st.subheader("📅 Visão Diária")

    st.info(
        "👉 Aqui você cola TODO o conteúdo que já existia na Visão Diária:\n\n"
        "- KPIs\n"
        "- Métricas SLA\n"
        "- Tabelas\n"
        "- Gráficos atuais\n\n"
        "Basta mover o código antigo para cá."
    )

elif tipo_visualizacao == "Evolução Mensal":
    st.subheader("📦 Evolução Mensal – Volumetria de Pedidos")

    if dff.empty:
        st.warning("Nenhum dado encontrado para os filtros selecionados.")
    else:
        volume = (
            dff
            .groupby(["Canal de Atuacao", "Mes_Ano"])
            .size()
            .reset_index(name="Volume")
        )

        fig = px.bar(
            volume,
            x="Canal de Atuacao",
            y="Volume",
            color="Mes_Ano",
            barmode="group",
            text="Volume",
            title="VOLUMETRIA DE PEDIDOS"
        )

        fig.update_layout(
            height=550,
            title_x=0.0,
            xaxis_title="Canal de Atuação",
            yaxis_title="",
            legend_title_text="Mês"
        )

        fig.update_traces(textposition="outside")

        st.plotly_chart(fig, use_container_width=True)
