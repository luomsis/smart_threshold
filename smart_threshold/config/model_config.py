"""
模型配置管理模块

管理预设模型和自定义模型配置。
"""

import json
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from enum import Enum


class ModelType(Enum):
    """模型类型"""
    PROPHET = "prophet"
    WELFORD = "welford"
    STATIC = "static"


class TemplateCategory(Enum):
    """模板分类"""
    # 系统预设（不可删除）
    SYSTEM = "system"
    # 用户自定义
    CUSTOM = "custom"


@dataclass
class ModelConfig:
    """模型配置"""
    # 基本信息
    id: str  # 唯一标识
    name: str  # 显示名称
    description: str  # 描述
    model_type: ModelType  # 模型类型
    category: TemplateCategory  # 分类

    # Prophet 参数（当 model_type == PROPHET 时使用）
    daily_seasonality: bool = True
    weekly_seasonality: bool = False
    yearly_seasonality: bool = False
    seasonality_mode: str = "additive"  # additive or multiplicative
    interval_width: float = 0.95
    n_changepoints: int = 25
    changepoint_range: float = 0.8
    changepoint_prior_scale: float = 0.05
    seasonality_prior_scale: float = 10.0
    holidays_prior_scale: float = 10.0

    # Welford 参数
    sigma_multiplier: float = 3.0
    use_rolling_window: bool = False
    window_size: Optional[int] = None

    # Static 参数
    upper_percentile: float = 99.0
    lower_bound: float = 0.0

    # 元数据
    created_at: str = ""
    updated_at: str = ""
    author: str = "system"
    tags: List[str] = field(default_factory=list)
    color: str = "#4ECDC4"  # 用于图表显示的颜色

    def __post_init__(self):
        """初始化后处理"""
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if not self.updated_at:
            self.updated_at = datetime.now().isoformat()

    def get_params(self) -> Dict[str, Any]:
        """获取模型参数字典"""
        if self.model_type == ModelType.PROPHET:
            return {
                "daily_seasonality": self.daily_seasonality,
                "weekly_seasonality": self.weekly_seasonality,
                "yearly_seasonality": self.yearly_seasonality,
                "seasonality_mode": self.seasonality_mode,
                "interval_width": self.interval_width,
                "n_changepoints": self.n_changepoints,
                "changepoint_range": self.changepoint_range,
                "changepoint_prior_scale": self.changepoint_prior_scale,
                "seasonality_prior_scale": self.seasonality_prior_scale,
                "holidays_prior_scale": self.holidays_prior_scale,
            }
        elif self.model_type == ModelType.WELFORD:
            params = {
                "sigma_multiplier": self.sigma_multiplier,
                "use_rolling_window": self.use_rolling_window,
            }
            if self.use_rolling_window and self.window_size:
                params["window_size"] = self.window_size
            return params
        elif self.model_type == ModelType.STATIC:
            return {
                "upper_percentile": self.upper_percentile,
                "lower_bound": self.lower_bound,
            }
        return {}

    def update_params(self, params: Dict[str, Any]) -> None:
        """更新参数"""
        for key, value in params.items():
            if hasattr(self, key):
                setattr(self, key, value)
        self.updated_at = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        data = asdict(self)
        # 转换枚举类型
        data["model_type"] = self.model_type.value
        data["category"] = self.category.value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ModelConfig":
        """从字典创建"""
        # 转换枚举类型
        if isinstance(data.get("model_type"), str):
            data["model_type"] = ModelType(data["model_type"])
        if isinstance(data.get("category"), str):
            data["category"] = TemplateCategory(data["category"])
        return cls(**data)


class ModelConfigManager:
    """
    模型配置管理器

    管理预设模型和用户自定义模型的存储和检索。
    """

    # 默认系统预设模型
    DEFAULT_CONFIGS = [
        ModelConfig(
            id="prophet_aggressive",
            name="Aggressive (敏感)",
            description="高灵敏度，检测更多异常，可能有更多误报",
            model_type=ModelType.PROPHET,
            category=TemplateCategory.SYSTEM,
            changepoint_prior_scale=0.3,
            seasonality_prior_scale=15.0,
            interval_width=0.80,
            n_changepoints=35,
            color="#FF6B6B",
            tags=["敏感", "高召回"]
        ),
        ModelConfig(
            id="prophet_standard",
            name="Standard (标准)",
            description="平衡配置，适合大多数场景",
            model_type=ModelType.PROPHET,
            category=TemplateCategory.SYSTEM,
            changepoint_prior_scale=0.05,
            seasonality_prior_scale=10.0,
            interval_width=0.95,
            n_changepoints=25,
            color="#4ECDC4",
            tags=["标准", "平衡"]
        ),
        ModelConfig(
            id="prophet_conservative",
            name="Conservative (保守)",
            description="低灵敏度，减少误报，可能漏掉一些异常",
            model_type=ModelType.PROPHET,
            category=TemplateCategory.SYSTEM,
            changepoint_prior_scale=0.001,
            seasonality_prior_scale=5.0,
            interval_width=0.99,
            n_changepoints=15,
            color="#95E1D3",
            tags=["保守", "高精度"]
        ),
        ModelConfig(
            id="welford_standard",
            name="Welford 3-Sigma",
            description="基于统计分布的动态阈值，适合高波动数据",
            model_type=ModelType.WELFORD,
            category=TemplateCategory.SYSTEM,
            sigma_multiplier=3.0,
            color="#FFE66D",
            tags=["统计", "高波动"]
        ),
        ModelConfig(
            id="static_percentile",
            name="Static Percentile",
            description="基于历史分位数的静态阈值，适合稀疏数据",
            model_type=ModelType.STATIC,
            category=TemplateCategory.SYSTEM,
            upper_percentile=99.0,
            color="#DDA0DD",
            tags=["静态", "稀疏"]
        ),
    ]

    def __init__(self, config_dir: Optional[Path] = None):
        """
        初始化模型配置管理器

        Args:
            config_dir: 配置文件目录（默认为项目根目录下的 config 目录）
        """
        if config_dir is None:
            # 默认使用项目根目录下的 config 目录
            project_root = Path(__file__).parent.parent.parent
            config_dir = project_root / "config" / "models"

        self.config_dir = config_dir
        self.config_dir.mkdir(parents=True, exist_ok=True)

        self.config_file = self.config_dir / "model_configs.json"
        self._configs: Dict[str, ModelConfig] = {}
        self._load_configs()

    def _load_configs(self) -> None:
        """加载配置文件"""
        # 首先加载默认配置
        for config in self.DEFAULT_CONFIGS:
            self._configs[config.id] = config

        # 然后加载保存的配置文件（覆盖默认值）
        if self.config_file.exists():
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                for config_data in data:
                    config = ModelConfig.from_dict(config_data)
                    # 覆盖默认配置（包括系统预设的修改）
                    self._configs[config.id] = config

            except Exception as e:
                print(f"加载配置文件失败: {e}")

    def _save_custom_configs(self) -> None:
        """保存用户自定义配置"""
        custom_configs = [
            config.to_dict()
            for config in self._configs.values()
            if config.category == TemplateCategory.CUSTOM
        ]

        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump(custom_configs, f, indent=2, ensure_ascii=False)

    def list_configs(
        self,
        model_type: Optional[ModelType] = None,
        category: Optional[TemplateCategory] = None
    ) -> List[ModelConfig]:
        """
        列出所有配置

        Args:
            model_type: 筛选模型类型
            category: 筛选分类

        Returns:
            配置列表
        """
        configs = list(self._configs.values())

        if model_type:
            configs = [c for c in configs if c.model_type == model_type]
        if category:
            configs = [c for c in configs if c.category == category]

        return configs

    def get_config(self, config_id: str) -> Optional[ModelConfig]:
        """
        获取指定配置

        Args:
            config_id: 配置 ID

        Returns:
            配置对象或 None
        """
        return self._configs.get(config_id)

    def add_config(self, config: ModelConfig) -> bool:
        """
        添加配置

        Args:
            config: 配置对象

        Returns:
            是否添加成功
        """
        # 检查 ID 是否已存在
        if config.id in self._configs:
            return False

        config.created_at = datetime.now().isoformat()
        config.updated_at = datetime.now().isoformat()
        config.category = TemplateCategory.CUSTOM

        self._configs[config.id] = config
        self._save_custom_configs()
        return True

    def update_config(self, config_id: str, updates: Dict[str, Any]) -> bool:
        """
        更新配置

        Args:
            config_id: 配置 ID
            updates: 更新的字段

        Returns:
            是否更新成功
        """
        config = self._configs.get(config_id)
        if not config:
            return False

        config.update_params(updates)
        config.updated_at = datetime.now().isoformat()

        # 保存配置（系统预设保存到配置文件，下次加载时会覆盖默认值）
        self._save_all_configs()
        return True

    def _save_all_configs(self) -> None:
        """保存所有配置（包括系统预设的修改）"""
        all_configs = [
            config.to_dict()
            for config in self._configs.values()
        ]

        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump(all_configs, f, indent=2, ensure_ascii=False)

    def delete_config(self, config_id: str) -> bool:
        """
        删除配置

        Args:
            config_id: 配置 ID

        Returns:
            是否删除成功
        """
        config = self._configs.get(config_id)
        if not config:
            return False

        # 系统预设配置不允许删除
        if config.category == TemplateCategory.SYSTEM:
            return False

        del self._configs[config_id]
        self._save_custom_configs()
        return True

    def duplicate_config(
        self,
        source_id: str,
        new_id: str,
        new_name: str,
        author: str = "user"
    ) -> Optional[ModelConfig]:
        """
        复制配置

        Args:
            source_id: 源配置 ID
            new_id: 新配置 ID
            new_name: 新配置名称
            author: 作者

        Returns:
            新配置或 None
        """
        source_config = self._configs.get(source_id)
        if not source_config:
            return None

        # 创建新配置
        import copy
        new_config = copy.deepcopy(source_config)
        new_config.id = new_id
        new_config.name = new_name
        new_config.category = TemplateCategory.CUSTOM
        new_config.author = author
        new_config.created_at = datetime.now().isoformat()
        new_config.updated_at = datetime.now().isoformat()

        self._configs[new_id] = new_config
        self._save_custom_configs()
        return new_config

    def search_configs(self, keyword: str) -> List[ModelConfig]:
        """
        搜索配置

        Args:
            keyword: 搜索关键词（匹配名称、描述、标签）

        Returns:
            匹配的配置列表
        """
        keyword_lower = keyword.lower()
        results = []

        for config in self._configs.values():
            if (keyword_lower in config.name.lower() or
                keyword_lower in config.description.lower() or
                any(keyword_lower in tag.lower() for tag in config.tags)):
                results.append(config)

        return results

    def get_prophet_configs(self) -> List[ModelConfig]:
        """获取所有 Prophet 配置"""
        return self.list_configs(model_type=ModelType.PROPHET)

    def get_welford_configs(self) -> List[ModelConfig]:
        """获取所有 Welford 配置"""
        return self.list_configs(model_type=ModelType.WELFORD)

    def get_static_configs(self) -> List[ModelConfig]:
        """获取所有 Static 配置"""
        return self.list_configs(model_type=ModelType.STATIC)


# 全局单例
_manager_instance: Optional[ModelConfigManager] = None


def get_model_config_manager() -> ModelConfigManager:
    """获取模型配置管理器单例"""
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = ModelConfigManager()
    return _manager_instance
