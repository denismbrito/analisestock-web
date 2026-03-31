"""
AnáliseStock — Streamlit App v3 (Yahoo Finance)
"""

import streamlit as st
import pandas as pd
import numpy as np
import math
import time
import io
import yfinance as yf

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
#  API Yahoo Finance (Substituindo a Brapi)
# ─────────────────────────────────────────────────────────────────────────────

def _safe(val, default=0.0):
    if val is None:
        return default
    try:
        f = float(val)
        return default if (math.isnan(f)) else f
    except (TypeError, ValueError):
        return default

def extrair_acao(ticker):
    try:
        # Adiciona .SA para buscar na bolsa brasileira (B3)
        info = yf.Ticker(f"{ticker}.SA").info
        
        if not info or ("regularMarketPrice" not in info and "currentPrice" not in info):
            return {"Ticker": ticker.upper(), "_erro": "Ativo não encontrado ou sem dados no Yahoo Finance"}

        valor = _safe(info.get("currentPrice") or info.get("regularMarketPrice"))
        dy    = _safe(info.get("dividendYield")) * 100

        y_low = _safe(info.get("fiftyTwoWeekLow"))
        var12 = round(((valor - y_low) / y_low) * 100, 2) if y_low > 0 and valor > 0 else 0.0
        v12   = valor / (1 + var12/100) if var12 != -100 else np.nan

        pvp  = _safe(info.get("priceToBook"))
        peg  = _safe(info.get("pegRatio"))
        debt = _safe(info.get("totalDebt"))
        cash = _safe(info.get("totalCash"))
        ebit = _safe(info.get("ebitda"))
        dle  = round((debt - cash) / ebit, 2) if ebit != 0 else 0.0

        return {
            "Ticker": ticker.upper(),
            "Valor Atual": valor,
            "Valor 12m Atrás": v12,
            "DY (%)": round(dy, 2),
            "Valorização 12m (%)": var12,
            "P/VP": round(pvp, 2),
            "PEG Ratio": round(peg, 2),
            "DL/EBITDA": dle,
        }
    except Exception as e:
        return {"Ticker": ticker.upper(), "_erro": str(e)}

def extrair_fii(ticker):
    try:
        info = yf.Ticker(f"{ticker}.SA").info
        
        if not info or ("regularMarketPrice" not in info and "currentPrice" not in info):
            return {"Ticker": ticker.upper(), "_erro": "Ativo não encontrado ou sem dados no Yahoo Finance"}

        valor = _safe(info.get("currentPrice") or info.get("regularMarketPrice"))
        
        # FIIs no Yahoo Finance às vezes salvam o DY em um campo diferente
        dy_f  = info.get("dividendYield") or info.get("trailingAnnualDividendYield")
        dy    = _safe(dy_f) * 100

        y_low = _safe(info.get("fiftyTwoWeekLow"))
        var12 = round(((valor - y_low) / y_low) * 100, 2) if y_low > 0 and valor > 0 else 0.0
        v12   = valor / (1 + var12/100) if var12 != -100 else np.nan
        pvp   = _safe(info.get("priceToBook"))

        return {
            "Ticker": ticker.upper(),
            "Valor Atual": valor,
            "Valor 12m Atrás": v12,
            "DY (%)": round(dy, 2),
            "Valorização 12m (%)": var12,
            "P/VP": round(pvp, 2),
        }
    except Exception as e:
        return {"Ticker": ticker.upper(), "_erro": str(e)}

# ─────────────────────────────────────────────────────────────────────────────
#  SCORES
# ─────────────────────────────────────────────────────────────────────────────

def scores_fiis(df):
    df = df.copy()
    df["ScoreEvolucao"]    = np.where(df["Valor Atual"] < df["Valor 12m Atrás"], 1, 0)
    df["ScorePreco"]       = np.where((df["P/VP"] >= 0.5) & (df["P/VP"] <= 0.95), 1, 0)
    df["ScoreVariacao12m"] = np.where((df["Valorização 12m (%)"] >= 1) & (df["Valorização 12m (%)"] <= 10), 1, 0)
    df["SomaScores"]       = df[["ScoreEvolucao", "ScorePreco", "ScoreVariacao12m"]].sum(axis=1)
    return df

def scores_acoes(df):
    df = df.copy()
    df["ScoreEvolucao"]    = np.where(df["Valor Atual"] < df["Valor 12m Atrás"], 1, 0)
    df["ScorePreco"]       = np.where((df["P/VP"] >= 0.5) & (df["P/VP"] <= 0.95), 1, 0)
    df["ScoreVariacao12m"] = np.where((df["Valorização 12m (%)"] >= 1) & (df["Valorização 12m (%)"] <= 10), 1, 0)
    df["ScorePeg"]         = np.where((df["PEG Ratio"] >= 0.4) & (df["PEG Ratio"] <= 1.0), 1, 0)
    df["ScoreAlavancagem"] = np.where((df["DL/EBITDA"] >= 1.0) & (df["DL/EBITDA"] <= 3.0), 1, 0)
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
        st.warning(f"Posição não mesclada: {e}")
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
#  SIDEBAR
# ─────────────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## 📊 AnáliseStock")
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
    rodar = st.button("🚀 Rodar Análise", use_container_width=True)
    st.caption("Fonte: Yahoo Finance · v3")

# ─────────────────────────────────────────────────────────────────────────────
#  HEADER
# ─────────────────────────────────────────────────────────────────────────────

st.markdown("""
<div class="main-header">
  <h1>📈 AnáliseStock</h1>
  <p>Análise quantitativa de Ações e FIIs da B3 · Scores, Magic Number e posição da carteira</p>
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
        except Exception as e:
            st.warning(f"posicao.xlsx: {e}")

    # Ações
    if tickers:
        p = st.progress(0, text="Buscando ações…")
        dados, erros = [], []
        for i, t in enumerate(tickers):
            p.progress((i+1)/len(tickers), text=f"🔍 {t}")
            r = extrair_acao(t)
            (erros if "_erro" in r else dados).append(r)
            time.sleep(0.1) # Yahoo finance é mais rápido, podemos diminuir o delay
        p.empty()
        
        dados_ok  = [r for r in dados if "_erro" not in r]
        erros_ok  = [(e["Ticker"], e["_erro"]) for e in erros]

        if dados_ok:
            df_a = pd.DataFrame(dados_ok)
            df_a = scores_acoes(df_a)
            df_a = mesclar(df_a, pos_a) if pos_a is not None else df_a.assign(**{"Qtd Atual":0})
            df_a = magic_number(df_a)
            st.session_state.df_a  = df_a
        else:
            st.session_state.df_a  = None
        st.session_state.err_a = erros_ok

    # FIIs
    if fiis:
        p = st.progress(0, text="Buscando FIIs…")
        dados, erros = [], []
        for i, t in enumerate(fiis):
            p.progress((i+1)/len(fiis), text=f"🔍 {t}")
            r = extrair_fii(t)
            (erros if "_erro" in r else dados).append(r)
            time.sleep(0.1)
        p.empty()
        
        dados_ok  = [r for r in dados if "_erro" not in r]
        erros_ok  = [(e["Ticker"], e["_erro"]) for e in erros]

        if dados_ok:
            df_f = pd.DataFrame(dados_ok)
            df_f = scores_fiis(df_f)
            df_f = mesclar(df_f, pos_f) if pos_f is not None else df_f.assign(**{"Qtd Atual":0})
            df_f = magic_number(df_f)
            st.session_state.df_f  = df_f
        else:
            st.session_state.df_f  = None
        st.session_state.err_f = erros_ok

    st.session_state.rodou = True
    st.rerun()

# ─────────────────────────────────────────────────────────────────────────────
#  RESULTADOS
# ─────────────────────────────────────────────────────────────────────────────

da = st.session_state.df_a
df = st.session_state.df_f

if not st.session_state.rodou:
    st.info("👈 Insira os tickers na barra lateral e clique em **Rodar Análise**.")
    with st.expander("ℹ️ Scores e Magic Number"):
        c1,c2 = st.columns(2)
        c1.markdown("**Ações (0–5)**\n| Score | Critério |\n|---|---|\n|ScoreEvolucao|Preço < 12m atrás|\n|ScorePreco|0,50≤P/VP≤0,95|\n|ScoreVariacao12m|1%≤Var12m≤10%|\n|ScorePeg|0,40≤PEG≤1,00|\n|ScoreAlavancagem|1,0≤DL/EBITDA≤3,0|")
        c2.markdown("**FIIs (0–3)**\n| Score | Critério |\n|---|---|\n|ScoreEvolucao|Preço < 12m atrás|\n|ScorePreco|0,50≤P/VP≤0,95|\n|ScoreVariacao12m|1%≤Var12m≤10%|\n\n**Magic Number**: Qtd para que dividendos mensais paguem 1 cota.")
    st.stop()

if da is None and df is None:
    all_e = st.session_state.err_a + st.session_state.err_f
    st.error("❌ Nenhum dado retornado.")
    for t,m in all_e:
        st.caption(f"**{t}** — {m}")
    st.stop()

# Métricas
c1,c2,c3,c4 = st.columns(4)
c1.metric("Ações",  len(da) if da is not None else 0)
c2.metric("Melhor (Ações)",  f"{int(da['SomaScore'].max())}/5"   if da is not None and len(da)>0 else "—")
c3.metric("FIIs",   len(df) if df is not None else 0)
c4.metric("Melhor (FIIs)",   f"{int(df['SomaScores'].max())}/3"  if df is not None and len(df)>0 else "—")

all_e = st.session_state.err_a + st.session_state.err_f
if all_e:
    with st.expander(f"⚠️ {len(all_e)} ticker(s) com falha"):
        for t,m in all_e:
            st.caption(f"**{t}** — {m}")

tab_a, tab_f, tab_r = st.tabs(["📋 Ações","🏢 FIIs","🏆 Ranking"])

# ── Ações ─────────────────────────────────────────────────────────────────
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
        st.markdown('<div class="score-legend">🟢 <b>5</b> excelente &nbsp;|&nbsp; 🟡 <b>3</b> moderado &nbsp;|&nbsp; 🔴 <b>0-1</b> abaixo dos critérios &nbsp;|&nbsp; <b>Nível Ating.</b>: vezes que dividendos mensais cobrem 1 cota</div>', unsafe_allow_html=True)
        st.download_button("⬇️ Baixar (.xlsx)", para_excel(dv[cs]), "acoes.xlsx",
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# ── FIIs ──────────────────────────────────────────────────────────────────
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
        st.markdown('<div class="score-legend">🟢 <b>3</b> excelente &nbsp;|&nbsp; 🟡 <b>2</b> moderado &nbsp;|&nbsp; 🔴 <b>0-1</b> abaixo dos critérios &nbsp;|&nbsp; <b>Nível Ating.</b>: vezes que dividendos mensais cobrem 1 cota</div>', unsafe_allow_html=True)
        st.download_button("⬇️ Baixar (.xlsx)", para_excel(dv[cs]), "fiis.xlsx",
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# ── Ranking ───────────────────────────────────────────────────────────────
with tab_r:
    st.markdown("### 🏆 Top ativos por score")
    ca,cf = st.columns(2)
    with ca:
        st.markdown("#### Ações — Top 10")
        if da is not None and len(da)>0:
            top = da.nlargest(10,"SomaScore")[["Ticker","SomaScore","DY (%)","P/VP"]].reset_index(drop=True)
            top.index += 1
            st.dataframe(top.style.format({"DY (%)":"{:.2f}%","P/VP":"{:.2f}"})
                            .background_gradient(subset=["SomaScore"],cmap="RdYlGn",vmin=0,vmax=5),
                         use_container_width=True)
        else:
            st.info("Sem dados.")
    with cf:
        st.markdown("#### FIIs — Top 10")
        if df is not None and len(df)>0:
            top = df.nlargest(10,"SomaScores")[["Ticker","SomaScores","DY (%)","P/VP"]].reset_index(drop=True)
            top.index += 1
            st.dataframe(top.style.format({"DY (%)":"{:.2f}%","P/VP":"{:.2f}"})
                            .background_gradient(subset=["SomaScores"],cmap="RdYlGn",vmin=0,vmax=3),
                         use_container_width=True)
        else:
            st.info("Sem dados.")
    if da is not None and len(da)>0:
        st.markdown("#### Distribuição scores — Ações")
        st.bar_chart(da["SomaScore"].value_counts().sort_index(), color="#f0c040")
    if df is not None and len(df)>0:
        st.markdown("#### Distribuição scores — FIIs")
        st.bar_chart(df["SomaScores"].value_counts().sort_index(), color="#3b82f6")
