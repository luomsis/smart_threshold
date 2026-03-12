/**
 * Charts Component - ECharts wrapper
 */

const Charts = {
    instances: {},
    resizeHandler: null,

    /**
     * Initialize resize handler (called once)
     */
    initResizeHandler() {
        if (this.resizeHandler) return;
        this.resizeHandler = () => {
            Object.values(this.instances).forEach(chart => {
                if (chart && typeof chart.resize === 'function') {
                    chart.resize();
                }
            });
        };
        window.addEventListener('resize', this.resizeHandler);
    },

    /**
     * Initialize or get chart instance
     */
    getChart(containerId) {
        // 检查 ECharts 是否已加载
        if (typeof echarts === 'undefined') {
            return null;
        }

        if (!this.instances[containerId]) {
            const container = document.getElementById(containerId);
            if (container) {
                this.instances[containerId] = echarts.init(container, 'dark');
                // Initialize global resize handler once
                this.initResizeHandler();
            }
        }
        return this.instances[containerId];
    },

    /**
     * Dispose chart instance
     */
    dispose(containerId) {
        if (this.instances[containerId]) {
            this.instances[containerId].dispose();
            delete this.instances[containerId];
        }
    },

    /**
     * Create confidence interval series for a model
     */
    createConfidenceSeries(result, trainLen, color, name, zIndex, opacity = 0.3) {
        // Pre-allocate null padding once
        const nullPadding = new Array(trainLen).fill(null);

        // Calculate upper - lower differences in single pass
        const upperDiffs = result.prediction.yhat_upper.map((upper, i) =>
            upper - result.prediction.yhat_lower[i]
        );

        return [
            // Lower bound baseline (transparent)
            {
                name: `${name}_下限`,
                type: 'line',
                data: nullPadding.concat(result.prediction.yhat_lower),
                symbol: 'none',
                lineStyle: { opacity: 0 },
                areaStyle: { opacity: 0 },
                stack: `${name}-confidence`,
                tooltip: { show: false },
                z: zIndex,
            },
            // Confidence interval range
            {
                name: `${name} 置信区间`,
                type: 'line',
                data: nullPadding.concat(upperDiffs),
                symbol: 'none',
                lineStyle: { opacity: 0 },
                areaStyle: {
                    color: Helpers.hexToRgba(color, opacity),
                    opacity: 0.8,
                },
                stack: `${name}-confidence`,
                tooltip: { formatter: () => `${name} 置信区间` },
                z: zIndex,
            },
        ];
    },

    /**
     * Create time series chart
     */
    createTimeSeriesChart(containerId, data, options = {}) {
        const chart = this.getChart(containerId);
        if (!chart) return;

        const series = [{
            name: options.seriesName || '指标值',
            type: 'line',
            data: data.values,
            smooth: true,
            symbol: 'none',
            lineStyle: {
                color: '#56a4ff',
                width: 2,
            },
            areaStyle: {
                color: {
                    type: 'linear',
                    x: 0, y: 0, x2: 0, y2: 1,
                    colorStops: [
                        { offset: 0, color: 'rgba(86, 164, 255, 0.3)' },
                        { offset: 1, color: 'rgba(86, 164, 255, 0.05)' },
                    ],
                },
            },
        }];

        // Add training range highlight
        if (options.trainStart && options.trainEnd) {
            // Add mark area for training range
            series[0].markArea = {
                silent: true,
                itemStyle: {
                    color: 'rgba(250, 173, 20, 0.15)',
                },
                data: [[
                    { xAxis: options.trainStart },
                    { xAxis: options.trainEnd },
                ]],
            };
        }

        const chartOptions = {
            backgroundColor: 'transparent',
            title: {
                text: options.title || '',
                left: 'center',
                textStyle: {
                    color: '#e6e8eb',
                    fontSize: 14,
                },
            },
            tooltip: {
                trigger: 'axis',
                backgroundColor: 'rgba(26, 29, 33, 0.9)',
                borderColor: '#30363d',
                textStyle: {
                    color: '#e6e8eb',
                },
            },
            grid: {
                left: '3%',
                right: '4%',
                bottom: '15%',
                top: options.title ? '15%' : '10%',
                containLabel: true,
            },
            xAxis: {
                type: 'category',
                data: data.timestamps,
                boundaryGap: false,
                axisLine: {
                    lineStyle: { color: '#30363d' },
                },
                axisLabel: {
                    color: '#8b9199',
                    formatter: (value) => Helpers.formatChartDate(value),
                },
            },
            yAxis: {
                type: 'value',
                axisLine: {
                    lineStyle: { color: '#30363d' },
                },
                axisLabel: {
                    color: '#8b9199',
                },
                splitLine: {
                    lineStyle: { color: '#30363d' },
                },
            },
            series,
            dataZoom: [
                {
                    type: 'inside',
                    start: 0,
                    end: 100,
                },
                {
                    type: 'slider',
                    start: 0,
                    end: 100,
                    height: 20,
                    bottom: 10,
                    borderColor: '#30363d',
                    backgroundColor: '#1a1d21',
                    fillerColor: 'rgba(86, 164, 255, 0.2)',
                    handleStyle: {
                        color: '#56a4ff',
                    },
                    textStyle: {
                        color: '#8b9199',
                    },
                },
            ],
        };

        chart.setOption(chartOptions, true);
        return chart;
    },

    /**
     * Create comparison chart
     */
    createComparisonChart(containerId, trainData, testData, results, modelConfigs) {
        const chart = this.getChart(containerId);
        if (!chart) return;

        // 防御性检查：确保 results 是数组
        if (!Array.isArray(results)) {
            return;
        }

        const series = [];
        const legendData = [];

        // 合并训练数据和测试数据作为历史数据
        const allHistoricalData = [...trainData.values, ...testData.values];
        const allTimestamps = [...trainData.timestamps, ...testData.timestamps];

        // 历史数据（训练+测试）- 灰色实线
        series.push({
            name: '历史数据',
            type: 'line',
            data: allHistoricalData,
            symbol: 'none',
            lineStyle: { color: '#8b9199', width: 2 },
            itemStyle: { color: '#8b9199' },
            z: 1,
        });
        legendData.push('历史数据');

        // 找出成功的模型，按MAPE排序（直接在比较器中计算，不创建临时对象）
        const successfulResults = results
            .filter(r => r.success && r.prediction)
            .sort((a, b) => a.mape - b.mape);

        if (successfulResults.length === 0) {
            // 没有成功模型，只显示历史数据
            chart.setOption({
                backgroundColor: 'transparent',
                title: { text: '模型预测对比 (无成功预测)', left: 'center', textStyle: { color: '#e6e8eb', fontSize: 14 } },
                xAxis: { type: 'category', data: allTimestamps },
                yAxis: { type: 'value' },
                series: series,
            }, true);
            return;
        }

        // 最佳模型（MAPE最小）显示置信区间
        const bestModel = successfulResults[0];
        const bestConfig = modelConfigs.find(c => c.id === bestModel.model_id);
        const bestColor = bestConfig?.color || Helpers.getChartColor(0);
        const bestName = bestConfig?.name || bestModel.model_id;

        // 预测区间起点（训练数据末尾）
        const trainLen = trainData.timestamps.length;

        // 最佳模型的置信区间 - 使用辅助方法创建
        const bestSeries = this.createConfidenceSeries(bestModel, trainLen, bestColor, bestName, 2, 0.3);
        series.push(...bestSeries);
        legendData.push(`${bestName} 置信区间`);

        // 其他模型也只显示置信区间（最多显示4个）
        const otherModels = successfulResults.slice(1, 5);
        otherModels.forEach((result, index) => {
            const config = modelConfigs.find(c => c.id === result.model_id);
            const color = config?.color || Helpers.getChartColor(index + 1);
            const name = config?.name || result.model_id;

            const modelSeries = this.createConfidenceSeries(result, trainLen, color, name, 3 + index, 0.15);
            series.push(...modelSeries);
            legendData.push(`${name} 置信区间`);
        });

        // 如果还有更多模型，在标题中提示
        const moreModelsCount = successfulResults.length - 5;
        const moreModelsText = moreModelsCount > 0 ? ` (还有${moreModelsCount}个模型未显示)` : '';

        // 如果有测试数据，显示测试区间标注
        const markAreas = [];
        if (testData.timestamps.length > 0) {
            markAreas.push([{
                name: '预测区间',
                xAxis: testData.timestamps[0],
                itemStyle: { color: 'rgba(86, 164, 255, 0.05)' },
                label: { show: true, position: 'insideTop', color: '#56a4ff', fontSize: 10 },
            }, {
                xAxis: testData.timestamps[testData.timestamps.length - 1],
            }]);
        }

        const chartOptions = {
            backgroundColor: 'transparent',
            title: {
                text: `模型预测对比 (最佳: ${bestName}, MAPE: ${Helpers.formatNumber(bestModel.mape, 2)}%)${moreModelsText}`,
                left: 'center',
                textStyle: { color: '#e6e8eb', fontSize: 14 },
            },
            tooltip: {
                trigger: 'axis',
                backgroundColor: 'rgba(26, 29, 33, 0.95)',
                borderColor: '#30363d',
                textStyle: { color: '#e6e8eb' },
                formatter: (params) => {
                    const dateStr = Helpers.formatChartDate(params[0].axisValue);
                    let html = `<div style="font-weight:600;margin-bottom:8px;border-bottom:1px solid #30363d;padding-bottom:5px;">${dateStr}</div>`;

                    // 历史数据
                    const historical = params.find(p => p.seriesName === '历史数据');
                    if (historical && historical.value !== null) {
                        html += `<div style="margin:4px 0;"><span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:#8b9199;margin-right:5px;"></span>历史数据: <b>${Number(historical.value).toFixed(2)}</b></div>`;
                    }

                    // 各模型预测
                    const predictions = params.filter(p =>
                        p.value !== null &&
                        p.seriesName !== '历史数据' &&
                        !p.seriesName.includes('_下限') &&
                        !p.seriesName.includes('置信区间')
                    );

                    if (predictions.length > 0) {
                        html += '<div style="margin-top:8px;border-top:1px solid #30363d;padding-top:5px;font-size:12px;color:#8b9199;">模型预测</div>';
                        predictions.forEach(p => {
                            const marker = `<span style="display:inline-block;width:10px;height:2px;background:${p.color};margin-right:5px;vertical-align:middle;"></span>`;
                            html += `<div style="margin:4px 0;">${marker}${p.seriesName}: <b>${Number(p.value).toFixed(2)}</b></div>`;
                        });
                    }

                    return html;
                },
            },
            legend: {
                data: legendData,
                top: 30,
                type: 'scroll',
                textStyle: { color: '#8b9199' },
            },
            grid: {
                left: '3%',
                right: '4%',
                bottom: '15%',
                top: '18%',
                containLabel: true,
            },
            xAxis: {
                type: 'category',
                data: allTimestamps,
                boundaryGap: false,
                axisLine: { lineStyle: { color: '#30363d' } },
                axisLabel: {
                    color: '#8b9199',
                    formatter: (value) => Helpers.formatChartDate(value),
                },
                splitLine: { show: false },
            },
            yAxis: {
                type: 'value',
                axisLine: { lineStyle: { color: '#30363d' } },
                axisLabel: { color: '#8b9199' },
                splitLine: { lineStyle: { color: '#30363d', type: 'dashed' } },
            },
            series,
            dataZoom: [
                { type: 'inside', start: 0, end: 100 },
                {
                    type: 'slider',
                    start: 0,
                    end: 100,
                    height: 20,
                    bottom: 10,
                    borderColor: '#30363d',
                    fillerColor: 'rgba(86, 164, 255, 0.2)',
                },
            ],
        };

        // 如果有测试数据，添加预测区间标注
        if (markAreas.length > 0) {
            chartOptions.xAxis.splitLine = { show: true, lineStyle: { color: 'rgba(86, 164, 255, 0.1)' } };
        }

        chart.setOption(chartOptions, true);
        return chart;
    },

    /**
     * Resize all charts
     */
    resizeAll() {
        Object.values(this.instances).forEach(chart => {
            chart.resize();
        });
    },
};

// Make Charts globally available
window.Charts = Charts;