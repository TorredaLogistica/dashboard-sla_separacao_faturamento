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

# =============================
# CABEÇALHO
# =============================
st.title("Dashboard SLA Separação e Faturamento")
st.caption(f"Atualizado em {datetime.now().strftime('%d/%m/%Y %H:%M')}")

# =============================
# METAS
# =============================
# ... Mesma definição de METAS_CLARO_BRASIL, METAS_NET, etc. do seu código original ...

# =============================
# FUNÇÕES AUXILIARES
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
# LEITURA DE DADOS (.xlsb)
# =============================
@st.cache_data
def load_data_xlsb(path):
    df = pd.read_excel(path, engine='pyxlsb')
    df.columns = df.columns.str.strip()
    
    # Garante colunas essenciais
    for col in ['Data NF','Aging_Ajustado_D+','Pedido','Empresa','CD Origem']:
        if col not in df.columns: df[col] = np.nan
    
    # Converte datas corretamente (numéricas ou datetime)
    df['Data NF'] = pd.to_datetime(df['Data NF'], errors='coerce')
    
    # Flags
    df['flag_d0'] = df['Aging_Ajustado_D+'].astype(str).str.contains('D\+0', regex=True)
    df['flag_d1'] = df['Aging_Ajustado_D+'].astype(str).str.contains('D\+1', regex=True)
    df['flag_d2'] = df['Aging_Ajustado_D+'].astype(str).str.contains('D\+2', regex=True)
    
    # Mês/Ano
    df['Mes_Ano'] = df['Data NF'].dt.strftime('%m/%Y')
    return df

caminho_arquivo = os.path.join(os.getcwd(), "Faturamento SLA 2026.xlsb")
df = load_data_xlsb(caminho_arquivo)

# =============================
# SIDEBAR
# =============================
with st.sidebar:
    st.image("logo_claro.png", use_container_width=True) if os.path.exists("logo_claro.png") else st.markdown("<h2 style='text-align: center; color: #e1261c;'>CLARO</h2>", unsafe_allow_html=True)
    aba = st.radio("Visualização", ["📅 Visão Diária","📊 Evolução Mensal"], horizontal=True)
    lista_meses = sorted(df['Mes_Ano'].dropna().unique(), key=lambda x: datetime.strptime(x, '%m/%Y'), reverse=True)
    mes_selecionado = st.selectbox("Mês de Referência", lista_meses)
    
    filtros = ['Operador','CD Origem','Empresa','Canal','Unidade de Negocio','Canal de Atuacao']
    mask = np.ones(len(df), dtype=bool)
    filtros_selecionados = {}
    for col in filtros:
        if col in df.columns:
            vals = st.multiselect(col, sorted(df[col].dropna().unique()))
            filtros_selecionados[col] = vals
            if vals: mask &= df[col].isin(vals)

dff_global = df[mask].copy()
empresas_filtradas = filtros_selecionados.get('Empresa', [])

# =============================
# DASHBOARD PRINCIPAL
# =============================
if aba == "📅 Visão Diária":
    base = dff_global[dff_global['Mes_Ano']==mes_selecionado].copy()
else:
    periodo = st.radio("Período Acumulado", [3,6,9,12,24], index=3, horizontal=True)
    meses_disponiveis = sorted(dff_global['Mes_Ano'].dropna().unique(), key=lambda x: datetime.strptime(x, '%m/%Y'))
    base = dff_global[dff_global['Mes_Ano'].isin(meses_disponiveis[-periodo:])].copy()

total = len(base)
if total > 0:
    p0 = base['flag_d0'].sum()
    p1 = (base['flag_d0'] | base['flag_d1']).sum()
    p2 = (base['flag_d0'] | base['flag_d1'] | base['flag_d2']).sum()
    
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Até D+0", f"{p0/total*100:.2f}%")
    c2.metric("Até D+1", f"{p1/total*100:.2f}%")
    c3.metric("Até D+2", f"{p2/total*100:.2f}%")
    c4.metric("Total Pedidos", f"{total:,}")

    valor_meta = obter_meta_dinamica(mes_selecionado, empresas_filtradas)
    st.info(f"💡 Regra de Meta Aplicada: {empresas_filtradas[0] if empresas_filtradas else 'Claro Brasil'} - {valor_meta:.2f}%")

    # Agrupamento
    if aba == "📅 Visão Diária":
        res = base.groupby('Data NF').agg({'flag_d0':'sum','flag_d1':'sum','flag_d2':'sum','Pedido':'count'}).reset_index()
        res['Até D+0'] = (res['flag_d0']/res['Pedido']*100).round(2)
        res['Até D+1'] = ((res['flag_d0']+res['flag_d1'])/res['Pedido']*100).round(2)
        res['Até D+2'] = ((res['flag_d0']+res['flag_d1']+res['flag_d2'])/res['Pedido']*100).round(2)
        res['Meta'] = valor_meta
        res['Mês'] = res['Data NF'].dt.strftime('%d/%m')
    else:
        res = base.groupby('Mes_Ano').agg({'flag_d0':'sum','flag_d1':'sum','flag_d2':'sum','Pedido':'count'}).reset_index()
        res = res.sort_values('Mes_Ano')
        res['Até D+0'] = (res['flag_d0']/res['Pedido']*100).round(2)
        res['Até D+1'] = ((res['flag_d0']+res['flag_d1'])/res['Pedido']*100).round(2)
        res['Até D+2'] = ((res['flag_d0']+res['flag_d1']+res['flag_d2'])/res['Pedido']*100).round(2)
        res['Meta'] = res['Mes_Ano'].apply(lambda x: obter_meta_dinamica(x, empresas_filtradas))
        res['Mês'] = res['Mes_Ano']

    # Gráfico linha + meta
    fig = go.Figure()
    for col in ['Até D+0','Até D+1','Até D+2']:
        fig.add_trace(go.Scatter(x=res['Mês'], y=res[col], name=col, mode='lines+markers+text',
                                 text=[f"{v:.2f}%" for v in res[col]], textposition='top center'))
    fig.add_trace(go.Scatter(x=res['Mês'], y=res['Meta'], name='Meta', mode='lines', line=dict(dash='dash', color='black')))
    st.plotly_chart(fig, use_container_width=True)

    # Tabela
    view = res[['Mês','Meta','Até D+0','Até D+1','Até D+2','Pedido']].copy()
    view['Meta'] = view['Meta'].apply(lambda x: f"{x:.2f}%")
    for c in ['Até D+0','Até D+1','Até D+2']: view[c] = view[c].apply(lambda x: f"{x:.2f}%")
    st.dataframe(view.style.apply(estilo_tabela, axis=1), use_container_width=True, hide_index=True)

    # Ranking CD Origem
    st.markdown("---")
    st.subheader("Ranking CD Origem - SLA D+1")
    rank = base.groupby('CD Origem').agg({'flag_d0':'sum','flag_d1':'sum','Pedido':'count'}).reset_index()
    rank['Até D+1'] = ((rank['flag_d0']+rank['flag_d1'])/rank['Pedido']*100).round(2)
    rank = rank.sort_values('Até D+1')
    fig_bar = px.bar(rank, x='CD Origem', y='Até D+1', text=rank['Até D+1'].apply(lambda x: f"{x:.2f}%"), color='Até D+1', color_continuous_scale='RdYlGn')
    st.plotly_chart(fig_bar, use_container_width=True)

else:
    st.warning("Nenhum dado encontrado para os filtros selecionados.")
