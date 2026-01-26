from typing import Dict, Tuple
from dataclasses import dataclass
import logging

from ..models.hype_cycle_phase import HypeCyclePhase, PhaseCharacteristics
from .news_metrics_calculator import NewsMetricsSnapshot

logger = logging.getLogger(__name__)


@dataclass
class NewsRuleThresholds:
    """Configurable thresholds for News-based rule evaluation"""

    # Volume thresholds
    low_article_count: int = 30
    high_article_count: int = 300

    # Growth thresholds
    high_growth_rate: float = 50.0
    decline_threshold: float = -20.0

    # Source thresholds
    low_source_count: int = 5
    high_source_count: int = 20

    # Concentration thresholds
    high_hhi: float = 0.25
    low_hhi: float = 0.10


class NewsHypeCycleRuleEngine:
    """Rule-based engine for determining Hype Cycle phase from News data"""

    def __init__(self, thresholds: NewsRuleThresholds = None):
        self.thresholds = thresholds or NewsRuleThresholds()

    def determine_phase(self, metrics: NewsMetricsSnapshot) -> Tuple[HypeCyclePhase, float, Dict, str]:
        """
        Determine Hype Cycle phase from News metrics

        Args:
            metrics: Calculated News metrics snapshot

        Returns:
            Tuple of (phase, confidence, rule_scores, rationale)
        """
        logger.info("Determining Hype Cycle phase from News metrics...")

        phase_scores = {
            HypeCyclePhase.TECHNOLOGY_TRIGGER: self._score_technology_trigger(metrics),
            HypeCyclePhase.PEAK_INFLATED_EXPECTATIONS: self._score_peak_inflated(metrics),
            HypeCyclePhase.TROUGH_DISILLUSIONMENT: self._score_trough(metrics),
            HypeCyclePhase.SLOPE_ENLIGHTENMENT: self._score_slope(metrics),
            HypeCyclePhase.PLATEAU_PRODUCTIVITY: self._score_plateau(metrics)
        }

        best_phase = max(phase_scores, key=phase_scores.get)
        confidence = phase_scores[best_phase]

        logger.info(f"News phase determined: {best_phase.value} (confidence: {confidence:.2f})")

        rationale = self._generate_rationale(best_phase, metrics, phase_scores)
        phase_scores_str = {phase.value: score for phase, score in phase_scores.items()}

        return best_phase, confidence, phase_scores_str, rationale

    def _score_technology_trigger(self, m: NewsMetricsSnapshot) -> float:
        """
        Score for Technology Trigger phase

        News Indicators:
        - Few articles (limited media attention)
        - Coverage from specialized/tech sources only
        - Few sources covering the topic
        - Limited author diversity
        """
        score = 0.0

        # Few articles
        if m.total_articles < self.thresholds.low_article_count:
            score += 0.30

        # Few sources (niche coverage)
        if m.unique_sources < self.thresholds.low_source_count:
            score += 0.25

        # High source concentration (specialized media)
        if m.source_concentration_hhi > self.thresholds.high_hhi:
            score += 0.20

        # Few authors covering
        if m.unique_authors < 20:
            score += 0.15

        # Many articles without author (press releases, wire services)
        if m.articles_without_author_percentage > 40:
            score += 0.10

        return min(score, 1.0)

    def _score_peak_inflated(self, m: NewsMetricsSnapshot) -> float:
        """
        Score for Peak of Inflated Expectations

        News Indicators:
        - High/increasing publication velocity (media frenzy)
        - Coverage from many diverse sources
        - Low source concentration (everyone covering)
        - Recent or current peak
        - Many emerging keywords (hype words)
        """
        score = 0.0

        # High or increasing velocity
        if m.velocity_trend in ["increasing", "peak_reached"]:
            score += 0.30

        # Many sources covering
        if m.unique_sources > self.thresholds.low_source_count:
            score += 0.20

        # Low concentration (broad coverage)
        if m.source_concentration_hhi < self.thresholds.low_hhi:
            score += 0.20

        # High recent activity
        if m.recent_velocity > m.avg_articles_per_month * 1.2:
            score += 0.15

        # Many emerging keywords (new hype terms)
        if len(m.emerging_keywords) > 5:
            score += 0.15

        return min(score, 1.0)

    def _score_trough(self, m: NewsMetricsSnapshot) -> float:
        """
        Score for Trough of Disillusionment

        News Indicators:
        - Declining article velocity
        - Sources dropping coverage
        - Declining keywords appear
        - Negative growth rate
        """
        score = 0.0

        # Declining velocity
        if m.velocity_trend == "decreasing":
            score += 0.35

        # Negative growth rate
        if m.growth_rate_early_vs_late < self.thresholds.decline_threshold:
            score += 0.25

        # Recent articles much fewer than earlier
        if m.articles_last_3_months < m.articles_first_3_months * 0.5:
            score += 0.20

        # More declining than emerging keywords
        if len(m.declining_keywords) > len(m.emerging_keywords):
            score += 0.10

        # Increasing source concentration (fewer sources remaining)
        if m.source_concentration_hhi > self.thresholds.low_hhi:
            score += 0.10

        return min(score, 1.0)

    def _score_slope(self, m: NewsMetricsSnapshot) -> float:
        """
        Score for Slope of Enlightenment

        News Indicators:
        - Stable publication velocity
        - Moderate source diversity
        - Balance of emerging and practical keywords
        - Coverage focused on use cases
        """
        score = 0.0

        # Stable velocity
        if m.velocity_trend == "stable":
            score += 0.30

        # Moderate source coverage
        if self.thresholds.low_source_count <= m.unique_sources <= self.thresholds.high_source_count:
            score += 0.25

        # Moderate HHI (established coverage pattern)
        if self.thresholds.low_hhi <= m.source_concentration_hhi <= self.thresholds.high_hhi:
            score += 0.20

        # Balance of keywords
        if len(m.emerging_keywords) > 0 and len(m.declining_keywords) > 0:
            score += 0.15

        # Good data quality
        if m.coverage_percentage > 60:
            score += 0.10

        return min(score, 1.0)

    def _score_plateau(self, m: NewsMetricsSnapshot) -> float:
        """
        Score for Plateau of Productivity

        News Indicators:
        - High total article count (established topic)
        - Stable velocity
        - Wide source coverage (mainstream)
        - Consistent coverage patterns
        """
        score = 0.0

        # High article count (mature topic)
        if m.total_articles > self.thresholds.high_article_count:
            score += 0.25

        # Stable velocity
        if m.velocity_trend == "stable":
            score += 0.25

        # Wide source coverage
        if m.unique_sources > self.thresholds.high_source_count:
            score += 0.20

        # Low HHI (mainstream coverage)
        if m.source_concentration_hhi < self.thresholds.low_hhi:
            score += 0.15

        # Good content quality
        if m.coverage_percentage > 70:
            score += 0.15

        return min(score, 1.0)

    def _generate_rationale(self, phase: HypeCyclePhase, metrics: NewsMetricsSnapshot,
                           scores: Dict[HypeCyclePhase, float]) -> str:
        """Generate human-readable explanation for News-based phase determination"""

        phase_info = PhaseCharacteristics.PHASE_DEFINITIONS[phase]

        rationale_parts = [
            f"News-based Phase: {phase_info['name']}",
            f"Confidence score: {scores[phase]:.2f}",
            "",
            "Key News indicators:",
        ]

        if phase == HypeCyclePhase.TECHNOLOGY_TRIGGER:
            rationale_parts.extend([
                f"- Total articles: {metrics.total_articles} (limited coverage)",
                f"- Unique sources: {metrics.unique_sources} (niche media)",
                f"- Source HHI: {metrics.source_concentration_hhi:.3f} (concentrated)",
                f"- Unique authors: {metrics.unique_authors}"
            ])

        elif phase == HypeCyclePhase.PEAK_INFLATED_EXPECTATIONS:
            rationale_parts.extend([
                f"- Velocity trend: {metrics.velocity_trend} (media frenzy)",
                f"- Unique sources: {metrics.unique_sources} (broad coverage)",
                f"- Source HHI: {metrics.source_concentration_hhi:.3f} (diverse)",
                f"- Emerging keywords: {len(metrics.emerging_keywords)} (hype terms)"
            ])

        elif phase == HypeCyclePhase.TROUGH_DISILLUSIONMENT:
            rationale_parts.extend([
                f"- Velocity trend: {metrics.velocity_trend} (declining)",
                f"- Growth rate: {metrics.growth_rate_early_vs_late:.1f}%",
                f"- Articles last 3 months: {metrics.articles_last_3_months}",
                f"- Declining keywords: {len(metrics.declining_keywords)}"
            ])

        elif phase == HypeCyclePhase.SLOPE_ENLIGHTENMENT:
            rationale_parts.extend([
                f"- Velocity trend: {metrics.velocity_trend} (stable)",
                f"- Unique sources: {metrics.unique_sources}",
                f"- Source HHI: {metrics.source_concentration_hhi:.3f}",
                f"- Data coverage: {metrics.coverage_percentage:.1f}%"
            ])

        elif phase == HypeCyclePhase.PLATEAU_PRODUCTIVITY:
            rationale_parts.extend([
                f"- Total articles: {metrics.total_articles} (established)",
                f"- Velocity trend: {metrics.velocity_trend}",
                f"- Unique sources: {metrics.unique_sources} (mainstream)",
                f"- Source HHI: {metrics.source_concentration_hhi:.3f}"
            ])

        # Add top sources
        rationale_parts.append("")
        rationale_parts.append("Top news sources:")
        for source, count in metrics.top_sources[:5]:
            rationale_parts.append(f"  - {source}: {count} articles")

        # Add phase scores comparison
        rationale_parts.append("")
        rationale_parts.append("Phase scores (News-based):")
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        for p, s in sorted_scores:
            phase_name = PhaseCharacteristics.PHASE_DEFINITIONS[p]["name"]
            rationale_parts.append(f"  {phase_name}: {s:.2f}")

        return "\n".join(rationale_parts)
