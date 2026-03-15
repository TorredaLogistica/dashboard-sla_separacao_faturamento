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
    elif not st.session_state["password_correct"]:
        st.text_input("Digite a senha", type="password", on_change=password_entered, key="password")
        st.error("Senha incorreta")
        st.stop()
check_password()

st.title("Dashboard SLA Separação e Faturamento")
st.caption(f"Atualizado em {datetime.now().strftime('%d/%m/%Y %H:%M')}")

# =============================
# DICIONÁRIOS DE METAS
# =============================
METAS_CLARO_BRASIL = {
    "01/2025": 76.09, "02/2025": 74.38, "03/2025": 79.52, "04/2025": 72.28, "05/2025": 81.73, "06/2025": 88.07,
    "07/2025": 82.91, "08/2025": 89.19, "09/2025": 92.77, "10/2025": 88.68, "11/2025": 82.47, "12/2025": 85.94,
    "01/2026": 94.45, "02/2026": 94.65, "03/2026": 94.63, "04/2026": 94.93, "05/2026": 94.31, "06/2026": 94.21,
    "07/2026": 94.36, "08/2026": 95.80, "09/2026": 95.36, "10/2026": 95.47, "11/2026": 95.56, "12/2026": 95.47
}
METAS_NET = { "01/2025":54.98, "02/2025":47.34, "03/2025":55.80, "04/2025":36.50, "05/2025":57.16, "06/2025":73.98,
    "07/2025":67.22, "08/2025":76.42, "09/2025":85.52, "10/2025":75.33, "11/2025":65.79, "12/2025":70.59,
    "01/2026":90, "02/2026":90, "03/2026":90, "04/2026":90, "05/2026":90, "06/2026":90,
    "07/2026":90, "08/2026":92, "09/2026":92, "10/2026":92, "11/2026":92, "12/2026":92 }
METAS_CLARO_TV = { "01/2025":26.91,"02/2025":31.21,"03/2025":58.02,"04/2025":38.19,"05/2025":54.97,"06/2025":78.13,
    "07/2025":82.01,"08/2025":73.10,"09/2025":66.67,"10/2025":64.25,"11/2025":63.69,"12/2025":48.48,
    "01/2026":85.02,"02/2026":85.11,"03/2026":85.19,"04/2026":85.04,"05/2026":84.80,"06/2026":84.90,
    "07/2026":85.19,"08/2026":84.77,"09/2026":84.97,"10/2026":84.97,"11/2026":85.05,"12/2026":84.97 }
METAS_EMBRATEL = { "01/2025":43.25,"02/2025":40.31,"03/2025":51.70,"04/2025":27.42,"05/2025":65.94,"06/2025":73.60,
    "07/2025":55.06,"08/2025":69.74,"09/2025":82.46,"10/2025":64.27,"11/2025":41.33,"12/2025":67.61,
    "01/2026":80,"02/2026":80,"03/2026":80.01,"04/2026":80.02,"05/2026":80.01,"06/2026":79.99,
    "07/2026":79.99,"08/2026":82,"09/2026":81.98,"10/2026":82.01,"11/2026":82,"12/2026":82 }
METAS_CLARO_MOVEL = { "01/2025":97.94,"02/2025":98.17,"03/2025":98.22,"04/2025":97.46,"05/2025":98.39,"06/2025":98.21,
    "07/2025":99.05,"08/2025":98.75,"09/2025":98.73,"10/2025":99.46,"11/2025":96.98,"12/2025":98.28,
    "01/2026":99.50,"02/2026":99.50,"03/2026":99.50,"04/2026":99.50,"05/2026":99.50,"06/2026":99.50,
    "07/2026":99.50,"08/2026":99.50,"09/2026":99.50,"10/2026":99.50,"11/2026":99.50,"12/2026":99.50 }

# =============================
# FUNÇÃO DE META DINÂMICA
# =============================
def obter_meta(mes, empresas):
    if empresas and len(empresas)==1:
        emp = empresas[0].upper()
        if "NET" in emp: return METAS_NET.get(mes, 85)
        if "TV" in emp: return METAS_CLARO_TV.get(mes,85)
        if "EMBRATEL" in emp: return METAS_EMBRATEL.get(mes,85)
        if "MOVEL" in emp: return METAS_CLARO_MOVEL.get(mes,85)
    return METAS_CLARO_BRASIL.get(mes,85)

# =============================
# LEITURA DE DADOS .XLSB
# =============================
@st.cache_data
def load_data(path):
    df = pd.read_excel(path, engine='pyxlsb')
    df.columns = df.columns.str.strip()
    
    # Corrige Data NF
    df['Data NF'] = pd.to_datetime(df['Data NF'], errors='coerce', origin='1899-12-30', unit='D')
    
    # Flags D+0, D+1, D+2
    df['flag_d0'] = df['Aging_Ajustado_D+'].astype(str).str.contains('D\+0', regex=True)
    df['flag_d1'] = df['Aging_Ajustado_D+'].astype(str).str.contains('D\+1', regex=True)
    df['flag_d2'] = df['Aging_Ajustado_D+'].astype(str).str.contains('D\+2', regex=True)
    
    df['Mes_Ano'] = df['Data NF'].dt.strftime('%m/%Y')
    return df

caminho = os.path.join(os.getcwd(), "Faturamento SLA 2026.xlsb")
df = load_data(caminho)

# =============================
# SIDEBAR FILTROS
# =============================
with st.sidebar:
    st.image("logo_claro.png", use_container_width=True) if os.path.exists("logo_claro.png") else st.markdown("<h2 style='text-align:center;color:#e1261c;'>CLARO</h2>", unsafe_allow_html=True)
    aba = st.radio("Visualização", ["📅 Visão Diária", "📊 Evolução Mensal"])
    meses_disponiveis = sorted(df['Mes_Ano'].dropna().unique(), key=lambda x: datetime.strptime(x,'%m/%Y'), reverse=True)
    mes = st.selectbox("Mês de referência", meses_disponiveis)
    
    # filtros adicionais
    filtros = ['Empresa','CD Origem','Operador','Canal']
    mask = np.ones(len(df),dtype=bool)
    filtros_selecionados = {}
    for col in filtros:
        if col in df.columns:
            vals = st.multiselect(col, sorted(df[col].dropna().unique()))
            filtros_selecionados[col] = vals
            if vals:
                mask &= df[col].isin(vals)

dff = df[mask].copy()
empresas_filtradas = filtros_selecionados.get('Empresa', [])

# =============================
# BASE PARA VISUALIZAÇÃO
# =============================
if aba == "📅 Visão Diária":
    base = dff[dff['Mes_Ano']==mes]
else:
    periodo = st.selectbox("Meses acumulados",[3,6,9,12,24], index=3)
    meses_ord = sorted(dff['Mes_Ano'].dropna().unique())
    base = dff[dff['Mes_Ano'].isin(meses_ord[-periodo:])]

total_pedidos = len(base)
if total_pedidos > 0:
    # =============================
    # KPIs
    # =============================
    p0 = base['flag_d0'].sum()
    p1 = (base['flag_d0'] | base['flag_d1']).sum()
    p2 = (base['flag_d0'] | base['flag_d1'] | base['flag_d2']).sum()

    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Até D+0", f"{p0}")
    c2.metric("Até D+1", f"{p1}")
    c3.metric("Até D+2", f"{p2}")
    c4.metric("Total Pedidos", f"{total_pedidos}")

    # =============================
    # AGRUPAMENTO
    # =============================
    if aba=="📅 Visão Diária":
        res = base.groupby('Data NF').agg({'flag_d0':'sum','flag_d1':'sum','flag_d2':'sum','Pedido':'count'}).reset_index()
        res['Até D+0'] = res['flag_d0']
        res['Até D+1'] = res['flag_d0']+res['flag_d1']
        res['Até D+2'] = res['flag_d0']+res['flag_d1']+res['flag_d2']
        res['Meta'] = obter_meta(mes, empresas_filtradas)
        res['Mês'] = res['Data NF'].dt.strftime('%d/%m')
    else:
        res = base.groupby('Mes_Ano').agg({'flag_d0':'sum','flag_d1':'sum','flag_d2':'sum','Pedido':'count'}).reset_index()
        res['Até D+0'] = res['flag_d0']
        res['Até D+1'] = res['flag_d0']+res['flag_d1']
        res['Até D+2'] = res['flag_d0']+res['flag_d1']+res['flag_d2']
        res['Meta'] = res['Mes_Ano'].apply(lambda x: obter_meta(x, empresas_filtradas))
        res['Mês'] = res['Mes_Ano']

    # =============================
    # GRÁFICO DE LINHA
    # =============================
    fig = go.Figure()
    for col in ['Até D+0','Até D+1','Até D+2']:
        fig.add_trace(go.Scatter(x=res['Mês'], y=res[col], name=col, mode='lines+markers'))
    fig.add_trace(go.Scatter(x=res['Mês'], y=res['Meta'], name='Meta', line=dict(dash='dash', color='black')))
    st.plotly_chart(fig, use_container_width=True)

    # =============================
    # TABELA
    # =============================
    st.dataframe(res[['Mês','Meta','Até D+0','Até D+1','Até D+2','Pedido']], use_container_width=True)

    # =============================
    # RANKING CD
    # =============================
    st.subheader("Ranking CD Origem")
    ranking = base.groupby('CD Origem').agg({'flag_d0':'sum','flag_d1':'sum','Pedido':'count'}).reset_index()
    ranking['Até D+1'] = ranking['flag_d0']+ranking['flag_d1']
    ranking = ranking.sort_values('Até D+1',ascending=False)
    fig_bar = px.bar(ranking, x='CD Origem', y='Até D+1', text='Até D+1', color='Até D+1', color_continuous_scale='RdYlGn')
    st.plotly_chart(fig_bar, use_container_width=True)

else:
    st.warning("Nenhum dado encontrado para os filtros selecionados.")
