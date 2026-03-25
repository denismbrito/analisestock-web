# AnáliseStock — Web App

Análise quantitativa de Ações e FIIs da B3 via Streamlit.

## Estrutura do projeto

```
analisestock_web/
├── app.py                   ← Aplicação principal
├── requirements.txt         ← Dependências Python
├── .streamlit/
│   └── config.toml          ← Tema e configurações
└── README.md
```

## Rodando localmente

```bash
# 1. Clone ou copie os arquivos
# 2. Instale as dependências
pip install -r requirements.txt

# 3. Rode o app
streamlit run app.py
```

Acesse: http://localhost:8501

## Deploy no Streamlit Community Cloud (gratuito)

### Pré-requisitos
- Conta no GitHub (gratuita)
- Conta no Streamlit Cloud: https://share.streamlit.io

### Passo a passo

1. **Crie um repositório no GitHub** (pode ser público ou privado):
   ```
   analisestock-web/
   ├── app.py
   ├── requirements.txt
   └── .streamlit/config.toml
   ```

2. **Faça push dos arquivos**:
   ```bash
   git init
   git add .
   git commit -m "feat: AnáliseStock web app"
   git remote add origin https://github.com/SEU_USUARIO/analisestock-web.git
   git push -u origin main
   ```

3. **No Streamlit Cloud**:
   - Clique em **New app**
   - Selecione o repositório e branch `main`
   - Main file path: `app.py`
   - Clique em **Deploy**

4. **Compartilhe o link** gerado (ex: `https://analisestock-web.streamlit.app`)

### Compartilhando com grupo restrito (sem login público)

No painel do Streamlit Cloud, vá em **Settings → Sharing** e adicione
os e-mails dos convidados. Apenas eles poderão acessar o app.

---

## Como usar o app

### Entradas

| Campo | Descrição |
|-------|-----------|
| Tickers de Ações | Um ticker por linha (ex: VALE3, ITUB4) |
| FIIs | Um ticker por linha (ex: KNRI11, MXRF11) |
| posicao.xlsx | Exportado da B3. Abas: `Acoes` e `Fundo de Investimento` |

### Colunas do posicao.xlsx esperadas
- `Código de Negociação` — ticker do ativo
- `Quantidade` — quantidade de cotas/ações

### Scores

**Ações (0–5)**
| Coluna | Critério |
|--------|----------|
| ScoreEvolucao | Valor Atual < Valor 12m Atrás |
| ScorePreco | 0,50 ≤ P/VP ≤ 0,95 |
| ScoreVariacao12m | 1% ≤ Valorização 12m ≤ 10% |
| ScorePeg | 0,40 ≤ PEG Ratio ≤ 1,00 |
| ScoreAlavancagem | 1,0 ≤ DL/EBITDA ≤ 3,0 |

**FIIs (0–3)**
| Coluna | Critério |
|--------|----------|
| ScoreEvolucao | Valor Atual < Valor 12m Atrás |
| ScorePreco | 0,50 ≤ P/VP ≤ 0,95 |
| ScoreVariacao12m | 1% ≤ Valorização 12m ≤ 10% |

### Magic Number

- **Rend. Mensal** = Valor Atual × (DY / 12)
- **Qtd Mágica** = Valor Atual / Rend. Mensal
- **Nível Atingimento** = floor(Qtd Atual / Qtd Mágica)

> Nível 1 = os dividendos mensais já pagam 1 cota por mês.

---

## Observações sobre scraping

O app faz scraping do StatusInvest. Em servidores cloud pode ocorrer bloqueio
por IP. Se isso acontecer:

1. Use um proxy residencial (ex: Bright Data, Oxylabs)
2. Ou rode localmente na sua máquina (sem risco de bloqueio)

O `sleep(0.4)` entre requisições é um intervalo de cortesia ao servidor.
