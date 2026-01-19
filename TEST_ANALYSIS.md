# Testing Hype Cycle Analysis - Guida Rapida

## 1. Creare la Tabella Database

Prima di testare, devi creare la tabella `technology_analyses` nel database.

Esegui lo script di migrazione:

```bash
python migrate_analysis_table.py
```

Dovresti vedere:
```
Creating technology_analyses table...
✓ Tabella technology_analyses creata con successo!
```

## 2. Avviare il Server FastAPI

```bash
uvicorn app.main:app --reload
```

Il server si avvierà su: http://localhost:8000

## 3. Testare l'Analisi

### Opzione A: Usando cURL

```bash
# Analizza i paper per Plant Cell Culture (technology_id = 1)
curl -X POST http://localhost:8000/technologies/1/analyze-papers

# Recupera l'analisi
curl http://localhost:8000/technologies/1/analysis
```

### Opzione B: Usando Swagger UI

1. Apri http://localhost:8000/docs
2. Cerca la sezione "Analysis"
3. Clicca su "POST /technologies/{technology_id}/analyze-papers"
4. Inserisci `1` come technology_id
5. Clicca "Execute"

### Opzione C: Usando Python

```python
import requests

# Analizza
response = requests.post("http://localhost:8000/technologies/1/analyze-papers")
print(response.json())

# Recupera analisi
analysis = requests.get("http://localhost:8000/technologies/1/analysis")
print(analysis.json())
```

## 4. Generare il Report

Dopo aver eseguito l'analisi, puoi generare un report markdown:

```python
from app.database import SessionLocal
from app.services.analysis_report_generator import AnalysisReportGenerator

db = SessionLocal()
generator = AnalysisReportGenerator(db)
report_path = generator.generate_report(technology_id=1)
print(f"Report generato: {report_path}")
```

Il report sarà salvato in: `info/HYPE_CYCLE_ANALYSIS_PLANT_CELL_CULTURE.md`

## 5. Cosa Aspettarsi

L'analisi su **Plant Cell Culture** (55,210 papers) dovrebbe richiedere 1-2 minuti e restituire:

- **Fase Hype Cycle**: Una delle 5 fasi Gartner
- **Confidence Score**: 0.0-1.0
- **Metriche Dettagliate**:
  - Velocità pubblicazione (trend nel tempo)
  - Citation growth rate
  - % Basic research vs Applied research (PRIORITÀ!)
  - Top keywords
  - Venue distribution
- **Rationale**: Spiegazione testuale della determinazione della fase

## 6. Verifica Risultati

### Controlla le metriche chiave:

1. **Research Type Distribution**:
   - Basic research %
   - Applied research %
   - Trend (toward_applied, toward_basic, stable)

2. **Publication Velocity**:
   - Peak year
   - Trend (increasing, decreasing, stable, peak_reached)

3. **Citation Metrics**:
   - Citation growth rate
   - Average citations

4. **Phase Determination**:
   - La fase dovrebbe essere coerente con le metriche
   - Rule scores dovrebbero mostrare la fase vincente con score più alto

## 7. Troubleshooting

### Errore: "Insufficient papers for analysis"
- Soluzione: Raccogli almeno 100 papers prima di analizzare

### Errore: "No papers found for technology"
- Soluzione: Esegui prima il collector: `POST /technologies/{id}/collect`

### Errore: Table 'technology_analyses' doesn't exist
- Soluzione: Esegui `python migrate_analysis_table.py`

### Errore: ModuleNotFoundError: No module named 'numpy'
- Soluzione: Installa le dipendenze: `pip install numpy`

## 8. Output Esempio

```json
{
  "id": 1,
  "technology_id": 1,
  "current_phase": "slope_enlightenment",
  "phase_confidence": 0.75,
  "total_papers_analyzed": 55210,
  "metrics": {
    "basic_research_percentage": 45.2,
    "applied_research_percentage": 54.8,
    "velocity_trend": "stable",
    "citation_growth_rate": 12.3,
    ...
  },
  "rationale": "Phase determined: Slope of Enlightenment\n..."
}
```

## 9. Next Steps

Dopo il test iniziale:

1. Valida i risultati (la fase ha senso?)
2. Aggiusta i threshold in `app/config.py` se necessario
3. Genera e rivedi il report markdown
4. Testa con altre tecnologie
5. Considera l'integrazione con altri data sources (patent, news, finance)

---

**Nota**: L'analisi è computazionalmente intensiva su 55K papers. Sii paziente! 🚀
