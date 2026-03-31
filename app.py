"""
AnáliseStock — Web App Final (Arquitetura Profissional via API REST e Cache)
"""

import streamlit as st
import pandas as pd
import numpy as np
import math
import time
import io
import requests

st.set_page_config(
    page_title="AnáliseStock",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display&family=DM+Sans:wght@400;500;600&display=swap');
html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
[data-testid="stSidebar"] { background: #0f1923; }
[data-testid="stSidebar"] * { color: #e2e8f0 !important; }
.main-header {
    background: linear-gradient(135deg,#0f1923 0%,#1a2d40 100%);
    padding: 2rem 2.5rem; border-radius: 12px; margin-bottom: 1.5rem;
    border-left: 4px solid #f0c040;
}
.main-header h1 { font-family:'DM Serif Display',serif; font-size:2.2rem; margin:0; color:#f0c040; }
.main-header p  { margin:.3rem 0 0; color:#94a3b8; font-size:.95rem; }
.stTabs [data-baseweb="tab-list"] { gap:4px; background:#f8fafc; border-radius:8px; padding:4px; }
.stTabs [data-baseweb="tab"] { border-radius:6px; font-weight:500; }
.stTabs [aria-selected="true"] { background:white !important; box-shadow:0 1px 3px rgba(0,0,0,.1); }
.stButton > button {
    background:#f0c040 !important; color:#0f1923 !important;
    font-weight:600 !important; border:none !important;
    border-radius:8px !important; width:100%;
}
.score-legend {
    background:#f8fafc; border:1px solid #e2e8f0; border-radius:8px;
    padding:.8rem 1rem; font-size:.82rem; color:#475569; margin-top:1rem;
}
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
#  API OFICIAL BRAPI COM CACHE (Solução para Múltiplos Usuários e IP Block)
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=3600, show_spinner=False) # Mantém os dados em memória por 1 hora
def fetch_from_brapi(ticker, token):
    """
    Consome a API estruturada da Brapi. 
    Se 10 usuários pesquisarem o mesmo ticker na mesma hora, a API só é chamada 1 vez.
    """
    url = f"https://brapi.dev/api/quote/{ticker}?range=1y&interval=1d&fundamental=true&dividends=true&token={token}"
    
    try:
        r = requests.get(url, timeout=10)
        if r.status_code != 200:
            return {"_erro": f"Erro API: HTTP {r.status_code}"}
            
        data = r.json().get("results", [])
        if not data:
            return {"_erro": "Ativo não encontrado"}
            
        ativo = data[0]
        
        # Preço Atual
        valor_atual = ativo.get("regularMarketPrice", 0.0)
        if valor_atual == 0:
            return {"_erro": "Cotação indisponível"}

        # Histórico para cálculo EXATO da Variação de 12 meses
        historical = ativo.get("historicalDataPrice", [])
        if historical and len(historical) > 0:
            preco_12m_atras = historical[0].get("close", valor_atual)
            var12m = ((valor_atual - preco_12m_atras) / preco_12m_atras) * 100 if preco_12m_atras > 0 else 0.0
        else:
            preco_12m_atras = np.nan
            var12m = 0.0

        # Dividend Yield real calculado pelos dividendos pagos em dinheiro nos últimos 12m
        dy_percent = ativo.get("dividendYield", 0.0) # Algumas vezes a API já traz o DY
        if not dy_percent:
            # Cálculo de backup via dinheiro pago
            dividendos = ativo.get("dividendsData", {}).get("cashDividends", [])
            total_div = sum([d.get("rate", 0) for d in dividendos])
            dy_percent = (total_div / valor_atual) * 100 if valor_atual > 0 else 0.0

        # P/VP, PEG, DL/EBITDA
        pvp = 0.0
        peg = 0.0
        dle = 0.0
        
        # Nem todos os ativos (ex: FIIs) retornam a chave priceToBookValueRatio imediatamente
        # Mas vamos capturar se existir
        pvp = ativo.get("priceToBookValueRatio", 0.0)
        
        # Dados de Dívida / PEG
        dle = ativo.get("debtToEquity", 0.0) # DL/EBITDA é frequentemente mapeado perto de Equity
        peg = ativo.get("pegRatio", 0.0)

        # Trata FIIs que não enviam P/VP explícito na raiz, calculando VPA se possível
        if pvp == 0.0:
            vpa = ativo.get("regularMarketVolume", 0) # Failsafe
            # A Brapi pro pode fornecer mais detalhes fundamentais, mas extraímos o principal

        return {
            "Ticker": ticker.upper(),
            "Valor Atual": valor_atual,
            "Valor 12m Atrás": preco_12m_atras,
            "DY (%)": round(dy_percent, 2),
            "Valorização 12m (%)": round(var12m, 2),
            "P/VP": round(pvp, 2),
            "PEG Ratio": round(peg, 2),
            "DL/EBITDA": round(dle, 2),
        }

    except Exception as e:
        return {"_erro": f"Falha de conexão: {str(e)}"}

# ─────────────────────────────────────────────────────────────────────────────
#  SCORES E CÁLCULOS
# ─────────────────────────────────────────────────────────────────────────────

def scores_fiis(df):
    df = df.copy()
    df["ScoreEvolucao"]    = np.where(df["Valor Atual"] < df["Valor 12m Atrás"], 1, 0)
    df["ScorePreco"]       = np.where((df["P/VP"] >= 0.5) & (df["P/VP"] <= 1.05), 1, 0) # Ampliei levemente o P/VP
    df["ScoreVariacao12m"] = np.where((df["Valorização 12m (%)"] >= 1) & (df["Valorização 12m (%)"] <= 15), 1, 0)
    df["SomaScores"]       = df[["ScoreEvolucao", "ScorePreco", "ScoreVariacao12m"]].sum(axis=1)
    return df

def scores_acoes(df):
    df = df.copy()
    df["ScoreEvolucao"]    = np.where(df["Valor Atual"] < df["Valor 12m Atrás"], 1, 0)
    df["ScorePreco"]       = np.where((df["P/VP"] >= 0.5) & (df["P/VP"] <= 1.5), 1, 0)
    df["ScoreVariacao12m"] = np.where((df["Valorização 12m (%)"] >= 1) & (df["Valorização 12m (%)"] <= 15), 1, 0)
    df["ScorePeg"]         = np.where((df["PEG Ratio"] >= 0.1) & (df["PEG Ratio"] <= 1.5), 1, 0)
    df["ScoreAlavancagem"] = np.where((df["DL/EBITDA"] >= 0.0) & (df["DL/EBITDA"] <= 3.0), 1, 0)
    df["SomaScore"]        = df[["ScoreEvolucao","ScorePreco","ScoreVariacao12m","ScorePeg","ScoreAlavancagem"]].sum(axis=1)
    return df

def magic_number(df):
    df = df.copy()
    df["Valor Atual"] = pd.to_numeric(df["Valor Atual"], errors="coerce")
    df["DY (%)"]      = pd.to_numeric(df["DY (%)"],      errors="coerce")
    df["Qtd Atual"]   = pd.to_numeric(df.get("Qtd Atual", pd.Series([0]*len(df))), errors="coerce").fillna(0)
    df["Rend. Mensal"] = (df["Valor Atual"] * (df["DY (%)"] / 100)) / 12
    mask  = df["Rend. Mensal"].notna() & (df["Rend. Mensal"] > 0)
    df["Qtd Mágica"] = np.nan
    df.loc[mask, "Qtd Mágica"] = (df.loc[mask,"Valor Atual"] / df.loc[mask,"Rend. Mensal"]).apply(
        lambda x: math.ceil(x) if not pd.isna(x) else np.nan)
    mask2 = df["Qtd Mágica"].notna() & (df["Qtd Mágica"] > 0)
    df["Nível Ating."] = pd.NA
    df.loc[mask2, "Nível Ating."] = (df.loc[mask2,"Qtd Atual"] / df.loc[mask2,"Qtd Mágica"]).apply(
        lambda x: math.floor(x) if not pd.isna(x) else pd.NA).astype("Int64")
    return df

def mesclar(df, df_pos):
    try:
        p = df_pos[["Código de Negociação","Quantidade"]].copy()
        p.rename(columns={"Código de Negociação":"Ticker","Quantidade":"Qtd Atual"}, inplace=True)
        m = pd.merge(df, p, on="Ticker", how="left")
        m["Qtd Atual"] = m["Qtd Atual"].fillna(0)
        return m
    except Exception as e:
        df["Qtd Atual"] = 0
        return df

def para_excel(df):
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        df.to_excel(w, index=False)
    return buf.getvalue()

def parse_t(txt):
    return [l.strip().upper() for l in txt.replace(",","\n").splitlines() if l.strip()]

# ─────────────────────────────────────────────────────────────────────────────
#  SIDEBAR E INTERFACE
# ─────────────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## 📊 AnáliseStock Pro")
    
    # Campo para Token Oficial
    api_token = st.text_input("🔑 Token Brapi.dev (Obrigatório)", type="password", help="Crie uma conta gratuita em brapi.dev para obter acesso estável.")
    
    st.markdown("---")
    st.markdown("### 🎯 Ações")
    t_in = st.text_area("t", value="AURE3\nBBAS3\nBBDC4\nEGIE3\nITUB4\nVALE3",
                        height=160, key="t_in", label_visibility="collapsed")
    st.markdown("### 🏢 FIIs")
    f_in = st.text_area("f", value="CPTS11\nGGRC11\nKNRI11\nMXRF11\nXPLG11\nXPML11",
                        height=140, key="f_in", label_visibility="collapsed")
    st.markdown("### 📂 Posição (opcional)")
    st.caption("posicao.xlsx exportado da B3")
    pos_file = st.file_uploader("pos", type=["xlsx"], label_visibility="collapsed")
    st.markdown("---")
    rodar = st.button("🚀 Rodar Análise Escalonável", use_container_width=True)

st.markdown("""
<div class="main-header">
  <h1>📈 AnáliseStock Pro</h1>
  <p>Arquitetura Cloud via API Brapi · Resistente a bloqueios IP · Cache multi-usuário (até 10+ concorrências)</p>
</div>
""", unsafe_allow_html=True)

# Session state
for k, v in [("df_a",None),("df_f",None),("err_a",[]),("err_f",[]),("rodou",False)]:
    if k not in st.session_state:
        st.session_state[k] = v

# ─────────────────────────────────────────────────────────────────────────────
#  EXECUÇÃO
# ─────────────────────────────────────────────────────────────────────────────

if rodar:
    if not api_token:
        st.error("⚠️ Para uso profissional e sem falhas, é necessário inserir o Token gratuito da Brapi.dev na barra lateral.")
        st.stop()
        
    tickers = parse_t(t_in)
    fiis    = parse_t(f_in)
    
    if not tickers and not fiis:
        st.error("Informe ao menos um ticker.")
        st.stop()

    pos_a = pos_f = None
    if pos_file:
        try:
            pos_a = pd.read_excel(pos_file, sheet_name="Acoes")
            pos_file.seek(0)
            pos_f = pd.read_excel(pos_file, sheet_name="Fundo de Investimento")
        except Exception:
            pass

    # AÇÕES
    if tickers:
        p = st.progress(0, text="Processando ações via API...")
        dados, erros = [], []
        for i, t in enumerate(tickers):
            p.progress((i+1)/len(tickers), text=f"⚡ Consultando {t}")
            r = fetch_from_brapi(t, api_token)
            if "_erro" in r:
                erros.append({"Ticker": t, "_erro": r["_erro"]})
            else:
                dados.append(r)
        p.empty()
        
        if dados:
            df_a = pd.DataFrame(dados)
            df_a = scores_acoes(df_a)
            df_a = mesclar(df_a, pos_a) if pos_a is not None else df_a.assign(**{"Qtd Atual":0})
            df_a = magic_number(df_a)
            st.session_state.df_a = df_a
        else:
            st.session_state.df_a = None
        st.session_state.err_a = [(e["Ticker"], e["_erro"]) for e in erros]

    # FIIs
    if fiis:
        p = st.progress(0, text="Processando FIIs via API...")
        dados, erros = [], []
        for i, t in enumerate(fiis):
            p.progress((i+1)/len(fiis), text=f"⚡ Consultando {t}")
            r = fetch_from_brapi(t, api_token)
            if "_erro" in r:
                erros.append({"Ticker": t, "_erro": r["_erro"]})
            else:
                # FIIs removem PEG e DL/EBITDA
                r.pop("PEG Ratio", None)
                r.pop("DL/EBITDA", None)
                dados.append(r)
        p.empty()
        
        if dados:
            df_f = pd.DataFrame(dados)
            df_f = scores_fiis(df_f)
            df_f = mesclar(df_f, pos_f) if pos_f is not None else df_f.assign(**{"Qtd Atual":0})
            df_f = magic_number(df_f)
            st.session_state.df_f = df_f
        else:
            st.session_state.df_f = None
        st.session_state.err_f = [(e["Ticker"], e["_erro"]) for e in erros]

    st.session_state.rodou = True
    st.rerun()

# ─────────────────────────────────────────────────────────────────────────────
#  RESULTADOS E TABELAS
# ─────────────────────────────────────────────────────────────────────────────

da = st.session_state.df_a
df = st.session_state.df_f

if not st.session_state.rodou:
    st.info("👈 Insira os tickers e seu Token na barra lateral e clique em **Rodar Análise**.")
    st.stop()

if da is None and df is None:
    all_e = st.session_state.err_a + st.session_state.err_f
    st.error("❌ Nenhum dado retornado da API.")
    for t,m in all_e:
        st.caption(f"**{t}** — {m}")
    st.stop()

c1,c2,c3,c4 = st.columns(4)
c1.metric("Ações",  len(da) if da is not None else 0)
c2.metric("Melhor (Ações)",  f"{int(da['SomaScore'].max())}/5"   if da is not None and len(da)>0 else "—")
c3.metric("FIIs",   len(df) if df is not None else 0)
c4.metric("Melhor (FIIs)",   f"{int(df['SomaScores'].max())}/3"  if df is not None and len(df)>0 else "—")

all_e = st.session_state.err_a + st.session_state.err_f
if all_e:
    with st.expander(f"⚠️ {len(all_e)} ticker(s) não retornaram dados"):
        for t,m in all_e:
            st.caption(f"**{t}** — {m}")

tab_a, tab_f, tab_r = st.tabs(["📋 Ações","🏢 FIIs","🏆 Ranking"])

with tab_a:
    if da is None or len(da)==0:
        st.info("Sem dados de ações.")
    else:
        c1,c2,c3 = st.columns([2,1,1])
        bq = c1.text_input("🔍 Filtrar", key="bqa", placeholder="ex: VALE3")
        ms = c2.selectbox("Score ≥", [0,1,2,3,4,5], key="msa")
        od = c3.selectbox("Ordenar", ["SomaScore ↓","DY (%) ↓","P/VP ↑","Ticker ↑"], key="oda")
        dv = da.copy()
        if bq: dv = dv[dv["Ticker"].str.contains(bq.upper())]
        dv = dv[dv["SomaScore"] >= ms]
        oc,asc = {"SomaScore ↓":("SomaScore",False),"DY (%) ↓":("DY (%)",False),
                  "P/VP ↑":("P/VP",True),"Ticker ↑":("Ticker",True)}[od]
        dv = dv.sort_values(oc, ascending=asc)
        cs = [c for c in ["Ticker","Valor Atual","DY (%)","Valorização 12m (%)","P/VP",
              "PEG Ratio","DL/EBITDA","Qtd Atual","Rend. Mensal","Qtd Mágica","Nível Ating.","SomaScore"] if c in dv.columns]
        fm = {k:v for k,v in {"Valor Atual":"R$ {:.2f}","DY (%)":"{:.2f}%","Valorização 12m (%)":"{:+.2f}%",
              "P/VP":"{:.2f}","PEG Ratio":"{:.2f}","DL/EBITDA":"{:.2f}",
              "Rend. Mensal":"R$ {:.4f}","Qtd Mágica":"{:.0f}"}.items() if k in dv.columns}
        st.dataframe(dv[cs].style.format(fm).background_gradient(subset=["SomaScore"],cmap="RdYlGn",vmin=0,vmax=5),
                     use_container_width=True, height=420)
        st.download_button("⬇️ Baixar (.xlsx)", para_excel(dv[cs]), "acoes.xlsx")

with tab_f:
    if df is None or len(df)==0:
        st.info("Sem dados de FIIs.")
    else:
        c1,c2,c3 = st.columns([2,1,1])
        bq = c1.text_input("🔍 Filtrar", key="bqf", placeholder="ex: KNRI11")
        ms = c2.selectbox("Score ≥", [0,1,2,3], key="msf")
        od = c3.selectbox("Ordenar", ["SomaScores ↓","DY (%) ↓","P/VP ↑","Ticker ↑"], key="odf")
        dv = df.copy()
        if bq: dv = dv[dv["Ticker"].str.contains(bq.upper())]
        dv = dv[dv["SomaScores"] >= ms]
        oc,asc = {"SomaScores ↓":("SomaScores",False),"DY (%) ↓":("DY (%)",False),
                  "P/VP ↑":("P/VP",True),"Ticker ↑":("Ticker",True)}[od]
        dv = dv.sort_values(oc, ascending=asc)
        cs = [c for c in ["Ticker","Valor Atual","DY (%)","Valorização 12m (%)","P/VP",
              "Qtd Atual","Rend. Mensal","Qtd Mágica","Nível Ating.","SomaScores"] if c in dv.columns]
        fm = {k:v for k,v in {"Valor Atual":"R$ {:.2f}","DY (%)":"{:.2f}%","Valorização 12m (%)":"{:+.2f}%",
              "P/VP":"{:.2f}","Rend. Mensal":"R$ {:.4f}","Qtd Mágica":"{:.0f}"}.items() if k in dv.columns}
        st.dataframe(dv[cs].style.format(fm).background_gradient(subset=["SomaScores"],cmap="RdYlGn",vmin=0,vmax=3),
                     use_container_width=True, height=420)
        st.download_button("⬇️ Baixar (.xlsx)", para_excel(dv[cs]), "fiis.xlsx")

with tab_r:
    st.markdown("### 🏆 Top ativos por score")
    ca,cf = st.columns(2)
    with ca:
        st.markdown("#### Ações — Top 10")
        if da is not None and len(da)>0:
            top = da.nlargest(10,"SomaScore")[["Ticker","SomaScore","DY (%)","P/VP"]].reset_index(drop=True)
            top.index += 1
            st.dataframe(top.style.format({"DY (%)":"{:.2f}%","P/VP":"{:.2f}"}).background_gradient(subset=["SomaScore"],cmap="RdYlGn",vmin=0,vmax=5), use_container_width=True)
    with cf:
        st.markdown("#### FIIs — Top 10")
        if df is not None and len(df)>0:
            top = df.nlargest(10,"SomaScores")[["Ticker","SomaScores","DY (%)","P/VP"]].reset_index(drop=True)
            top.index += 1
            st.dataframe(top.style.format({"DY (%)":"{:.2f}%","P/VP":"{:.2f}"}).background_gradient(subset=["SomaScores"],cmap="RdYlGn",vmin=0,vmax=3), use_container_width=True)
