/**
 * Charts Component - ECharts wrapper
 */

const Charts = {
    instances: {},
    resizeHandler: null,

    // ==================== 通用方法 ====================

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

    getChart(containerId) {
        if (typeof echarts === 'undefined') return null;

        if (!this.instances[containerId]) {
            const container = document.getElementById(containerId);
            if (container) {
                this.instances[containerId] = echarts.init(container, 'dark');
                this.initResizeHandler();
            }
        }
        return this.instances[containerId];
    },

    dispose(containerId) {
        if (this.instances[containerId]) {
            this.instances[containerId].dispose();
            delete this.instances[containerId];
        }
    },

    resizeAll() {
        Object.values(this.instances).forEach(chart => chart.resize());
    },

    // ==================== 图表配置 ====================

    getBaseChartOptions() {
        return {
            backgroundColor: 'transparent',
            tooltip: {
                trigger: 'axis',
                backgroundColor: 'rgba(26, 29, 33, 0.95)',
                borderColor: '#30363d',
                textStyle: { color: '#e6e8eb' },
            },
            grid: {
                left: '3%',
                right: '4%',
                bottom: '15%',
                top: '10%',
                containLabel: true,
            },
            xAxis: {
                type: 'category',
                boundaryGap: false,
                axisLine: { lineStyle: { color: '#30363d' } },
                axisLabel: {
                    color: '#8b9199',
                    formatter: (value) => Helpers.formatChartDate(value),
                },
            },
            yAxis: {
                type: 'value',
                axisLine: { lineStyle: { color: '#30363d' } },
                axisLabel: { color: '#8b9199' },
                splitLine: { lineStyle: { color: '#30363d', type: 'dashed' } },
            },
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
    },

    // ==================== 时间序列图表 ====================

    createTimeSeriesChart(containerId, data, options = {}) {
        const chart = this.getChart(containerId);
        if (!chart) return;

        const series = [{
            name: options.seriesName || '指标值',
            type: 'line',
            data: data.values,
            smooth: true,
            symbol: 'none',
            lineStyle: { color: '#56a4ff', width: 2 },
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

        if (options.trainStart && options.trainEnd) {
            series[0].markArea = {
                silent: true,
                itemStyle: { color: 'rgba(250, 173, 20, 0.15)' },
                data: [[
                    { xAxis: options.trainStart },
                    { xAxis: options.trainEnd },
                ]],
            };
        }

        const chartOptions = this.getBaseChartOptions();
        chartOptions.xAxis.data = data.timestamps;
        chartOptions.series = series;

        if (options.title) {
            chartOptions.title = {
                text: options.title,
                left: 'center',
                textStyle: { color: '#e6e8eb', fontSize: 14 },
            };
            chartOptions.grid.top = '15%';
        }

        chart.setOption(chartOptions, true);
        return chart;
    },

    // ==================== 模型对比图表 ====================

    createComparisonChart(containerId, trainData, testData, results, modelConfigs) {
        const chart = this.getChart(containerId);
        if (!chart || !Array.isArray(results)) return;

        const series = [];
        const legendData = [];
        const totalLen = trainData.timestamps.length;

        // 历史数据
        series.push({
            name: '历史数据',
            type: 'line',
            data: trainData.values,
            symbol: 'none',
            lineStyle: { color: '#8b9199', width: 2 },
            itemStyle: { color: '#8b9199' },
            z: 1,
        });
        legendData.push('历史数据');

        // 筛选成功的模型
        const successfulResults = results
            .filter(r => r.success && r.prediction && Array.isArray(r.prediction.yhat))
            .sort((a, b) => a.mape - b.mape);

        if (successfulResults.length === 0) {
            chart.setOption({
                backgroundColor: 'transparent',
                title: { text: '模型预测对比 (无成功预测)', left: 'center', textStyle: { color: '#e6e8eb', fontSize: 14 } },
                xAxis: { type: 'category', data: trainData.timestamps },
                yAxis: { type: 'value' },
                series: series,
            }, true);
            return;
        }

        // 时间戳映射
        const timestampToIndex = new Map();
        trainData.timestamps.forEach((ts, idx) => {
            timestampToIndex.set(new Date(ts).getTime(), idx);
        });

        // 渲染模型
        const bestModel = successfulResults[0];
        this._addModelSeries(series, legendData, bestModel, modelConfigs, timestampToIndex, totalLen, 0, true);

        successfulResults.slice(1, 5).forEach((result, index) => {
            this._addModelSeries(series, legendData, result, modelConfigs, timestampToIndex, totalLen, index + 1, false);
        });

        const moreModelsText = successfulResults.length > 5 ? ` (还有${successfulResults.length - 5}个模型未显示)` : '';

        const chartOptions = this.getBaseChartOptions();
        Object.assign(chartOptions, {
            title: {
                text: `模型预测对比 (最佳: ${bestModel.model_name}, MAPE: ${Helpers.formatNumber(bestModel.mape, 2)}%)${moreModelsText}`,
                left: 'center',
                textStyle: { color: '#e6e8eb', fontSize: 14 },
            },
            legend: {
                data: legendData,
                top: 30,
                type: 'scroll',
                textStyle: { color: '#8b9199' },
            },
            xAxis: { ...chartOptions.xAxis, data: trainData.timestamps },
            grid: { ...chartOptions.grid, top: '18%' },
            series,
        });

        chart.setOption(chartOptions, true);
        return chart;
    },

    _addModelSeries(series, legendData, result, modelConfigs, timestampToIndex, totalLen, index, isBest) {
        const config = modelConfigs.find(c => c.id === result.model_id);
        const color = config?.color || Helpers.getChartColor(index);
        const name = config?.name || result.model_id;
        const opacity = isBest ? 0.3 : 0.15;
        const zIndex = isBest ? 2 : 3 + index;

        // 置信区间
        const confSeries = this._createConfidenceSeries(result, timestampToIndex, totalLen, color, name, opacity, zIndex);
        if (confSeries.length > 0) {
            series.push(...confSeries);
            legendData.push(`${name} 置信区间`);
        }

        // 预测线
        series.push({
            name,
            type: 'line',
            data: this._alignPredictionData(result.prediction, timestampToIndex, totalLen, 'yhat'),
            symbol: 'none',
            lineStyle: { color, width: isBest ? 2 : 1.5, type: 'dashed' },
            itemStyle: { color },
            z: isBest ? 10 : 11 + index,
        });
        legendData.push(name);
    },

    _alignPredictionData(prediction, timestampToIndex, totalLen, field) {
        const data = new Array(totalLen).fill(null);
        if (!prediction.timestamps || !prediction[field]) return data;

        prediction.timestamps.forEach((ts, i) => {
            const idx = timestampToIndex.get(new Date(ts).getTime());
            if (idx !== undefined) {
                data[idx] = prediction[field][i];
            }
        });
        return data;
    },

    _createConfidenceSeries(result, timestampToIndex, totalLen, color, name, opacity, zIndex) {
        const prediction = result.prediction;
        if (!prediction?.yhat_upper || !prediction?.yhat_lower || !prediction?.timestamps) {
            return [];
        }

        const lowerData = new Array(totalLen).fill(0);
        const diffData = new Array(totalLen).fill(0);
        const posToPredIdx = new Map();

        prediction.timestamps.forEach((ts, i) => {
            const idx = timestampToIndex.get(new Date(ts).getTime());
            if (idx !== undefined) {
                lowerData[idx] = prediction.yhat_lower[i];
                diffData[idx] = prediction.yhat_upper[i] - prediction.yhat_lower[i];
                posToPredIdx.set(idx, i);
            }
        });

        const originalLower = prediction.yhat_lower;
        const originalUpper = prediction.yhat_upper;

        return [
            {
                name: `${name}_下限基线`,
                type: 'line',
                data: lowerData,
                symbol: 'none',
                lineStyle: { width: 0, opacity: 0 },
                itemStyle: { opacity: 0 },
                areaStyle: { opacity: 0 },
                stack: `confidence-${name}`,
                z: zIndex,
                tooltip: { show: false },
            },
            {
                name: `${name} 置信区间`,
                type: 'line',
                data: diffData,
                symbol: 'none',
                lineStyle: { width: 0, opacity: 0 },
                areaStyle: { color: Helpers.hexToRgba(color, opacity) },
                stack: `confidence-${name}`,
                z: zIndex + 1,
                tooltip: {
                    formatter: function(params) {
                        const predIdx = posToPredIdx.get(params.dataIndex);
                        if (predIdx !== undefined) {
                            return `${name} 置信区间: [${originalLower[predIdx].toFixed(2)}, ${originalUpper[predIdx].toFixed(2)}]`;
                        }
                        return `${name} 置信区间`;
                    }
                },
            },
        ];
    },
};

window.Charts = Charts;