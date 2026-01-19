from typing import Dict, Tuple
from dataclasses import dataclass
import logging

from ..models.hype_cycle_phase import HypeCyclePhase, PhaseCharacteristics
from .paper_metrics_calculator import MetricsSnapshot

logger = logging.getLogger(__name__)


@dataclass
class RuleThresholds:
    """Configurable thresholds for rule evaluation"""

    # Velocity thresholds
    velocity_growth_threshold: float = 20.0  # % increase = increasing
    velocity_decline_threshold: float = -15.0  # % decrease = declining

    # Citation thresholds
    high_citation_threshold: int = 100
    citation_growth_high: float = 30.0  # % = rapid growth
    citation_growth_moderate: float = 10.0  # % = moderate growth

    # Research type thresholds
    basic_research_high: float = 70.0  # % = mostly basic
    applied_research_high: float = 60.0  # % = mostly applied
    applied_research_very_high: float = 80.0  # % = overwhelmingly applied

    # Temporal thresholds
    peak_recency_years: int = 3  # peak within last N years

    # Confidence thresholds
    min_papers_for_analysis: int = 100
    high_confidence_threshold: float = 0.8


class HypeCycleRuleEngine:
    """Rule-based engine for determining Hype Cycle phase"""

    def __init__(self, thresholds: RuleThresholds = None):
        self.thresholds = thresholds or RuleThresholds()

    def determine_phase(self, metrics: MetricsSnapshot) -> Tuple[HypeCyclePhase, float, Dict, str]:
        """
        Determine Hype Cycle phase from metrics

        Args:
            metrics: Calculated metrics snapshot

        Returns:
            Tuple of (phase, confidence, rule_scores, rationale)
        """
        logger.info("Determining Hype Cycle phase from metrics...")

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

        logger.info(f"Phase determined: {best_phase.value} (confidence: {confidence:.2f})")

        # Generate rationale
        rationale = self._generate_rationale(best_phase, metrics, phase_scores)

        # Convert enum keys to strings for JSON serialization
        phase_scores_str = {phase.value: score for phase, score in phase_scores.items()}

        return best_phase, confidence, phase_scores_str, rationale

    def _score_technology_trigger(self, m: MetricsSnapshot) -> float:
        """
        Score for Technology Trigger phase

        Indicators:
        - Rapid publication growth (early stage)
        - High % basic research (>70%)
        - Low average citations (papers too new)
        - Academic venues dominant
        """
        score = 0.0

        # Check if in early growth phase
        if m.velocity_trend == "increasing" and m.growth_rate_early_vs_late > 50:
            score += 0.3

        # High basic research percentage
        if m.basic_research_percentage > self.thresholds.basic_research_high:
            score += 0.25

        # Low citations (avg < 20)
        if m.avg_citations_per_paper < 20:
            score += 0.2

        # Academic venues (>90%)
        if m.academic_venue_percentage > 90:
            score += 0.15

        # Recent activity relatively low compared to total
        years_span = len(m.publication_velocity)
        if years_span > 0:
            expected_recent = (len(m.publication_velocity) * m.avg_papers_per_year / years_span) * 2
            if m.papers_last_2_years < expected_recent:
                score += 0.1

        return min(score, 1.0)

    def _score_peak_inflated(self, m: MetricsSnapshot) -> float:
        """
        Score for Peak of Inflated Expectations

        Indicators:
        - At or near peak publication velocity
        - Rapid citation growth
        - Shift toward applied research (40-60%)
        - Emerging keywords about breakthroughs
        """
        score = 0.0

        # Check if at peak or just passed it
        if m.publication_velocity:
            current_year = max(m.publication_velocity.keys())
            years_since_peak = current_year - m.peak_year
            if years_since_peak <= self.thresholds.peak_recency_years:
                score += 0.3

        # High citation growth rate
        if m.citation_growth_rate > self.thresholds.citation_growth_high:
            score += 0.25

        # Mixed research types with increasing applied
        if 40 <= m.applied_research_percentage <= 60 and m.research_type_trend == "toward_applied":
            score += 0.25

        # High publication velocity
        if m.velocity_trend in ["increasing", "peak_reached"]:
            score += 0.2

        return min(score, 1.0)

    def _score_trough(self, m: MetricsSnapshot) -> float:
        """
        Score for Trough of Disillusionment

        Indicators:
        - Declining publication velocity
        - Stagnant citations
        - Recent peak followed by decline
        """
        score = 0.0

        # Declining velocity
        if m.velocity_trend == "decreasing":
            score += 0.35

        # Peak was recent but velocity declining
        if m.publication_velocity:
            current_year = max(m.publication_velocity.keys())
            years_since_peak = current_year - m.peak_year
            if 1 <= years_since_peak <= 3:
                score += 0.3

        # Low citation growth
        if m.citation_growth_rate < self.thresholds.citation_growth_moderate:
            score += 0.2

        # Papers in last year significantly less than peak
        if m.papers_last_year < m.peak_count * 0.7:
            score += 0.15

        return min(score, 1.0)

    def _score_slope(self, m: MetricsSnapshot) -> float:
        """
        Score for Slope of Enlightenment

        Indicators:
        - Gradual increase in publications after trough
        - High applied research (60-80%)
        - Steady citation growth
        - Focus on implementations
        """
        score = 0.0

        # Moderate applied research percentage
        if self.thresholds.applied_research_high <= m.applied_research_percentage < self.thresholds.applied_research_very_high:
            score += 0.3

        # Stable or gradually increasing velocity
        if m.velocity_trend in ["stable", "increasing"] and m.growth_rate_early_vs_late > 0:
            score += 0.25

        # Moderate citation growth
        if self.thresholds.citation_growth_moderate <= m.citation_growth_rate < self.thresholds.citation_growth_high:
            score += 0.25

        # Peak was a while ago (4-7 years)
        if m.publication_velocity:
            current_year = max(m.publication_velocity.keys())
            years_since_peak = current_year - m.peak_year
            if 4 <= years_since_peak <= 7:
                score += 0.2

        return min(score, 1.0)

    def _score_plateau(self, m: MetricsSnapshot) -> float:
        """
        Score for Plateau of Productivity

        Indicators:
        - Stable publication velocity (plateau)
        - Very high applied research (>80%)
        - High citations on established papers
        - Industry focus
        """
        score = 0.0

        # Very high applied research
        if m.applied_research_percentage > self.thresholds.applied_research_very_high:
            score += 0.35

        # Stable velocity
        if m.velocity_trend == "stable":
            score += 0.25

        # High average citations
        if m.avg_citations_per_paper > 50:
            score += 0.2

        # Industry venues
        if m.industry_venue_percentage > 30:
            score += 0.1

        # Peak was long ago (8+ years)
        if m.publication_velocity:
            current_year = max(m.publication_velocity.keys())
            years_since_peak = current_year - m.peak_year
            if years_since_peak >= 8:
                score += 0.1

        return min(score, 1.0)

    def _generate_rationale(self, phase: HypeCyclePhase, metrics: MetricsSnapshot,
                           scores: Dict[HypeCyclePhase, float]) -> str:
        """Generate human-readable explanation for phase determination"""

        phase_info = PhaseCharacteristics.PHASE_DEFINITIONS[phase]

        rationale_parts = [
            f"Phase determined: {phase_info['name']}",
            f"Confidence score: {scores[phase]:.2f}",
            "",
            "Key indicators:",
        ]

        # Add phase-specific rationale
        if phase == HypeCyclePhase.TECHNOLOGY_TRIGGER:
            rationale_parts.extend([
                f"- High basic research percentage: {metrics.basic_research_percentage:.1f}%",
                f"- Publication trend: {metrics.velocity_trend}",
                f"- Average citations: {metrics.avg_citations_per_paper:.1f} (low, indicating early stage)",
                f"- Academic venue dominance: {metrics.academic_venue_percentage:.1f}%"
            ])

        elif phase == HypeCyclePhase.PEAK_INFLATED_EXPECTATIONS:
            rationale_parts.extend([
                f"- Peak publication year: {metrics.peak_year} ({metrics.peak_count} papers)",
                f"- Citation growth rate: {metrics.citation_growth_rate:.1f}% (rapid)",
                f"- Applied research percentage: {metrics.applied_research_percentage:.1f}% (increasing)",
                f"- Research type trend: {metrics.research_type_trend}"
            ])

        elif phase == HypeCyclePhase.TROUGH_DISILLUSIONMENT:
            rationale_parts.extend([
                f"- Publication velocity: {metrics.velocity_trend} (declining)",
                f"- Peak was in {metrics.peak_year}, now declining",
                f"- Papers last year: {metrics.papers_last_year} (down from peak: {metrics.peak_count})",
                f"- Citation growth: {metrics.citation_growth_rate:.1f}% (stagnant)"
            ])

        elif phase == HypeCyclePhase.SLOPE_ENLIGHTENMENT:
            rationale_parts.extend([
                f"- Applied research percentage: {metrics.applied_research_percentage:.1f}% (high)",
                f"- Publication trend: {metrics.velocity_trend} (stable/gradual growth)",
                f"- Citation growth: {metrics.citation_growth_rate:.1f}% (moderate)",
                f"- Research focus: shifting to practical implementations"
            ])

        elif phase == HypeCyclePhase.PLATEAU_PRODUCTIVITY:
            rationale_parts.extend([
                f"- Applied research percentage: {metrics.applied_research_percentage:.1f}% (very high)",
                f"- Publication velocity: {metrics.velocity_trend} (stable plateau)",
                f"- Average citations: {metrics.avg_citations_per_paper:.1f} (well-established)",
                f"- Industry involvement: {metrics.industry_venue_percentage:.1f}%"
            ])

        # Add comparison with other phases
        rationale_parts.append("")
        rationale_parts.append("Phase scores (for comparison):")
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        for p, s in sorted_scores:
            phase_name = PhaseCharacteristics.PHASE_DEFINITIONS[p]["name"]
            rationale_parts.append(f"  {phase_name}: {s:.2f}")

        return "\n".join(rationale_parts)
