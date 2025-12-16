# Gartner Hype Cycle API - Tech Catalog

API REST per gestire un catalogo di tecnologie con keywords, excluded terms e tickers per la raccolta dati e l'analisi del Gartner Hype Cycle.

## Stack Tecnologico

- **Backend**: Python 3.10+ con FastAPI
- **Database**: SQLite con SQLAlchemy ORM
- **Validazione**: Pydantic
- **Server**: Uvicorn

## Setup

### 1. Installare le dipendenze

```bash
pip install -r requirements.txt
```

### 2. (Opzionale) Configurare environment variables

```bash
cp .env.example .env
```

Il file `.env` è opzionale. Se non presente, verrà usato il default `sqlite:///./data/hype_cycle.db`.

### 3. Avviare il server

```bash
uvicorn app.main:app --reload
```

Il server sarà disponibile su `http://localhost:8000`

### 4. Aprire la documentazione interattiva

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Struttura del Progetto

```
Hype Cycle/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app con endpoints CRUD
│   ├── config.py            # Configurazione
│   ├── database.py          # SQLAlchemy setup
│   ├── models/
│   │   ├── __init__.py
│   │   └── technology.py    # Modello Technology
│   └── schemas/
│       ├── __init__.py
│       └── technology.py    # Pydantic schemas
├── data/                    # Creata automaticamente
│   └── hype_cycle.db        # Database SQLite
├── .env                     # Config locale (gitignored)
├── .env.example             # Template
├── .gitignore
├── requirements.txt
└── README.md
```

## API Endpoints

### `POST /technologies`
Crea una nuova tecnologia.

**Request**:
```json
{
  "name": "Plant Cell Culture",
  "description": "Growing plant cells in vitro",
  "keywords": ["plant cell culture", "tissue culture"],
  "excluded_terms": ["animal cell"],
  "tickers": ["BAYN.DE", "DSM.AS"]
}
```

**Response** (201):
```json
{
  "id": 1,
  "name": "Plant Cell Culture",
  "description": "Growing plant cells in vitro",
  "keywords": ["plant cell culture", "tissue culture"],
  "excluded_terms": ["animal cell"],
  "tickers": ["BAYN.DE", "DSM.AS"],
  "is_active": true,
  "created_at": "2024-12-12T10:00:00",
  "updated_at": "2024-12-12T10:00:00"
}
```

### `GET /technologies`
Lista tutte le tecnologie.

**Query Params**:
- `is_active` (optional): `true` o `false`
- `skip` (optional): Offset per paginazione (default: 0)
- `limit` (optional): Limite risultati (default: 100, max: 500)

### `GET /technologies/{id}`
Ottieni dettagli di una tecnologia.

### `PUT /technologies/{id}`
Aggiorna una tecnologia (update parziale supportato).

### `DELETE /technologies/{id}`
Elimina una tecnologia.

**Query Params**:
- `hard_delete` (optional): `true` per delete permanente, `false` per soft delete (default)

## Esempi d'Uso

### Con curl

```bash
# Creare una tecnologia
curl -X POST "http://localhost:8000/technologies" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Plant Cell Culture",
    "description": "Growing plant cells in vitro",
    "keywords": ["plant cell culture", "tissue culture"],
    "excluded_terms": ["animal cell"],
    "tickers": ["BAYN.DE", "DSM.AS"]
  }'

# Listare tutte le tecnologie
curl "http://localhost:8000/technologies"

# Ottenere una tecnologia specifica
curl "http://localhost:8000/technologies/1"

# Aggiornare una tecnologia
curl -X PUT "http://localhost:8000/technologies/1" \
  -H "Content-Type: application/json" \
  -d '{"keywords": ["new keyword 1", "new keyword 2"]}'

# Eliminare una tecnologia (soft delete)
curl -X DELETE "http://localhost:8000/technologies/1"

# Eliminare permanentemente
curl -X DELETE "http://localhost:8000/technologies/1?hard_delete=true"
```

### Con Python

```python
import requests

# Creare una tecnologia
response = requests.post(
    "http://localhost:8000/technologies",
    json={
        "name": "Plant Cell Culture",
        "keywords": ["plant cell culture", "tissue culture"],
        "excluded_terms": ["animal cell"],
        "tickers": ["BAYN.DE"]
    }
)
print(response.json())

# Listare tecnologie
response = requests.get("http://localhost:8000/technologies")
print(response.json())
```

## Database Schema

### Tabella `technologies`

| Campo | Tipo | Descrizione |
|-------|------|-------------|
| id | INTEGER | Primary key (auto-increment) |
| name | VARCHAR(200) | Nome tecnologia (unique) |
| description | TEXT | Descrizione (opzionale) |
| keywords | TEXT | JSON array di keywords |
| excluded_terms | TEXT | JSON array di termini da escludere |
| tickers | TEXT | JSON array di ticker azionari |
| is_active | BOOLEAN | Flag attivo/inattivo |
| created_at | TIMESTAMP | Data creazione |
| updated_at | TIMESTAMP | Data ultimo aggiornamento |

## Features

- ✅ CRUD completo per tech catalog
- ✅ Validazione input con Pydantic
- ✅ Database SQLite con SQLAlchemy ORM
- ✅ Documentazione API automatica (Swagger UI)
- ✅ Gestione JSON per keywords/excluded_terms/tickers
- ✅ Soft delete (is_active flag) e hard delete
- ✅ Timestamps automatici (created_at, updated_at)
- ✅ Paginazione per lista tecnologie
- ✅ Filtri per is_active

## Prossimi Step

Questa è la **Fase 1** del progetto Gartner Hype Cycle API. Prossime fasi includeranno:

1. **Data Collection**: Collector per Semantic Scholar API
2. **Metrics Calculation**: Calcolo metriche da papers raccolti
3. **Hype Cycle Positioning**: Engine basato su regole per determinare fase
4. **Investment Recommendations**: Sistema di raccomandazioni

## Licenza

MIT
