# Yahoo Finance Data Collection Report

**Generated:** 2025-12-17 11:27:57
**Technology:** Plant Cell Culture
**Technology ID:** 1

---

## Executive Summary

Questo report fornisce un'analisi dettagliata dei dati finanziari raccolti da Yahoo Finance per la tecnologia **Plant Cell Culture**.

### Metriche Chiave

- **Ticker Processati:** 5 (3 stocks + 2 indici di mercato)
- **Datapoint Totali:** 560
- **Periodo Coperto:** Fino a 10 anni (2016-2025)
- **Frequenza Dati:** Mensile
- **Volume Totale Scambiato:** 20,998,129,740,995

---

## 1. Ticker Analizzati

### 1.1 Stocks (Azioni)

#### BIIB

**Company:** Biogen Inc.
**Sector:** Healthcare
**Industry:** Drug Manufacturers - General

**Statistiche Prezzo:**
- Datapoint: 120
- Periodo: 2016-01-01 → 2025-12-01
- Min Close: $121.08
- Max Close: $353.49
- Avg Close: $256.20
- Volume Totale: 3,758,269,466

**Performance:**
- Prezzo Iniziale (2016-01-01): $273.06
- Prezzo Finale (2025-12-01): $171.50
- Variazione: -37.19%

**Fundamentals:**
- Market Cap: $25,159,440,384 (25.16B)
- P/E Ratio: 15.62
- Forward P/E: 11.29
- Beta: 0.13
- EPS: $10.98
- Dividend Yield: N/A

---

#### CTVA

**Company:** Corteva, Inc.
**Sector:** Basic Materials
**Industry:** Agricultural Inputs

**Statistiche Prezzo:**
- Datapoint: 80
- Periodo: 2019-05-01 → 2025-12-01
- Min Close: $21.82
- Max Close: $73.97
- Avg Close: $47.83
- Volume Totale: 6,475,480,433

**Performance:**
- Prezzo Iniziale (2019-05-01): $24.80
- Prezzo Finale (2025-12-01): $65.48
- Variazione: +164.01%

**Fundamentals:**
- Market Cap: $44,467,470,336 (44.47B)
- P/E Ratio: 26.51
- Forward P/E: 17.89
- Beta: 0.74
- EPS: $2.47
- Dividend Yield: 110.00%

---

#### GILD

**Company:** Gilead Sciences, Inc.
**Sector:** Healthcare
**Industry:** Drug Manufacturers - General

**Statistiche Prezzo:**
- Datapoint: 120
- Periodo: 2016-01-01 → 2025-12-01
- Min Close: $47.35
- Max Close: $125.84
- Avg Close: $64.85
- Volume Totale: 21,087,259,096

**Performance:**
- Prezzo Iniziale (2016-01-01): $58.74
- Prezzo Finale (2025-12-01): $118.78
- Variazione: +102.22%

**Fundamentals:**
- Market Cap: $147,383,042,048 (147.38B)
- P/E Ratio: 18.39
- Forward P/E: 13.58
- Beta: 0.33
- EPS: $6.46
- Dividend Yield: 266.00%

---

### 1.2 Market Indices (Indici di Mercato)

Gli indici di mercato forniscono un benchmark per confrontare la performance delle azioni.

#### ^GSPC

**Name:** S&P 500

**Statistiche:**
- Datapoint: 120
- Periodo: 2016-01-01 → 2025-12-01
- Min: 1,932.23
- Max: 6,849.09
- Avg: 3,787.61

**Performance:**
- Valore Iniziale: 1,940.24
- Valore Finale: 6,800.26
- Variazione: +250.49%

---

#### ^IXIC

**Name:** NASDAQ Composite

**Statistiche:**
- Datapoint: 120
- Periodo: 2016-01-01 → 2025-12-01
- Min: 4,557.95
- Max: 23,724.96
- Avg: 11,469.70

**Performance:**
- Valore Iniziale: 4,613.95
- Valore Finale: 23,111.46
- Variazione: +400.90%

---

## 2. Analisi Comparativa

### 2.1 Performance Comparison (Periodo Completo)

| Ticker | Tipo | Prezzo Iniziale | Prezzo Finale | Variazione % |
|--------|------|-----------------|---------------|-------------|
| ^IXIC | Index | $4613.95 | $23111.46 | +400.90% |
| ^GSPC | Index | $1940.24 | $6800.26 | +250.49% |
| CTVA | Stock | $24.80 | $65.48 | +164.01% |
| GILD | Stock | $58.74 | $118.78 | +102.22% |
| BIIB | Stock | $273.06 | $171.50 | -37.19% |

### 2.2 Highlights

**Best Performer:** ^IXIC (+400.90%)
**Worst Performer:** BIIB (-37.19%)

### 2.3 Volatilità (Beta)

Il Beta misura la volatilità di un'azione rispetto al mercato (Beta = 1 significa volatilità uguale al mercato).

| Ticker | Beta | Interpretazione |
|--------|------|-----------------|
| BIIB | 0.13 | Bassa volatilità |
| CTVA | 0.74 | Volatilità moderata |
| GILD | 0.33 | Bassa volatilità |

## 3. Analisi per Settore

### Healthcare

**Aziende:** BIIB, GILD
**Market Cap Totale:** $172,542,482,432
**P/E Medio:** 17.00

### Basic Materials

**Aziende:** CTVA
**Market Cap Totale:** $44,467,470,336
**P/E Medio:** 26.51

---

## 4. Qualità dei Dati

### 4.1 Completezza

- **Datapoint Attesi:** ~600 (5 ticker × 120 mesi)
- **Datapoint Raccolti:** 560
- **Completezza:** 93.3%

**Note:** CTVA ha solo 80 datapoint perché è stata quotata in borsa nel 2019 (IPO), quindi ha meno storia disponibile.

### 4.2 Aggiornamento Dati

- **Data più recente:** 2025-12-01
- **Frequenza aggiornamento:** Mensile
- **Fonte:** Yahoo Finance (via yfinance library)

---

## 5. Informazioni Tecniche

### 5.1 Database Schema

**Tabella: stock_prices**
- Contiene time-series OHLCV (Open, High, Low, Close, Volume)
- Unique constraint su (technology_id, ticker, date)
- Indicizzata per query veloci per ticker e date range

**Tabella: stock_info**
- Contiene metadata aziendali e fundamentals snapshot
- Unique constraint su (technology_id, ticker)
- Aggiornata ad ogni collection run (upsert pattern)

### 5.2 API Endpoints

**Collection:**
```
POST /technologies/1/collect-finance
```

**Query Prices:**
```
GET /technologies/1/finance/prices?ticker=BIIB&start_date=2024-01-01&limit=100
```

**Query Info:**
```
GET /technologies/1/finance/info
```

### 5.3 Configurazione

- **Lookback Period:** 10 anni
- **Frequency:** Mensile (1mo)
- **Market Indices:** ^IXIC (NASDAQ), ^GSPC (S&P500)
- **Rate Limiting:** 0.5s tra ticker
- **Duplicate Handling:** Automatico via unique constraints

---

## 6. Conclusioni

Il collector Yahoo Finance ha raccolto con successo **{total_actual} datapoint** per {len(price_stats)} ticker diversi, coprendo un periodo di fino a 10 anni con dati mensili.

### Highlights:

1. **Copertura Completa:** Tutti i ticker richiesti sono stati processati senza errori
2. **Dati Puliti:** Nessun duplicato, gestione robusta degli errori
3. **Fundamentals Completi:** Market Cap, P/E, Beta, e altre metriche disponibili
4. **Indici di Benchmark:** NASDAQ e S&P500 inclusi per confronto
5. **Performance Tracking:** Variazioni percentuali calcolate per tutto il periodo

### Prossimi Passi:

- Schedulare collection periodiche per mantenere dati aggiornati
- Integrare con altri collector (papers, patents, news) per analisi Hype Cycle
- Creare dashboard di visualizzazione per trend temporali
- Analizzare correlazioni tra performance azionaria e metriche tecnologiche

---

**Report generato automaticamente dal Yahoo Finance Collector**
*Hype Cycle API - Tech Catalog v1.0.0*
