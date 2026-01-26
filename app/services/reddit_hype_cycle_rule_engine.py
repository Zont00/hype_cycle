from typing import Dict, Tuple
from dataclasses import dataclass
import logging

from ..models.hype_cycle_phase import HypeCyclePhase, PhaseCharacteristics
from .reddit_metrics_calculator import RedditMetricsSnapshot

logger = logging.getLogger(__name__)


@dataclass
class RedditRuleThresholds:
    """Configurable thresholds for Reddit-based rule evaluation"""

    # Volume thresholds
    low_post_count: int = 50
    high_post_count: int = 500

    # Engagement thresholds
    high_avg_score: float = 100.0
    low_avg_score: float = 20.0
    high_avg_comments: float = 50.0
    low_avg_comments: float = 10.0

    # Trend thresholds
    high_growth_rate: float = 50.0
    decline_threshold: float = -20.0

    # Distribution thresholds
    high_hhi: float = 0.25  # Concentrated discussion
    low_hhi: float = 0.10  # Diverse discussion

    # Subreddit thresholds
    low_subreddit_count: int = 3
    high_subreddit_count: int = 15


class RedditHypeCycleRuleEngine:
    """Rule-based engine for determining Hype Cycle phase from Reddit data"""

    def __init__(self, thresholds: RedditRuleThresholds = None):
        self.thresholds = thresholds or RedditRuleThresholds()

    def determine_phase(self, metrics: RedditMetricsSnapshot) -> Tuple[HypeCyclePhase, float, Dict, str]:
        """
        Determine Hype Cycle phase from Reddit metrics

        Args:
            metrics: Calculated Reddit metrics snapshot

        Returns:
            Tuple of (phase, confidence, rule_scores, rationale)
        """
        logger.info("Determining Hype Cycle phase from Reddit metrics...")

        phase_scores = {
            HypeCyclePhase.TECHNOLOGY_TRIGGER: self._score_technology_trigger(metrics),
            HypeCyclePhase.PEAK_INFLATED_EXPECTATIONS: self._score_peak_inflated(metrics),
            HypeCyclePhase.TROUGH_DISILLUSIONMENT: self._score_trough(metrics),
            HypeCyclePhase.SLOPE_ENLIGHTENMENT: self._score_slope(metrics),
            HypeCyclePhase.PLATEAU_PRODUCTIVITY: self._score_plateau(metrics)
        }

        best_phase = max(phase_scores, key=phase_scores.get)
        confidence = phase_scores[best_phase]

        logger.info(f"Reddit phase determined: {best_phase.value} (confidence: {confidence:.2f})")

        rationale = self._generate_rationale(best_phase, metrics, phase_scores)
        phase_scores_str = {phase.value: score for phase, score in phase_scores.items()}

        return best_phase, confidence, phase_scores_str, rationale

    def _score_technology_trigger(self, m: RedditMetricsSnapshot) -> float:
        """
        Score for Technology Trigger phase

        Reddit Indicators:
        - Few posts (niche topic)
        - Discussion concentrated in tech-specific subreddits
        - Low overall engagement (not mainstream yet)
        - Few unique authors (early enthusiasts)
        """
        score = 0.0

        # Few posts total
        if m.total_posts < self.thresholds.low_post_count:
            score += 0.25

        # Concentrated in few subreddits (niche discussion)
        if m.unique_subreddits < self.thresholds.low_subreddit_count:
            score += 0.25

        # Low average engagement
        if m.avg_score_per_post < self.thresholds.low_avg_score:
            score += 0.20

        # Few unique authors (early community)
        if m.unique_authors < 30:
            score += 0.15

        # High author concentration (few evangelists)
        if m.author_concentration_hhi > self.thresholds.high_hhi:
            score += 0.15

        return min(score, 1.0)

    def _score_peak_inflated(self, m: RedditMetricsSnapshot) -> float:
        """
        Score for Peak of Inflated Expectations

        Reddit Indicators:
        - High posting velocity (buzz)
        - High engagement (viral posts)
        - Discussion spreading to many subreddits
        - Many new authors joining discussion
        - Emerging keywords showing excitement
        """
        score = 0.0

        # High or increasing velocity
        if m.velocity_trend in ["increasing", "peak_reached"]:
            score += 0.25

        # High engagement
        if m.avg_score_per_post > self.thresholds.high_avg_score:
            score += 0.20

        # Many highly engaged posts
        if m.highly_engaged_count > 10:
            score += 0.15

        # Discussion spreading
        if m.unique_subreddits > self.thresholds.low_subreddit_count:
            score += 0.15

        # Low concentration (diverse discussion)
        if m.subreddit_concentration_hhi < self.thresholds.low_hhi:
            score += 0.15

        # Rising engagement trend
        if m.engagement_trend == "increasing":
            score += 0.10

        return min(score, 1.0)

    def _score_trough(self, m: RedditMetricsSnapshot) -> float:
        """
        Score for Trough of Disillusionment

        Reddit Indicators:
        - Declining post velocity
        - Decreasing engagement
        - Declining keywords appear
        - Discussion retracting to core subreddits
        """
        score = 0.0

        # Declining velocity
        if m.velocity_trend == "decreasing":
            score += 0.30

        # Declining engagement
        if m.engagement_trend == "decreasing":
            score += 0.25

        # Negative growth rate
        if m.growth_rate_early_vs_late < self.thresholds.decline_threshold:
            score += 0.20

        # Posts declining from earlier period
        if m.posts_last_3_months < m.posts_first_3_months * 0.5:
            score += 0.15

        # Declining keywords present
        if len(m.declining_keywords) > len(m.emerging_keywords):
            score += 0.10

        return min(score, 1.0)

    def _score_slope(self, m: RedditMetricsSnapshot) -> float:
        """
        Score for Slope of Enlightenment

        Reddit Indicators:
        - Stable posting velocity
        - Moderate but consistent engagement
        - Discussion in multiple relevant subreddits
        - Mix of technical and practical discussions (link posts)
        """
        score = 0.0

        # Stable velocity
        if m.velocity_trend == "stable":
            score += 0.25

        # Stable engagement
        if m.engagement_trend == "stable":
            score += 0.20

        # Moderate subreddit spread
        if self.thresholds.low_subreddit_count <= m.unique_subreddits <= self.thresholds.high_subreddit_count:
            score += 0.20

        # Good mix of post types (practical discussions)
        if 30 <= m.link_post_percentage <= 60:
            score += 0.15

        # Moderate HHI (established communities)
        if self.thresholds.low_hhi <= m.subreddit_concentration_hhi <= self.thresholds.high_hhi:
            score += 0.10

        # Balance of emerging and declining keywords
        if len(m.emerging_keywords) > 0 and len(m.declining_keywords) > 0:
            score += 0.10

        return min(score, 1.0)

    def _score_plateau(self, m: RedditMetricsSnapshot) -> float:
        """
        Score for Plateau of Productivity

        Reddit Indicators:
        - Stable, mature discussion volume
        - High total posts (established topic)
        - Wide subreddit coverage (mainstream)
        - Consistent engagement patterns
        - Many link posts (resources, tools, products)
        """
        score = 0.0

        # High total posts (mature topic)
        if m.total_posts > self.thresholds.high_post_count:
            score += 0.25

        # Stable velocity
        if m.velocity_trend == "stable":
            score += 0.20

        # Wide subreddit spread (mainstream)
        if m.unique_subreddits > self.thresholds.high_subreddit_count:
            score += 0.20

        # Stable engagement
        if m.engagement_trend == "stable":
            score += 0.15

        # High link post percentage (resources, products)
        if m.link_post_percentage > 40:
            score += 0.10

        # Good data quality (established community)
        if m.coverage_percentage > 50:
            score += 0.10

        return min(score, 1.0)

    def _generate_rationale(self, phase: HypeCyclePhase, metrics: RedditMetricsSnapshot,
                           scores: Dict[HypeCyclePhase, float]) -> str:
        """Generate human-readable explanation for Reddit-based phase determination"""

        phase_info = PhaseCharacteristics.PHASE_DEFINITIONS[phase]

        rationale_parts = [
            f"Reddit-based Phase: {phase_info['name']}",
            f"Confidence score: {scores[phase]:.2f}",
            "",
            "Key Reddit indicators:",
        ]

        if phase == HypeCyclePhase.TECHNOLOGY_TRIGGER:
            rationale_parts.extend([
                f"- Total posts: {metrics.total_posts} (niche topic)",
                f"- Unique subreddits: {metrics.unique_subreddits} (concentrated)",
                f"- Avg score: {metrics.avg_score_per_post:.1f} (low mainstream interest)",
                f"- Unique authors: {metrics.unique_authors} (early community)"
            ])

        elif phase == HypeCyclePhase.PEAK_INFLATED_EXPECTATIONS:
            rationale_parts.extend([
                f"- Velocity trend: {metrics.velocity_trend} (high activity)",
                f"- Avg score: {metrics.avg_score_per_post:.1f} (high engagement)",
                f"- Highly engaged posts: {metrics.highly_engaged_count}",
                f"- Unique subreddits: {metrics.unique_subreddits} (spreading)",
                f"- Engagement trend: {metrics.engagement_trend}"
            ])

        elif phase == HypeCyclePhase.TROUGH_DISILLUSIONMENT:
            rationale_parts.extend([
                f"- Velocity trend: {metrics.velocity_trend} (declining)",
                f"- Engagement trend: {metrics.engagement_trend}",
                f"- Growth rate: {metrics.growth_rate_early_vs_late:.1f}%",
                f"- Declining keywords: {len(metrics.declining_keywords)}"
            ])

        elif phase == HypeCyclePhase.SLOPE_ENLIGHTENMENT:
            rationale_parts.extend([
                f"- Velocity trend: {metrics.velocity_trend} (stable)",
                f"- Engagement trend: {metrics.engagement_trend}",
                f"- Unique subreddits: {metrics.unique_subreddits}",
                f"- Link posts: {metrics.link_post_percentage:.1f}% (practical focus)"
            ])

        elif phase == HypeCyclePhase.PLATEAU_PRODUCTIVITY:
            rationale_parts.extend([
                f"- Total posts: {metrics.total_posts} (mature topic)",
                f"- Velocity trend: {metrics.velocity_trend}",
                f"- Unique subreddits: {metrics.unique_subreddits} (mainstream)",
                f"- Link posts: {metrics.link_post_percentage:.1f}%"
            ])

        # Add top subreddits
        rationale_parts.append("")
        rationale_parts.append("Top subreddits:")
        for subreddit, count in metrics.top_subreddits[:5]:
            rationale_parts.append(f"  - r/{subreddit}: {count} posts")

        # Add phase scores comparison
        rationale_parts.append("")
        rationale_parts.append("Phase scores (Reddit-based):")
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        for p, s in sorted_scores:
            phase_name = PhaseCharacteristics.PHASE_DEFINITIONS[p]["name"]
            rationale_parts.append(f"  {phase_name}: {s:.2f}")

        return "\n".join(rationale_parts)
