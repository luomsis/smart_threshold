"""
SmartThreshold 完整演示脚本

演示 DB 监控算法自动选型的完整流程：
1. 生成三种场景的 Mock 数据
2. 执行特征分析
3. 自动路由到对应算法
4. 训练前 6 天，预测第 7 天
5. 生成可视化报告
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pandas as pd
from rich.console import Console
from rich.theme import Theme
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.text import Text
from rich import box
from datetime import datetime

from smart_threshold.core.model_router import ModelRouter, AlgorithmType
from smart_threshold.core.feature_analyzer import FeatureExtractor
from smart_threshold.data.generator import DataGenerator, ScenarioType
from smart_threshold.utils.visualization import TimeSeriesVisualizer

# 自定义主题
custom_theme = Theme({
    "header": "bold cyan",
    "subheader": "bold yellow",
    "success": "bold green",
    "info": "dim cyan",
    "warning": "bold yellow",
    "muted": "dim white",
    "value": "bold magenta",
    "border": "bright_blue",
})

console = Console(theme=custom_theme)


def run_scenario(scenario: ScenarioType, days: int = 7):
    """
    运行单个场景的完整流程

    Args:
        scenario: 场景类型
        days: 总天数
    """
    # 场景标题面板
    scenario_name = scenario.value.upper()
    console.print()
    console.print(Panel(
        Text(f"▓ 场景: {scenario_name} ▓", justify="center"),
        title="📊 监控场景分析",
        title_align="center",
        border_style="border",
        padding=(0, 2),
    ))

    # 进度步骤
    steps = [
        "[1/5] 📊 生成 Mock 数据",
        "[2/5] 🔍 执行特征分析",
        "[3/5] 🤖 自动选择算法",
        "[4/5] 🧠 训练与预测",
        "[5/5] 📈 生成可视化",
    ]

    with console.status("[bold cyan]⏳ 处理中...") as status:
        for step in steps:
            status.update(f"{step}")
            console.print(f"  {step}", style="info")

        # 1. 生成数据
        generator = DataGenerator(freq="1min", seed=42)
        data = generator.generate(scenario, days=days)
        console.print(f"    ✓ 生成 {len(data)} 个数据点", style="success")

        # 2. 特征分析
        extractor = FeatureExtractor()
        features = extractor.analyze(data)
        console.print(f"    ✓ 特征分析完成", style="success")

        # 3. 算法路由
        router = ModelRouter(verbose=False)
        predictor = router.select_predictor(data)
        algo_name = predictor.__class__.__name__
        console.print(f"    ✓ 选择算法: [value]{algo_name}[/value]", style="success")

        # 分割训练集和测试集
        train_days = days - 1
        train_size = train_days * 1440  # 每天分钟数

        train_data = data[:train_size]
        test_data = data[train_size:]

        # 4. 训练与预测
        predictor.fit(train_data)
        prediction = predictor.predict(periods=len(test_data), freq="1min")
        console.print(f"    ✓ 训练完成", style="success")

        # 计算预测准确率
        mae = abs(test_data.values - prediction.yhat).mean()
        mape = (abs(test_data.values - prediction.yhat) / (test_data.values + 1e-6)).mean() * 100

        # 检测异常值
        anomalies = test_data[test_data > prediction.yhat_upper]

        # 5. 可视化
        visualizer = TimeSeriesVisualizer(figsize=(16, 6))

        # 场景特定的标签
        labels = {
            ScenarioType.QPS: ("QPS (每秒查询数)", "QPS"),
            ScenarioType.RT: ("RT (响应时间 ms)", "响应时间 (ms)"),
            ScenarioType.ERROR_COUNT: ("错误计数", "错误数"),
        }

        ylabel, short_ylabel = labels[scenario]

        fig = visualizer.plot_prediction(
            train_data=train_data,
            test_data=test_data,
            prediction=prediction,
            title=f"{scenario.value.upper()} 场景 - {short_ylabel}预测与动态阈值",
            ylabel=ylabel,
            show_anomalies=True,
        )

        # 保存图表
        output_dir = project_root / "outputs"
        output_dir.mkdir(exist_ok=True)
        output_path = output_dir / f"{scenario.value}_prediction.png"
        fig.savefig(str(output_path), dpi=150, bbox_inches="tight")
        console.print(f"    ✓ 图表已保存: [dim]{output_path}[/dim]", style="success")

    # 显示结果面板
    console.print()
    console.print(Panel(
        f"""[cyan]训练集:[/cyan] {len(train_data)} 点
[cyan]测试集:[/cyan] {len(test_data)} 点
[cyan]MAE:[/cyan] [value]{mae:.2f}[/value]
[cyan]MAPE:[/cyan] [value]{mape:.2f}%[/value]
[cyan]异常值:[/cyan] [warning]{len(anomalies)}[/warning] 个""",
        title="📋 预测结果",
        border_style="success",
    ))

    return features, predictor, prediction


def main():
    """主函数：运行所有场景"""
    # 欢迎面板
    console.print()
    console.print(Panel(
        Text("SmartThreshold 演示", style="header bold", justify="center"),
        title="🚀",
        title_align="center",
        border_style="border",
        padding=(0, 3),
        subtitle="DB 监控算法自动选型 Demo"
    ))

    console.print()
    console.print("[dim]  输入: 1分钟采样率的时序数据[/dim]")
    console.print("[dim]  输出: 自动选择算法 + 动态阈值预测[/dim]")
    console.print()

    # 运行三种场景
    results = {}

    for scenario in ScenarioType:
        features, predictor, prediction = run_scenario(scenario, days=7)
        results[scenario] = {
            "features": features,
            "predictor": predictor,
            "prediction": prediction,
        }

    # 汇总报告
    console.print()
    console.print(Panel(
        Text("汇总报告", style="header", justify="center"),
        title="📊",
        title_align="center",
        border_style="border",
        padding=(0, 2),
    ))

    # 创建汇总表格
    table = Table(
        title=None,
        box=box.ROUNDED,
        border_style="border",
        header_style="bold cyan",
        padding=(0, 1),
    )
    table.add_column("场景", style="bold", no_wrap=True, width=15)
    table.add_column("季节性", justify="center", width=10)
    table.add_column("稀疏度", justify="right", width=10)
    table.add_column("算法", style="value", width=20)

    for scenario, result in results.items():
        f = result["features"]
        algo = result["predictor"].__class__.__name__
        seasonality = "✓ 是" if f.has_seasonality else "✗ 否"
        seasonality_style = "success" if f.has_seasonality else "muted"
        sparsity = f"{f.sparsity_ratio:>6.1%}"

        table.add_row(
            scenario.value,
            Text(seasonality, style=seasonality_style),
            Text(sparsity, style="info"),
            Text(algo, style="value"),
        )

    console.print()
    console.print(table)

    # 完成面板
    console.print()
    console.print(Panel(
        Text("✅ 演示完成！请查看 outputs/ 目录中的可视化图表", justify="center", style="success"),
        border_style="success",
        padding=(0, 2),
    ))
    console.print()


if __name__ == "__main__":
    main()
