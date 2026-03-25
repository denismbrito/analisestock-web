"""
AnáliseStock — Streamlit App
Página web responsiva para análise de Ações e FIIs da B3.
"""

import streamlit as st
import pandas as pd
import numpy as np
import math
import time
import io
import requests
from bs4 import BeautifulSoup
import re

# ─── Configuração da página ──────────────────────────────────────────────────
st.set_page_config(
    page_title="AnáliseStock",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── CSS customizado ─────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display&family=DM+Sans:wght@400;500;600&display=swap');

html, body, [class*="css"] {
    font-family: 'DM Sans', sans-serif;
}

/* Sidebar */
[data-testid="stSidebar"] {
    background: #0f1923;
}
[data-testid="stSidebar"] * {
    color: #e2e8f0 !important;
}
[data-testid="stSidebar"] .stMarkdown h2 {
    font-family: 'DM Serif Display', serif;
    color: #f0c040 !important;
    font-size: 1.4rem;
    border-bottom: 1px solid #2d3748;
    padding-bottom: 0.5rem;
    margin-bottom: 1rem;
}

/* Header principal */
.main-header {
    background: linear-gradient(135deg, #0f1923 0%, #1a2d40 100%);
    color: white;
    padding: 2rem 2.5rem;
    border-radius: 12px;
    margin-bottom: 1.5rem;
    border-left: 4px solid #f0c040;
}
.main-header h1 {
    font-family: 'DM Serif Display', serif;
    font-size: 2.2rem;
    margin: 0;
    color: #f0c040;
}
.main-header p {
    margin: 0.3rem 0 0;
    color: #94a3b8;
    font-size: 0.95rem;
}

/* Cards de métricas */
.metric-card {
    background: white;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    padding: 1rem 1.2rem;
    text-align: center;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06);
}
.metric-card .value {
    font-size: 1.8rem;
    font-weight: 600;
    color: #0f1923;
    line-height: 1.2;
}
.metric-card .label {
    font-size: 0.78rem;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-top: 0.2rem;
}

/* Score badge */
.score-badge {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 20px;
    font-weight: 600;
    font-size: 0.85rem;
}
.score-5 { background: #166534; color: #dcfce7; }
.score-4 { background: #14532d; color: #bbf7d0; }
.score-3 { background: #854d0e; color: #fef9c3; }
.score-2 { background: #7c2d12; color: #ffedd5; }
.score-1 { background: #991b1b; color: #fee2e2; }
.score-0 { background: #374151; color: #f3f4f6; }

/* Tabs */
.stTabs [data-baseweb="tab-list"] {
    gap: 4px;
    background: #f8fafc;
    border-radius: 8px;
    padding: 4px;
}
.stTabs [data-baseweb="tab"] {
    border-radius: 6px;
    font-weight: 500;
    font-size: 0.9rem;
}
.stTabs [aria-selected="true"] {
    background: white !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
}

/* Botão de análise */
.stButton > button {
    background: #f0c040 !important;
    color: #0f1923 !important;
    font-weight: 600 !important;
    border: none !important;
    border-radius: 8px !important;
    padding: 0.6rem 2rem !important;
    font-size: 1rem !important;
    width: 100%;
    transition: opacity 0.2s;
}
.stButton > button:hover {
    opacity: 0.88;
}

/* Dataframe */
[data-testid="stDataFrame"] {
    border-radius: 8px;
    overflow: hidden;
}

/* Aviso de score */
.score-legend {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 0.8rem 1rem;
    font-size: 0.82rem;
    color: #475569;
    margin-top: 1rem;
}

/* Status indicator */
.status-ok { color: #16a34a; font-weight: 500; }
.status-warn { color: #d97706; font-weight: 500; }
</style>
""", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════════════
#  EXTRATORES (adaptados do código original)
# ════════════════════════════════════════════════════════════════════════════

HEADERS = {
    'User-Agent': ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                   'AppleWebKit/537.36 (KHTML, like Gecko) '
                   'Chrome/120.0.0.0 Safari/537.36')
}


def _clean_float(value_str: str) -> float:
    """Limpa e converte string numérica BR para float."""
    if not value_str or value_str.strip() == '-':
        return 0.0
    cleaned = value_str.strip().replace('R$', '').replace('%', '').strip()
    if ',' in cleaned:
        cleaned = cleaned.replace('.', '').replace(',', '.')
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def _extract_by_datakey(soup, data_key: str) -> float:
    """Extrai indicador de ação via atributo data-key."""
    btn = soup.find('button', {'data-key': data_key})
    if btn:
        container = btn.find_parent('div')
        block = container.find_parent('div') if container else None
        if block:
            tag = block.find('strong', class_='value')
            if tag:
                return _clean_float(tag.text)
    raise AttributeError(f"data-key '{data_key}' não encontrado")


def extrair_fii(ticker: str) -> dict | None:
    """Extrai dados de um FII do StatusInvest."""
    url = f"https://statusinvest.com.br/fundos-imobiliarios/{ticker.lower()}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=12)
        r.raise_for_status()
        soup = BeautifulSoup(r.content, 'html.parser')

        val_tag = soup.find('div', title='Valor atual do ativo')
        if not val_tag:
            raise AttributeError("Valor atual não encontrado")
        valor_atual = _clean_float(val_tag.find('strong', class_='value').text)

        dy_tag = soup.find('div', title='Dividend Yield com base nos últimos 12 meses')
        dy_str = dy_tag.find('strong', class_='value').text if dy_tag else '-'
        dy = _clean_float(dy_str) / 100 if dy_str.strip() != '-' else 0.0

        appr_tag = soup.find('div', title=re.compile(r'Valorização no preço do ativo com base nos últimos 12 meses'))
        appr_str = appr_tag.find('strong', class_='value').text if appr_tag else '-'
        appr_12m = _clean_float(appr_str) / 100 if appr_str.strip() != '-' else 0.0

        mo_tag = soup.find('div', title='Valorização no preço do ativo com base no mês atual')
        mo_str = mo_tag.find('b', class_='v-align-middle').text if mo_tag else '0'
        appr_mo = _clean_float(mo_str)

        pvp_tag = soup.find('h3', class_='title m-0', string='P/VP')
        pvp = 0.0
        if pvp_tag:
            pvp_val = pvp_tag.find_next_sibling('strong', class_='value')
            if pvp_val:
                pvp = _clean_float(pvp_val.text)

        v12 = valor_atual / (1 + appr_12m) if (1 + appr_12m) != 0 else None

        return {
            'Ticker': ticker.upper(),
            'Valor Atual': valor_atual,
            'Valor 12m Atrás': v12,
            'DY (%)': dy * 100,
            'Valorização 12m (%)': appr_12m * 100,
            'Valorização Mês (%)': appr_mo,
            'P/VP': pvp,
        }
    except Exception as e:
        return {'Ticker': ticker.upper(), '_erro': str(e)}


def extrair_acao(ticker: str) -> dict | None:
    """Extrai dados de uma ação do StatusInvest."""
    url = f"https://statusinvest.com.br/acoes/{ticker.lower()}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.content, 'html.parser')

        val_tag = soup.find('div', title='Valor atual do ativo')
        if not val_tag:
            raise AttributeError("Valor atual não encontrado")
        valor_atual = _clean_float(val_tag.find('strong', class_='value').text)

        dy_h3 = soup.find('h3', string='Dividend Yield')
        dy = 0.0
        if dy_h3:
            dy_val = dy_h3.find_parent('div')
            dy_tag2 = dy_val.find_next_sibling('strong', class_='value') if dy_val else None
            if not dy_tag2 and dy_val:
                dy_tag2 = dy_val.find('strong', class_='value')
            dy = _clean_float(dy_tag2.text) / 100 if dy_tag2 else 0.0

        appr_tag = soup.find('div', title=re.compile(r'Valorização no preço do ativo'))
        appr_12m_raw = _clean_float(appr_tag.find('strong', class_='value').text) / 100 if appr_tag else 0.0

        mo_tag = soup.find('div', title='Valorização no preço do ativo com base no mês atual')
        appr_mo = 0.0
        if mo_tag:
            b = mo_tag.find('b', class_='v-align-middle')
            appr_mo = _clean_float(b.text) if b else 0.0

        pvp  = _extract_by_datakey(soup, 'p_vp')
        peg  = _extract_by_datakey(soup, 'peg_Ratio')
        dl_e = _extract_by_datakey(soup, 'dividaliquida_ebitda')

        v12 = valor_atual / (1 + appr_12m_raw) if (1 + appr_12m_raw) != 0 else None

        return {
            'Ticker': ticker.upper(),
            'Valor Atual': valor_atual,
            'Valor 12m Atrás': v12,
            'DY (%)': dy * 100,
            'Valorização 12m (%)': appr_12m_raw * 100,
            'Valorização Mês (%)': appr_mo,
            'P/VP': pvp,
            'PEG Ratio': peg,
            'DL/EBITDA': dl_e,
        }
    except Exception as e:
        return {'Ticker': ticker.upper(), '_erro': str(e)}


# ════════════════════════════════════════════════════════════════════════════
#  SCORES
# ════════════════════════════════════════════════════════════════════════════

def calcular_scores_fiis(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df['ScoreEvolucao']    = (df['Valor Atual'] < df['Valor 12m Atrás']).astype(int)
    df['ScorePreco']       = ((df['P/VP'] >= 0.5) & (df['P/VP'] <= 0.95)).astype(int)
    df['ScoreVariacao12m'] = ((df['Valorização 12m (%)'] >= 1) & (df['Valorização 12m (%)'] <= 10)).astype(int)
    df['SomaScores']       = df['ScoreEvolucao'] + df['ScorePreco'] + df['ScoreVariacao12m']
    return df


def calcular_scores_acoes(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df['ScoreEvolucao']    = np.where(df['Valor Atual'] < df['Valor 12m Atrás'], 1, 0)
    df['ScorePreco']       = np.where((df['P/VP'] >= 0.5) & (df['P/VP'] <= 0.95), 1, 0)
    df['ScoreVariacao12m'] = np.where((df['Valorização 12m (%)'] >= 1) & (df['Valorização 12m (%)'] <= 10), 1, 0)
    df['ScorePeg']         = np.where((df['PEG Ratio'] >= 0.4) & (df['PEG Ratio'] <= 1.0), 1, 0)
    df['ScoreAlavancagem'] = np.where((df['DL/EBITDA'] >= 1.0) & (df['DL/EBITDA'] <= 3.0), 1, 0)
    df['SomaScore']        = df[['ScoreEvolucao','ScorePreco','ScoreVariacao12m','ScorePeg','ScoreAlavancagem']].sum(axis=1)
    return df


# ════════════════════════════════════════════════════════════════════════════
#  MAGIC NUMBER
# ════════════════════════════════════════════════════════════════════════════

def calcular_magic_number(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df['Valor Atual']  = pd.to_numeric(df['Valor Atual'], errors='coerce')
    df['DY (%)']       = pd.to_numeric(df['DY (%)'], errors='coerce')
    df['Qtd Atual']    = pd.to_numeric(df.get('Qtd Atual', 0), errors='coerce').fillna(0)

    df['Rend. Mensal'] = (df['Valor Atual'] * (df['DY (%)'] / 100)) / 12
    mask = (df['Rend. Mensal'].notna()) & (df['Rend. Mensal'] > 0)
    df['Qtd Mágica'] = np.nan
    df.loc[mask, 'Qtd Mágica'] = (
        df.loc[mask, 'Valor Atual'] / df.loc[mask, 'Rend. Mensal']
    ).apply(lambda x: math.ceil(x) if not pd.isna(x) else np.nan)

    mask2 = (df['Qtd Mágica'].notna()) & (df['Qtd Mágica'] > 0)
    df['Nível Atingimento'] = np.nan
    df.loc[mask2, 'Nível Atingimento'] = (
        df.loc[mask2, 'Qtd Atual'] / df.loc[mask2, 'Qtd Mágica']
    ).apply(lambda x: math.floor(x) if not pd.isna(x) else np.nan).astype('Int64')

    return df


# ════════════════════════════════════════════════════════════════════════════
#  HELPERS DE UI
# ════════════════════════════════════════════════════════════════════════════

def score_color(val, max_score):
    """Retorna classe CSS de cor para score."""
    pct = val / max_score if max_score > 0 else 0
    if pct >= 0.8: return 'score-5'
    if pct >= 0.6: return 'score-4'
    if pct >= 0.4: return 'score-3'
    if pct >= 0.2: return 'score-2'
    if pct >  0.0: return 'score-1'
    return 'score-0'


def render_score_col(df, col, max_score):
    """Cria coluna de badges HTML para scores."""
    def badge(val):
        try:
            v = int(val)
            cls = score_color(v, max_score)
            return f'<span class="score-badge {cls}">{v}/{max_score}</span>'
        except:
            return ''
    return df[col].apply(badge)


def fmt_pct(v):
    try: return f"{float(v):+.2f}%"
    except: return str(v)

def fmt_brl(v):
    try: return f"R$ {float(v):,.2f}".replace(',','X').replace('.',',').replace('X','.')
    except: return str(v)

def fmt_float2(v):
    try: return f"{float(v):.2f}"
    except: return str(v)


def df_para_excel(df: pd.DataFrame) -> bytes:
    """Serializa DataFrame para bytes de XLSX."""
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine='openpyxl') as w:
        df.to_excel(w, index=False)
    return buf.getvalue()


def parse_tickers(texto: str) -> list[str]:
    """Extrai lista de tickers de um texto (um por linha ou separados por vírgula)."""
    tickers = []
    for linha in texto.replace(',', '\n').splitlines():
        t = linha.strip().upper()
        if t:
            tickers.append(t)
    return tickers


def mesclar_posicao(df_dados: pd.DataFrame, df_posicao: pd.DataFrame, coluna_sheet: str) -> pd.DataFrame:
    """Faz merge de quantidade da posição no DataFrame de dados."""
    try:
        df_pos = df_posicao[['Código de Negociação', 'Quantidade']].copy()
        df_pos.rename(columns={'Código de Negociação': 'Ticker', 'Quantidade': 'Qtd Atual'}, inplace=True)
        df_merged = pd.merge(df_dados, df_pos, on='Ticker', how='left')
        df_merged['Qtd Atual'] = df_merged['Qtd Atual'].fillna(0)
        return df_merged
    except Exception as e:
        st.warning(f"Não foi possível mesclar posição ({coluna_sheet}): {e}")
        df_dados['Qtd Atual'] = 0
        return df_dados


# ════════════════════════════════════════════════════════════════════════════
#  SIDEBAR
# ════════════════════════════════════════════════════════════════════════════

with st.sidebar:
    st.markdown("## 📊 AnáliseStock")
    st.markdown("---")

    st.markdown("### 🎯 Tickers de Ações")
    tickers_input = st.text_area(
        "Um por linha (ou separados por vírgula)",
        value="AURE3\nBBAS3\nBBDC4\nEGIE3\nITUB4\nVALE3",
        height=160,
        key="tickers_input",
        label_visibility="collapsed",
    )

    st.markdown("### 🏢 FIIs")
    fiis_input = st.text_area(
        "Um por linha",
        value="CPTS11\nGGRC11\nKNRI11\nMXRF11\nXPLG11\nXPML11",
        height=140,
        key="fiis_input",
        label_visibility="collapsed",
    )

    st.markdown("### 📂 Posição da Carteira")
    st.caption("Arquivo .xlsx exportado da B3 (opcional)")
    posicao_file = st.file_uploader(
        "posicao.xlsx",
        type=["xlsx"],
        label_visibility="collapsed",
    )

    st.markdown("---")
    rodar = st.button("🚀 Rodar Análise", use_container_width=True)

    st.markdown("---")
    st.caption("Dados: statusinvest.com.br")
    st.caption("v4 · Streamlit Cloud")


# ════════════════════════════════════════════════════════════════════════════
#  HEADER
# ════════════════════════════════════════════════════════════════════════════

st.markdown("""
<div class="main-header">
    <h1>📈 AnáliseStock</h1>
    <p>Análise quantitativa de Ações e FIIs da B3 · Scores, Magic Number e posição da carteira</p>
</div>
""", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════════════
#  ESTADO DA SESSÃO
# ════════════════════════════════════════════════════════════════════════════

if 'df_acoes' not in st.session_state:
    st.session_state.df_acoes = None
if 'df_fiis' not in st.session_state:
    st.session_state.df_fiis = None
if 'erros_acoes' not in st.session_state:
    st.session_state.erros_acoes = []
if 'erros_fiis' not in st.session_state:
    st.session_state.erros_fiis = []


# ════════════════════════════════════════════════════════════════════════════
#  EXECUÇÃO DA ANÁLISE
# ════════════════════════════════════════════════════════════════════════════

if rodar:
    tickers = parse_tickers(tickers_input)
    fiis    = parse_tickers(fiis_input)

    if not tickers and not fiis:
        st.error("⚠️ Informe ao menos um ticker ou FII antes de rodar a análise.")
        st.stop()

    # Carrega posição se enviada
    df_pos_acoes = None
    df_pos_fiis  = None
    if posicao_file:
        try:
            df_pos_acoes = pd.read_excel(posicao_file, sheet_name='Acoes')
            posicao_file.seek(0)
            df_pos_fiis  = pd.read_excel(posicao_file, sheet_name='Fundo de Investimento')
        except Exception as e:
            st.warning(f"Não foi possível ler posicao.xlsx: {e}")

    # ── Extração Ações ────────────────────────────────────────────────────
    if tickers:
        st.markdown("### ⚙️ Extraindo dados das Ações...")
        prog_a = st.progress(0, text="Iniciando...")
        dados_acoes = []
        erros_a = []
        for i, t in enumerate(tickers):
            prog_a.progress((i + 1) / len(tickers), text=f"Buscando {t}…")
            resultado = extrair_acao(t)
            if resultado:
                if '_erro' in resultado:
                    erros_a.append((t, resultado['_erro']))
                else:
                    dados_acoes.append(resultado)
            time.sleep(0.4)  # cortesia ao servidor
        prog_a.empty()

        if dados_acoes:
            df_a = pd.DataFrame(dados_acoes)
            df_a = calcular_scores_acoes(df_a)
            if df_pos_acoes is not None:
                df_a = mesclar_posicao(df_a, df_pos_acoes, 'Acoes')
            else:
                df_a['Qtd Atual'] = 0
            df_a = calcular_magic_number(df_a)
            st.session_state.df_acoes   = df_a
            st.session_state.erros_acoes = erros_a

    # ── Extração FIIs ────────────────────────────────────────────────────
    if fiis:
        st.markdown("### ⚙️ Extraindo dados dos FIIs...")
        prog_f = st.progress(0, text="Iniciando...")
        dados_fiis = []
        erros_f = []
        for i, t in enumerate(fiis):
            prog_f.progress((i + 1) / len(fiis), text=f"Buscando {t}…")
            resultado = extrair_fii(t)
            if resultado:
                if '_erro' in resultado:
                    erros_f.append((t, resultado['_erro']))
                else:
                    dados_fiis.append(resultado)
            time.sleep(0.4)
        prog_f.empty()

        if dados_fiis:
            df_f = pd.DataFrame(dados_fiis)
            df_f = calcular_scores_fiis(df_f)
            if df_pos_fiis is not None:
                df_f = mesclar_posicao(df_f, df_pos_fiis, 'Fundo de Investimento')
            else:
                df_f['Qtd Atual'] = 0
            df_f = calcular_magic_number(df_f)
            st.session_state.df_fiis   = df_f
            st.session_state.erros_fiis = erros_f

    st.success("✅ Análise concluída! Veja os resultados abaixo.")
    st.rerun()


# ════════════════════════════════════════════════════════════════════════════
#  EXIBIÇÃO DOS RESULTADOS
# ════════════════════════════════════════════════════════════════════════════

df_a = st.session_state.df_acoes
df_f = st.session_state.df_fiis

if df_a is None and df_f is None:
    # Estado inicial — instrução ao usuário
    st.info(
        "👈 **Como usar:** Insira os tickers na barra lateral, faça upload da sua "
        "posição (opcional) e clique em **Rodar Análise**."
    )

    with st.expander("ℹ️ Sobre os scores e o Magic Number"):
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("""
**Scores de Ações (0–5)**
| Score | Critério |
|-------|----------|
| ScoreEvolucao | Preço atual < preço há 12m |
| ScorePreco | 0,50 ≤ P/VP ≤ 0,95 |
| ScoreVariacao12m | 1% ≤ Valorização 12m ≤ 10% |
| ScorePeg | 0,40 ≤ PEG Ratio ≤ 1,00 |
| ScoreAlavancagem | 1,0 ≤ DL/EBITDA ≤ 3,0 |
""")
        with col2:
            st.markdown("""
**Scores de FIIs (0–3)**
| Score | Critério |
|-------|----------|
| ScoreEvolucao | Preço atual < preço há 12m |
| ScorePreco | 0,50 ≤ P/VP ≤ 0,95 |
| ScoreVariacao12m | 1% ≤ Valorização 12m ≤ 10% |

**Magic Number**
> Quantidade de cotas necessária para que os dividendos mensais cubram o custo de 1 cota.
""")
    st.stop()


# ── Resumo geral ─────────────────────────────────────────────────────────
total_acoes = len(df_a) if df_a is not None else 0
total_fiis  = len(df_f) if df_f is not None else 0
erros_total = len(st.session_state.erros_acoes) + len(st.session_state.erros_fiis)

col_m1, col_m2, col_m3, col_m4 = st.columns(4)
with col_m1:
    st.metric("Ações analisadas", total_acoes)
with col_m2:
    best_a = int(df_a['SomaScore'].max()) if df_a is not None and len(df_a) > 0 else 0
    st.metric("Melhor score (Ações)", f"{best_a}/5")
with col_m3:
    st.metric("FIIs analisados", total_fiis)
with col_m4:
    best_f = int(df_f['SomaScores'].max()) if df_f is not None and len(df_f) > 0 else 0
    st.metric("Melhor score (FIIs)", f"{best_f}/3")


# ── Erros ────────────────────────────────────────────────────────────────
all_erros = st.session_state.erros_acoes + st.session_state.erros_fiis
if all_erros:
    with st.expander(f"⚠️ {len(all_erros)} ticker(s) com falha na extração"):
        for t, msg in all_erros:
            st.caption(f"**{t}** — {msg}")


# ── Abas principais ──────────────────────────────────────────────────────
tab_a, tab_f, tab_ranking = st.tabs(["📋 Ações", "🏢 FIIs", "🏆 Ranking Geral"])


# ───────────────────────────── ABA AÇÕES ─────────────────────────────────
with tab_a:
    if df_a is None or len(df_a) == 0:
        st.info("Nenhum dado de ação disponível.")
    else:
        st.markdown(f"**{len(df_a)} ações analisadas**")

        # Filtros
        c1, c2, c3 = st.columns([2, 1, 1])
        with c1:
            busca_a = st.text_input("🔍 Filtrar por ticker", key="busca_a", placeholder="ex: VALE3")
        with c2:
            min_score_a = st.selectbox("Score mínimo", [0,1,2,3,4,5], index=0, key="minscore_a")
        with c3:
            ordenar_a = st.selectbox("Ordenar por", ["SomaScore ↓", "DY (%) ↓", "Valorização 12m (%) ↓", "Ticker ↑"], key="ord_a")

        df_a_view = df_a.copy()
        if busca_a:
            df_a_view = df_a_view[df_a_view['Ticker'].str.contains(busca_a.upper())]
        df_a_view = df_a_view[df_a_view['SomaScore'] >= min_score_a]

        ordem_map = {
            "SomaScore ↓": ('SomaScore', False),
            "DY (%) ↓": ('DY (%)', False),
            "Valorização 12m (%) ↓": ('Valorização 12m (%)', False),
            "Ticker ↑": ('Ticker', True),
        }
        col_ord, asc = ordem_map[ordenar_a]
        df_a_view = df_a_view.sort_values(col_ord, ascending=asc)

        # Colunas de exibição
        cols_show = ['Ticker','Valor Atual','DY (%)','Valorização 12m (%)','P/VP',
                     'PEG Ratio','DL/EBITDA','Qtd Atual','Rend. Mensal',
                     'Qtd Mágica','Nível Atingimento','SomaScore']
        cols_show = [c for c in cols_show if c in df_a_view.columns]

        st.dataframe(
            df_a_view[cols_show].style.format({
                'Valor Atual': 'R$ {:.2f}',
                'DY (%)': '{:.2f}%',
                'Valorização 12m (%)': '{:+.2f}%',
                'P/VP': '{:.2f}',
                'PEG Ratio': '{:.2f}',
                'DL/EBITDA': '{:.2f}',
                'Rend. Mensal': 'R$ {:.4f}',
                'Qtd Mágica': '{:.0f}',
            }).background_gradient(subset=['SomaScore'], cmap='RdYlGn', vmin=0, vmax=5),
            use_container_width=True,
            height=420,
        )

        st.markdown("""
<div class="score-legend">
🟢 <b>5</b> = excelente &nbsp;|&nbsp; 🟡 <b>3</b> = moderado &nbsp;|&nbsp;
🔴 <b>0–1</b> = não atende critérios &nbsp;|&nbsp;
<b>Nível Atingimento</b>: quantas vezes os dividendos mensais cobrem 1 cota
</div>""", unsafe_allow_html=True)

        # Download
        st.download_button(
            "⬇️ Baixar Ações (.xlsx)",
            data=df_para_excel(df_a_view[cols_show]),
            file_name="analise_acoes.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )


# ───────────────────────────── ABA FIIs ──────────────────────────────────
with tab_f:
    if df_f is None or len(df_f) == 0:
        st.info("Nenhum dado de FII disponível.")
    else:
        st.markdown(f"**{len(df_f)} FIIs analisados**")

        c1, c2, c3 = st.columns([2, 1, 1])
        with c1:
            busca_f = st.text_input("🔍 Filtrar por ticker", key="busca_f", placeholder="ex: KNRI11")
        with c2:
            min_score_f = st.selectbox("Score mínimo", [0,1,2,3], index=0, key="minscore_f")
        with c3:
            ordenar_f = st.selectbox("Ordenar por", ["SomaScores ↓", "DY (%) ↓", "P/VP ↑", "Ticker ↑"], key="ord_f")

        df_f_view = df_f.copy()
        if busca_f:
            df_f_view = df_f_view[df_f_view['Ticker'].str.contains(busca_f.upper())]
        df_f_view = df_f_view[df_f_view['SomaScores'] >= min_score_f]

        ordem_map_f = {
            "SomaScores ↓": ('SomaScores', False),
            "DY (%) ↓": ('DY (%)', False),
            "P/VP ↑": ('P/VP', True),
            "Ticker ↑": ('Ticker', True),
        }
        col_ord_f, asc_f = ordem_map_f[ordenar_f]
        df_f_view = df_f_view.sort_values(col_ord_f, ascending=asc_f)

        cols_show_f = ['Ticker','Valor Atual','DY (%)','Valorização 12m (%)','P/VP',
                       'Qtd Atual','Rend. Mensal','Qtd Mágica','Nível Atingimento','SomaScores']
        cols_show_f = [c for c in cols_show_f if c in df_f_view.columns]

        st.dataframe(
            df_f_view[cols_show_f].style.format({
                'Valor Atual': 'R$ {:.2f}',
                'DY (%)': '{:.2f}%',
                'Valorização 12m (%)': '{:+.2f}%',
                'P/VP': '{:.2f}',
                'Rend. Mensal': 'R$ {:.4f}',
                'Qtd Mágica': '{:.0f}',
            }).background_gradient(subset=['SomaScores'], cmap='RdYlGn', vmin=0, vmax=3),
            use_container_width=True,
            height=420,
        )

        st.download_button(
            "⬇️ Baixar FIIs (.xlsx)",
            data=df_para_excel(df_f_view[cols_show_f]),
            file_name="analise_fiis.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )


# ───────────────────────────── ABA RANKING ───────────────────────────────
with tab_ranking:
    st.markdown("### 🏆 Top ativos por score")

    col_ra, col_rf = st.columns(2)

    with col_ra:
        st.markdown("#### Ações")
        if df_a is not None and len(df_a) > 0:
            top_a = df_a.nlargest(10, 'SomaScore')[['Ticker','SomaScore','DY (%)','P/VP']].reset_index(drop=True)
            top_a.index += 1
            st.dataframe(
                top_a.style.format({'DY (%)': '{:.2f}%', 'P/VP': '{:.2f}'})
                     .background_gradient(subset=['SomaScore'], cmap='RdYlGn', vmin=0, vmax=5),
                use_container_width=True,
            )
        else:
            st.info("Sem dados de ações.")

    with col_rf:
        st.markdown("#### FIIs")
        if df_f is not None and len(df_f) > 0:
            top_f = df_f.nlargest(10, 'SomaScores')[['Ticker','SomaScores','DY (%)','P/VP']].reset_index(drop=True)
            top_f.index += 1
            st.dataframe(
                top_f.style.format({'DY (%)': '{:.2f}%', 'P/VP': '{:.2f}'})
                     .background_gradient(subset=['SomaScores'], cmap='RdYlGn', vmin=0, vmax=3),
                use_container_width=True,
            )
        else:
            st.info("Sem dados de FIIs.")

    # Gráfico de distribuição de scores
    if df_a is not None and len(df_a) > 0:
        st.markdown("#### Distribuição de scores — Ações")
        dist = df_a['SomaScore'].value_counts().sort_index()
        st.bar_chart(dist, color="#f0c040")

    if df_f is not None and len(df_f) > 0:
        st.markdown("#### Distribuição de scores — FIIs")
        dist_f = df_f['SomaScores'].value_counts().sort_index()
        st.bar_chart(dist_f, color="#3b82f6")
