import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date
import os

st.set_page_config(layout="wide", page_title="Dashboard SLA Faturamento")

# =============================
# LOGIN (Mantido conforme original)
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
# CABEÇALHO (COM AJUSTE DE FUSO HORÁRIO)
# =============================
from datetime import timedelta

st.title("Dashboard SLA Separação e Faturamento")
# Ajusta para o horário de Brasília (UTC-3)
horario_brasilia = datetime.now() - timedelta(hours=3)
st.caption(f"Atualizado em {horario_brasilia.strftime('%d/%m/%Y %H:%M')}")

# =============================
# DICIONÁRIOS DE METAS (Mantidos conforme original)
# =============================
METAS_CLARO_BRASIL = {"01/2025": 76.09, "02/2025": 74.38, "03/2025": 79.52, "04/2025": 72.28, "05/2025": 81.73, "06/2025": 88.07, "07/2025": 82.91, "08/2025": 89.19, "09/2025": 92.77, "10/2025": 88.68, "11/2025": 82.47, "12/2025": 85.94, "01/2026": 94.45, "02/2026": 94.65, "03/2026": 94.63, "04/2026": 94.93, "05/2026": 94.31, "06/2026": 94.21, "07/2026": 94.36, "08/2026": 95.80, "09/2026": 95.36, "10/2026": 95.47, "11/2026": 95.56, "12/2026": 95.47}
METAS_NET = {"01/2026": 90.00, "02/2026": 90.00, "03/2026": 90.00} # Resumido para brevidade
METAS_CLARO_TV = {"01/2026": 85.02, "02/2026": 85.11, "03/2026": 85.19}
METAS_EMBRATEL = {"01/2026": 80.00, "02/2026": 80.00, "03/2026": 80.01}
METAS_CLARO_MOVEL = {"01/2026": 99.50, "02/2026": 99.50, "03/2026": 99.50}

# =============================
# FUNÇÕES DE APOIO
# =============================
def estilo_tabela(row):
    try:
        m = float(str(row['Meta']).replace('%','').replace(',', '.'))
        v = float(str(row['Até D+1']).replace('%','').replace(',', '.'))
        return [f"color: {'green' if v >= m else 'red'}; font-weight: bold" if name == 'Até D+1' else "" for name in row.index]
    except: return ["" for _ in row.index]

def obter_meta_dinamica(mes, empresas_selecionadas):
    if empresas_selecionadas and len(empresas_selecionadas) == 1:
        emp = empresas_selecionadas[0]
        if emp == 'NET': return METAS_NET.get(mes, 85.0)
        if emp == 'Claro TV': return METAS_CLARO_TV.get(mes, 85.0)
        if emp == 'Embratel': return METAS_EMBRATEL.get(mes, 85.0)
        if emp == 'Claro Movel': return METAS_CLARO_MOVEL.get(mes, 85.0)
    return METAS_CLARO_BRASIL.get(mes, 85.0)

# =============================
# CARGA DE DADOS (CORRIGIDA PARA .XLSB E GITHUB)
# =============================

@st.cache_data
def load_data(path):
    # engine='pyxlsb' é necessário para arquivos .xlsb
    df = pd.read_excel(path, engine='pyxlsb')
    df.columns = df.columns.str.strip()
    
    # CORREÇÃO DATA 1970: Converte números seriais do Excel para data real
    if pd.api.types.is_numeric_dtype(df['Data NF']):
        df['Data NF'] = pd.to_datetime(df['Data NF'], unit='D', origin='1899-12-30')
    else:
        df['Data NF'] = pd.to_datetime(df['Data NF'])
        
    df['Mes_Ano'] = df['Data NF'].dt.strftime('%m/%Y')
    
    # Extrai apenas o número depois do D+
    df["aging_num"] = df["Aging_Ajustado_D+"].astype(str).str.extract(r"D\+(\d+)").astype(int)

    # Flags corretas
    df["flag_d0"] = df["aging_num"] == 0
    df["flag_d1"] = df["aging_num"] == 1
    df["flag_d2"] = df["aging_num"] == 2
    return df

# Para o GitHub, o arquivo deve estar na raiz do repositório
caminho_arquivo = "Faturamento SLA 2026.xlsb"

if not os.path.exists(caminho_arquivo):
    st.error(f"Arquivo {caminho_arquivo} não encontrado!")
    st.stop()

df = load_data(caminho_arquivo)

# =============================
# SIDEBAR
# =============================
with st.sidebar:
    if os.path.exists("logo_claro.png"):
        st.image("logo_claro.png", use_container_width=True)
    
    aba = st.radio("Visualização", ["📅 Visão Diária", "📊 Evolução Mensal"], horizontal=True)
    lista_meses = sorted(df['Mes_Ano'].unique(), key=lambda x: datetime.strptime(x, '%m/%Y'), reverse=True)
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
    st.subheader(f"Indicadores Consolidados - {mes_selecionado}")
    base = dff_global[dff_global['Mes_Ano'] == mes_selecionado].copy()
else:
    periodo = st.radio("Período Acumulado:", [3, 6, 9, 12, 24], index=3, horizontal=True)
    st.subheader(f"Indicadores Consolidados - Acumulado ({periodo} meses)")
    meses_disponiveis = sorted(dff_global['Mes_Ano'].unique(), key=lambda x: datetime.strptime(x, '%m/%Y'))
    base = dff_global[dff_global['Mes_Ano'].isin(meses_disponiveis[-periodo:])].copy()

total = len(base)
if total > 0:
    p0, p1, p2 = base['flag_d0'].sum(), (base['flag_d0'] | base['flag_d1']).sum(), (base['flag_d0'] | base['flag_d1'] | base['flag_d2']).sum()
    sla_d1_atual = (p1 / total * 100)
    tipo_meta = empresas_filtradas[0] if (empresas_filtradas and len(empresas_filtradas) == 1) else "Claro Brasil (Padrão)"

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Até D+0", f"{(p0/total*100):.2f}%".replace('.', ','))
    
    if aba == "📅 Visão Diária":
        meta_ref = obter_meta_dinamica(mes_selecionado, empresas_filtradas)
        variacao = sla_d1_atual - meta_ref
        c2.metric("Até D+1", f"{sla_d1_atual:.2f}%".replace('.', ','), delta=f"{variacao:+.2f}% vs meta".replace('.', ','))
        st.info(f"💡 **Regra de Meta Aplicada:** {tipo_meta} - **{meta_ref:.2f}%**".replace('.', ','))
    else:
        c2.metric("Até D+1", f"{sla_d1_atual:.2f}%".replace('.', ','))
        st.info(f"💡 **Regra de Meta Aplicada:** {tipo_meta}")

    c3.metric("Até D+2", f"{(p2/total*100):.2f}%".replace('.', ','))
    c4.metric("Total Pedidos", f"{total:,}".replace(',', '.'))

    # LÓGICA DE AGRUPAMENTO PARA GRÁFICOS
    if aba == "📅 Visão Diária":
        res = base.groupby('Data NF').agg({'flag_d0':'sum','flag_d1':'sum','flag_d2':'sum','Pedido':'count'}).reset_index()
        res['Até D+0'] = (res['flag_d0']/res['Pedido']*100).round(2)
        res['Até D+1'] = ((res['flag_d0']+res['flag_d1'])/res['Pedido']*100).round(2)
        res['Até D+2'] = ((res['flag_d0']+res['flag_d1']+res['flag_d2'])/res['Pedido']*100).round(2)
        res['Meta'] = obter_meta_dinamica(mes_selecionado, empresas_filtradas)
        res['Mês'] = res['Data NF'].dt.strftime('%d/%m')
    else:
        res = base.groupby('Mes_Ano').agg({'flag_d0':'sum','flag_d1':'sum','flag_d2':'sum','Pedido':'count'}).reset_index()
        res['data_sort'] = pd.to_datetime(res['Mes_Ano'], format='%m/%Y')
        res = res.sort_values('data_sort')
        res['Até D+0'] = (res['flag_d0']/res['Pedido']*100).round(2)
        res['Até D+1'] = ((res['flag_d0']+res['flag_d1'])/res['Pedido']*100).round(2)
        res['Até D+2'] = ((res['flag_d0']+res['flag_d1']+res['flag_d2'])/res['Pedido']*100).round(2)
        res['Meta'] = res['Mes_Ano'].apply(lambda x: obter_meta_dinamica(x, empresas_filtradas))
        res['Mês'] = res['Mes_Ano']

    
    # =============================
    # GRÁFICO DE LINHAS (CORES AJUSTADAS)
    # =============================
    fig = go.Figure()

    # Linha Até D+0 (Mantive o padrão)
    fig.add_trace(go.Scatter(x=res['Mês'], y=res['Até D+0'], name='Até D+0', 
                             mode='lines+markers+text', 
                             text=[f"{v:.1f}%" for v in res['Até D+0']], 
                             textposition="top center"))

    # Linha Até D+1 - VERDE BANDEIRA
    fig.add_trace(go.Scatter(x=res['Mês'], y=res['Até D+1'], name='Até D+1', 
                             mode='lines+markers+text', 
                             line=dict(color='#006400', width=3), # Verde Bandeira (DarkGreen)
                             text=[f"{v:.1f}%" for v in res['Até D+1']], 
                             textposition="top center"))

    # Linha Até D+2 (Mantive o padrão)
    fig.add_trace(go.Scatter(x=res['Mês'], y=res['Até D+2'], name='Até D+2', 
                             mode='lines+markers+text', 
                             text=[f"{v:.1f}%" for v in res['Até D+2']], 
                             textposition="top center"))

    # Linha de Meta - CINZA
    fig.add_trace(go.Scatter(x=res['Mês'], y=res['Meta'], name='Meta', 
                             line=dict(dash='dash', color='#808080', width=2))) # Cinza

    fig.update_layout(
        title="Evolução SLA %",
        xaxis_title="Período",
        yaxis_title="Percentual (%)",
        legend_title="Indicadores",
        hovermode="x unified"
    )

    st.plotly_chart(fig, use_container_width=True)

    # ... (código anterior do gráfico de linhas)

    # TABELA DE RESUMO (SLA E METAS)
    view = res[['Mês', 'Meta', 'Até D+0', 'Até D+1', 'Até D+2', 'Pedido']].copy()
    
    # Exibição na tela (com formatação de % e estilo colorido)
    view_display = view.copy()
    for c in ['Meta', 'Até D+0', 'Até D+1', 'Até D+2']: 
        view_display[c] = view_display[c].apply(lambda x: f"{x:.2f}%".replace('.', ','))
    
    st.dataframe(view_display.style.apply(estilo_tabela, axis=1), use_container_width=True, hide_index=True)

    # =============================
    # BOTÃO DE DOWNLOAD - TABELA RESUMO (FORMATADO %)
    # =============================
    import io
    buffer_resumo = io.BytesIO()
    
    with pd.ExcelWriter(buffer_resumo, engine='xlsxwriter') as writer:
        # Enviamos os dados divididos por 100 para o Excel aplicar a % corretamente
        df_excel_resumo = view.copy()
        cols_percent = ['Meta', 'Até D+0', 'Até D+1', 'Até D+2']
        for col in cols_percent:
            df_excel_resumo[col] = df_excel_resumo[col] / 100

        df_excel_resumo.to_excel(writer, index=False, sheet_name='Resumo_SLA')
        
        workbook  = writer.book
        worksheet = writer.sheets['Resumo_SLA']

        # Criamos o formato de porcentagem
        format_percent = workbook.add_format({'num_format': '0.00%'})

        # Aplicamos o formato nas colunas específicas (Meta, D0, D1, D2)
        # No ExcelWriter, as colunas são 0-indexadas. Meta é a 1, D+0 é a 2...
        for i, col_name in enumerate(df_excel_resumo.columns):
            column_len = max(df_excel_resumo[col_name].astype(str).map(len).max(), len(col_name)) + 2
            if col_name in cols_percent:
                worksheet.set_column(i, i, column_len, format_percent)
            else:
                worksheet.set_column(i, i, column_len)

    st.download_button(
        label="📥 Baixar Tabela de Resumo em Excel (.xlsx)",
        data=buffer_resumo.getvalue(),
        file_name=f"resumo_sla_{mes_selecionado.replace('/', '_')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key="btn_resumo_excel"
    )

    # =============================
    # RANKINGS (CD, EMPRESA, CANAL)
    # =============================
    
    # 1. RANKING CD ORIGEM
    st.subheader("Ranking CD Origem Críticos (SLA Até D+1)")
    rank_cd = base.groupby('CD Origem').agg({'flag_d0':'sum','flag_d1':'sum','Pedido':'count'}).reset_index()
    rank_cd['Até D+1'] = ((rank_cd['flag_d0']+rank_cd['flag_d1'])/rank_cd['Pedido']*100).round(2)
    rank_cd = rank_cd.sort_values('Até D+1')
    
    fig_bar_cd = px.bar(rank_cd, x='CD Origem', y='Até D+1', 
                        text=rank_cd['Até D+1'].apply(lambda x: f"{x:.2f}%"), 
                        color='Até D+1', color_continuous_scale='RdYlGn')
    st.plotly_chart(fig_bar_cd, use_container_width=True)

    # 2. RANKING EMPRESAS
    st.subheader("Ranking Empresas Críticos (SLA Até D+1)")
    rank_emp = base.groupby('Empresa').agg({'flag_d0':'sum','flag_d1':'sum','Pedido':'count'}).reset_index()
    rank_emp['Até D+1'] = ((rank_emp['flag_d0']+rank_emp['flag_d1'])/rank_emp['Pedido']*100).round(2)
    rank_emp = rank_emp.sort_values('Até D+1')
    
    fig_bar_emp = px.bar(rank_emp, x='Empresa', y='Até D+1', 
                         text=rank_emp['Até D+1'].apply(lambda x: f"{x:.2f}%"), 
                         color='Até D+1', color_continuous_scale='RdYlGn')
    st.plotly_chart(fig_bar_emp, use_container_width=True)

    # 3. RANKING CANAL DE ATUAÇÃO
    st.subheader("Ranking Canal de Atuação Críticos (SLA Até D+1)")
    rank_canal = base.groupby('Canal de Atuacao').agg({'flag_d0':'sum','flag_d1':'sum','Pedido':'count'}).reset_index()
    rank_canal['Até D+1'] = ((rank_canal['flag_d0']+rank_canal['flag_d1'])/rank_canal['Pedido']*100).round(2)
    rank_canal = rank_canal.sort_values('Até D+1')
    
    fig_bar_canal = px.bar(rank_canal, x='Canal de Atuacao', y='Até D+1', 
                           text=rank_canal['Até D+1'].apply(lambda x: f"{x:.2f}%"), 
                           color='Até D+1', color_continuous_scale='RdYlGn')
    st.plotly_chart(fig_bar_canal, use_container_width=True)

    # =============================
    # TABELA DE DETALHAMENTO FINAL
    # =============================
    st.markdown("---")
    st.subheader("📋 Detalhamento dos Pedidos")
    
    colunas_detalhe = [
        'Data NF', 'Pedido', 'Empresa', 'CD Origem', 
        'Operador', 'Canal de Atuacao', 'Aging_Ajustado_D+'
    ]
    
    # Filtra apenas as colunas que existem no arquivo
    colunas_presentes = [c for c in colunas_detalhe if c in base.columns]
    df_detalhe = base[colunas_presentes].copy()

    # Formatação de data para a tabela
    if 'Data NF' in df_detalhe.columns:
        df_detalhe['Data NF'] = df_detalhe['Data NF'].dt.strftime('%d/%m/%Y')

    st.dataframe(df_detalhe, use_container_width=True, hide_index=True)

    # =============================
    # BOTÃO DE DOWNLOAD (FORMATO EXCEL)
    # =============================
    import io

    # Criar um buffer na memória para o arquivo Excel
    buffer = io.BytesIO()
    
    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
        df_detalhe.to_excel(writer, index=False, sheet_name='Detalhamento')
        # Ajuste automático de largura das colunas (opcional mas melhora o visual)
        worksheet = writer.sheets['Detalhamento']
        for i, col in enumerate(df_detalhe.columns):
            column_len = max(df_detalhe[col].astype(str).map(len).max(), len(col)) + 2
            worksheet.set_column(i, i, column_len)

    st.download_button(
        label="📥 Baixar Detalhamento em Excel (.xlsx)",
        data=buffer.getvalue(),
        file_name=f"detalhe_sla_{mes_selecionado.replace('/', '_')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

else:
    st.warning("Nenhum dado encontrado para os filtros selecionados.")





# =============================
# VOLUMETRIA DE PEDIDOS
# =============================

st.markdown("---")
st.subheader("Volumetria de Pedidos")

# Dados do gráfico
df_volume = pd.DataFrame({
    "Canal de Atuação": ["Agente Autorizado", "Ecommerce", "Loja Própria"],
    "Janeiro": [337, 139, 423],
    "Fevereiro": [505, 135, 420],
    "Março": [751, 158, 617],
    "Abril": [576, 120, 257],
    "Maio": [141, 39, 195]
})

# Converte para formato longo
df_volume_melt = df_volume.melt(
    id_vars="Canal de Atuação",
    var_name="Mês",
    value_name="Volume"
)

# Gráfico
fig_volume = px.bar(
    df_volume_melt,
    x="Canal de Atuação",
    y="Volume",
    color="Mês",
    barmode="group",
    text="Volume",
    title="VOLUMETRIA DE PEDIDOS"
)

# Ajustes visuais (seguindo padrão do dashboard)
fig_volume.update_layout(
    height=550,
    title_x=0.0,
    xaxis_title="Canal de Atuação",
    yaxis_title="",
    legend_title_text="Mês",
)

fig_volume.update_traces(
    textposition="outside"
)

st.plotly_chart(fig_volume, use_container_width=True)
