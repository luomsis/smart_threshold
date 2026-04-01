/**
 * Predict Component - Quick prediction without pipeline
 */

const Predict = {
    // State
    state: {
        models: [],
        queryData: null,
        resultData: null,
    },

    // DataQuery instance (reused)
    dataQuery: null,

    /**
     * Initialize predict component
     */
    async init() {
        // Create a copy of DataQuery with our prefix
        this.dataQuery = Object.assign({}, DataQuery);
        this.dataQuery.state = Object.assign({}, DataQuery.state);

        // Initialize data query with prefix 'predict-'
        await this.dataQuery.init('predict-');

        // Override the onQuerySuccess callback
        this.dataQuery.onQuerySuccess = () => this.onQuerySuccess();

        // Load models
        await this.loadModels();

        // Bind additional events
        this.bindEvents();
    },

    /**
     * Bind event listeners
     */
    bindEvents() {
        // Start predict button
        const btnStart = document.getElementById('predict-btn-start');
        if (btnStart) {
            btnStart.addEventListener('click', () => this.startPredict());
        }

        // Train range inputs
        const trainStartInput = document.getElementById('predict-train-start');
        const trainEndInput = document.getElementById('predict-train-end');
        if (trainStartInput) {
            trainStartInput.addEventListener('change', () => this.updateTrainRange());
        }
        if (trainEndInput) {
            trainEndInput.addEventListener('change', () => this.updateTrainRange());
        }
    },

    /**
     * Load models for selection
     */
    async loadModels() {
        try {
            const models = await API.listModels();
            this.state.models = models;

            const select = document.getElementById('predict-model');
            if (!select) return;

            select.innerHTML = '<option value="">请选择模型...</option>';

            models.forEach(m => {
                const option = document.createElement('option');
                option.value = m.id;
                option.textContent = `${m.name} (${m.model_type})`;
                select.appendChild(option);
            });

            // Auto-select first model if available
            if (models.length > 0) {
                select.value = models[0].id;
            }
        } catch (error) {
            Helpers.showToast('加载模型失败: ' + error.message, 'error');
        }
    },

    /**
     * Handle query success - show preview chart and config section
     */
    onQuerySuccess() {
        const data = this.dataQuery.getQueryData();
        this.state.queryData = data;

        if (!data || data.timestamps.length === 0) {
            Helpers.showToast('查询成功但无数据', 'error');
            return;
        }

        // Show stats panel
        this.showStatsPanel(data);

        // Show preview chart
        this.renderPreviewChart(data);

        // Show config section
        document.getElementById('predict-config-section').style.display = 'block';

        // Auto set training range (80% of data)
        this.autoTrainRange(data);
    },

    /**
     * Show stats panel with data statistics
     */
    showStatsPanel(data) {
        const values = data.values;
        const count = values.length;
        const min = Math.min(...values);
        const max = Math.max(...values);
        const mean = values.reduce((a, b) => a + b, 0) / count;

        document.getElementById('predict-stat-count').textContent = count;
        document.getElementById('predict-stat-min').textContent = Helpers.formatNumber(min, 2);
        document.getElementById('predict-stat-max').textContent = Helpers.formatNumber(max, 2);
        document.getElementById('predict-stat-mean').textContent = Helpers.formatNumber(mean, 2);

        document.getElementById('predict-stats-panel').style.display = 'block';
    },

    /**
     * Render preview chart
     */
    renderPreviewChart(data) {
        document.getElementById('predict-preview-panel').style.display = 'block';

        const trainRange = this.dataQuery.getTrainRange();
        Charts.createTimeSeriesChart('predict-preview-chart', data, {
            seriesName: data.name,
            trainStart: trainRange.start ? Helpers.formatChartDate(trainRange.start) : null,
            trainEnd: trainRange.end ? Helpers.formatChartDate(trainRange.end) : null,
        });
    },

    /**
     * Auto set training range (80% of data)
     */
    autoTrainRange(data) {
        const splitIdx = Math.floor(data.timestamps.length * 0.8);
        const startDate = new Date(data.timestamps[0]);
        const endDate = new Date(data.timestamps[splitIdx]);

        // Update dataQuery state
        this.dataQuery.state.trainStart = startDate.toISOString();
        this.dataQuery.state.trainEnd = endDate.toISOString();

        // Update UI
        const trainStartInput = document.getElementById('predict-train-start');
        const trainEndInput = document.getElementById('predict-train-end');

        if (trainStartInput) {
            trainStartInput.value = Helpers.formatDateOnly(startDate);
        }
        if (trainEndInput) {
            trainEndInput.value = Helpers.formatDateOnly(endDate);
        }
    },

    /**
     * Update train range from UI inputs
     */
    updateTrainRange() {
        const trainStartInput = document.getElementById('predict-train-start');
        const trainEndInput = document.getElementById('predict-train-end');

        if (!trainStartInput || !trainEndInput) return;

        const start = trainStartInput.value;
        const end = trainEndInput.value;

        if (start && end) {
            this.dataQuery.state.trainStart = new Date(start).toISOString();
            this.dataQuery.state.trainEnd = new Date(end + 'T23:59:59').toISOString();

            // Update preview chart with new train range
            if (this.state.queryData) {
                this.renderPreviewChart(this.state.queryData);
            }
        }
    },

    /**
     * Start prediction
     */
    async startPredict() {
        const data = this.state.queryData;
        if (!data) {
            Helpers.showToast('请先查询数据', 'error');
            return;
        }

        const modelSelect = document.getElementById('predict-model');
        const modelId = modelSelect ? modelSelect.value : null;
        if (!modelId) {
            Helpers.showToast('请选择模型', 'error');
            return;
        }

        const trainStart = this.dataQuery.state.trainStart;
        const trainEnd = this.dataQuery.state.trainEnd;
        if (!trainStart || !trainEnd) {
            Helpers.showToast('请设置训练区间', 'error');
            return;
        }

        const periodsSelect = document.getElementById('predict-periods');
        const predictPeriods = periodsSelect ? parseInt(periodsSelect.value) : 1440;

        const step = this.dataQuery.getStep();

        Helpers.showLoading(true, '正在预测...');

        try {
            const params = {
                datasource_id: this.dataQuery.getDataSourceId(),
                metric_id: this.dataQuery.getMetric(),
                endpoint: this.dataQuery.getEndpoint(),
                train_start: trainStart,
                train_end: trainEnd,
                step: step,
                model_id: modelId,
                predict_periods: predictPeriods,
            };

            const result = await API.directPredict(params);

            // DirectPredictResponse has a different structure
            // It contains: original_data, predicted_data, algorithm, train_points, predict_points, validation_metrics
            this.state.resultData = result;
            this.renderResultChart(data, result);
            this.showResultStats(result);
            Helpers.showToast('预测成功', 'success');
        } catch (error) {
            Helpers.showToast('预测失败: ' + error.message, 'error');
        } finally {
            Helpers.showLoading(false);
        }
    },

    /**
     * Render result chart with original data and prediction
     */
    renderResultChart(originalData, result) {
        document.getElementById('predict-result-panel').style.display = 'block';

        const chart = Charts.getChart('predict-result-chart');
        if (!chart) return;

        // DirectPredictResponse format:
        // - original_data: [{timestamp, value}]
        // - predicted_data: [{timestamp, yhat, yhat_upper, yhat_lower}]
        const predictedData = result.predicted_data || [];
        const trainEnd = new Date(this.dataQuery.state.trainEnd);

        // Build timestamp index map for efficient lookup
        const timestampToIdx = new Map();
        const allTimestamps = [];

        // Add original data timestamps
        originalData.timestamps.forEach((ts, i) => {
            const tsDate = new Date(ts);
            const tsKey = tsDate.getTime();
            if (!timestampToIdx.has(tsKey)) {
                timestampToIdx.set(tsKey, allTimestamps.length);
                allTimestamps.push(ts);
            }
        });

        // Add prediction timestamps (only those after train end)
        predictedData.forEach(point => {
            const tsDate = new Date(point.timestamp);
            if (tsDate > trainEnd) {
                const tsKey = tsDate.getTime();
                if (!timestampToIdx.has(tsKey)) {
                    timestampToIdx.set(tsKey, allTimestamps.length);
                    allTimestamps.push(point.timestamp);
                }
            }
        });

        // Sort timestamps by date
        allTimestamps.sort((a, b) => new Date(a) - new Date(b));

        // Rebuild index map after sorting
        timestampToIdx.clear();
        allTimestamps.forEach((ts, i) => {
            timestampToIdx.set(new Date(ts).getTime(), i);
        });

        // Build series data
        const series = [];
        const legendData = [];

        // Original data series (solid line)
        const originalValues = new Array(allTimestamps.length).fill(null);
        originalData.timestamps.forEach((ts) => {
            const tsKey = new Date(ts).getTime();
            const idx = timestampToIdx.get(tsKey);
            const valueIdx = originalData.timestamps.indexOf(ts);
            if (idx !== undefined && valueIdx !== -1) {
                originalValues[idx] = originalData.values[valueIdx];
            }
        });

        series.push({
            name: '原始数据',
            type: 'line',
            data: originalValues,
            smooth: true,
            symbol: 'none',
            lineStyle: { color: '#56a4ff', width: 2 },
            itemStyle: { color: '#56a4ff' },
            z: 10,
        });
        legendData.push('原始数据');

        // Prediction series (dashed line)
        if (predictedData.length > 0) {
            const predictValues = new Array(allTimestamps.length).fill(null);
            const yhatUpperValues = new Array(allTimestamps.length).fill(null);
            const yhatLowerValues = new Array(allTimestamps.length).fill(null);

            predictedData.forEach(point => {
                const tsDate = new Date(point.timestamp);
                if (tsDate > trainEnd) {
                    const tsKey = tsDate.getTime();
                    const idx = timestampToIdx.get(tsKey);
                    if (idx !== undefined) {
                        predictValues[idx] = point.yhat;
                        yhatUpperValues[idx] = point.yhat_upper;
                        yhatLowerValues[idx] = point.yhat_lower;
                    }
                }
            });

            // 预测值（实线）
            series.push({
                name: '预测值',
                type: 'line',
                data: predictValues,
                smooth: true,
                symbol: 'none',
                lineStyle: { color: '#f2cc0c', width: 2 },
                itemStyle: { color: '#f2cc0c' },
                z: 11,
            });
            legendData.push('预测值');

            // 预测上限（白色虚线）
            series.push({
                name: '预测上限',
                type: 'line',
                data: yhatUpperValues,
                smooth: true,
                symbol: 'none',
                lineStyle: { color: '#ffffff', width: 1.5, type: 'dashed' },
                itemStyle: { color: '#ffffff' },
                z: 10,
            });
            legendData.push('预测上限');

            // 预测下限（白色虚线）
            series.push({
                name: '预测下限',
                type: 'line',
                data: yhatLowerValues,
                smooth: true,
                symbol: 'none',
                lineStyle: { color: '#ffffff', width: 1.5, type: 'dashed' },
                itemStyle: { color: '#ffffff' },
                z: 10,
            });
            legendData.push('预测下限');
        }

        // Mark area for train range
        const trainStartTs = Helpers.formatChartDate(this.dataQuery.state.trainStart);
        const trainEndTs = Helpers.formatChartDate(this.dataQuery.state.trainEnd);

        // Add mark area for training range on original data series
        if (series[0]) {
            series[0].markArea = {
                silent: true,
                itemStyle: { color: 'rgba(250, 173, 20, 0.15)' },
                data: [[
                    { xAxis: trainStartTs },
                    { xAxis: trainEndTs },
                ]],
            };
        }

        const chartOptions = Charts.getBaseChartOptions();
        Object.assign(chartOptions, {
            title: {
                text: `预测结果 (${result.algorithm || result.model_id})`,
                left: 'center',
                textStyle: { color: '#e6e8eb', fontSize: 14 },
            },
            legend: {
                data: legendData,
                top: 30,
                textStyle: { color: '#8b9199' },
            },
            xAxis: { ...chartOptions.xAxis, data: allTimestamps },
            grid: { ...chartOptions.grid, top: '18%' },
            series,
        });

        chart.setOption(chartOptions, true);
    },

    /**
     * Show result statistics
     */
    showResultStats(result) {
        document.getElementById('predict-result-stats-panel').style.display = 'block';

        // DirectPredictResponse format
        const trainCount = result.train_points || 0;
        const predictCount = result.predict_points || 0;
        const validationMetrics = result.validation_metrics || {};

        document.getElementById('predict-result-algorithm').textContent = result.algorithm || '-';
        document.getElementById('predict-result-train-count').textContent = trainCount;
        document.getElementById('predict-result-predict-count').textContent = predictCount;

        // MAPE might not be available in validation_metrics, show interval width instead
        const mapeEl = document.getElementById('predict-result-mape');
        if (validationMetrics.avg_interval_width) {
            mapeEl.textContent = Helpers.formatNumber(validationMetrics.avg_interval_width, 2);
        } else {
            mapeEl.textContent = '-';
        }

        // Update result info
        const infoEl = document.getElementById('predict-result-info');
        if (infoEl) {
            infoEl.textContent = `算法: ${result.algorithm || result.model_id} | 训练点: ${trainCount} | 预测点: ${predictCount}`;
        }
    },

    /**
     * Refresh/reset component
     */
    refresh() {
        // Reset state
        this.state.queryData = null;
        this.state.resultData = null;

        // Hide panels
        document.getElementById('predict-stats-panel').style.display = 'none';
        document.getElementById('predict-preview-panel').style.display = 'none';
        document.getElementById('predict-config-section').style.display = 'none';
        document.getElementById('predict-result-panel').style.display = 'none';
        document.getElementById('predict-result-stats-panel').style.display = 'none';

        // Dispose charts
        Charts.dispose('predict-preview-chart');
        Charts.dispose('predict-result-chart');

        // Reset data query state and reload
        this.dataQuery.reset();
        this.dataQuery.loadDataSources();
    },
};

// Make Predict globally available
window.Predict = Predict;