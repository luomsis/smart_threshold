"""
Algorithm registry for dynamic algorithm discovery and registration.
"""

from typing import Type, Optional

from smart_threshold.algorithms.base import BaseAlgorithm


class AlgorithmRegistry:
    """
    Registry for threshold algorithms.

    Allows dynamic registration and discovery of algorithms.
    Each algorithm is registered with its algorithm_id.
    """

    _algorithms: dict[str, Type[BaseAlgorithm]] = {}

    @classmethod
    def register(cls, algorithm_class: Type[BaseAlgorithm]) -> Type[BaseAlgorithm]:
        """
        Register an algorithm class.

        Can be used as a decorator:
            @AlgorithmRegistry.register
            class MyAlgorithm(BaseAlgorithm):
                ...

        Args:
            algorithm_class: Algorithm class to register

        Returns:
            The same class (for decorator usage)
        """
        cls._algorithms[algorithm_class.algorithm_id] = algorithm_class
        return algorithm_class

    @classmethod
    def get(cls, algorithm_id: str) -> Optional[Type[BaseAlgorithm]]:
        """
        Get an algorithm class by ID.

        Args:
            algorithm_id: Algorithm identifier

        Returns:
            Algorithm class or None if not found
        """
        return cls._algorithms.get(algorithm_id)

    @classmethod
    def create(cls, algorithm_id: str, params: Optional[dict] = None) -> BaseAlgorithm:
        """
        Create an algorithm instance by ID.

        Args:
            algorithm_id: Algorithm identifier
            params: Algorithm parameters

        Returns:
            Algorithm instance

        Raises:
            ValueError: If algorithm not found
        """
        algo_class = cls.get(algorithm_id)
        if algo_class is None:
            raise ValueError(f"Algorithm not found: {algorithm_id}")
        return algo_class(params)

    @classmethod
    def list_ids(cls) -> list[str]:
        """
        List all registered algorithm IDs.

        Returns:
            List of algorithm IDs
        """
        return list(cls._algorithms.keys())

    @classmethod
    def list_all(cls) -> list[Type[BaseAlgorithm]]:
        """
        List all registered algorithm classes.

        Returns:
            List of algorithm classes
        """
        return list(cls._algorithms.values())

    @classmethod
    def get_all_info(cls) -> list[dict]:
        """
        Get information about all registered algorithms.

        Returns:
            List of algorithm info dictionaries
        """
        return [algo.get_algorithm_info() for algo in cls._algorithms.values()]


def register_algorithm(algorithm_class: Type[BaseAlgorithm]) -> Type[BaseAlgorithm]:
    """
    Decorator to register an algorithm.

    Usage:
        @register_algorithm
        class ThreeSigmaAlgorithm(BaseAlgorithm):
            ...

    Args:
        algorithm_class: Algorithm class to register

    Returns:
        The same class
    """
    return AlgorithmRegistry.register(algorithm_class)