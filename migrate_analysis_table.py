"""
Database migration script to create the technology_analyses table.

Run this script after implementing the analysis models:
python migrate_analysis_table.py
"""

from app.database import engine, Base
from app.models.technology_analysis import TechnologyAnalysis

def create_analysis_table():
    """Create the technology_analyses table in the database"""
    print("Creating technology_analyses table...")

    try:
        # Create only the TechnologyAnalysis table
        Base.metadata.create_all(bind=engine, tables=[TechnologyAnalysis.__table__])
        print("[OK] Tabella technology_analyses creata con successo!")
        print("\nLa tabella e' pronta per l'uso con i seguenti campi:")
        print("  - id (PK)")
        print("  - technology_id (FK unique)")
        print("  - current_phase")
        print("  - phase_confidence")
        print("  - analysis_date")
        print("  - total_papers_analyzed")
        print("  - date_range_start, date_range_end")
        print("  - metrics (JSON)")
        print("  - rule_scores (JSON)")
        print("  - rationale")

    except Exception as e:
        print(f"[ERROR] Errore durante la creazione della tabella: {e}")
        raise

if __name__ == "__main__":
    create_analysis_table()
