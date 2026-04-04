"""
Metrics Manager — Agrégation des métriques Ranker + Printer
"""

import logging
from typing import Dict, Any, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class PipelineMetrics:
    """Métriques globales du pipeline"""
    ranker_metrics: Any          # RankerMetrics
    printer_metrics: Any         # PrinterMetrics
    pipeline_score: float        # Score global pipeline
    status: str                  # "EXCELLENT" / "GOOD" / "FAIR" / "POOR"
    
    def __str__(self) -> str:
        bar = "█" * int(self.pipeline_score * 10) + "░" * (10 - int(self.pipeline_score * 10))
        return (
            f"\n{'='*60}\n"
            f"PIPELINE METRICS\n"
            f"{'='*60}\n"
            f"Global Score : {bar} {self.pipeline_score:.1%} ({self.status})\n"
            f"\n{str(self.ranker_metrics)}\n"
            f"\n{str(self.printer_metrics)}\n"
            f"{'='*60}\n"
        )


def compute_pipeline_metrics(
    ranker_metrics: Any,
    printer_metrics: Any
) -> PipelineMetrics:
    """
    Combine les métriques Ranker et Printer
    
    Pondération:
    - 50% Ranker (foundation)
    - 50% Printer (output quality)
    """
    
    pipeline_score = (
        ranker_metrics.global_score * 0.50 +
        printer_metrics.global_score * 0.50
    )
    
    # Status basé sur score global
    if pipeline_score >= 0.90:
        status = "EXCELLENT"
    elif pipeline_score >= 0.75:
        status = "GOOD"
    elif pipeline_score >= 0.60:
        status = "FAIR"
    else:
        status = "POOR"
    
    logger.info(
        f"[METRICS] Pipeline score: {pipeline_score:.1%} ({status}) "
        f"= Ranker {ranker_metrics.global_score:.1%} + Printer {printer_metrics.global_score:.1%}"
    )
    
    return PipelineMetrics(
        ranker_metrics=ranker_metrics,
        printer_metrics=printer_metrics,
        pipeline_score=pipeline_score,
        status=status
    )