"""
Test Summary Script - Display analysis results in a nice format
"""

import json
import requests

def display_summary():
    print("=" * 80)
    print("HYPE CYCLE ANALYSIS - TEST RESULTS")
    print("=" * 80)
    print()

    # Fetch analysis from API
    response = requests.get("http://127.0.0.1:8000/technologies/1/analysis")

    if response.status_code != 200:
        print(f"ERROR: Could not fetch analysis (status {response.status_code})")
        return

    data = response.json()
    metrics = data['metrics']

    print(f"Technology: Plant Cell Culture")
    print(f"Papers Analyzed: {data['total_papers_analyzed']:,}")
    print(f"Date Range: {data['date_range_start']} to {data['date_range_end']}")
    print(f"Analysis Date: {data['analysis_date']}")
    print()

    print("-" * 80)
    print("PHASE DETERMINATION")
    print("-" * 80)

    phase_names = {
        "technology_trigger": "Technology Trigger",
        "peak_inflated_expectations": "Peak of Inflated Expectations",
        "trough_disillusionment": "Trough of Disillusionment",
        "slope_enlightenment": "Slope of Enlightenment",
        "plateau_productivity": "Plateau of Productivity"
    }

    current_phase_name = phase_names[data['current_phase']]
    print(f"\nCurrent Phase: {current_phase_name}")
    print(f"Confidence: {data['phase_confidence']:.1%}")
    print()

    print("Phase Scores:")
    for phase, score in data['rule_scores'].items():
        phase_name = phase_names[phase]
        bar = "#" * int(score * 50)  # 50 chars max
        current = " <-- CURRENT" if phase == data['current_phase'] else ""
        print(f"  {phase_name:40s} [{score:.2f}] {bar}{current}")
    print()

    print("-" * 80)
    print("KEY METRICS - RESEARCH TYPE (PRIORITA!)")
    print("-" * 80)
    print(f"  Basic Science Research:  {metrics['basic_research_percentage']:6.1f}%")
    print(f"  Applied Research:        {metrics['applied_research_percentage']:6.1f}%")
    print(f"  Mixed Research:          {metrics['mixed_research_percentage']:6.1f}%")
    print(f"  Trend:                   {metrics['research_type_trend']}")
    print()

    print("-" * 80)
    print("PUBLICATION VELOCITY")
    print("-" * 80)
    print(f"  Average papers/year:     {metrics['avg_papers_per_year']:,.1f}")
    print(f"  Peak year:               {metrics['peak_year']} ({metrics['peak_count']:,} papers)")
    print(f"  Recent velocity:         {metrics['recent_velocity']:,.1f} papers/year")
    print(f"  Trend:                   {metrics['velocity_trend']}")
    print()

    print("-" * 80)
    print("CITATION METRICS")
    print("-" * 80)
    print(f"  Total citations:         {metrics['total_citations']:,}")
    print(f"  Average per paper:       {metrics['avg_citations_per_paper']:.1f}")
    print(f"  Median:                  {metrics['median_citations']:.1f}")
    print(f"  Growth rate:             {metrics['citation_growth_rate']:.1f}%")
    print(f"  Highly cited papers:     {metrics['highly_cited_count']:,}")
    print()

    print("-" * 80)
    print("TOP 10 KEYWORDS")
    print("-" * 80)
    for i, (keyword, count) in enumerate(metrics['top_keywords'][:10], 1):
        print(f"  {i:2d}. {keyword:20s} {count:,} occurrences")
    print()

    print("-" * 80)
    print("DATA QUALITY")
    print("-" * 80)
    print(f"  Papers with abstracts:   {metrics['papers_with_abstracts']:,} ({metrics['papers_with_abstracts']/data['total_papers_analyzed']*100:.1f}%)")
    print(f"  Papers with PDFs:        {metrics['papers_with_pdf']:,} ({metrics['papers_with_pdf']/data['total_papers_analyzed']*100:.1f}%)")
    print(f"  Overall coverage:        {metrics['coverage_percentage']:.1f}%")
    print()

    print("=" * 80)
    print("REPORT FILE: info/HYPE_CYCLE_ANALYSIS_PLANT_CELL_CULTURE.md")
    print("=" * 80)
    print()

    print("ANALYSIS NOTES:")
    print("- Peak and Trough have equal scores (0.50), indicating transition phase")
    print("- Peak year is 2024 (most recent), velocity still increasing")
    print("- Citation growth rate is negative (-76.3%), unusual pattern to investigate")
    print("- Only 30% applied research, lower than expected for Peak phase")
    print("- Technology may be between Peak and Trough phases")
    print()

if __name__ == "__main__":
    display_summary()
