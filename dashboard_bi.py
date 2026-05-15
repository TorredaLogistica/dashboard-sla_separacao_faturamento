import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date
import os




# =============================
# DETECÇÃO AUTOMÁTICA DE CELULAR + AJUSTES DE FONTE (PLOTLY)
# =============================

def detectar_mobile() -> bool:
    """Detecta acesso via celular/tablet pelo User-Agent.

    Usa st.context.headers quando disponível.
    Se st.context não existir/der erro, retorna False.
    """
    try:
        ua = str(st.context.headers.get("user-agent", "")).lower()
    except Exception:
        return False

    sinais_mobile = [
        "android", "iphone", "ipad", "ipod", "mobile",
        "windows phone", "opera mini", "blackberry",
    ]
    return any(s in ua for s in sinais_mobile)




def _corrigir_undefined_plotly(fig):
    """Remove textos 'undefined' (Plotly/JS) em títulos de eixos/legenda/colorbar.

    Em alguns cenários, o Plotly pode renderizar literalmente a palavra "undefined"
    quando o título do eixo (ou de legenda/colorbar) está ausente/None.
    Esta função limpa isso sem alterar os dados.
    """
    try:
        # Eixos (xaxis, xaxis2, yaxis, yaxis2, ...)
        for k in fig.layout:
            if str(k).startswith('xaxis') or str(k).startswith('yaxis'):
                ax = fig.layout[k]
                try:
                    t = ax.title.text
                    if t is None or str(t).strip().lower() == 'undefined':
                        ax.title.text = ''
                except Exception:
                    pass

        # Título da legenda
        try:
            lt = fig.layout.legend.title.text
            if lt is None or str(lt).strip().lower() == 'undefined':
                fig.layout.legend.title.text = ''
        except Exception:
            pass

        # Colorbar (quando usa escala contínua)
        try:
            ca = fig.layout.coloraxis
            if ca and ca.colorbar and ca.colorbar.title:
                ct = ca.colorbar.title.text
                if ct is None or str(ct).strip().lower() == 'undefined':
                    ca.colorbar.title.text = ''
        except Exception:
            pass

    except Exception:
        pass

    return fig
def aplicar_estilo_plotly(fig, modo_mobile: bool = False):
    """Ajusta fontes do Plotly para melhor legibilidade e proporção."""
    # Fontes base (maiores no desktop; no celular mantém legível sem estourar layout)
    font_base = 16 if not modo_mobile else 13
    font_axis = 14 if not modo_mobile else 12
    font_legend = 14 if not modo_mobile else 12
    font_title = 22 if not modo_mobile else 18

    fig.update_layout(
        font=dict(size=font_base),
        title_font=dict(size=font_title),
        legend=dict(font=dict(size=font_legend)),
        xaxis=dict(tickfont=dict(size=font_axis), title_font=dict(size=font_axis)),
        yaxis=dict(tickfont=dict(size=font_axis), title_font=dict(size=font_axis)),
    )
    fig = _corrigir_undefined_plotly(fig)
    return fig


def ajustar_percentual_fora_do_padrao(fig, limiar_outside=15.0, tamanho_padrao=12, offset_outside=1.0):
    """Mantém o rótulo padrão DENTRO da barra e move SOMENTE o que ficar fora do padrão para FORA.

    Como identificar "fora do padrão"?
      - Principal: barras com valor (y) pequeno.
      - Para ser mais robusto, calcula um limiar mínimo dinamicamente baseado na altura do gráfico,
        para garantir espaço suficiente para o texto (vertical) dentro da barra.

    Regras:
      - Barras normais: NÃO altera nada (mantém exatamente o print 1).
      - Fora do padrão (barra pequena):
          * remove o texto dentro apenas daquela barra
          * adiciona um rótulo externo (Scatter) no topo, horizontal, tamanho padrão
          * garante folga no eixo Y para não cortar
    """
    try:
        # Folga para não cortar texto externo
        fig.update_traces(cliponaxis=False)
        fig.update_layout(margin=dict(t=95))

        # Calcula limiar dinâmico (em %) para caber o texto dentro da barra
        # Aproximação: texto vertical precisa de ~ (tamanho_padrao*3) px de altura útil.
        h = fig.layout.height if getattr(fig.layout, 'height', None) else 550
        m = fig.layout.margin
        mt = m.t if m and getattr(m, 't', None) is not None else 90
        mb = m.b if m and getattr(m, 'b', None) is not None else 60
        # área útil aproximada
        plot_h = max(200, h - mt - mb)
        px_necessarios = max(28, int(tamanho_padrao * 3))
        limiar_dinamico = (px_necessarios / plot_h) * 100.0

        limiar_final = max(float(limiar_outside), float(limiar_dinamico))

        # Dá folga no eixo Y para o texto 'outside'
        try:
            fig.update_yaxes(range=[0, 110])
        except Exception:
            pass

        novas_traces = []

        for tr in list(fig.data):
            if getattr(tr, 'type', None) != 'bar':
                continue
            if tr.y is None or tr.x is None:
                continue

            y_vals = [float(v) for v in tr.y]
            x_vals = list(tr.x)

            # texto atual (se já veio formatado), senão gera
            if getattr(tr, 'text', None) is not None:
                txt = list(tr.text)
                txt = [t if t is not None else '' for t in txt]
            else:
                txt = [f"{v:.2f}%" for v in y_vals]

            # Detecta os pontos fora do padrão
            small_idx = [i for i, v in enumerate(y_vals) if v < limiar_final]
            if not small_idx:
                continue

            # 1) remove texto dentro SOMENTE nas barras pequenas
            for i in small_idx:
                txt[i] = ''
            tr.text = txt

            # 2) adiciona texto externo no topo (horizontal)
            xs = [x_vals[i] for i in small_idx]
            ys = [y_vals[i] + float(offset_outside) for i in small_idx]
            ts = [f"{y_vals[i]:.2f}%" for i in small_idx]

            novas_traces.append(go.Scatter(
                x=xs,
                y=ys,
                mode='text',
                text=ts,
                textposition='top center',
                textangle=0,
                textfont=dict(size=tamanho_padrao, color='#111111'),
                showlegend=False,
                hoverinfo='skip',
                cliponaxis=False,
            ))

        for nt in novas_traces:
            fig.add_trace(nt)

    except Exception:
        pass

    return fig
st.set_page_config(layout="wide", page_title="Dashboard SLA Faturamento")

# =============================
# LOGIN (Mantido conforme original)
# =============================
def check_password():
    """Login simples e robusto.

    Evita KeyError em cenários comuns no celular (reconexão do WebSocket,
    aba "dormindo", troca de rede), onde o session_state pode reiniciar
    sem a chave 'password'.
    """

    # Inicializa as chaves para evitar KeyError
    if "password" not in st.session_state:
        st.session_state["password"] = ""
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False

    def password_entered():
        if st.session_state.get("password", "") == "claro2026":
            st.session_state["password_correct"] = True
            # Não deletar a chave (evita KeyError após reconexões no mobile)
            st.session_state["password"] = ""
        else:
            st.session_state["password_correct"] = False

    if not st.session_state.get("password_correct", False):
        st.title("🔒 Acesso Restrito")
        st.text_input(
            "Digite a senha",
            type="password",
            on_change=password_entered,
            key="password",
        )

        # Mostra erro somente depois que o usuário tentar
        if st.session_state.get("password", "") != "" and not st.session_state.get("password_correct", False):
            st.error("Senha incorreta")

        st.stop()

check_password()

# =============================
# CABEÇALHO (COM AJUSTE DE FUSO HORÁRIO)
# =============================
from datetime import timedelta

st.title("Dashboard Separação e Faturamento")
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




def normalizar_pedido(serie: pd.Series) -> pd.Series:
    """Padroniza a coluna Pedido para exibição SEM separador de milhar.

    Converte sempre para texto para evitar formatação automática do Streamlit.
    Exemplos esperados:
      32,310,684 -> 32310684
      32.310.684 -> 32310684
      32310684.0 -> 32310684
    """
    if serie is None:
        return serie

    # Se vier numérico (int/float), converte para inteiro (preserva NA) e depois string
    if pd.api.types.is_numeric_dtype(serie):
        num = pd.to_numeric(serie, errors='coerce').round(0).astype('Int64')
        return num.astype(str).mask(num.isna(), '')

    s = serie.astype(str)

    # remove espaços (inclui NBSP)
    s = (s
         .str.replace(' ', '', regex=False)
         .str.replace(' ', '', regex=False)
         .str.strip()
    )

    # remove somente separadores de milhar (vírgula/ponto) em grupos de 3 dígitos
    s = s.str.replace(r'(?<=\d)[,\.](?=\d{3}(\D|$))', '', regex=True)

    # trata casos tipo "32310684.0" / "32310684,0"
    s = s.str.replace(r'([\.,]0)$', '', regex=True)

    # fallback: se ainda restar algo numérico, força int quando for inteiro-like
    num = pd.to_numeric(s, errors='coerce')
    mask = ~num.isna()
    if mask.any():
        intlike = mask & (np.isclose(num % 1, 0))
        if intlike.any():
            s.loc[intlike] = num.loc[intlike].round(0).astype('Int64').astype(str)

    return s.replace({'nan': '', 'None': '', '<NA>': ''})

# 🔥 BOTÃO DE ATUALIZAÇÃO (COLOCA AQUI)
if st.button("🔄 Atualizar dados"):
    st.cache_data.clear()
    st.rerun()

# =============================
# CARGA DE DADOS (CORRIGIDA PARA .XLSB E GITHUB)
# =============================

@st.cache_data
def load_data(path):
    # engine='pyxlsb' é necessário para arquivos .xlsb
    df = pd.read_excel(path, engine='pyxlsb')
    df.columns = df.columns.str.strip()

    # =============================
    # SANEAR CATEGORIAS (evita categorias vazias e a palavra 'undefined' em rankings)
    # =============================
    def _sanear_categoria(df_, col, valor_padrao='Não informado'):
        if col not in df_.columns:
            return df_
        s = (df_[col]
             .fillna(valor_padrao)
             .astype(str)
             .str.replace(' ', '', regex=False)  # remove NBSP
             .str.strip()
        )
        s = s.replace({
            '': valor_padrao,
            'nan': valor_padrao,
            'NaN': valor_padrao,
            'None': valor_padrao,
            '<NA>': valor_padrao,
            'undefined': valor_padrao,
            'Undefined': valor_padrao,
            'UNDEFINED': valor_padrao,
        })
        df_[col] = s
        return df_

    for _c in ['CD Origem', 'Empresa', 'Canal de Atuacao', 'Canal', 'Operador', 'Unidade de Negocio']:
        df = _sanear_categoria(df, _c)

    # PME como sigla nas colunas de canal
    for _c in ['Canal de Atuacao', 'Canal']:
        if _c in df.columns:
            df[_c] = df[_c].replace({'Pme': 'PME', 'pme': 'PME', 'pme.': 'PME', 'p.m.e': 'PME'})


    # =============================
    # PADRONIZAÇÃO DE PEDIDO (SEM SEPARADOR DE MILHAR)
    # =============================
    # Garante que o ID do pedido fique como texto e sem formatação: 32310684
    if 'Pedido' not in df.columns and 'Pedidos' in df.columns:
        df['Pedido'] = df['Pedidos']

    if 'Pedido' in df.columns:
        df['Pedido'] = normalizar_pedido(df['Pedido'])

    
    # PADRONIZAÇÃO DE CANAIS (evita duplicidade por maiúsculas/minúsculas, espaços e acentos)
    import unicodedata, re
    def _norm_key(v):
        s = '' if v is None else str(v)
        s = s.strip()
        s = re.sub(r'\s+', ' ', s)
        s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode('ascii')
        return s.lower()
    
    def _beautify(v):
        s = '' if v is None else str(v).strip()
        if not s: return s
        # padronização simples em Title Case (com exceções)
        low = _norm_key(s)
        # exceções conhecidas (ajuste aqui se quiser)
        if low in ['ecommerce', 'e-commerce', 'e commerce']: return 'Ecommerce'
        if low in ['loja propria', 'loja própria']: return 'Loja Própria'
        if low in ['agente autorizado', 'agentes autorizados', 'agente autorizados']: return 'Agente Autorizado'
        if low in ['pme', 'p.m.e', 'pme.']: return 'PME'  # mantém sigla
        # Title Case geral
        words = s.lower().split(' ')
        keep_lower = {'de','da','do','das','dos','e'}
        words2 = [w if w in keep_lower else w.capitalize() for w in words]
        return ' '.join(words2)
    
    def _padronizar_coluna(df_, col):
        if col not in df_.columns: return df_
        orig = df_[col].astype(str).fillna('').map(lambda x: x.strip())
        key = orig.map(_norm_key)
        # escolhe o valor mais frequente por chave normalizada
        canon = orig.groupby(key).agg(lambda s: s.value_counts().index[0] if len(s.value_counts()) else '')
        canon = canon.map(_beautify)
        df_[col] = key.map(canon).fillna(orig.map(_beautify))
        return df_
    
    df = _padronizar_coluna(df, 'Canal de Atuacao')
    df = _padronizar_coluna(df, 'Canal')
    
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

    # 📱 Modo celular: melhora a leitura (rótulos dos valores na vertical)
    # 📱 Modo celular (automático via User-Agent, com opção de override)
    auto_mobile = detectar_mobile()
    if 'modo_mobile' not in st.session_state:
        st.session_state['modo_mobile'] = auto_mobile
    modo_mobile = st.checkbox('📱 Modo celular (auto)', key='modo_mobile', help='Ativado automaticamente quando detectado acesso por celular. Desmarque para forçar modo desktop.')

    
    aba = st.radio("Visualização", ["📅 Visão Diária", "📊 Evolução Mensal", "📦 Volumetria de Pedidos"], horizontal=True)
    lista_meses = sorted(df['Mes_Ano'].unique(), key=lambda x: datetime.strptime(x, '%m/%Y'), reverse=True)
    if aba == "📦 Volumetria de Pedidos":
        meses_selecionados = st.multiselect("Mês de Referência", lista_meses, default=[lista_meses[0]] if lista_meses else [])
        mes_selecionado = meses_selecionados[0] if meses_selecionados else (lista_meses[0] if lista_meses else None)
    else:
        mes_selecionado = st.selectbox("Mês de Referência", lista_meses)
        meses_selecionados = [mes_selecionado] if mes_selecionado else []
    
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
# VOLUMETRIA DE PEDIDOS (NOVA VISÃO)
# =============================
if aba == "📦 Volumetria de Pedidos":
    st.subheader("📦 Volumetria de Pedidos")

    base_vol = dff_global[dff_global['Mes_Ano'].isin(meses_selecionados)].copy()
    if base_vol.empty:
        st.warning("Nenhum dado encontrado para os filtros selecionados.")
        st.stop()

    # Define a coluna de canal (prioriza Canal de Atuacao; fallback para Canal)
    if 'Canal de Atuacao' in base_vol.columns:
        col_canal = 'Canal de Atuacao'
    elif 'Canal' in base_vol.columns:
        col_canal = 'Canal'
    else:
        st.error("Coluna de canal não encontrada (esperado: 'Canal de Atuacao' ou 'Canal').")
        st.stop()

    # Conta pedidos (se existir coluna Pedido) ou linhas (fallback)
    if 'Pedido' in base_vol.columns:
        vol = (base_vol.groupby([col_canal, 'Mes_Ano'])['Pedido'].count().reset_index(name='Volume'))
    else:
        vol = (base_vol.groupby([col_canal, 'Mes_Ano']).size().reset_index(name='Volume'))

    ordem_meses = sorted(meses_selecionados, key=lambda x: datetime.strptime(x, '%m/%Y')) if meses_selecionados else None
    cat_orders = {'Mes_Ano': ordem_meses} if ordem_meses else None

    fig_volume = px.bar(
        vol,
        x=col_canal,
        y='Volume',
        color='Mes_Ano',
        barmode='group',
        text='Volume',
        title='VOLUMETRIA DE PEDIDOS',
        category_orders=cat_orders
    )

    # Padrão dos rankings: rótulos dentro da barra, no topo, na vertical (de baixo para cima)
    fig_volume.update_traces(textposition='inside', textangle=-90, insidetextanchor='end', cliponaxis=False)
    fig_volume.update_layout(
        height=(650 if modo_mobile else 560),
        title_x=0.0,
        xaxis_title='Canal de Atuação',
        yaxis_title='',
        legend_title_text='Mês'
    )
    if modo_mobile:
        # No celular: rótulos na vertical (leitura de baixo para cima)
        fig_volume.update_traces(textposition='outside', textangle=-90, textfont_size=11, cliponaxis=False)
        fig_volume.update_layout(margin=dict(l=30, r=10, t=70, b=120), legend_orientation='h', legend_y=-0.25)
    else:
        fig_volume.update_traces(textposition='outside', textfont_size=13)

    fig_volume = aplicar_estilo_plotly(fig_volume, modo_mobile)

    st.plotly_chart(fig_volume, use_container_width=True, theme=None)
    st.stop()


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

    fig = aplicar_estilo_plotly(fig, modo_mobile)

    # Ajuste pontual: evita cortar os rótulos (%) no topo do gráfico de linhas

    try:

        fig.update_traces(cliponaxis=False)

        fig.update_yaxes(range=[0, 105])

        fig.update_layout(margin=dict(t=90))

    except Exception:

        pass

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
    fig_bar_cd = aplicar_estilo_plotly(fig_bar_cd, modo_mobile)
    # Ajuste: % dentro da barra (no topo) e prevenção de 'undefined'
    try:
        fig_bar_cd.update_traces(cliponaxis=False)
        # % dentro da barra, alinhado ao topo (como no print)
        fig_bar_cd.update_traces(textposition='inside', textangle=-90, insidetextanchor='end')
        # Evita que títulos automáticos virem 'undefined' no render
        fig_bar_cd.update_layout(xaxis_title='', yaxis_title='', legend_title_text='', coloraxis_colorbar_title_text='')
    except Exception:
        pass
    st.plotly_chart(fig_bar_cd, use_container_width=True, theme=None)
    # 2. RANKING EMPRESAS
    st.subheader("Ranking Empresas Críticos (SLA Até D+1)")
    rank_emp = base.groupby('Empresa').agg({'flag_d0':'sum','flag_d1':'sum','Pedido':'count'}).reset_index()
    rank_emp['Até D+1'] = ((rank_emp['flag_d0']+rank_emp['flag_d1'])/rank_emp['Pedido']*100).round(2)
    rank_emp = rank_emp.sort_values('Até D+1')
    
    fig_bar_emp = px.bar(rank_emp, x='Empresa', y='Até D+1', 
                         text=rank_emp['Até D+1'].apply(lambda x: f"{x:.2f}%"), 
                         color='Até D+1', color_continuous_scale='RdYlGn')
    fig_bar_emp = aplicar_estilo_plotly(fig_bar_emp, modo_mobile)
    # Ajuste: % dentro da barra (no topo) e prevenção de 'undefined'
    try:
        fig_bar_emp.update_traces(cliponaxis=False)
        # % dentro da barra, alinhado ao topo (como no print)
        fig_bar_emp.update_traces(textposition='inside', textangle=-90, insidetextanchor='end')
        # Evita que títulos automáticos virem 'undefined' no render
        fig_bar_emp.update_layout(xaxis_title='', yaxis_title='', legend_title_text='', coloraxis_colorbar_title_text='')
    except Exception:
        pass
    st.plotly_chart(fig_bar_emp, use_container_width=True, theme=None)
    # 3. RANKING CANAL DE ATUAÇÃO
    st.subheader("Ranking Canal de Atuação Críticos (SLA Até D+1)")
    rank_canal = base.groupby('Canal de Atuacao').agg({'flag_d0':'sum','flag_d1':'sum','Pedido':'count'}).reset_index()
    rank_canal['Até D+1'] = ((rank_canal['flag_d0']+rank_canal['flag_d1'])/rank_canal['Pedido']*100).round(2)
    rank_canal = rank_canal.sort_values('Até D+1')
    
    fig_bar_canal = px.bar(rank_canal, x='Canal de Atuacao', y='Até D+1', 
                           text=rank_canal['Até D+1'].apply(lambda x: f"{x:.2f}%"), 
                           color='Até D+1', color_continuous_scale='RdYlGn')
    fig_bar_canal = aplicar_estilo_plotly(fig_bar_canal, modo_mobile)
    # Ajuste: % dentro da barra (no topo) e prevenção de 'undefined'
    try:
        fig_bar_canal.update_traces(cliponaxis=False)
        # % dentro da barra, alinhado ao topo (como no print)
        fig_bar_canal.update_traces(textposition='inside', textangle=-90, insidetextanchor='end')
        # Evita que títulos automáticos virem 'undefined' no render
        fig_bar_canal.update_layout(xaxis_title='', yaxis_title='', legend_title_text='', coloraxis_colorbar_title_text='')
    except Exception:
        pass
    st.plotly_chart(fig_bar_canal, use_container_width=True, theme=None)
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


    # Garantia extra: Pedido sem separador de milhar na exibição/baixar Excel
    if 'Pedido' in df_detalhe.columns:
        df_detalhe['Pedido'] = normalizar_pedido(df_detalhe['Pedido'])

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
