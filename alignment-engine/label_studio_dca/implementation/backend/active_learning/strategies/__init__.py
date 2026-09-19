"""
Active Learning strategies.

Provides various sampling strategies for intelligent task selection.
"""

from backend.active_learning.strategies.base import BaseStrategy
from backend.active_learning.strategies.uncertainty import UncertaintySampling
from backend.active_learning.strategies.diversity import DiversitySampling
from backend.active_learning.strategies.committee import QueryByCommittee
from backend.active_learning.strategies.hybrid import HybridStrategy
from backend.active_learning.strategies.random import RandomSampling

__all__ = [
    'BaseStrategy',
    'UncertaintySampling',
    'DiversitySampling',
    'QueryByCommittee',
    'HybridStrategy',
    'RandomSampling',
    'get_strategy',
]

# Strategy registry
STRATEGY_REGISTRY = {
    'uncertainty': UncertaintySampling,
    'diversity': DiversitySampling,
    'committee': QueryByCommittee,
    'hybrid': HybridStrategy,
    'random': RandomSampling,
}


def get_strategy(strategy_name: str, **kwargs) -> BaseStrategy:
    """
    Factory function to get strategy instance.
    
    Args:
        strategy_name: Name of the strategy
        **kwargs: Strategy-specific parameters
    
    Returns:
        Strategy instance
    """
    if strategy_name not in STRATEGY_REGISTRY:
        raise ValueError(
            f"Unknown strategy: {strategy_name}. "
            f"Available: {list(STRATEGY_REGISTRY.keys())}"
        )
    
    strategy_class = STRATEGY_REGISTRY[strategy_name]
    return strategy_class(**kwargs)
