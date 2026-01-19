"""
Script to generate the Hype Cycle analysis report
"""

from app.database import SessionLocal
from app.services.analysis_report_generator import AnalysisReportGenerator

def main():
    db = SessionLocal()
    try:
        generator = AnalysisReportGenerator(db)
        report_path = generator.generate_report(technology_id=1)
        print(f"Report generato con successo: {report_path}")
    finally:
        db.close()

if __name__ == "__main__":
    main()
