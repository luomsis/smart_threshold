"""
配置管理器

提供统一的配置加载、覆盖和验证功能。
"""

import os
from pathlib import Path
from typing import Any, Optional
import yaml


def get_default_config_path() -> Path:
    """获取默认配置文件路径"""
    return Path(__file__).parent / "default_config.yaml"


class ConfigManager:
    """
    配置管理器

    功能：
    1. 从 YAML 文件加载默认配置
    2. 支持运行时覆盖配置项
    3. 验证配置有效性

    使用示例:
    >>> # 使用默认配置
    >>> cm = ConfigManager()
    >>>
    >>> # 使用自定义配置文件
    >>> cm = ConfigManager(config_path="/path/to/config.yaml")
    >>>
    >>> # 运行时覆盖
    >>> cm.set_override("algorithms.welford.sigma_multiplier", 2.5)
    >>>
    >>> # 获取最终配置
    >>> config = cm.get_final_config("welford", {"sigma_multiplier": 3.0})
    """

    # 默认配置
    DEFAULT_CONFIG = {
        "algorithms": {
            "prophet": {
                "daily_seasonality": True,
                "weekly_seasonality": False,
                "yearly_seasonality": False,
                "seasonality_mode": "additive",
                "interval_width": 0.95,
                "n_changepoints": 25,
                "changepoint_range": 0.8,
                "changepoint_prior_scale": 0.05,
                "seasonality_prior_scale": 10.0,
                "holidays_prior_scale": 10.0,
                "mcmc_samples": 0,
            },
            "welford": {
                "confidence_level": 0.997,
                "sigma_multiplier": 3.0,
                "use_rolling_window": False,
                "window_size": 1440,
            },
            "static": {
                "upper_percentile": 99.0,
                "confidence_level": 0.99,
                "lower_bound": 0.0,
            },
        },
        "backtest": {
            "enabled": True,
            "scan_range": [1.5, 4.0],
            "scan_step": 0.1,
            "target_coverage": 0.98,
            "max_anomaly_rate": 0.02,
        },
        "router": {
            "seasonality_threshold": 0.3,
            "sparsity_threshold": 0.8,
        },
    }

    def __init__(
        self,
        config_path: Optional[str] = None,
        config_dict: Optional[dict] = None,
    ):
        """
        初始化配置管理器

        Args:
            config_path: YAML 配置文件路径（可选）
            config_dict: 直接传入配置字典（可选）
        """
        self._config: dict = self.DEFAULT_CONFIG.copy()
        self._overrides: dict = {}

        # 加载配置文件
        if config_path:
            self._load_from_file(config_path)

        # 加载配置字典
        if config_dict:
            self._merge_config(config_dict)

    def _load_from_file(self, config_path: str) -> None:
        """
        从 YAML 文件加载配置

        Args:
            config_path: 配置文件路径
        """
        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(f"配置文件不存在: {config_path}")

        with open(path, "r", encoding="utf-8") as f:
            loaded_config = yaml.safe_load(f)

        if loaded_config:
            self._merge_config(loaded_config)

    def _merge_config(self, new_config: dict) -> None:
        """
        合并配置（深度合并）

        Args:
            new_config: 新配置字典
        """
        def deep_merge(base: dict, new: dict) -> dict:
            """深度合并字典"""
            result = base.copy()
            for key, value in new.items():
                if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                    result[key] = deep_merge(result[key], value)
                else:
                    result[key] = value
            return result

        self._config = deep_merge(self._config, new_config)

    def set_override(self, key: str, value: Any) -> None:
        """
        设置配置覆盖

        使用点分隔的路径表示嵌套键，如 "algorithms.welford.sigma_multiplier"

        Args:
            key: 配置键（支持点分隔路径）
            value: 配置值
        """
        keys = key.split(".")
        current = self._overrides

        for k in keys[:-1]:
            if k not in current:
                current[k] = {}
            current = current[k]

        current[keys[-1]] = value

    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置值

        Args:
            key: 配置键（支持点分隔路径）
            default: 默认值

        Returns:
            配置值
        """
        # 优先从覆盖中获取
        keys = key.split(".")
        current = self._overrides

        try:
            for k in keys:
                current = current[k]
            return current
        except (KeyError, TypeError):
            pass

        # 从主配置获取
        current = self._config
        try:
            for k in keys:
                current = current[k]
            return current
        except (KeyError, TypeError):
            return default

    def get_final_config(
        self, algorithm: str, default_config: dict
    ) -> dict:
        """
        获取算法的最终配置

        合并顺序：默认配置 < YAML配置 < 运行时覆盖 < 参数工厂配置

        Args:
            algorithm: 算法名称（如 "welford"）
            default_config: 参数工厂生成的默认配置

        Returns:
            合并后的配置字典
        """
        # 从 YAML 配置获取算法配置
        yaml_config = self.get(f"algorithms.{algorithm}", {})

        # 从运行时覆盖获取算法配置
        override_config = self._overrides.get("algorithms", {}).get(algorithm, {})

        # 合并：YAML < 覆盖 < 参数工厂
        def deep_merge(base: dict, *updates: dict) -> dict:
            """深度合并多个字典"""
            result = base.copy()
            for update in updates:
                for key, value in update.items():
                    if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                        result[key] = deep_merge(result[key], value)
                    else:
                        result[key] = value
            return result

        # 先合并 YAML 和覆盖
        config = deep_merge(yaml_config, override_config)

        # 最后合并参数工厂配置（参数工厂优先级最高）
        config = deep_merge(config, default_config)

        return config

    def get_backtest_config(self) -> dict:
        """获取回测配置"""
        backtest_config = self.get("backtest", {})
        override = self._overrides.get("backtest", {})
        return {**backtest_config, **override}

    def get_router_config(self) -> dict:
        """获取路由器配置"""
        router_config = self.get("router", {})
        override = self._overrides.get("router", {})
        return {**router_config, **override}

    @property
    def config(self) -> dict:
        """获取完整配置（只读）"""
        return self._config.copy()

    def save_to_file(self, path: str) -> None:
        """
        保存当前配置到 YAML 文件

        Args:
            path: 保存路径
        """
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(self._config, f, default_flow_style=False, allow_unicode=True)

    @classmethod
    def create_default_config_file(cls, path: Optional[str] = None) -> str:
        """
        创建默认配置文件

        Args:
            path: 保存路径（默认为项目根目录下的 default_config.yaml）

        Returns:
            配置文件路径
        """
        if path is None:
            path = get_default_config_path()

        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(cls.DEFAULT_CONFIG, f, default_flow_style=False, allow_unicode=True)

        return str(path)

    def __repr__(self) -> str:
        return f"ConfigManager(overrides={len(self._overrides)} items)"
