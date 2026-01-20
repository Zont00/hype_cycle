from dataclasses import dataclass, asdict
from typing import Dict, List, Tuple, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from collections import defaultdict, Counter
import numpy as np
import logging

from ..models import Patent

logger = logging.getLogger(__name__)


@dataclass
class PatentMetricsSnapshot:
    """Snapshot of all calculated patent metrics"""
    # Volume metrics
    total_patents: int
    patent_velocity: Dict[int, int]  # year -> count
    velocity_trend: str  # "increasing", "decreasing", "stable", "peak_reached"
    avg_patents_per_year: float
    peak_year: int
    peak_count: int
    recent_velocity: float  # patents/year in last 2 years

    # Citation metrics
    total_forward_citations: int
    total_backward_citations: int
    avg_forward_citations: float
    avg_backward_citations: float
    citation_ratio: float  # forward/backward
    median_forward_citations: float
    highly_cited_count: int  # patents with citations > threshold

    # Assignee metrics
    unique_assignees_count: int
    top_assignees: List[Tuple[str, int]]  # (name, count)
    assignee_concentration_hhi: float  # 0-1, Herfindahl-Hirschman Index
    corporate_percentage: float
    academic_percentage: float
    individual_percentage: float
    new_entrants_by_year: Dict[int, int]  # year -> new assignee count

    # Geographic metrics
    country_distribution: Dict[str, int]  # country -> count
    unique_countries: int
    top_countries: List[Tuple[str, int]]  # (country, count)

    # Patent type metrics
    utility_percentage: float
    design_percentage: float
    other_type_percentage: float

    # Temporal metrics
    first_patent_year: int
    technology_age_years: int
    patents_last_year: int
    patents_last_2_years: int

    # Data quality
    patents_with_abstract: int
    coverage_percentage: float

    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return asdict(self)


class PatentMetricsCalculator:
    """Calculate metrics from patent data for Hype Cycle analysis"""

    # Keywords for classifying assignee types
    ACADEMIC_KEYWORDS = [
        "university", "università", "universität", "universite", "universidad",
        "college", "institute", "institut", "research", "laboratory", "lab",
        "national", "federal", "government", "hospital", "medical center",
        "school", "academy", "foundation", "council", "center for",
        "centre for", "dept", "department"
    ]

    CORPORATE_KEYWORDS = [
        "inc", "corp", "corporation", "ltd", "llc", "gmbh", "co.", "company",
        "technologies", "pharmaceuticals", "biotech", "systems", "solutions",
        "industries", "enterprises", "holdings", "group", "limited", "s.a.",
        "ag", "bv", "nv", "plc", "pty", "pvt", "srl", "spa"
    ]

    def __init__(self, db: Session):
        self.db = db

    def calculate_metrics(self, technology_id: int) -> PatentMetricsSnapshot:
        """
        Calculate all metrics for a technology's patents

        Args:
            technology_id: ID of technology to analyze

        Returns:
            PatentMetricsSnapshot with all calculated metrics
        """
        logger.info(f"Starting patent metrics calculation for technology {technology_id}")

        # Fetch all patents for this technology
        patents = self.db.query(Patent)\
            .filter(Patent.technology_id == technology_id)\
            .order_by(Patent.patent_year)\
            .all()

        if not patents:
            raise ValueError(f"No patents found for technology {technology_id}")

        if len(patents) < 10:
            raise ValueError(f"Insufficient patents for analysis. Found {len(patents)}, need at least 10.")

        logger.info(f"Found {len(patents)} patents to analyze")

        # Calculate each metric category
        volume_metrics = self._calculate_volume_metrics(patents)
        citation_metrics = self._calculate_citation_metrics(patents)
        assignee_metrics = self._calculate_assignee_metrics(patents)
        geographic_metrics = self._calculate_geographic_metrics(patents)
        type_metrics = self._calculate_type_metrics(patents)
        temporal_metrics = self._calculate_temporal_metrics(patents)
        quality_metrics = self._calculate_quality_metrics(patents)

        # Combine into snapshot
        metrics = PatentMetricsSnapshot(
            **volume_metrics,
            **citation_metrics,
            **assignee_metrics,
            **geographic_metrics,
            **type_metrics,
            **temporal_metrics,
            **quality_metrics
        )

        logger.info("Patent metrics calculation completed")
        return metrics

    def _calculate_volume_metrics(self, patents: List[Patent]) -> Dict:
        """Calculate patent volume and velocity metrics"""
        logger.info("Calculating patent volume metrics...")

        # Group by year
        year_counts = defaultdict(int)
        for patent in patents:
            if patent.patent_year:
                year_counts[patent.patent_year] += 1

        # Sort years
        sorted_years = sorted(year_counts.keys())

        if not sorted_years:
            raise ValueError("No patents with year information")

        # Find peak
        peak_year = max(year_counts, key=year_counts.get)
        peak_count = year_counts[peak_year]

        # Calculate trend
        if len(sorted_years) >= 3:
            recent_3yr = sum(year_counts[y] for y in sorted_years[-3:]) / 3
            earlier_3yr = sum(year_counts[y] for y in sorted_years[:3]) / 3

            if recent_3yr > earlier_3yr * 1.2:
                trend = "increasing"
            elif recent_3yr < earlier_3yr * 0.8:
                trend = "decreasing"
            elif peak_year in sorted_years[-3:]:
                trend = "peak_reached"
            else:
                trend = "stable"
        else:
            trend = "insufficient_data"

        # Recent velocity (last 2 years)
        current_year = datetime.now().year
        recent_years = [y for y in sorted_years if y >= current_year - 2]
        recent_velocity = sum(year_counts[y] for y in recent_years) / max(len(recent_years), 1)

        return {
            "total_patents": len(patents),
            "patent_velocity": dict(year_counts),
            "velocity_trend": trend,
            "avg_patents_per_year": len(patents) / max(len(sorted_years), 1),
            "peak_year": peak_year,
            "peak_count": peak_count,
            "recent_velocity": recent_velocity
        }

    def _calculate_citation_metrics(self, patents: List[Patent]) -> Dict:
        """Calculate citation-based metrics"""
        logger.info("Calculating patent citation metrics...")

        forward_citations = [
            p.patent_num_times_cited_by_us_patents or 0
            for p in patents
        ]
        backward_citations = [
            p.patent_num_us_patents_cited or 0
            for p in patents
        ]

        total_forward = sum(forward_citations)
        total_backward = sum(backward_citations)
        avg_forward = total_forward / len(patents)
        avg_backward = total_backward / len(patents)

        # Citation ratio (forward/backward)
        citation_ratio = total_forward / max(total_backward, 1)

        # Median forward citations
        median_forward = float(np.median(forward_citations))

        # Highly cited threshold (top 10% or 50+ citations)
        threshold = max(50, np.percentile(forward_citations, 90)) if forward_citations else 50
        highly_cited = sum(1 for c in forward_citations if c >= threshold)

        return {
            "total_forward_citations": total_forward,
            "total_backward_citations": total_backward,
            "avg_forward_citations": avg_forward,
            "avg_backward_citations": avg_backward,
            "citation_ratio": citation_ratio,
            "median_forward_citations": median_forward,
            "highly_cited_count": highly_cited
        }

    def _calculate_assignee_metrics(self, patents: List[Patent]) -> Dict:
        """Calculate assignee-related metrics including HHI concentration"""
        logger.info("Calculating patent assignee metrics...")

        # Extract all assignees from patents
        assignee_counts = Counter()
        assignee_types = {"corporate": 0, "academic": 0, "individual": 0}
        assignee_first_year = {}  # track when each assignee first appears

        for patent in patents:
            assignees = patent.assignees or []
            patent_year = patent.patent_year

            for assignee in assignees:
                # Extract assignee name
                name = assignee.get("assignee_organization") or assignee.get("assignee_individual_name_first", "")
                if not name:
                    continue

                name_lower = name.lower()
                assignee_counts[name] += 1

                # Track first appearance year
                if name not in assignee_first_year and patent_year:
                    assignee_first_year[name] = patent_year

                # Classify assignee type
                assignee_type = self._classify_assignee_type(assignee)
                assignee_types[assignee_type] += 1

        # Total assignees (for percentage calculation)
        total_assignee_entries = sum(assignee_types.values())

        # Unique assignees
        unique_assignees = len(assignee_counts)

        # Top assignees
        top_assignees = assignee_counts.most_common(10)

        # Calculate HHI (Herfindahl-Hirschman Index)
        hhi = self._calculate_hhi(assignee_counts)

        # Percentages by type
        if total_assignee_entries > 0:
            corporate_pct = (assignee_types["corporate"] / total_assignee_entries) * 100
            academic_pct = (assignee_types["academic"] / total_assignee_entries) * 100
            individual_pct = (assignee_types["individual"] / total_assignee_entries) * 100
        else:
            corporate_pct = academic_pct = individual_pct = 0.0

        # New entrants by year
        new_entrants_by_year = defaultdict(int)
        for assignee, first_year in assignee_first_year.items():
            if first_year:
                new_entrants_by_year[first_year] += 1

        return {
            "unique_assignees_count": unique_assignees,
            "top_assignees": top_assignees,
            "assignee_concentration_hhi": hhi,
            "corporate_percentage": corporate_pct,
            "academic_percentage": academic_pct,
            "individual_percentage": individual_pct,
            "new_entrants_by_year": dict(new_entrants_by_year)
        }

    def _classify_assignee_type(self, assignee: Dict) -> str:
        """
        Classify an assignee as corporate, academic, or individual

        Args:
            assignee: Dict with assignee data

        Returns:
            "corporate", "academic", or "individual"
        """
        org_name = (assignee.get("assignee_organization") or "").lower()
        individual_first = assignee.get("assignee_individual_name_first", "")
        individual_last = assignee.get("assignee_individual_name_last", "")

        # If no organization but has individual name, it's individual
        if not org_name and (individual_first or individual_last):
            return "individual"

        # Check for academic keywords
        if any(kw in org_name for kw in self.ACADEMIC_KEYWORDS):
            return "academic"

        # Check for corporate keywords
        if any(kw in org_name for kw in self.CORPORATE_KEYWORDS):
            return "corporate"

        # Default: if has organization name, assume corporate
        if org_name:
            return "corporate"

        return "individual"

    def _calculate_hhi(self, assignee_counts: Dict[str, int]) -> float:
        """
        Calculate Herfindahl-Hirschman Index (HHI) for market concentration

        HHI = sum of squared market shares
        Range: 0 (perfect competition) to 1 (monopoly)
        - < 0.15: Low concentration (competitive market)
        - 0.15 - 0.25: Moderate concentration
        - > 0.25: High concentration

        Args:
            assignee_counts: Dict of assignee name -> patent count

        Returns:
            HHI value between 0 and 1
        """
        total = sum(assignee_counts.values())
        if total == 0:
            return 0.0

        hhi = sum((count / total) ** 2 for count in assignee_counts.values())
        return hhi

    def _calculate_geographic_metrics(self, patents: List[Patent]) -> Dict:
        """Calculate geographic distribution metrics"""
        logger.info("Calculating patent geographic metrics...")

        country_counts = Counter()

        for patent in patents:
            assignees = patent.assignees or []
            for assignee in assignees:
                country = assignee.get("assignee_country")
                if country:
                    country_counts[country] += 1

        unique_countries = len(country_counts)
        top_countries = country_counts.most_common(10)

        return {
            "country_distribution": dict(country_counts),
            "unique_countries": unique_countries,
            "top_countries": top_countries
        }

    def _calculate_type_metrics(self, patents: List[Patent]) -> Dict:
        """Calculate patent type distribution metrics"""
        logger.info("Calculating patent type metrics...")

        type_counts = Counter()

        for patent in patents:
            patent_type = (patent.patent_type or "unknown").lower()
            type_counts[patent_type] += 1

        total = len(patents)
        utility_pct = (type_counts.get("utility", 0) / total) * 100
        design_pct = (type_counts.get("design", 0) / total) * 100
        other_pct = 100 - utility_pct - design_pct

        return {
            "utility_percentage": utility_pct,
            "design_percentage": design_pct,
            "other_type_percentage": other_pct
        }

    def _calculate_temporal_metrics(self, patents: List[Patent]) -> Dict:
        """Calculate time-based metrics"""
        logger.info("Calculating patent temporal metrics...")

        current_year = datetime.now().year

        # Get all years
        years = [p.patent_year for p in patents if p.patent_year]

        if not years:
            return {
                "first_patent_year": 0,
                "technology_age_years": 0,
                "patents_last_year": 0,
                "patents_last_2_years": 0
            }

        first_year = min(years)
        technology_age = current_year - first_year

        patents_last_year = sum(1 for p in patents if p.patent_year == current_year - 1)
        patents_last_2_years = sum(1 for p in patents if p.patent_year and p.patent_year >= current_year - 2)

        return {
            "first_patent_year": first_year,
            "technology_age_years": technology_age,
            "patents_last_year": patents_last_year,
            "patents_last_2_years": patents_last_2_years
        }

    def _calculate_quality_metrics(self, patents: List[Patent]) -> Dict:
        """Calculate data quality metrics"""
        logger.info("Calculating patent data quality metrics...")

        total = len(patents)
        with_abstract = sum(1 for p in patents if p.patent_abstract)
        coverage = (with_abstract / total) * 100

        return {
            "patents_with_abstract": with_abstract,
            "coverage_percentage": coverage
        }
