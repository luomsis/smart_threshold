"""
可视化模块

提供时序数据和预测结果的绘图功能。
"""

from typing import Optional
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.figure import Figure

# 设置中文字体支持
plt.rcParams["font.sans-serif"] = ["Arial Unicode MS", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False


class TimeSeriesVisualizer:
    """
    时序数据可视化器

    绘制时序数据、预测值和动态阈值区间。
    """

    # 默认颜色方案
    COLORS = {
        "actual": "#1f77b4",  # 蓝色
        "predict": "#ff7f0e",  # 橙色
        "upper": "#d62728",  # 红色
        "lower": "#d62728",  # 红色
        "fill": "#ff7f0e",  # 橙色（半透明）
        "anomaly": "#d62728",  # 红色
    }

    def __init__(self, figsize: tuple[int, int] = (14, 6)):
        """
        初始化可视化器

        Args:
            figsize: 图表尺寸 (宽, 高)
        """
        self.figsize = figsize

    def plot_prediction(
        self,
        train_data: pd.Series,
        test_data: pd.Series,
        prediction,
        title: str = "时序预测与动态阈值",
        ylabel: str = "值",
        show_anomalies: bool = True,
        anomaly_threshold: Optional[str] = None,
        save_path: Optional[str] = None,
    ) -> Figure:
        """
        绘制预测结果

        Args:
            train_data: 训练数据
            test_data: 测试数据（真实值）
            prediction: 预测结果 (PredictionResult)
            title: 图表标题
            ylabel: Y 轴标签
            show_anomalies: 是否标注异常值
            anomaly_threshold: 异常检测方向 ('upper', 'lower', 'both')
            save_path: 保存路径（可选）

        Returns:
            Figure: matplotlib Figure 对象
        """
        fig, ax = plt.subplots(figsize=self.figsize)

        # 绘制训练数据
        ax.plot(
            train_data.index,
            train_data.values,
            color=self.COLORS["actual"],
            linewidth=1,
            alpha=0.7,
            label="训练数据",
        )

        # 绘制测试数据（真实值）
        ax.plot(
            test_data.index,
            test_data.values,
            color=self.COLORS["actual"],
            linewidth=1.5,
            label="真实值",
        )

        # 绘制预测值
        ax.plot(
            prediction.ds,
            prediction.yhat,
            color=self.COLORS["predict"],
            linewidth=2,
            linestyle="--",
            label=f"预测值 ({prediction.algorithm})",
        )

        # 绘制置信区间
        ax.fill_between(
            prediction.ds,
            prediction.yhat_lower,
            prediction.yhat_upper,
            color=self.COLORS["fill"],
            alpha=0.2,
            label=f"{prediction.confidence_level*100:.0f}% 置信区间",
        )

        # 绘制阈值线
        ax.plot(
            prediction.ds,
            prediction.yhat_upper,
            color=self.COLORS["upper"],
            linewidth=1,
            linestyle=":",
            alpha=0.7,
        )
        ax.plot(
            prediction.ds,
            prediction.yhat_lower,
            color=self.COLORS["lower"],
            linewidth=1,
            linestyle=":",
            alpha=0.7,
        )

        # 检测并标注异常值
        if show_anomalies:
            self._mark_anomalies(
                ax, test_data, prediction, threshold_type=anomaly_threshold
            )

        # 绘制训练/测试分界线
        train_end = train_data.index[-1]
        ax.axvline(
            train_end,
            color="gray",
            linestyle="-",
            linewidth=2,
            alpha=0.5,
            label="训练/测试分界",
        )

        # 设置标题和标签
        ax.set_title(title, fontsize=14, fontweight="bold")
        ax.set_xlabel("时间", fontsize=12)
        ax.set_ylabel(ylabel, fontsize=12)

        # 设置 x 轴格式
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d %H:%M"))
        plt.xticks(rotation=45)

        # 添加网格
        ax.grid(True, alpha=0.3)

        # 添加图例
        ax.legend(loc="best", framealpha=0.9)

        plt.tight_layout()

        # 保存图表
        if save_path:
            fig.savefig(save_path, dpi=150, bbox_inches="tight")

        return fig

    def _mark_anomalies(
        self,
        ax,
        test_data: pd.Series,
        prediction,
        threshold_type: Optional[str] = "upper",
    ) -> None:
        """
        标注异常值

        Args:
            ax: matplotlib 轴对象
            test_data: 测试数据
            prediction: 预测结果
            threshold_type: 异常检测方向
        """
        # 对齐预测结果和测试数据
        pred_df = prediction.to_dataframe()
        pred_df.set_index("ds", inplace=True)

        # 找到时间重叠的部分
        common_index = test_data.index.intersection(pred_df.index)
        if len(common_index) == 0:
            return

        actual_values = test_data.loc[common_index]
        upper_values = pred_df.loc[common_index, "yhat_upper"]
        lower_values = pred_df.loc[common_index, "yhat_lower"]

        # 检测异常
        if threshold_type == "upper" or threshold_type is None:
            anomalies = actual_values > upper_values
        elif threshold_type == "lower":
            anomalies = actual_values < lower_values
        else:  # both
            anomalies = (actual_values > upper_values) | (actual_values < lower_values)

        anomaly_points = actual_values[anomalies]

        # 标注异常点
        if len(anomaly_points) > 0:
            ax.scatter(
                anomaly_points.index,
                anomaly_points.values,
                color=self.COLORS["anomaly"],
                s=50,
                zorder=5,
                label=f"异常值 ({len(anomaly_points)} 个)",
                marker="x",
            )

    def plot_features(
        self,
        features,
        title: str = "数据特征分析",
        save_path: Optional[str] = None,
    ) -> Figure:
        """
        绘制特征分析结果

        Args:
            features: FeatureResult 对象
            title: 图表标题
            save_path: 保存路径

        Returns:
            Figure: matplotlib Figure 对象
        """
        fig, ax = plt.subplots(figsize=(10, 4))

        # 准备特征数据
        feature_names = [
            "季节性强度",
            "稀疏度",
            "平稳性\n(1-p值)",
        ]
        feature_values = [
            features.seasonality_strength,
            features.sparsity_ratio,
            1 - features.adf_pvalue if features.adf_pvalue is not None else 0,
        ]

        # 绘制柱状图
        colors = ["#2ecc71" if v < 0.5 else "#e74c3c" for v in feature_values]
        bars = ax.bar(feature_names, feature_values, color=colors, alpha=0.7)

        # 添加数值标签
        for bar, value in zip(bars, feature_values):
            height = bar.get_height()
            ax.text(
                bar.get_x() + bar.get_width() / 2.0,
                height,
                f"{value:.3f}",
                ha="center",
                va="bottom",
                fontsize=10,
            )

        # 添加阈值线
        ax.axhline(
            y=0.3,
            color="gray",
            linestyle="--",
            alpha=0.5,
            label="判定阈值",
        )

        ax.set_title(title, fontsize=14, fontweight="bold")
        ax.set_ylim(0, 1.1)
        ax.legend()
        ax.grid(axis="y", alpha=0.3)

        plt.tight_layout()

        if save_path:
            fig.savefig(save_path, dpi=150, bbox_inches="tight")

        return fig

    @staticmethod
    def close_all() -> None:
        """关闭所有图表"""
        plt.close("all")
