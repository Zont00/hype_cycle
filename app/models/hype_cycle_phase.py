from enum import Enum
from typing import Dict, List


class HypeCyclePhase(str, Enum):
    """Gartner Hype Cycle phases"""
    TECHNOLOGY_TRIGGER = "technology_trigger"
    PEAK_INFLATED_EXPECTATIONS = "peak_inflated_expectations"
    TROUGH_DISILLUSIONMENT = "trough_disillusionment"
    SLOPE_ENLIGHTENMENT = "slope_enlightenment"
    PLATEAU_PRODUCTIVITY = "plateau_productivity"


class PhaseCharacteristics:
    """Metadata and characteristics for each Hype Cycle phase"""

    PHASE_DEFINITIONS = {
        HypeCyclePhase.TECHNOLOGY_TRIGGER: {
            "name": "Technology Trigger",
            "description": "A potential technology breakthrough kicks things off. Early proof-of-concept stories and media interest trigger significant publicity. Often no usable products exist and commercial viability is unproven.",
            "indicators": [
                "Rapid growth in publication velocity",
                "High percentage of basic science research (>70%)",
                "Low citation counts (papers too new)",
                "Primarily academic/research venues",
                "Emerging keywords and exploratory language",
                "Few or no product-oriented papers"
            ]
        },
        HypeCyclePhase.PEAK_INFLATED_EXPECTATIONS: {
            "name": "Peak of Inflated Expectations",
            "description": "Early publicity produces a number of success stories—often accompanied by scores of failures. Some companies take action; most don't.",
            "indicators": [
                "Peak publication velocity (maximum papers/year)",
                "Accelerating citation growth rate",
                "Mix of basic and applied research (40-60% applied)",
                "Increasing media/news mentions",
                "Appearance of 'breakthrough' and 'revolutionary' keywords",
                "Shift toward applied research and product focus"
            ]
        },
        HypeCyclePhase.TROUGH_DISILLUSIONMENT: {
            "name": "Trough of Disillusionment",
            "description": "Interest wanes as experiments and implementations fail to deliver. Producers of the technology shake out or fail. Investment continues only if surviving providers improve their products.",
            "indicators": [
                "Declining publication velocity",
                "Stagnant or decreasing citation growth",
                "Increasing percentage of critical/problem-focused papers",
                "Decline in media mentions",
                "Keywords shift to 'challenges', 'limitations', 'problems'",
                "Consolidation of research topics"
            ]
        },
        HypeCyclePhase.SLOPE_ENLIGHTENMENT: {
            "name": "Slope of Enlightenment",
            "description": "More instances of how the technology can benefit the enterprise start to crystallize and become more widely understood. Second- and third-generation products appear.",
            "indicators": [
                "Gradual increase in publication velocity",
                "Steady citation growth (not explosive)",
                "High percentage of applied research (60-80%)",
                "Focus on practical implementations and case studies",
                "Keywords: 'optimization', 'implementation', 'application'",
                "Shift to industry/applied venues"
            ]
        },
        HypeCyclePhase.PLATEAU_PRODUCTIVITY: {
            "name": "Plateau of Productivity",
            "description": "Mainstream adoption starts to take off. Criteria for assessing provider viability are more clearly defined. Technology's broad market applicability and relevance are paying off.",
            "indicators": [
                "Stable publication velocity (plateau)",
                "High citation counts on established papers",
                "Predominantly applied research (>80%)",
                "Focus on incremental improvements and standardization",
                "Keywords: 'standard', 'protocol', 'commercial', 'scalable'",
                "Industry partnerships and product-focused research"
            ]
        }
    }
