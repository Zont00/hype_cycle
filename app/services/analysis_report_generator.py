import os
from datetime import datetime
from typing import Dict
from sqlalchemy.orm import Session
import logging

from ..models import Technology, TechnologyAnalysis
from ..models.hype_cycle_phase import PhaseCharacteristics, HypeCyclePhase

logger = logging.getLogger(__name__)


class AnalysisReportGenerator:
    """Generate markdown reports for Hype Cycle analysis"""

    def __init__(self, db: Session):
        self.db = db
        self.report_dir = "info"

    def generate_report(self, technology_id: int) -> str:
        """
        Generate comprehensive analysis report

        Args:
            technology_id: ID of technology to generate report for

        Returns:
            Path to generated report file
        """
        logger.info(f"Generating analysis report for technology {technology_id}...")

        # Fetch data
        technology = self.db.query(Technology).filter(Technology.id == technology_id).first()
        analysis = self.db.query(TechnologyAnalysis)\
            .filter(TechnologyAnalysis.technology_id == technology_id)\
            .first()

        if not technology:
            raise ValueError(f"Technology with ID {technology_id} not found")
        if not analysis:
            raise ValueError(f"No analysis found for technology {technology_id}")

        # Generate report content
        report_content = self._build_report_content(technology, analysis)

        # Save to file
        filename = f"HYPE_CYCLE_ANALYSIS_{technology.name.upper().replace(' ', '_')}.md"
        filepath = os.path.join(self.report_dir, filename)

        os.makedirs(self.report_dir, exist_ok=True)

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(report_content)

        logger.info(f"Report generated: {filepath}")
        return filepath

    def _build_report_content(self, technology: Technology, analysis: TechnologyAnalysis) -> str:
        """Build the markdown report content"""

        phase_enum = HypeCyclePhase(analysis.current_phase)
        phase_info = PhaseCharacteristics.PHASE_DEFINITIONS[phase_enum]
        metrics = analysis.metrics

        report = f"""# Hype Cycle Analysis Report - {technology.name}

**Analysis Date**: {analysis.analysis_date.strftime('%Y-%m-%d %H:%M:%S')}
**Technology ID**: {technology.id}
**Papers Analyzed**: {analysis.total_papers_analyzed:,}
**Date Range**: {analysis.date_range_start} to {analysis.date_range_end}

---

## Executive Summary

Based on analysis of **{analysis.total_papers_analyzed:,}** scientific papers, **{technology.name}** is currently in the **{phase_info['name']}** phase of the Gartner Hype Cycle.

**Confidence Level**: {analysis.phase_confidence:.1%}

### Phase Description

{phase_info['description']}

---

## Current Phase: {phase_info['name']}

### Characteristic Indicators

"""

        for indicator in phase_info['indicators']:
            report += f"- {indicator}\n"

        report += f"""

---

## Calculated Metrics

### Publication Velocity

- **Average papers per year**: {metrics['avg_papers_per_year']:.1f}
- **Peak year**: {metrics['peak_year']} ({metrics['peak_count']} papers)
- **Recent velocity** (last 2 years): {metrics['recent_velocity']:.1f} papers/year
- **Trend**: {metrics['velocity_trend']}

### Citation Metrics

- **Total citations**: {metrics['total_citations']:,}
- **Average citations per paper**: {metrics['avg_citations_per_paper']:.1f}
- **Median citations**: {metrics['median_citations']:.1f}
- **Citation growth rate**: {metrics['citation_growth_rate']:.1f}%
- **Highly cited papers**: {metrics['highly_cited_count']}

### Research Type Distribution

- **Basic research**: {metrics['basic_research_percentage']:.1f}%
- **Applied research**: {metrics['applied_research_percentage']:.1f}%
- **Mixed research**: {metrics['mixed_research_percentage']:.1f}%
- **Trend**: {metrics['research_type_trend']}

### Venue Distribution

- **Academic venues**: {metrics['academic_venue_percentage']:.1f}%
- **Industry venues**: {metrics['industry_venue_percentage']:.1f}%
- **Conferences**: {metrics['conference_percentage']:.1f}%
- **Journals**: {metrics['journal_percentage']:.1f}%

### Top Keywords

"""

        # Add top keywords
        for keyword, count in metrics['top_keywords'][:10]:
            report += f"- **{keyword}**: {count} occurrences\n"

        report += f"""

### Emerging Keywords (Recent Papers)

"""
        if metrics['emerging_keywords']:
            for keyword in metrics['emerging_keywords'][:10]:
                report += f"- {keyword}\n"
        else:
            report += "- No significant emerging keywords detected\n"

        report += f"""

### Data Quality

- **Papers with abstracts**: {metrics['papers_with_abstracts']:,} ({metrics['papers_with_abstracts']/analysis.total_papers_analyzed*100:.1f}%)
- **Papers with PDFs**: {metrics['papers_with_pdf']:,} ({metrics['papers_with_pdf']/analysis.total_papers_analyzed*100:.1f}%)
- **Overall coverage**: {metrics['coverage_percentage']:.1f}%

"""

        # Add patent metrics section if available
        patent_metrics = analysis.patent_metrics
        if patent_metrics:
            report += self._build_patent_metrics_section(patent_metrics)

        report += f"""---

## Phase Determination Rationale

{analysis.rationale}

---

## Visualizations (Suggested)

The following visualizations would enhance this report:

1. **Publication Velocity Timeline**: Line chart showing papers/year over time
2. **Citation Distribution**: Histogram of citation counts
3. **Research Type Trend**: Stacked area chart showing basic vs applied research over time
4. **Hype Cycle Curve**: Position marker on standard Gartner Hype Cycle curve
5. **Keyword Cloud**: Word cloud of top keywords

---

## Recommendations

Based on the current phase (**{phase_info['name']}**), we recommend:

"""

        # Add phase-specific recommendations
        if phase_enum == HypeCyclePhase.TECHNOLOGY_TRIGGER:
            report += """
1. **Monitor publication growth**: Track if velocity continues to increase
2. **Watch for applied research**: Look for shift from basic to applied (40%+ applied = moving to Peak)
3. **Identify key researchers**: Early contributors often become leaders in the field
4. **Track patent activity**: Patent filings may indicate commercialization attempts
5. **Monitor funding**: Research grants and venture capital interest are key indicators
"""
        elif phase_enum == HypeCyclePhase.PEAK_INFLATED_EXPECTATIONS:
            report += """
1. **Prepare for potential decline**: Peak often followed by trough within 1-3 years
2. **Evaluate practical applications**: Distinguish hype from real progress
3. **Monitor failure rates**: Increase in problem/challenge papers = entering Trough
4. **Track industry adoption**: Real products vs announcements and promises
5. **Be cautious with investment**: Peak is high-risk for new investments
"""
        elif phase_enum == HypeCyclePhase.TROUGH_DISILLUSIONMENT:
            report += """
1. **Identify survivors**: Focus on research groups still actively publishing quality work
2. **Look for practical solutions**: Papers addressing real-world challenges
3. **Watch for stabilization**: Velocity bottoming out = approaching Slope
4. **Evaluate realistic applications**: Shift from grand visions to practical, achievable uses
5. **Investment opportunity**: Trough can be good entry point for long-term investors
"""
        elif phase_enum == HypeCyclePhase.SLOPE_ENLIGHTENMENT:
            report += """
1. **Track applied research growth**: Should continue increasing toward 80%+
2. **Monitor commercial products**: Second/third generation solutions emerging
3. **Identify best practices**: Standardization and protocols being established
4. **Watch industry partnerships**: Academia-industry collaboration increasing
5. **Consider market entry**: Good time for commercial applications and products
"""
        elif phase_enum == HypeCyclePhase.PLATEAU_PRODUCTIVITY:
            report += """
1. **Monitor mainstream adoption**: Technology becoming standard in the field
2. **Track incremental improvements**: Focus on optimization vs breakthrough
3. **Watch for disruption**: May be disrupted or replaced by newer technologies
4. **Evaluate market saturation**: Stable velocity indicates mature market
5. **Focus on efficiency**: Optimization and cost reduction become key differentiators
"""

        report += f"""

---

## Next Analysis Recommendations

- **Re-analyze after**: {(analysis.analysis_date.year + 1)}-{analysis.analysis_date.month:02d} (1 year)
- **Collect additional data sources**: Patents, news articles, Reddit discussions for fuller picture
- **Track specific metrics**:
  - Publication velocity trend
  - Applied research percentage
  - Citation growth rate
  - Emerging keywords

---

## Appendix: Methodology

### Data Sources
- **Papers**: Semantic Scholar API
- **Date Range**: {analysis.date_range_start} to {analysis.date_range_end}
- **Total Papers**: {analysis.total_papers_analyzed:,}

### Metrics Calculated
1. **Publication Velocity**: Papers per year, trend analysis
2. **Citation Analysis**: Growth rates, highly cited papers
3. **Research Classification**: Basic vs applied research using keyword analysis
4. **Topic Analysis**: Keyword extraction from titles and abstracts
5. **Venue Analysis**: Academic vs industry publication venues

### Phase Determination
- **Method**: Rule-based scoring system
- **Phases Evaluated**: All 5 Gartner Hype Cycle phases
- **Confidence Score**: {analysis.phase_confidence:.1%}

### Limitations
- Analysis based on papers only (not including patents, news, finance data yet)
- Keyword analysis uses simple pattern matching (not advanced NLP)
- Thresholds are configurable and may need calibration for specific domains
- Data quality depends on abstract availability ({metrics['papers_with_abstracts']/analysis.total_papers_analyzed*100:.1f}% coverage)

---

**Report Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Analysis Engine Version**: 1.0.0
**Technology**: {technology.name}
**Hype Cycle Phase**: {phase_info['name']}
"""

        return report

    def _build_patent_metrics_section(self, patent_metrics: Dict) -> str:
        """Build the patent metrics section of the report"""

        section = """---

## Patent Analysis Metrics

"""

        # Volume metrics
        section += f"""### Patent Volume

- **Total patents analyzed**: {patent_metrics.get('total_patents', 0):,}
- **Average patents per year**: {patent_metrics.get('avg_patents_per_year', 0):.1f}
- **Peak year**: {patent_metrics.get('peak_year', 'N/A')} ({patent_metrics.get('peak_count', 0)} patents)
- **Recent velocity** (last 2 years): {patent_metrics.get('recent_velocity', 0):.1f} patents/year
- **Velocity trend**: {patent_metrics.get('velocity_trend', 'N/A')}
- **Technology age**: {patent_metrics.get('technology_age_years', 0)} years (first patent: {patent_metrics.get('first_patent_year', 'N/A')})

"""

        # Citation metrics
        section += f"""### Citation Metrics

- **Total forward citations**: {patent_metrics.get('total_forward_citations', 0):,}
- **Total backward citations**: {patent_metrics.get('total_backward_citations', 0):,}
- **Average forward citations**: {patent_metrics.get('avg_forward_citations', 0):.1f}
- **Average backward citations**: {patent_metrics.get('avg_backward_citations', 0):.1f}
- **Citation ratio** (forward/backward): {patent_metrics.get('citation_ratio', 0):.2f}
- **Median forward citations**: {patent_metrics.get('median_forward_citations', 0):.1f}
- **Highly cited patents**: {patent_metrics.get('highly_cited_count', 0)}

"""

        # Assignee metrics
        section += f"""### Assignee Analysis

- **Unique assignees**: {patent_metrics.get('unique_assignees_count', 0)}
- **Assignee concentration (HHI)**: {patent_metrics.get('assignee_concentration_hhi', 0):.3f}
"""
        # Interpret HHI
        hhi = patent_metrics.get('assignee_concentration_hhi', 0)
        if hhi < 0.15:
            hhi_interpretation = "Low concentration (competitive market)"
        elif hhi < 0.25:
            hhi_interpretation = "Moderate concentration"
        else:
            hhi_interpretation = "High concentration (few dominant players)"
        section += f"  - *Interpretation*: {hhi_interpretation}\n"

        section += f"""
#### Assignee Type Distribution

- **Corporate**: {patent_metrics.get('corporate_percentage', 0):.1f}%
- **Academic**: {patent_metrics.get('academic_percentage', 0):.1f}%
- **Individual**: {patent_metrics.get('individual_percentage', 0):.1f}%

#### Top Assignees

"""
        top_assignees = patent_metrics.get('top_assignees', [])
        for i, assignee_data in enumerate(top_assignees[:10], 1):
            if isinstance(assignee_data, (list, tuple)) and len(assignee_data) >= 2:
                name, count = assignee_data[0], assignee_data[1]
                section += f"{i}. **{name}**: {count} patents\n"

        # Geographic metrics
        section += f"""

### Geographic Distribution

- **Unique countries**: {patent_metrics.get('unique_countries', 0)}

#### Top Countries

"""
        top_countries = patent_metrics.get('top_countries', [])
        for country_data in top_countries[:5]:
            if isinstance(country_data, (list, tuple)) and len(country_data) >= 2:
                country, count = country_data[0], country_data[1]
                section += f"- **{country}**: {count} patents\n"

        # Patent type metrics
        section += f"""

### Patent Type Distribution

- **Utility patents**: {patent_metrics.get('utility_percentage', 0):.1f}%
- **Design patents**: {patent_metrics.get('design_percentage', 0):.1f}%
- **Other types**: {patent_metrics.get('other_type_percentage', 0):.1f}%

### Patent Data Quality

- **Patents with abstracts**: {patent_metrics.get('patents_with_abstract', 0):,}
- **Coverage**: {patent_metrics.get('coverage_percentage', 0):.1f}%

"""

        return section
