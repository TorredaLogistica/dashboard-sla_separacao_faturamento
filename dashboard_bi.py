import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date
from zoneinfo import ZoneInfo
from pathlib import Path
import os
import io
import base64
import hashlib




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
st.set_page_config(layout="wide", page_title="Dashboard SLA Faturamento")

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
    for chave in [
        '_cache_sidebar_base', '_ultimo_tipo_volumetria',
        'meses_volumetria_calendario', 'meses_volumetria_corte'
    ]:
        st.session_state.pop(chave, None)
    for col in ['Operador','CD Origem','Empresa','Canal','Unidade de Negocio','Canal de Atuacao']:
        st.session_state.pop(f'filtro_sidebar_{col}', None)
    st.rerun()

# =============================
# CARGA DE DADOS (CORRIGIDA PARA .XLSB E GITHUB)
# =============================


@st.cache_data
def load_data(path):
    # =============================
    # LEITURA ESTÁVEL DA BASE PRINCIPAL (mantém o comportamento original)
    # =============================
    df = pd.read_excel(path, engine='pyxlsb')
    df.columns = df.columns.str.strip()

    # =============================
    # SANEAR CATEGORIAS
    # =============================
    def _sanear_categoria(df_, col, valor_padrao='Não informado'):
        if col not in df_.columns:
            return df_
        s = (df_[col]
             .fillna(valor_padrao)
             .astype(str)
             .str.replace('\u00A0', '', regex=False)
             .str.strip())
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

    for _c in ['Canal de Atuacao', 'Canal']:
        if _c in df.columns:
            df[_c] = df[_c].replace({'Pme': 'PME', 'pme': 'PME', 'pme.': 'PME', 'p.m.e': 'PME'})

    # =============================
    # PEDIDO
    # =============================
    if 'Pedido' not in df.columns and 'Pedidos' in df.columns:
        df['Pedido'] = df['Pedidos']
    if 'Pedido' in df.columns:
        df['Pedido'] = normalizar_pedido(df['Pedido'])

    # =============================
    # PADRONIZAÇÃO DE CANAIS
    # =============================
    import unicodedata, re
    def _norm_key(v):
        s = '' if v is None else str(v)
        s = s.strip()
        s = re.sub(r'\s+', ' ', s)
        s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode('ascii')
        return s.lower()

    def _beautify(v):
        s = '' if v is None else str(v).strip()
        if not s:
            return s
        low = _norm_key(s)
        if low in ['ecommerce', 'e-commerce', 'e commerce']:
            return 'Ecommerce'
        if low in ['loja propria', 'loja própria']:
            return 'Loja Própria'
        if low in ['agente autorizado', 'agentes autorizados', 'agente autorizados']:
            return 'Agente Autorizado'
        if low in ['pme', 'p.m.e', 'pme.']:
            return 'PME'
        words = s.lower().split(' ')
        keep_lower = {'de', 'da', 'do', 'das', 'dos', 'e'}
        words2 = [w if w in keep_lower else w.capitalize() for w in words]
        return ' '.join(words2)

    def _padronizar_coluna(df_, col):
        if col not in df_.columns:
            return df_
        orig = df_[col].astype(str).fillna('').map(lambda x: x.strip())
        key = orig.map(_norm_key)
        canon = orig.groupby(key).agg(lambda s: s.value_counts().index[0] if len(s.value_counts()) else '')
        canon = canon.map(_beautify)
        df_[col] = key.map(canon).fillna(orig.map(_beautify))
        return df_

    df = _padronizar_coluna(df, 'Canal de Atuacao')
    df = _padronizar_coluna(df, 'Canal')

    # =============================
    # FUNÇÕES AUXILIARES DE DATA
    # =============================
    def _converter_data_excel(serie):
        s = serie.copy()
        if pd.api.types.is_numeric_dtype(s):
            return pd.to_datetime(s, unit='D', origin='1899-12-30', errors='coerce')
        s_num = pd.to_numeric(s, errors='coerce')
        out = pd.to_datetime(s, errors='coerce', dayfirst=True)
        mask_num = s_num.notna() & out.isna()
        if mask_num.any():
            out.loc[mask_num] = pd.to_datetime(s_num.loc[mask_num], unit='D', origin='1899-12-30', errors='coerce')
        return out

    def _score_aba_corte(df_sheet):
        if df_sheet is None or df_sheet.empty or df_sheet.shape[1] < 3:
            return -1.0
        tmp = df_sheet.iloc[:, :3].copy()
        d1 = _converter_data_excel(tmp.iloc[:, 1])
        d2 = _converter_data_excel(tmp.iloc[:, 2])
        taxa_d1 = float(d1.notna().mean()) if len(d1) else 0.0
        taxa_d2 = float(d2.notna().mean()) if len(d2) else 0.0
        labels = tmp.iloc[:, 0].astype(str).str.strip()
        tem_mes_ano = float(labels.str.contains(r'\d{1,2}/\d{2,4}|[a-zA-ZçÇ]{3,}\s*[-/]?\s*\d{2,4}', regex=True, na=False).mean()) if len(labels) else 0.0
        return taxa_d1 + taxa_d2 + tem_mes_ano

    def _aplicar_mapa_corte(df_base, df_cortes):
        if df_cortes is None or df_cortes.empty or df_cortes.shape[1] < 3:
            return df_base, False

        mapa_corte = df_cortes.iloc[:, :3].copy()
        mapa_corte.columns = ['Mes_Corte_Original', 'Data_Inicio_Corte', 'Data_Fim_Corte']
        mapa_corte['Data_Inicio_Corte'] = _converter_data_excel(mapa_corte['Data_Inicio_Corte'])
        mapa_corte['Data_Fim_Corte'] = _converter_data_excel(mapa_corte['Data_Fim_Corte'])
        mapa_corte = mapa_corte.dropna(subset=['Data_Inicio_Corte', 'Data_Fim_Corte']).copy()
        if mapa_corte.empty:
            return df_base, False

        # Regra final: filtro sempre em MM/AAAA pela data final do corte
        mapa_corte['Mes_Corte_Fatura'] = mapa_corte['Data_Fim_Corte'].dt.strftime('%m/%Y')
        mapa_corte = (
            mapa_corte[['Mes_Corte_Fatura', 'Data_Inicio_Corte', 'Data_Fim_Corte']]
            .drop_duplicates()
            .sort_values(['Data_Fim_Corte', 'Data_Inicio_Corte'])
            .reset_index(drop=True)
        )
        if mapa_corte.empty:
            return df_base, False

        intervalos = pd.IntervalIndex.from_arrays(
            mapa_corte['Data_Inicio_Corte'],
            mapa_corte['Data_Fim_Corte'],
            closed='both'
        )
        idx = intervalos.get_indexer(df_base['Data NF'])
        mask_idx = idx >= 0
        if mask_idx.any():
            valores_mes = mapa_corte['Mes_Corte_Fatura'].to_numpy()
            valores_inicio = mapa_corte['Data_Inicio_Corte'].to_numpy()
            valores_fim = mapa_corte['Data_Fim_Corte'].to_numpy()
            df_base.loc[mask_idx, 'Mes_Corte_Fatura'] = valores_mes[idx[mask_idx]]
            df_base.loc[mask_idx, 'Data_Inicio_Corte_Mapa'] = valores_inicio[idx[mask_idx]]
            df_base.loc[mask_idx, 'Data_Fim_Corte_Mapa'] = valores_fim[idx[mask_idx]]

        mapa_ordem = {mes: pos + 1 for pos, mes in enumerate(mapa_corte['Mes_Corte_Fatura'].tolist())}
        df_base['Mes_Corte_Fatura_Ordem'] = df_base['Mes_Corte_Fatura'].map(mapa_ordem)
        return df_base, bool(mask_idx.any())

    # =============================
    # DATAS PRINCIPAIS
    # =============================
    if 'Data NF' not in df.columns:
        raise KeyError("Coluna 'Data NF' não encontrada na aba principal.")

    df['Data NF'] = _converter_data_excel(df['Data NF'])
    df = df[df['Data NF'].notna()].copy()
    df['Mes_Ano'] = df['Data NF'].dt.strftime('%m/%Y')

    # =============================
    # CORTE DE FATURA (V11)
    # 1) tenta detectar a aba de cortes dentro do próprio XLSB
    # 2) se o arquivo em produção tiver só 1 aba, tenta arquivo auxiliar externo
    # =============================
    df['Mes_Corte_Fatura'] = pd.NA
    df['Mes_Corte_Fatura_Ordem'] = np.nan
    df.attrs['abas_encontradas'] = ''
    df.attrs['aba_corte_detectada'] = ''
    df.attrs['erro_corte'] = ''
    df.attrs['fonte_corte'] = ''

    try:
        with pd.ExcelFile(path, engine='pyxlsb') as xls2:
            sheet_names = [str(s).strip() for s in xls2.sheet_names]
            df.attrs['abas_encontradas'] = ' | '.join(sheet_names)

            aba_principal = sheet_names[0] if sheet_names else ''
            for candidato in ['planilha1', 'sheet1', 'base', 'dados']:
                achou = next((s for s in sheet_names if str(s).strip().lower().replace(' ', '') == candidato), None)
                if achou:
                    aba_principal = achou
                    break

            melhor_aba_corte = None
            melhor_score = -1.0
            melhor_df_corte = None

            for s in sheet_names:
                if s == aba_principal:
                    continue
                try:
                    df_sheet = pd.read_excel(xls2, sheet_name=s)
                    score = _score_aba_corte(df_sheet)
                    if score > melhor_score:
                        melhor_score = score
                        melhor_aba_corte = s
                        melhor_df_corte = df_sheet.copy()
                except Exception:
                    continue

            if melhor_aba_corte is not None and melhor_score > 0.80 and melhor_df_corte is not None:
                df.attrs['aba_corte_detectada'] = melhor_aba_corte
                df, ok = _aplicar_mapa_corte(df, melhor_df_corte)
                if ok:
                    df.attrs['fonte_corte'] = f"Aba interna: {melhor_aba_corte}"
    except Exception as e:
        df.attrs['erro_corte'] = str(e)

    # Fallback controlado: arquivo auxiliar externo com datas de corte
    if df['Mes_Corte_Fatura'].isna().all():
        candidatos_aux = [
            'datas_corte_fatura.xlsx',
            'datas_corte_fatura.xlsb',
            'corte_fatura.xlsx',
            'corte_fatura.xlsb',
            'planilha2.xlsx',
            'planilha2.xlsb'
        ]
        for nome_aux in candidatos_aux:
            p_aux = Path(nome_aux)
            if not p_aux.exists():
                continue
            try:
                if p_aux.suffix.lower() == '.csv':
                    df_aux = pd.read_csv(p_aux)
                elif p_aux.suffix.lower() == '.xlsb':
                    df_aux = pd.read_excel(p_aux, engine='pyxlsb')
                else:
                    df_aux = pd.read_excel(p_aux)
                df_aux.columns = [str(c).strip() for c in df_aux.columns]
                df, ok = _aplicar_mapa_corte(df, df_aux)
                if ok:
                    df.attrs['fonte_corte'] = f"Arquivo auxiliar: {nome_aux}"
                    break
            except Exception:
                continue

    if df['Mes_Corte_Fatura'].isna().all() and not df.attrs.get('erro_corte'):
        df.attrs['erro_corte'] = 'Nenhuma aba de corte válida foi detectada automaticamente e nenhum arquivo auxiliar foi encontrado.'

    # Extrai apenas o número depois do D+
    df['aging_num'] = df['Aging_Ajustado_D+'].astype(str).str.extract(r'D\+(\d+)').astype(int)
    df['flag_d0'] = df['aging_num'] == 0
    df['flag_d1'] = df['aging_num'] == 1
    df['flag_d2'] = df['aging_num'] == 2
    return df

# Para o GitHub, o arquivo deve estar na raiz do repositório
caminho_arquivo = "Faturamento SLA 2026.xlsb"

if not os.path.exists(caminho_arquivo):
    st.error(f"Arquivo {caminho_arquivo} não encontrado!")
    st.stop()

try:
    df = load_data(caminho_arquivo)
except Exception as e:
    st.error(f"Erro ao carregar a base: {e}")
    st.stop()


# =============================
# IDENTIFICAÇÃO DO USUÁRIO + DASHBOARD DE ACESSOS
# INDICADOR: SEPARAÇÃO E FATURAMENTO
# =============================
# Persistência do histórico:
# - Com GitHub configurado em secrets, o GitHub vira a fonte principal do histórico.
# - Sem GitHub, o app mantém CSV/Excel local como backup.

LOG_ACESSOS_SF_CSV = "log_separacao_faturamento_acessos.csv"
LOG_ACESSOS_SF_XLSX = "log_separacao_faturamento_acessos.xlsx"
FUSO_HORARIO_LOG = "America/Sao_Paulo"
SENHA_DASHBOARD_ACESSOS = "admin"
ADMIN_LOG_USUARIO = "admin"
ADMIN_LOG_SENHA = "admin"
COLUNAS_LOG_SF = ["ID", "Usuario", "Data", "Indicador", "Visualizacao", "Detalhe"]
COLUNAS_EXIBICAO_LOG_SF = ["Usuario", "Data", "Indicador", "Visualizacao", "Detalhe"]


def _get_config_sf(nome: str, padrao: str = "") -> str:
    try:
        valor = st.secrets.get(nome, "")
        if valor:
            return str(valor)
    except Exception:
        pass
    return str(os.getenv(nome, padrao) or padrao)


def github_sf_configurado() -> bool:
    return bool(_get_config_sf("GITHUB_TOKEN") and _get_config_sf("GITHUB_REPO"))


def _github_sf_info() -> dict:
    return {
        "token": _get_config_sf("GITHUB_TOKEN"),
        "repo": _get_config_sf("GITHUB_REPO"),
        "branch": _get_config_sf("GITHUB_BRANCH", "main"),
        "path": _get_config_sf("GITHUB_LOG_SF_PATH", LOG_ACESSOS_SF_CSV),
    }


def _limpar_nome_visualizacao(aba_atual: str) -> str:
    mapa = {
        "📅 Visão Diária": "Visão Diária",
        "📊 Evolução Mensal": "Evolução Mensal",
        "📦 Volumetria de Pedidos": "Volumetria de Pedidos",
        "📊 Dashboard de Acessos": "Dashboard de Acessos",
        "Entrada no Indicador": "Entrada no Indicador",
    }
    return mapa.get(str(aba_atual), str(aba_atual))


def obter_usuario_logado_sf() -> str:
    usuario = str(st.session_state.get("usuario_logado_sf", "")).strip()
    return usuario if usuario else "Usuário"


def _gerar_id_log_sf(usuario: str, data, indicador: str, visualizacao: str, detalhe: str) -> str:
    try:
        data_txt = pd.to_datetime(data, errors="coerce").strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        data_txt = str(data)
    chave = f"{usuario}|{data_txt}|{indicador}|{visualizacao}|{detalhe}"
    return hashlib.sha256(chave.encode("utf-8")).hexdigest()[:16]


def _normalizar_log_sf(df_log: pd.DataFrame) -> pd.DataFrame:
    if df_log is None or df_log.empty:
        return pd.DataFrame(columns=COLUNAS_LOG_SF)

    df_log = df_log.copy()
    for col in COLUNAS_LOG_SF:
        if col not in df_log.columns:
            df_log[col] = "" if col != "Data" else pd.NaT

    df_log = df_log[COLUNAS_LOG_SF].copy()
    df_log["Usuario"] = df_log["Usuario"].fillna("Usuário").astype(str).str.strip().replace("", "Usuário")
    df_log["Indicador"] = df_log["Indicador"].fillna("Separação e Faturamento").astype(str).str.strip().replace("", "Separação e Faturamento")
    df_log["Visualizacao"] = df_log["Visualizacao"].fillna("Não informado").astype(str).str.strip().replace("", "Não informado")
    df_log["Detalhe"] = df_log["Detalhe"].fillna("").astype(str).str.strip()
    df_log["Data"] = pd.to_datetime(df_log["Data"], errors="coerce", dayfirst=True)
    df_log = df_log.dropna(subset=["Data"]).copy()

    if df_log.empty:
        return pd.DataFrame(columns=COLUNAS_LOG_SF)

    df_log["Data"] = df_log["Data"].dt.floor("s")
    mask_id_vazio = df_log["ID"].fillna("").astype(str).str.strip().eq("")
    if mask_id_vazio.any():
        df_log.loc[mask_id_vazio, "ID"] = df_log.loc[mask_id_vazio].apply(
            lambda r: _gerar_id_log_sf(r["Usuario"], r["Data"], r["Indicador"], r["Visualizacao"], r["Detalhe"]),
            axis=1
        )

    df_log = df_log.drop_duplicates(subset=["ID"], keep="first")
    df_log = df_log.drop_duplicates(subset=COLUNAS_EXIBICAO_LOG_SF, keep="first")
    df_log = df_log.sort_values("Data", ascending=True).reset_index(drop=True)
    return df_log


def _df_log_sf_para_csv_bytes(df_log: pd.DataFrame) -> bytes:
    df_log = _normalizar_log_sf(df_log)
    df_csv = df_log.copy()
    if not df_csv.empty:
        df_csv["Data"] = df_csv["Data"].dt.strftime("%Y-%m-%d %H:%M:%S")
    return df_csv.to_csv(index=False, sep=";", encoding="utf-8-sig").encode("utf-8-sig")


def _csv_bytes_para_log_sf(conteudo: bytes) -> pd.DataFrame:
    if not conteudo:
        return pd.DataFrame(columns=COLUNAS_LOG_SF)
    try:
        return _normalizar_log_sf(pd.read_csv(io.BytesIO(conteudo), sep=";", encoding="utf-8-sig"))
    except Exception:
        return pd.DataFrame(columns=COLUNAS_LOG_SF)


def _github_ler_log_sf() -> tuple[pd.DataFrame, str | None]:
    if not github_sf_configurado():
        return pd.DataFrame(columns=COLUNAS_LOG_SF), None

    try:
        import requests
        cfg = _github_sf_info()
        url = f"https://api.github.com/repos/{cfg['repo']}/contents/{cfg['path']}"
        headers = {
            "Authorization": f"Bearer {cfg['token']}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        resp = requests.get(url, headers=headers, params={"ref": cfg["branch"]}, timeout=15)
        if resp.status_code == 404:
            return pd.DataFrame(columns=COLUNAS_LOG_SF), None
        resp.raise_for_status()
        dados = resp.json()
        conteudo = base64.b64decode(dados.get("content", ""))
        sha = dados.get("sha")
        return _csv_bytes_para_log_sf(conteudo), sha
    except Exception:
        return pd.DataFrame(columns=COLUNAS_LOG_SF), None


def _github_salvar_log_sf(df_log: pd.DataFrame, mensagem: str = "Atualiza log Separação e Faturamento") -> bool:
    if not github_sf_configurado():
        return False

    try:
        import requests
        cfg = _github_sf_info()
        url = f"https://api.github.com/repos/{cfg['repo']}/contents/{cfg['path']}"
        headers = {
            "Authorization": f"Bearer {cfg['token']}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        _, sha_atual = _github_ler_log_sf()
        payload = {
            "message": mensagem,
            "content": base64.b64encode(_df_log_sf_para_csv_bytes(df_log)).decode("utf-8"),
            "branch": cfg["branch"],
        }
        if sha_atual:
            payload["sha"] = sha_atual

        resp = requests.put(url, headers=headers, json=payload, timeout=20)
        if resp.status_code == 409:
            df_remoto, sha_novo = _github_ler_log_sf()
            df_final = _normalizar_log_sf(pd.concat([df_remoto, df_log], ignore_index=True))
            payload["content"] = base64.b64encode(_df_log_sf_para_csv_bytes(df_final)).decode("utf-8")
            if sha_novo:
                payload["sha"] = sha_novo
            resp = requests.put(url, headers=headers, json=payload, timeout=20)
        resp.raise_for_status()
        return True
    except Exception:
        return False


def _ler_log_sf_local() -> pd.DataFrame:
    if os.path.exists(LOG_ACESSOS_SF_CSV):
        try:
            return _normalizar_log_sf(pd.read_csv(LOG_ACESSOS_SF_CSV, sep=";", encoding="utf-8-sig"))
        except Exception:
            pass
    if os.path.exists(LOG_ACESSOS_SF_XLSX):
        try:
            return _normalizar_log_sf(pd.read_excel(LOG_ACESSOS_SF_XLSX, engine="openpyxl"))
        except Exception:
            pass
    return pd.DataFrame(columns=COLUNAS_LOG_SF)


def salvar_log_sf_local(df_log: pd.DataFrame):
    df_log = _normalizar_log_sf(df_log)
    Path(LOG_ACESSOS_SF_CSV).write_bytes(_df_log_sf_para_csv_bytes(df_log))
    try:
        df_log.to_excel(LOG_ACESSOS_SF_XLSX, index=False, engine="openpyxl")
    except Exception:
        pass


def carregar_log_sf() -> pd.DataFrame:
    if github_sf_configurado():
        df_github, _sha = _github_ler_log_sf()
        if not df_github.empty:
            salvar_log_sf_local(df_github)
            return df_github
        df_local = _ler_log_sf_local()
        if not df_local.empty:
            _github_salvar_log_sf(df_local, "Migra histórico inicial Separação e Faturamento")
            salvar_log_sf_local(df_local)
            return df_local
        return pd.DataFrame(columns=COLUNAS_LOG_SF)
    return _ler_log_sf_local()


def salvar_log_sf(df_log: pd.DataFrame, mensagem_github: str = "Atualiza log Separação e Faturamento"):
    df_log = _normalizar_log_sf(df_log)
    salvar_log_sf_local(df_log)
    if github_sf_configurado():
        _github_salvar_log_sf(df_log, mensagem_github)


def registrar_log_sf(visualizacao: str, detalhe: str = "Acesso à visualização", usuario: str | None = None):
    try:
        visualizacao = _limpar_nome_visualizacao(visualizacao)
        usuario = (usuario or obter_usuario_logado_sf()).strip() or "Usuário"
        detalhe = (detalhe or "").strip()
        indicador = "Separação e Faturamento"
        data_hora_sp = datetime.now(ZoneInfo(FUSO_HORARIO_LOG)).replace(tzinfo=None).replace(microsecond=0)

        chave_evento = f"{usuario}|{indicador}|{visualizacao}|{detalhe}"
        ultimo = st.session_state.get("_ultimo_log_sf_evento", {})
        if ultimo.get("chave") == chave_evento:
            try:
                segundos = (data_hora_sp - ultimo.get("data")).total_seconds()
                if 0 <= segundos <= 3:
                    return
            except Exception:
                pass

        novo = pd.DataFrame([{
            "ID": _gerar_id_log_sf(usuario, data_hora_sp, indicador, visualizacao, detalhe),
            "Usuario": usuario,
            "Data": data_hora_sp,
            "Indicador": indicador,
            "Visualizacao": visualizacao,
            "Detalhe": detalhe,
        }])
        base = carregar_log_sf()
        base = pd.concat([base, novo], ignore_index=True)
        salvar_log_sf(base, "Registra acesso no indicador Separação e Faturamento")
        st.session_state["_ultimo_log_sf_evento"] = {"chave": chave_evento, "data": data_hora_sp}
    except Exception as e:
        st.toast(f"Não foi possível registrar o acesso: {e}", icon="⚠️")


def registrar_visualizacao_sf(aba_atual: str):
    visualizacao = _limpar_nome_visualizacao(aba_atual)
    usuario = obter_usuario_logado_sf()
    chave = f"view|{usuario}|{visualizacao}"
    if st.session_state.get("_ultima_visualizacao_sf_logada") != chave:
        registrar_log_sf(visualizacao, "Acesso à visualização", usuario=usuario)
        st.session_state["_ultima_visualizacao_sf_logada"] = chave


def apagar_logs_sf() -> bool:
    try:
        vazio = pd.DataFrame(columns=COLUNAS_LOG_SF)
        salvar_log_sf(vazio, "Apaga histórico do indicador Separação e Faturamento")
        st.session_state["_ultimo_log_sf_evento"] = {}
        st.session_state["_ultima_visualizacao_sf_logada"] = None
        return True
    except Exception:
        return False


def render_identificacao_usuario_sf():
    st.markdown("## 🔐 Identificação de acesso")
    st.info("Para acessar o indicador de Separação e Faturamento, informe seu nome de usuário.")
    nome_digitado = st.text_input("Nome do usuário", key="input_usuario_logado_sf")
    if st.button("Acessar indicador", use_container_width=True):
        nome_digitado = (nome_digitado or "").strip()
        if not nome_digitado:
            st.error("Informe o nome do usuário para continuar.")
            return
        st.session_state.usuario_logado_sf = nome_digitado
        st.session_state.acesso_sf_liberado = True
        registrar_log_sf("Entrada no Indicador", "Acesso liberado ao indicador", usuario=nome_digitado)
        st.rerun()


def render_senha_dashboard_acessos_sf():
    st.markdown("## 🔐 Acesso restrito")
    st.info("Informe a senha para acessar o Dashboard de Acessos.")
    senha_digitada = st.text_input("Senha", type="password", key="senha_dashboard_acessos_sf")
    if st.button("Entrar", use_container_width=True):
        if senha_digitada == SENHA_DASHBOARD_ACESSOS:
            st.session_state.dashboard_acessos_sf_autenticado = True
            registrar_log_sf("Dashboard de Acessos", "Acesso autorizado", usuario=obter_usuario_logado_sf())
            st.rerun()
        else:
            st.error("Senha incorreta. Tente novamente.")


def render_dashboard_acessos_sf():
    st.subheader("📊 Dashboard de Acessos")
    st.caption("Histórico de acessos das visualizações do indicador Separação e Faturamento.")
    fonte_log = "GitHub" if github_sf_configurado() else "arquivo local do app"
    st.caption(f"Fonte do histórico: {fonte_log}")

    df_log = carregar_log_sf()
    if df_log.empty:
        st.warning("Ainda não há registros de acessos para este indicador.")
        return
    df_log = df_log.dropna(subset=["Data"]).copy()
    if df_log.empty:
        st.warning("O arquivo de log existe, mas ainda não possui datas válidas.")
        return

    data_min = df_log["Data"].min().date()
    data_max = df_log["Data"].max().date()

    st.markdown("### 🔎 Filtros")
    col_dt_ini, col_dt_fim = st.columns(2)
    data_inicio = col_dt_ini.date_input("Data início", value=data_min, min_value=data_min, max_value=data_max, format="DD/MM/YYYY", key="sf_log_data_inicio")
    data_fim = col_dt_fim.date_input("Data fim", value=data_max, min_value=data_min, max_value=data_max, format="DD/MM/YYYY", key="sf_log_data_fim")

    inicio = pd.to_datetime(data_inicio)
    fim = pd.to_datetime(data_fim) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
    df_filtrado = df_log[(df_log["Data"] >= inicio) & (df_log["Data"] <= fim)].copy()

    if df_filtrado.empty:
        st.info("Não há acessos registrados para o período selecionado.")
    else:
        total_acessos = len(df_filtrado)
        usuarios_unicos = df_filtrado["Usuario"].nunique()
        indicadores_acessados = df_filtrado["Indicador"].nunique()
        c1, c2, c3 = st.columns(3)
        c1.metric("Total de acessos", f"{total_acessos:,}".replace(",", "."))
        c2.metric("Usuários únicos", f"{usuarios_unicos:,}".replace(",", "."))
        c3.metric("Indicadores acessados", f"{indicadores_acessados:,}".replace(",", "."))
        st.caption(f"Histórico carregado de {data_inicio.strftime('%d/%m/%Y')} até {data_fim.strftime('%d/%m/%Y')}.")

        st.markdown("### 👤 Acessos por usuário")
        ranking_usuario = df_filtrado["Usuario"].fillna("Usuário").value_counts().reset_index()
        ranking_usuario.columns = ["Usuário", "Qtd Acessos"]
        st.dataframe(ranking_usuario, use_container_width=True, hide_index=True)
        st.bar_chart(ranking_usuario.set_index("Usuário"))

        st.markdown("### 📌 Acessos por visualização")
        ranking_visualizacao = df_filtrado["Visualizacao"].fillna("Não informado").value_counts().reset_index()
        ranking_visualizacao.columns = ["Visualização", "Qtd Acessos"]
        st.dataframe(ranking_visualizacao, use_container_width=True, hide_index=True)
        st.bar_chart(ranking_visualizacao.set_index("Visualização"))

        st.markdown("### 📅 Acessos por dia")
        acessos_dia = df_filtrado.copy()
        acessos_dia["Dia"] = acessos_dia["Data"].dt.date
        acessos_dia = acessos_dia.groupby("Dia").size().reset_index(name="Qtd Acessos")
        st.line_chart(acessos_dia.set_index("Dia"))

        st.markdown("### 🕒 Últimos acessos")
        ultimos = df_filtrado.sort_values("Data", ascending=False).copy()
        ultimos = ultimos[COLUNAS_EXIBICAO_LOG_SF].copy()
        ultimos["Data"] = ultimos["Data"].dt.strftime("%d/%m/%Y %H:%M:%S")
        st.dataframe(ultimos, use_container_width=True, hide_index=True)

        csv_download = ultimos.to_csv(index=False, sep=";", encoding="utf-8-sig").encode("utf-8-sig")
        st.download_button("⬇️ Baixar histórico filtrado em CSV", data=csv_download, file_name=LOG_ACESSOS_SF_CSV, mime="text/csv", use_container_width=True)

    if os.path.exists(LOG_ACESSOS_SF_XLSX):
        with open(LOG_ACESSOS_SF_XLSX, "rb") as f:
            st.download_button("⬇️ Baixar histórico completo em Excel", data=f, file_name=LOG_ACESSOS_SF_XLSX, mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)

    st.markdown("---")
    with st.expander("🛡️ Administração do log - apagar registros"):
        st.warning("Atenção: esta ação apaga todos os registros de acessos deste indicador.")
        usuario_admin = st.text_input("Usuário administrador", key="usuario_admin_log_sf")
        senha_admin = st.text_input("Senha administrador", type="password", key="senha_admin_log_sf")
        confirmar = st.checkbox("Confirmo que desejo apagar todos os registros", key="confirmar_apagar_log_sf")
        if st.button("🗑️ Apagar todos os registros", use_container_width=True):
            if usuario_admin == ADMIN_LOG_USUARIO and senha_admin == ADMIN_LOG_SENHA and confirmar:
                if apagar_logs_sf():
                    st.success("Registros apagados com sucesso.")
                    st.rerun()
                else:
                    st.error("Não foi possível apagar os registros.")
            else:
                st.error("Usuário/senha inválidos ou confirmação não marcada.")

def _montar_cache_sidebar(df_base, filtros_cols):
    """Pré-calcula opções da sidebar para evitar recomputações custosas a cada rerun."""
    lista_meses = sorted(df_base['Mes_Ano'].dropna().unique(), key=lambda x: datetime.strptime(x, '%m/%Y'), reverse=True)

    opcoes_filtros = {}
    for col in filtros_cols:
        if col in df_base.columns:
            opcoes_filtros[col] = sorted(df_base[col].dropna().unique())

    if {'Mes_Corte_Fatura', 'Mes_Corte_Fatura_Ordem'}.issubset(df_base.columns):
        base_corte_sidebar = (
            df_base.loc[df_base['Mes_Corte_Fatura'].notna(), ['Mes_Corte_Fatura', 'Mes_Corte_Fatura_Ordem']]
                   .drop_duplicates()
                   .sort_values('Mes_Corte_Fatura_Ordem', ascending=False)
        )
        lista_meses_corte = base_corte_sidebar['Mes_Corte_Fatura'].tolist()
    else:
        lista_meses_corte = []

    return {
        'lista_meses': lista_meses,
        'lista_meses_corte': lista_meses_corte,
        'opcoes_filtros': opcoes_filtros,
    }

if 'dashboard_acessos_sf_autenticado' not in st.session_state:
    st.session_state.dashboard_acessos_sf_autenticado = False
if 'usuario_logado_sf' not in st.session_state:
    st.session_state.usuario_logado_sf = ''
if 'acesso_sf_liberado' not in st.session_state:
    st.session_state.acesso_sf_liberado = False

if not st.session_state.acesso_sf_liberado or not str(st.session_state.usuario_logado_sf).strip():
    render_identificacao_usuario_sf()
    st.stop()

st.caption(f"Usuário logado: {obter_usuario_logado_sf()}")

# =============================
# SIDEBAR
# =============================

with st.sidebar:
    if os.path.exists("logo_claro.png"):
        st.image("logo_claro.png", use_container_width=True)

    auto_mobile = detectar_mobile()
    if 'modo_mobile' not in st.session_state:
        st.session_state['modo_mobile'] = auto_mobile
    modo_mobile = st.checkbox('📱 Modo celular (auto)', key='modo_mobile', help='Ativado automaticamente quando detectado acesso por celular. Desmarque para forçar modo desktop.')

    filtros = ['Operador','CD Origem','Empresa','Canal','Unidade de Negocio','Canal de Atuacao']
    if '_cache_sidebar_base' not in st.session_state:
        st.session_state['_cache_sidebar_base'] = _montar_cache_sidebar(df, filtros)
    cache_sidebar = st.session_state['_cache_sidebar_base']

    aba = st.radio("Visualização", ["📅 Visão Diária", "📊 Evolução Mensal", "📦 Volumetria de Pedidos", "📊 Dashboard de Acessos"], horizontal=True)
    lista_meses = cache_sidebar['lista_meses']

    tipo_volumetria = "Calendário (Data NF)"
    meses_selecionados = []
    mes_selecionado = lista_meses[0] if lista_meses else None
    mask = np.ones(len(df), dtype=bool)
    filtros_selecionados = {}

    if aba != "📊 Dashboard de Acessos":
        if '_ultimo_tipo_volumetria' not in st.session_state:
            st.session_state['_ultimo_tipo_volumetria'] = None
        if 'meses_volumetria_calendario' not in st.session_state:
            st.session_state['meses_volumetria_calendario'] = []
        if 'meses_volumetria_corte' not in st.session_state:
            st.session_state['meses_volumetria_corte'] = []

        if aba == "📦 Volumetria de Pedidos":
            tipo_volumetria = st.radio("Tipo de Período", ["Calendário (Data NF)", "Corte de Fatura"], horizontal=False, key='tipo_periodo_volumetria')
            mudou_tipo_volumetria = st.session_state.get('_ultimo_tipo_volumetria') != tipo_volumetria
            lista_meses_corte = cache_sidebar['lista_meses_corte']
            if tipo_volumetria == "Calendário (Data NF)":
                if mudou_tipo_volumetria or not st.session_state['meses_volumetria_calendario']:
                    st.session_state['meses_volumetria_calendario'] = [lista_meses[0]] if lista_meses else []
                meses_selecionados = st.multiselect("Mês de Referência", lista_meses, key='meses_volumetria_calendario')
            else:
                if mudou_tipo_volumetria or not st.session_state['meses_volumetria_corte']:
                    st.session_state['meses_volumetria_corte'] = [lista_meses_corte[0]] if lista_meses_corte else []
                meses_selecionados = st.multiselect("Mês de Corte da Fatura", lista_meses_corte, key='meses_volumetria_corte')
                if not lista_meses_corte:
                    st.caption("⚠️ Não foi possível detectar automaticamente a aba de cortes neste arquivo.")
            if mudou_tipo_volumetria:
                for col in filtros:
                    chave_filtro = f'filtro_sidebar_{col}'
                    if chave_filtro in st.session_state:
                        st.session_state[chave_filtro] = []
            st.session_state['_ultimo_tipo_volumetria'] = tipo_volumetria
            mes_selecionado = meses_selecionados[0] if meses_selecionados else None
        else:
            mes_selecionado = st.selectbox("Mês de Referência", lista_meses)
            meses_selecionados = [mes_selecionado] if mes_selecionado else []

        opcoes_filtros = cache_sidebar['opcoes_filtros']
        for col in filtros:
            if col in df.columns:
                chave_filtro = f'filtro_sidebar_{col}'
                if chave_filtro not in st.session_state:
                    st.session_state[chave_filtro] = []
                vals = st.multiselect(col, opcoes_filtros.get(col, []), key=chave_filtro)
                filtros_selecionados[col] = vals
                if vals:
                    mask &= df[col].isin(vals)
dff_global = df[mask].copy()
empresas_filtradas = filtros_selecionados.get('Empresa', [])

if aba != "📊 Dashboard de Acessos":
    st.session_state.dashboard_acessos_sf_autenticado = False
    registrar_visualizacao_sf(aba)

if aba == "📊 Dashboard de Acessos":
    if not st.session_state.dashboard_acessos_sf_autenticado:
        render_senha_dashboard_acessos_sf()
    else:
        render_dashboard_acessos_sf()
    st.stop()



# =============================
# VOLUMETRIA DE PEDIDOS (NOVA VISÃO)
# =============================
if aba == "📦 Volumetria de Pedidos":
    st.subheader("📦 Volumetria de Pedidos")

    def _coluna_canal(df_local):
        if 'Canal de Atuacao' in df_local.columns:
            return 'Canal de Atuacao'
        if 'Canal' in df_local.columns:
            return 'Canal'
        st.error("Coluna de canal não encontrada (esperado: 'Canal de Atuacao' ou 'Canal').")
        st.stop()

    def _contar_volume(df_local, group_cols):
        if 'Pedido' in df_local.columns:
            return df_local.groupby(group_cols, sort=False, observed=True)['Pedido'].count().reset_index(name='Volume')
        return df_local.groupby(group_cols, sort=False, observed=True).size().reset_index(name='Volume')

    def _formatar_inteiro_local(valor):
        try:
            return f"{int(round(float(valor))):,}".replace(',', '.')
        except:
            return str(valor)

    def _calcular_estilo_texto_volumetria(df_plot, col_categoria, col_valor='Volume', agrupado=False):
        """Mantém tamanho uniforme por gráfico, reduzindo somente quando não couber; se ainda truncar, rotaciona na vertical."""
        if df_plot is None or df_plot.empty or col_categoria not in df_plot.columns or col_valor not in df_plot.columns:
            return {'font_size': (18 if modo_mobile else 21), 'textangle': 0}

        valores = pd.to_numeric(df_plot[col_valor], errors='coerce').fillna(0)
        if valores.empty:
            return {'font_size': (18 if modo_mobile else 21), 'textangle': 0}

        max_chars = int(valores.round(0).astype(int).astype(str).str.len().max())
        qtd_categorias = max(int(df_plot[col_categoria].nunique()), 1)
        multiplicador_barras = 3 if agrupado else 1

        largura_util = 430 if modo_mobile else 1180
        barras_estimadas = max(qtd_categorias * multiplicador_barras, 1)
        px_por_barra = largura_util / barras_estimadas

        font_size_base = 18 if modo_mobile else 21
        font_size_reduzida = max(14 if modo_mobile else 17, int(round(font_size_base * 0.80)))

        def largura_texto_estimada(font_size):
            return max_chars * font_size * 0.62

        if largura_texto_estimada(font_size_base) <= (px_por_barra * 0.85):
            return {'font_size': font_size_base, 'textangle': 0}

        if largura_texto_estimada(font_size_reduzida) <= (px_por_barra * 0.85):
            return {'font_size': font_size_reduzida, 'textangle': 0}

        return {'font_size': font_size_reduzida, 'textangle': -90}

    def _formatar_figura_volumetria(fig, df_plot, col_categoria, eixo_x_titulo, altura=None, rotacionar_x=False, legenda_titulo='Mês', agrupado=False, estilo_texto=None):
        if estilo_texto is None:
            estilo_texto = _calcular_estilo_texto_volumetria(df_plot, col_categoria, 'Volume', agrupado=agrupado)

        fig.update_layout(
            height=altura or (650 if modo_mobile else 560),
            title_x=0.0,
            xaxis_title=eixo_x_titulo,
            yaxis_title='',
            legend_title_text=legenda_titulo,
        )

        fig.update_traces(
            textposition='outside',
            textangle=estilo_texto['textangle'],
            textfont_size=estilo_texto['font_size'],
            cliponaxis=False,
            texttemplate='%{text}',
        )

        if modo_mobile:
            fig.update_layout(margin=dict(l=30, r=10, t=70, b=120), legend_orientation='h', legend_y=-0.25)
        else:
            fig.update_layout(margin=dict(l=40, r=20, t=70, b=80))

        if rotacionar_x:
            fig.update_xaxes(tickangle=-35)
        return aplicar_estilo_plotly(fig, modo_mobile)

    def _obter_projecao_periodo(df_local, coluna_periodo, periodo_ref):
        if df_local is None or df_local.empty or not periodo_ref:
            return None

        base_periodo = df_local.loc[df_local[coluna_periodo] == periodo_ref]
        if base_periodo.empty or 'Data NF' not in base_periodo.columns:
            return None

        ultima_data = pd.to_datetime(base_periodo['Data NF'], errors='coerce').dropna().max()
        if pd.isna(ultima_data):
            return None

        volume_atual = int(base_periodo['Pedido'].count()) if 'Pedido' in base_periodo.columns else int(len(base_periodo))

        if coluna_periodo == 'Mes_Ano':
            periodo_dt = datetime.strptime(str(periodo_ref), '%m/%Y')
            data_inicio = pd.Timestamp(periodo_dt.year, periodo_dt.month, 1)
            data_fim = data_inicio + pd.offsets.MonthEnd(1)
        else:
            if 'Data_Inicio_Corte_Mapa' not in base_periodo.columns or 'Data_Fim_Corte_Mapa' not in base_periodo.columns:
                return None
            data_inicio = pd.to_datetime(base_periodo['Data_Inicio_Corte_Mapa'], errors='coerce').dropna().min()
            data_fim = pd.to_datetime(base_periodo['Data_Fim_Corte_Mapa'], errors='coerce').dropna().max()
            if pd.isna(data_inicio) or pd.isna(data_fim):
                return None

        ultima_data_util = min(pd.Timestamp(ultima_data).normalize(), pd.Timestamp(data_fim).normalize())
        data_inicio = pd.Timestamp(data_inicio).normalize()
        data_fim = pd.Timestamp(data_fim).normalize()

        dias_decorridos = int((ultima_data_util - data_inicio).days + 1)
        dias_totais = int((data_fim - data_inicio).days + 1)

        if dias_decorridos <= 0 or dias_totais <= 0 or dias_decorridos >= dias_totais:
            return None

        volume_projetado = int(round(volume_atual / dias_decorridos * dias_totais))
        if volume_projetado <= volume_atual:
            return None

        return {'volume_projetado': volume_projetado}

    def _adicionar_linha_projecao(fig, df_local, df_plot, coluna_periodo, ordem_periodos, estilo_texto=None):
        if df_plot is None or df_plot.empty or coluna_periodo not in df_plot.columns:
            return fig

        periodos_disponiveis = df_plot[coluna_periodo].dropna().tolist()
        if not periodos_disponiveis:
            return fig
        periodos_set = set(periodos_disponiveis)
        periodos_plot = [p for p in (ordem_periodos or periodos_disponiveis) if p in periodos_set]
        if not periodos_plot:
            return fig

        ultimo_periodo = periodos_plot[-1]
        proj = _obter_projecao_periodo(df_local, coluna_periodo, ultimo_periodo)
        if not proj:
            return fig

        if estilo_texto is None:
            estilo_texto = _calcular_estilo_texto_volumetria(df_plot, coluna_periodo, 'Volume', agrupado=False)

        qtd_periodos = max(len(periodos_plot), 1)
        indice_ultimo = qtd_periodos - 1
        centro = (indice_ultimo + 0.5) / qtd_periodos
        meia_linha = min(0.11, 0.35 / qtd_periodos)
        x0 = max(0.0, centro - meia_linha)
        x1 = min(1.0, centro + meia_linha)
        y_proj = proj['volume_projetado']
        y_max_atual = max(float(df_plot['Volume'].max()), float(y_proj))

        fig.add_shape(
            type='line',
            xref='paper',
            yref='y',
            x0=x0,
            x1=x1,
            y0=y_proj,
            y1=y_proj,
            line=dict(color='#444444', width=2, dash='dot')
        )
        fig.add_annotation(
            x=centro,
            y=y_proj,
            xref='paper',
            yref='y',
            text=f"Projetado: {_formatar_inteiro_local(y_proj)}",
            showarrow=False,
            xanchor='center',
            yanchor='bottom',
            align='center',
            yshift=10 if not modo_mobile else 8,
            font=dict(size=estilo_texto['font_size'], color='#2c3e50')
        )
        fig.update_yaxes(range=[0, y_max_atual * 1.18])
        return fig
    coluna_periodo = 'Mes_Ano'
    legenda_periodo = 'Mês'
    titulo_geral = 'Volumetria de Pedidos Geral'
    titulo_canal = 'Volumetria de Pedidos por Canal'

    if tipo_volumetria == "Corte de Fatura":
        coluna_periodo = 'Mes_Corte_Fatura'
        legenda_periodo = 'Mês de Corte'
        titulo_geral = 'Volumetria de Pedidos Geral - Corte de Fatura'
        titulo_canal = 'Volumetria de Pedidos por Canal - Corte de Fatura'

    base_vol = dff_global[dff_global[coluna_periodo].isin(meses_selecionados)].copy()
    if base_vol.empty:
        st.warning("Nenhum dado encontrado para os filtros selecionados.")
        st.stop()

    if coluna_periodo == 'Mes_Ano':
        # Calendário: do mais antigo para o mais novo (esquerda -> direita)
        ordem_periodos = sorted(meses_selecionados, key=lambda x: datetime.strptime(x, '%m/%Y')) if meses_selecionados else None
    else:
        # Corte de Fatura: do mais antigo para o mais novo (esquerda -> direita)
        ordem_periodos = (
            base_vol[[coluna_periodo, 'Mes_Corte_Fatura_Ordem']]
            .dropna()
            .drop_duplicates()
            .sort_values('Mes_Corte_Fatura_Ordem', ascending=True)[coluna_periodo]
            .tolist()
        )

    category_orders = {coluna_periodo: ordem_periodos} if ordem_periodos else None
    col_canal = _coluna_canal(base_vol)
    colunas_base_vol = [coluna_periodo, 'Data NF', col_canal]
    if 'Pedido' in base_vol.columns:
        colunas_base_vol.append('Pedido')
    if coluna_periodo == 'Mes_Corte_Fatura':
        if 'Mes_Corte_Fatura_Ordem' in base_vol.columns:
            colunas_base_vol.append('Mes_Corte_Fatura_Ordem')
        if 'Data_Inicio_Corte_Mapa' in base_vol.columns:
            colunas_base_vol.append('Data_Inicio_Corte_Mapa')
        if 'Data_Fim_Corte_Mapa' in base_vol.columns:
            colunas_base_vol.append('Data_Fim_Corte_Mapa')
    colunas_base_vol = [c for c in dict.fromkeys(colunas_base_vol) if c in base_vol.columns]
    base_vol = base_vol[colunas_base_vol].copy()

    vol_geral = _contar_volume(base_vol, [coluna_periodo])
    estilo_geral = _calcular_estilo_texto_volumetria(vol_geral, coluna_periodo, 'Volume', agrupado=False)
    fig_geral = px.bar(vol_geral, x=coluna_periodo, y='Volume', color=coluna_periodo, text='Volume', title=titulo_geral, category_orders=category_orders)
    fig_geral = _formatar_figura_volumetria(
        fig_geral,
        vol_geral,
        coluna_periodo,
        eixo_x_titulo=('Mês de Referência' if coluna_periodo == 'Mes_Ano' else 'Mês de Corte da Fatura'),
        altura=(500 if not modo_mobile else 620),
        legenda_titulo=legenda_periodo,
        estilo_texto=estilo_geral
    )
    fig_geral = _adicionar_linha_projecao(fig_geral, base_vol, vol_geral, coluna_periodo, ordem_periodos, estilo_texto=estilo_geral)
    st.plotly_chart(fig_geral, use_container_width=True)

    vol_canal = _contar_volume(base_vol, [col_canal, coluna_periodo])
    estilo_canal = _calcular_estilo_texto_volumetria(vol_canal, col_canal, 'Volume', agrupado=True)
    fig_canal = px.bar(vol_canal, x=col_canal, y='Volume', color=coluna_periodo, barmode='group', text='Volume', title=titulo_canal, category_orders=category_orders)
    fig_canal = _formatar_figura_volumetria(
        fig_canal,
        vol_canal,
        col_canal,
        eixo_x_titulo='Canal de Atuação',
        altura=(650 if not modo_mobile else 720),
        rotacionar_x=True,
        legenda_titulo=legenda_periodo,
        agrupado=True,
        estilo_texto=estilo_canal
    )
    st.plotly_chart(fig_canal, use_container_width=True)
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
        fig_bar_cd.update_traces(textposition='inside', insidetextanchor='end')
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
        fig_bar_emp.update_traces(textposition='inside', insidetextanchor='end')
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
        fig_bar_canal.update_traces(textposition='inside', insidetextanchor='end')
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
