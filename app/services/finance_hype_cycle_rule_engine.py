from typing import Dict, Tuple
from dataclasses import dataclass
import logging

from ..models.hype_cycle_phase import HypeCyclePhase, PhaseCharacteristics
from .finance_metrics_calculator import FinanceMetricsSnapshot

logger = logging.getLogger(__name__)


@dataclass
class FinanceRuleThresholds:
    """Configurable thresholds for Finance-based rule evaluation"""

    # Return thresholds
    high_return: float = 50.0  # % total return
    low_return: float = -20.0  # % total return
    moderate_return_low: float = 5.0
    moderate_return_high: float = 30.0

    # Volatility thresholds
    high_volatility: float = 3.0  # % daily std
    low_volatility: float = 1.0

    # Volume thresholds
    high_volume_growth: float = 50.0  # % increase
    low_volume_growth: float = -30.0

    # Drawdown thresholds
    severe_drawdown: float = 40.0  # %
    moderate_drawdown: float = 20.0

    # Price trend thresholds
    strong_bullish: float = 30.0  # % 3-month change
    strong_bearish: float = -20.0


class FinanceHypeCycleRuleEngine:
    """Rule-based engine for determining Hype Cycle phase from Finance data"""

    def __init__(self, thresholds: FinanceRuleThresholds = None):
        self.thresholds = thresholds or FinanceRuleThresholds()

    def determine_phase(self, metrics: FinanceMetricsSnapshot) -> Tuple[HypeCyclePhase, float, Dict, str]:
        """
        Determine Hype Cycle phase from Finance metrics

        Args:
            metrics: Calculated Finance metrics snapshot

        Returns:
            Tuple of (phase, confidence, rule_scores, rationale)
        """
        logger.info("Determining Hype Cycle phase from Finance metrics...")

        phase_scores = {
            HypeCyclePhase.TECHNOLOGY_TRIGGER: self._score_technology_trigger(metrics),
            HypeCyclePhase.PEAK_INFLATED_EXPECTATIONS: self._score_peak_inflated(metrics),
            HypeCyclePhase.TROUGH_DISILLUSIONMENT: self._score_trough(metrics),
            HypeCyclePhase.SLOPE_ENLIGHTENMENT: self._score_slope(metrics),
            HypeCyclePhase.PLATEAU_PRODUCTIVITY: self._score_plateau(metrics)
        }

        best_phase = max(phase_scores, key=phase_scores.get)
        confidence = phase_scores[best_phase]

        logger.info(f"Finance phase determined: {best_phase.value} (confidence: {confidence:.2f})")

        rationale = self._generate_rationale(best_phase, metrics, phase_scores)
        phase_scores_str = {phase.value: score for phase, score in phase_scores.items()}

        return best_phase, confidence, phase_scores_str, rationale

    def _score_technology_trigger(self, m: FinanceMetricsSnapshot) -> float:
        """
        Score for Technology Trigger phase

        Finance Indicators:
        - High volatility (uncertainty)
        - Few tickers (limited market presence)
        - Low volume (limited trading interest)
        - No/low P/E ratio data (pre-revenue companies)
        """
        score = 0.0

        # High volatility (uncertainty in early stage)
        if m.volatility > self.thresholds.high_volatility:
            score += 0.25

        # Few tickers analyzed
        if len(m.tickers_analyzed) <= 3:
            score += 0.25

        # Volume declining or low (not mainstream yet)
        if m.volume_trend == "decreasing":
            score += 0.20

        # No P/E data (pre-revenue)
        if m.avg_pe_ratio is None:
            score += 0.15

        # Low correlation (stocks not moving together yet)
        if m.avg_correlation_between_tickers is not None and m.avg_correlation_between_tickers < 0.3:
            score += 0.15

        return min(score, 1.0)

    def _score_peak_inflated(self, m: FinanceMetricsSnapshot) -> float:
        """
        Score for Peak of Inflated Expectations

        Finance Indicators:
        - Strong bullish trend (rapid price increases)
        - High total returns
        - Increasing volume (buying frenzy)
        - High volatility (speculation)
        - High P/E ratios (overvaluation)
        """
        score = 0.0

        # Strong bullish trend
        if m.price_trend == "bullish":
            score += 0.25

        # High recent returns
        if m.price_change_last_3_months > self.thresholds.strong_bullish:
            score += 0.20

        # Increasing volume (frenzy)
        if m.volume_trend == "increasing":
            score += 0.20

        # High volatility (speculation)
        if m.volatility > self.thresholds.high_volatility:
            score += 0.15

        # High total return
        if m.total_return > self.thresholds.high_return:
            score += 0.10

        # High P/E (overvaluation)
        if m.avg_pe_ratio is not None and m.avg_pe_ratio > 50:
            score += 0.10

        return min(score, 1.0)

    def _score_trough(self, m: FinanceMetricsSnapshot) -> float:
        """
        Score for Trough of Disillusionment

        Finance Indicators:
        - Bearish trend (price decline)
        - High drawdown
        - Declining volume (loss of interest)
        - Negative returns
        - Low Sharpe ratio (poor risk-adjusted returns)
        """
        score = 0.0

        # Bearish trend
        if m.price_trend == "bearish":
            score += 0.30

        # High drawdown (crash)
        if m.max_drawdown > self.thresholds.severe_drawdown:
            score += 0.25

        # Negative recent returns
        if m.price_change_last_3_months < self.thresholds.strong_bearish:
            score += 0.20

        # Declining volume (disinterest)
        if m.volume_trend == "decreasing":
            score += 0.15

        # Negative Sharpe ratio
        if m.sharpe_ratio < 0:
            score += 0.10

        return min(score, 1.0)

    def _score_slope(self, m: FinanceMetricsSnapshot) -> float:
        """
        Score for Slope of Enlightenment

        Finance Indicators:
        - Moderate positive trend (recovery)
        - Decreasing volatility (stabilization)
        - Stable volume
        - Positive but moderate returns
        - Improving fundamentals
        """
        score = 0.0

        # Moderate positive returns (recovery)
        if self.thresholds.moderate_return_low <= m.price_change_last_3_months <= self.thresholds.moderate_return_high:
            score += 0.25

        # Stable or slightly bullish
        if m.price_trend in ["sideways", "bullish"]:
            score += 0.20

        # Stable volume
        if m.volume_trend == "stable":
            score += 0.20

        # Lower volatility (stabilizing)
        if m.volatility < self.thresholds.high_volatility:
            score += 0.15

        # Moderate drawdown (recovered from worst)
        if self.thresholds.moderate_drawdown <= m.max_drawdown < self.thresholds.severe_drawdown:
            score += 0.10

        # Positive Sharpe ratio
        if 0 < m.sharpe_ratio < 1:
            score += 0.10

        return min(score, 1.0)

    def _score_plateau(self, m: FinanceMetricsSnapshot) -> float:
        """
        Score for Plateau of Productivity

        Finance Indicators:
        - Stable prices (sideways trend)
        - Low volatility (mature market)
        - Stable volume
        - Reasonable P/E (fair valuation)
        - Good Sharpe ratio (steady returns)
        - Multiple sectors represented
        """
        score = 0.0

        # Sideways/stable trend
        if m.price_trend == "sideways":
            score += 0.25

        # Low volatility (mature)
        if m.volatility < self.thresholds.low_volatility:
            score += 0.20

        # Stable volume
        if m.volume_trend == "stable":
            score += 0.20

        # Reasonable P/E ratio (fair valuation)
        if m.avg_pe_ratio is not None and 10 < m.avg_pe_ratio < 30:
            score += 0.15

        # Good Sharpe ratio (steady risk-adjusted returns)
        if m.sharpe_ratio >= 1:
            score += 0.10

        # Multiple sectors (diversified industry)
        if len(m.sectors_represented) > 1:
            score += 0.10

        return min(score, 1.0)

    def _generate_rationale(self, phase: HypeCyclePhase, metrics: FinanceMetricsSnapshot,
                           scores: Dict[HypeCyclePhase, float]) -> str:
        """Generate human-readable explanation for Finance-based phase determination"""

        phase_info = PhaseCharacteristics.PHASE_DEFINITIONS[phase]

        rationale_parts = [
            f"Finance-based Phase: {phase_info['name']}",
            f"Confidence score: {scores[phase]:.2f}",
            "",
            "Key Finance indicators:",
        ]

        if phase == HypeCyclePhase.TECHNOLOGY_TRIGGER:
            rationale_parts.extend([
                f"- Volatility: {metrics.volatility:.2f}% (high uncertainty)",
                f"- Tickers analyzed: {len(metrics.tickers_analyzed)} (limited presence)",
                f"- Volume trend: {metrics.volume_trend}",
                f"- Avg P/E ratio: {metrics.avg_pe_ratio if metrics.avg_pe_ratio else 'N/A'}"
            ])

        elif phase == HypeCyclePhase.PEAK_INFLATED_EXPECTATIONS:
            rationale_parts.extend([
                f"- Price trend: {metrics.price_trend} (rapid growth)",
                f"- 3-month change: {metrics.price_change_last_3_months:.1f}%",
                f"- Volume trend: {metrics.volume_trend} (buying frenzy)",
                f"- Volatility: {metrics.volatility:.2f}% (speculation)",
                f"- Total return: {metrics.total_return:.1f}%"
            ])

        elif phase == HypeCyclePhase.TROUGH_DISILLUSIONMENT:
            rationale_parts.extend([
                f"- Price trend: {metrics.price_trend} (decline)",
                f"- Max drawdown: {metrics.max_drawdown:.1f}%",
                f"- 3-month change: {metrics.price_change_last_3_months:.1f}%",
                f"- Volume trend: {metrics.volume_trend}",
                f"- Sharpe ratio: {metrics.sharpe_ratio:.2f}"
            ])

        elif phase == HypeCyclePhase.SLOPE_ENLIGHTENMENT:
            rationale_parts.extend([
                f"- Price trend: {metrics.price_trend} (recovery)",
                f"- 3-month change: {metrics.price_change_last_3_months:.1f}%",
                f"- Volatility: {metrics.volatility:.2f}% (stabilizing)",
                f"- Volume trend: {metrics.volume_trend}",
                f"- Sharpe ratio: {metrics.sharpe_ratio:.2f}"
            ])

        elif phase == HypeCyclePhase.PLATEAU_PRODUCTIVITY:
            rationale_parts.extend([
                f"- Price trend: {metrics.price_trend} (stable)",
                f"- Volatility: {metrics.volatility:.2f}% (mature)",
                f"- Volume trend: {metrics.volume_trend}",
                f"- Avg P/E ratio: {metrics.avg_pe_ratio:.1f}" if metrics.avg_pe_ratio else "- Avg P/E ratio: N/A",
                f"- Sharpe ratio: {metrics.sharpe_ratio:.2f}"
            ])

        # Add ticker performance
        rationale_parts.append("")
        rationale_parts.append("Ticker performance:")
        for ticker, perf in list(metrics.ticker_performance.items())[:5]:
            if 'total_return_pct' in perf:
                rationale_parts.append(f"  - {ticker}: {perf['total_return_pct']:.1f}% return, {perf.get('volatility_pct', 0):.2f}% volatility")

        # Add phase scores comparison
        rationale_parts.append("")
        rationale_parts.append("Phase scores (Finance-based):")
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        for p, s in sorted_scores:
            phase_name = PhaseCharacteristics.PHASE_DEFINITIONS[p]["name"]
            rationale_parts.append(f"  {phase_name}: {s:.2f}")

        return "\n".join(rationale_parts)
