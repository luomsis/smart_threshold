"""
Algorithm module for dynamic threshold calculation.

This module provides a pluggable algorithm framework with JSON Schema support
for dynamic frontend form rendering.
"""

from smart_threshold.algorithms.base import BaseAlgorithm, AlgorithmResult
from smart_threshold.algorithms.registry import AlgorithmRegistry, register_algorithm

# Import all algorithms to register them
from smart_threshold.algorithms.three_sigma import ThreeSigmaAlgorithm
from smart_threshold.algorithms.prophet_algo import ProphetAlgorithm
from smart_threshold.algorithms.moving_average import MovingAverageAlgorithm
from smart_threshold.algorithms.holt_winters import HoltWintersAlgorithm

__all__ = [
    "BaseAlgorithm",
    "AlgorithmResult",
    "AlgorithmRegistry",
    "register_algorithm",
    "ThreeSigmaAlgorithm",
    "ProphetAlgorithm",
    "MovingAverageAlgorithm",
    "HoltWintersAlgorithm",
]