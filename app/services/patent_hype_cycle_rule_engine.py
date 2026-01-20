from typing import Dict, Tuple
from dataclasses import dataclass
import logging

from ..models.hype_cycle_phase import HypeCyclePhase, PhaseCharacteristics
from .patent_metrics_calculator import PatentMetricsSnapshot

logger = logging.getLogger(__name__)


@dataclass
class PatentRuleThresholds:
    """Configurable thresholds for patent-based rule evaluation"""

    # Volume thresholds
    low_patent_count: int = 50  # Below this = early stage
    high_patent_count: int = 500  # Above this = mature

    # Velocity thresholds
    high_growth_rate: float = 50.0  # % YoY increase = rapid growth
    moderate_growth_rate: float = 20.0  # % YoY increase = moderate
    decline_threshold: float = -10.0  # % decline

    # Citation thresholds
    high_citation_ratio: float = 1.0  # forward/backward > 1 = influential
    low_citation_ratio: float = 0.3  # < 0.3 = derivative/early

    # Assignee thresholds
    high_hhi: float = 0.25  # Concentrated market (few players)
    low_hhi: float = 0.10  # Competitive market (many players)
    high_corporate_pct: float = 80.0  # Corporate dominated
    high_academic_pct: float = 50.0  # Academic dominated (early stage)

    # Geographic thresholds
    low_country_spread: int = 5  # Few countries = niche
    high_country_spread: int = 20  # Many countries = global

    # Temporal thresholds
    young_technology_years: int = 5  # < 5 years = early
    mature_technology_years: int = 15  # > 15 years = mature
    recent_peak_years: int = 3  # Peak within last 3 years

    # Patent type thresholds
    high_utility_pct: float = 70.0  # High utility = R&D focus
    high_design_pct: float = 20.0  # High design = product focus


class PatentHypeCycleRuleEngine:
    """Rule-based engine for determining Hype Cycle phase from patent data"""

    def __init__(self, thresholds: PatentRuleThresholds = None):
        self.thresholds = thresholds or PatentRuleThresholds()

    def determine_phase(self, metrics: PatentMetricsSnapshot) -> Tuple[HypeCyclePhase, float, Dict, str]:
        """
        Determine Hype Cycle phase from patent metrics

        Args:
            metrics: Calculated patent metrics snapshot

        Returns:
            Tuple of (phase, confidence, rule_scores, rationale)
        """
        logger.info("Determining Hype Cycle phase from patent metrics...")

        # Score each phase based on rules
        phase_scores = {
            HypeCyclePhase.TECHNOLOGY_TRIGGER: self._score_technology_trigger(metrics),
            HypeCyclePhase.PEAK_INFLATED_EXPECTATIONS: self._score_peak_inflated(metrics),
            HypeCyclePhase.TROUGH_DISILLUSIONMENT: self._score_trough(metrics),
            HypeCyclePhase.SLOPE_ENLIGHTENMENT: self._score_slope(metrics),
            HypeCyclePhase.PLATEAU_PRODUCTIVITY: self._score_plateau(metrics)
        }

        # Find highest scoring phase
        best_phase = max(phase_scores, key=phase_scores.get)
        confidence = phase_scores[best_phase]

        logger.info(f"Patent phase determined: {best_phase.value} (confidence: {confidence:.2f})")

        # Generate rationale
        rationale = self._generate_rationale(best_phase, metrics, phase_scores)

        # Convert enum keys to strings for JSON serialization
        phase_scores_str = {phase.value: score for phase, score in phase_scores.items()}

        return best_phase, confidence, phase_scores_str, rationale

    def _score_technology_trigger(self, m: PatentMetricsSnapshot) -> float:
        """
        Score for Technology Trigger phase

        Patent Indicators:
        - Few patents total (<50)
        - Mainly academic/research institutions (>50% academic)
        - Low forward citations (patents too new)
        - Few assignees (concentrated, early players)
        - First patent recent (<5 years)
        - High utility patent percentage (R&D focus)
        """
        score = 0.0

        # Few patents total
        if m.total_patents < self.thresholds.low_patent_count:
            score += 0.25

        # High academic percentage
        if m.academic_percentage > self.thresholds.high_academic_pct:
            score += 0.25

        # Low forward citations (new patents not yet cited)
        if m.avg_forward_citations < 2:
            score += 0.15

        # Young technology
        if m.technology_age_years < self.thresholds.young_technology_years:
            score += 0.15

        # Few unique assignees (early entrants only)
        if m.unique_assignees_count < 20:
            score += 0.1

        # Low geographic spread
        if m.unique_countries < self.thresholds.low_country_spread:
            score += 0.1

        return min(score, 1.0)

    def _score_peak_inflated(self, m: PatentMetricsSnapshot) -> float:
        """
        Score for Peak of Inflated Expectations

        Patent Indicators:
        - Rapid patent growth (>50% YoY)
        - Many new entrants (high new_entrants rate)
        - Shift from academic to corporate (40-60% corporate)
        - Peak year recent or current
        - Growing geographic spread
        - Low HHI (many players competing)
        """
        score = 0.0

        # Check if at or near peak
        if m.patent_velocity:
            current_year = max(m.patent_velocity.keys())
            years_since_peak = current_year - m.peak_year
            if years_since_peak <= self.thresholds.recent_peak_years:
                score += 0.25

        # Velocity increasing or at peak
        if m.velocity_trend in ["increasing", "peak_reached"]:
            score += 0.25

        # Mixed corporate/academic (transition phase)
        if 40 <= m.corporate_percentage <= 70:
            score += 0.15

        # Low concentration (many competitors entering)
        if m.assignee_concentration_hhi < self.thresholds.low_hhi:
            score += 0.15

        # High recent activity
        if m.recent_velocity > m.avg_patents_per_year * 1.2:
            score += 0.1

        # Growing number of countries
        if self.thresholds.low_country_spread < m.unique_countries < self.thresholds.high_country_spread:
            score += 0.1

        return min(score, 1.0)

    def _score_trough(self, m: PatentMetricsSnapshot) -> float:
        """
        Score for Trough of Disillusionment

        Patent Indicators:
        - Declining patent velocity
        - Recent peak followed by decline
        - Some assignees exiting (concentration may increase)
        - Forward citations slowing
        - Corporate still dominant but fewer new entrants
        """
        score = 0.0

        # Declining velocity
        if m.velocity_trend == "decreasing":
            score += 0.30

        # Peak was recent but now declining (1-5 years ago)
        if m.patent_velocity:
            current_year = max(m.patent_velocity.keys())
            years_since_peak = current_year - m.peak_year
            if 1 <= years_since_peak <= 5:
                score += 0.25

        # Recent patents significantly less than peak
        if m.patents_last_year < m.peak_count * 0.6:
            score += 0.15

        # Low citation ratio (patents cite more than they're cited)
        if m.citation_ratio < self.thresholds.low_citation_ratio:
            score += 0.15

        # Moderate concentration (some consolidation)
        if self.thresholds.low_hhi <= m.assignee_concentration_hhi <= self.thresholds.high_hhi:
            score += 0.1

        # New entrants declining (check if recent years have fewer new entrants)
        if m.new_entrants_by_year:
            recent_years = sorted(m.new_entrants_by_year.keys())[-3:]
            if len(recent_years) >= 2:
                recent_entrants = sum(m.new_entrants_by_year.get(y, 0) for y in recent_years[-2:])
                earlier_entrants = sum(m.new_entrants_by_year.get(y, 0) for y in recent_years[:-2]) if len(recent_years) > 2 else recent_entrants
                if recent_entrants < earlier_entrants * 0.8:
                    score += 0.05

        return min(score, 1.0)

    def _score_slope(self, m: PatentMetricsSnapshot) -> float:
        """
        Score for Slope of Enlightenment

        Patent Indicators:
        - Stable or gradual patent increase after decline
        - Corporate dominant (70-85%)
        - Selective new entrants (quality over quantity)
        - Stable citation patterns
        - Moderate concentration (established players)
        - Mix of utility and design patents (products emerging)
        """
        score = 0.0

        # Stable velocity
        if m.velocity_trend == "stable":
            score += 0.25

        # High corporate percentage (industry-led)
        if 70 <= m.corporate_percentage < 90:
            score += 0.20

        # Peak was 4-10 years ago (recovered from trough)
        if m.patent_velocity:
            current_year = max(m.patent_velocity.keys())
            years_since_peak = current_year - m.peak_year
            if 4 <= years_since_peak <= 10:
                score += 0.20

        # Moderate HHI (established competitive landscape)
        if self.thresholds.low_hhi <= m.assignee_concentration_hhi <= self.thresholds.high_hhi:
            score += 0.15

        # Good geographic spread (international adoption)
        if m.unique_countries >= self.thresholds.low_country_spread:
            score += 0.1

        # Moderate citation ratio
        if 0.3 <= m.citation_ratio <= 1.0:
            score += 0.1

        return min(score, 1.0)

    def _score_plateau(self, m: PatentMetricsSnapshot) -> float:
        """
        Score for Plateau of Productivity

        Patent Indicators:
        - Stable patent volume (plateau)
        - Few large players dominate (high HHI)
        - Very high corporate percentage (>85%)
        - High forward citations on key patents
        - Wide geographic spread
        - Mature technology (>10 years)
        - Mix of utility and design patents
        """
        score = 0.0

        # Stable velocity (plateau)
        if m.velocity_trend == "stable":
            score += 0.20

        # Very high corporate percentage
        if m.corporate_percentage > 85:
            score += 0.20

        # High concentration (few dominant players)
        if m.assignee_concentration_hhi > self.thresholds.high_hhi:
            score += 0.15

        # Mature technology
        if m.technology_age_years > self.thresholds.mature_technology_years:
            score += 0.15

        # Wide geographic spread (global adoption)
        if m.unique_countries >= self.thresholds.high_country_spread:
            score += 0.1

        # High citation ratio (influential patents)
        if m.citation_ratio > self.thresholds.high_citation_ratio:
            score += 0.1

        # Peak was long ago (>10 years)
        if m.patent_velocity:
            current_year = max(m.patent_velocity.keys())
            years_since_peak = current_year - m.peak_year
            if years_since_peak > 10:
                score += 0.1

        return min(score, 1.0)

    def _generate_rationale(self, phase: HypeCyclePhase, metrics: PatentMetricsSnapshot,
                           scores: Dict[HypeCyclePhase, float]) -> str:
        """Generate human-readable explanation for patent-based phase determination"""

        phase_info = PhaseCharacteristics.PHASE_DEFINITIONS[phase]

        rationale_parts = [
            f"Patent-based Phase: {phase_info['name']}",
            f"Confidence score: {scores[phase]:.2f}",
            "",
            "Key patent indicators:",
        ]

        # Add phase-specific rationale
        if phase == HypeCyclePhase.TECHNOLOGY_TRIGGER:
            rationale_parts.extend([
                f"- Total patents: {metrics.total_patents} (early stage)",
                f"- Academic percentage: {metrics.academic_percentage:.1f}% (research-driven)",
                f"- Technology age: {metrics.technology_age_years} years (young)",
                f"- Avg forward citations: {metrics.avg_forward_citations:.1f} (low, patents too new)",
                f"- Unique assignees: {metrics.unique_assignees_count} (few early players)"
            ])

        elif phase == HypeCyclePhase.PEAK_INFLATED_EXPECTATIONS:
            rationale_parts.extend([
                f"- Peak year: {metrics.peak_year} (recent)",
                f"- Velocity trend: {metrics.velocity_trend} (high activity)",
                f"- Corporate percentage: {metrics.corporate_percentage:.1f}% (transitioning)",
                f"- HHI concentration: {metrics.assignee_concentration_hhi:.3f} (many competitors)",
                f"- Recent velocity: {metrics.recent_velocity:.1f} patents/year"
            ])

        elif phase == HypeCyclePhase.TROUGH_DISILLUSIONMENT:
            rationale_parts.extend([
                f"- Velocity trend: {metrics.velocity_trend} (declining)",
                f"- Peak was in {metrics.peak_year}, now declining",
                f"- Patents last year: {metrics.patents_last_year} (down from peak: {metrics.peak_count})",
                f"- Citation ratio: {metrics.citation_ratio:.2f} (low impact)",
                f"- New entrants declining (consolidation phase)"
            ])

        elif phase == HypeCyclePhase.SLOPE_ENLIGHTENMENT:
            rationale_parts.extend([
                f"- Velocity trend: {metrics.velocity_trend} (stabilizing)",
                f"- Corporate percentage: {metrics.corporate_percentage:.1f}% (industry-led)",
                f"- HHI concentration: {metrics.assignee_concentration_hhi:.3f} (established players)",
                f"- Geographic spread: {metrics.unique_countries} countries",
                f"- Years since peak: {max(metrics.patent_velocity.keys()) - metrics.peak_year if metrics.patent_velocity else 'N/A'}"
            ])

        elif phase == HypeCyclePhase.PLATEAU_PRODUCTIVITY:
            rationale_parts.extend([
                f"- Velocity trend: {metrics.velocity_trend} (stable plateau)",
                f"- Corporate percentage: {metrics.corporate_percentage:.1f}% (industry dominated)",
                f"- HHI concentration: {metrics.assignee_concentration_hhi:.3f} (consolidated)",
                f"- Technology age: {metrics.technology_age_years} years (mature)",
                f"- Geographic spread: {metrics.unique_countries} countries (global)"
            ])

        # Add top assignees
        rationale_parts.append("")
        rationale_parts.append("Top patent holders:")
        for name, count in metrics.top_assignees[:5]:
            rationale_parts.append(f"  - {name}: {count} patents")

        # Add comparison with other phases
        rationale_parts.append("")
        rationale_parts.append("Phase scores (patent-based):")
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        for p, s in sorted_scores:
            phase_name = PhaseCharacteristics.PHASE_DEFINITIONS[p]["name"]
            rationale_parts.append(f"  {phase_name}: {s:.2f}")

        return "\n".join(rationale_parts)
