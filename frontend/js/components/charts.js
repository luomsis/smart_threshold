/**
 * Charts Component - ECharts wrapper
 */

const Charts = {
    instances: {},

    /**
     * Initialize or get chart instance
     */
    getChart(containerId) {
        if (!this.instances[containerId]) {
            const container = document.getElementById(containerId);
            if (container) {
                this.instances[containerId] = echarts.init(container, 'dark');
                // Resize on window resize
                window.addEventListener('resize', () => {
                    this.instances[containerId].resize();
                });
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
                bottom: '3%',
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
                    formatter: (value) => {
                        const date = new Date(value);
                        return `${date.getMonth() + 1}/${date.getDate()} ${date.getHours()}:${String(date.getMinutes()).padStart(2, '0')}`;
                    },
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
    createComparisonChart(containerId, testData, results, modelConfigs) {
        const chart = this.getChart(containerId);
        if (!chart) return;

        const series = [{
            name: '实际值',
            type: 'line',
            data: testData.values,
            symbol: 'none',
            lineStyle: {
                color: '#e6e8eb',
                width: 2,
            },
        }];

        const legend = ['实际值'];

        results.forEach(result => {
            if (!result.success || !result.prediction) return;

            const config = modelConfigs.find(c => c.id === result.model_id);
            const color = config ? config.color : '#56a4ff';
            const name = config ? config.name : result.model_id;

            // Prediction line
            series.push({
                name: `${name}`,
                type: 'line',
                data: result.prediction.yhat,
                symbol: 'none',
                lineStyle: {
                    color: color,
                    width: 2,
                    type: 'dashed',
                },
            });

            // Confidence interval
            series.push({
                name: `${name} 区间`,
                type: 'line',
                data: result.prediction.yhat_upper,
                symbol: 'none',
                lineStyle: {
                    opacity: 0,
                },
                areaStyle: {
                    color: Helpers.hexToRgba(color, 0.15),
                },
            });

            // Lower bound (for area fill)
            series.push({
                name: `${name} 下限`,
                type: 'line',
                data: result.prediction.yhat_lower,
                symbol: 'none',
                lineStyle: {
                    opacity: 0,
                },
                areaStyle: {
                    color: 'transparent',
                },
            });

            legend.push(name);
        });

        const chartOptions = {
            backgroundColor: 'transparent',
            title: {
                text: '模型预测对比',
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
            legend: {
                data: legend,
                top: 30,
                textStyle: {
                    color: '#8b9199',
                },
            },
            grid: {
                left: '3%',
                right: '4%',
                bottom: '15%',
                top: '20%',
                containLabel: true,
            },
            xAxis: {
                type: 'category',
                data: testData.timestamps,
                boundaryGap: false,
                axisLine: {
                    lineStyle: { color: '#30363d' },
                },
                axisLabel: {
                    color: '#8b9199',
                    formatter: (value) => {
                        const date = new Date(value);
                        return `${date.getMonth() + 1}/${date.getDate()} ${date.getHours()}:${String(date.getMinutes()).padStart(2, '0')}`;
                    },
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
            ],
        };

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