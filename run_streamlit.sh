#!/bin/bash
# SmartThreshold Streamlit 应用启动脚本

echo "======================================"
echo "  SmartThreshold Streamlit 应用"
echo "======================================"
echo ""

# 检查虚拟环境
if [ ! -d ".venv" ]; then
    echo "❌ 未找到虚拟环境，请先运行: uv sync"
    exit 1
fi

# 激活虚拟环境
source .venv/bin/activate

echo "🚀 启动高级应用..."
echo ""
echo "功能:"
echo "  - 数据源管理 (Prometheus/Mock)"
echo "  - 指标查询和可视化"
echo "  - 多模型对比和参数优化"
echo "  - 自定义模型保存"
echo ""
echo "应用将在浏览器中打开: http://localhost:8501"
echo "按 Ctrl+C 停止服务"
echo ""

streamlit run streamlit_advanced.py
