"""
配置管理模块

提供统一的配置管理接口，支持：
- 从 YAML 文件加载默认配置
- 运行时配置覆盖
- 配置验证
- 模型配置管理
"""

from smart_threshold.config.config_manager import ConfigManager, get_default_config_path
from smart_threshold.config.model_config import (
    ModelConfig,
    ModelConfigManager,
    ModelType,
    TemplateCategory,
    get_model_config_manager,
)

__all__ = [
    "ConfigManager",
    "get_default_config_path",
    "ModelConfig",
    "ModelConfigManager",
    "ModelType",
    "TemplateCategory",
    "get_model_config_manager",
]
