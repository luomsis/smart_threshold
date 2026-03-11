/**
 * Dashboard Component
 */

const Dashboard = {
    // State
    state: {
        dataSources: [],
        currentDataSource: null,
        metrics: [],
        queryData: null,
        trainStart: null,
        trainEnd: null,
        models: [],
        selectedModels: [],
        comparisonResults: null,
    },

    /**
     * Initialize dashboard
     */
    async init() {
        this.bindEvents();
        await this.loadDataSources();
        await this.loadModels();
    },

    /**
     * Bind event listeners
     */
    bindEvents() {
        // Time range slider
        const timeRange = document.getElementById('time-range');
        const timeRangeValue = document.getElementById('time-range-value');
        timeRange.addEventListener('input', () => {
            timeRangeValue.textContent = `${timeRange.value} 天`;
        });

        // Query button
        document.getElementById('btn-query').addEventListener('click', () => this.executeQuery());

        // Training range buttons
        document.getElementById('btn-set-train').addEventListener('click', () => this.setTrainRange());
        document.getElementById('btn-auto-train').addEventListener('click', () => this.autoTrainRange());

        // Compare button
        document.getElementById('btn-compare').addEventListener('click', () => this.runComparison());

        // Label selection
        document.getElementById('label-select').addEventListener('change', (e) => this.loadLabelValues(e.target.value));

        // Refresh button
        document.getElementById('btn-refresh').addEventListener('click', () => this.refresh());
    },

    /**
     * Load data sources
     */
    async loadDataSources() {
        try {
            const dataSources = await API.listDataSources();
            this.state.dataSources = dataSources;

            if (dataSources.length > 0) {
                this.state.currentDataSource = dataSources[0];
                Sidebar.updateCurrentDataSource(this.state.currentDataSource.name);
                await this.loadMetrics();
            }
        } catch (error) {
            Helpers.showToast('加载数据源失败: ' + error.message, 'error');
        }
    },

    /**
     * Load metrics
     */
    async loadMetrics() {
        if (!this.state.currentDataSource) return;

        try {
            const metrics = await API.listMetrics(this.state.currentDataSource.id);
            this.state.metrics = metrics;

            const select = document.getElementById('metric-select');
            select.innerHTML = '<option value="">请选择指标...</option>';
            metrics.forEach(m => {
                const option = document.createElement('option');
                option.value = m.name;
                option.textContent = m.name;
                select.appendChild(option);
            });

            // Also load labels
            await this.loadLabels();
        } catch (error) {
            Helpers.showToast('加载指标失败: ' + error.message, 'error');
        }
    },

    /**
     * Load labels
     */
    async loadLabels() {
        if (!this.state.currentDataSource) return;

        try {
            const labels = await API.listLabels(this.state.currentDataSource.id);
            const select = document.getElementById('label-select');
            select.innerHTML = '<option value="">请选择标签...</option>';
            labels.forEach(label => {
                const option = document.createElement('option');
                option.value = label;
                option.textContent = label;
                select.appendChild(option);
            });
        } catch (error) {
            Helpers.showToast('加载标签失败: ' + error.message, 'error');
        }
    },

    /**
     * Load label values
     */
    async loadLabelValues(labelName) {
        if (!this.state.currentDataSource || !labelName) {
            document.getElementById('label-value-select').innerHTML = '<option value="">全部</option>';
            return;
        }

        try {
            const result = await API.getLabelValues(this.state.currentDataSource.id, labelName);
            const select = document.getElementById('label-value-select');
            select.innerHTML = '<option value="">全部</option>';
            result.values.forEach(v => {
                const option = document.createElement('option');
                option.value = v;
                option.textContent = v;
                select.appendChild(option);
            });
        } catch (error) {
            Helpers.showToast('加载标签值失败: ' + error.message, 'error');
        }
    },

    /**
     * Execute query
     */
    async executeQuery() {
        const metric = document.getElementById('metric-select').value;
        if (!metric) {
            Helpers.showToast('请选择指标', 'error');
            return;
        }

        const days = parseInt(document.getElementById('time-range').value);
        const step = document.getElementById('step-select').value;

        const { start, end } = Helpers.getDateRange(days);

        Helpers.showLoading(true, '正在查询数据...');

        try {
            const result = await API.queryData(this.state.currentDataSource.id, metric, {
                start: start.toISOString(),
                end: end.toISOString(),
                step,
            });

            if (result.success && result.data && result.data.length > 0) {
                const metricData = result.data[0];
                this.state.queryData = {
                    name: metricData.name,
                    timestamps: metricData.data.map(d => d.timestamp),
                    values: metricData.data.map(d => d.value),
                };

                this.displayStats();
                this.displayChart();
                this.autoTrainRange();

                Helpers.showToast(`查询成功！获取到${metricData.data.length}个数据点`, 'success');
            } else {
                Helpers.showToast('查询失败: ' + (result.error || '无数据'), 'error');
            }
        } catch (error) {
            Helpers.showToast('查询失败: ' + error.message, 'error');
        } finally {
            Helpers.showLoading(false);
        }
    },

    /**
     * Display statistics
     */
    displayStats() {
        const data = this.state.queryData;
        if (!data) return;

        const values = data.values;
        document.getElementById('stat-count').textContent = values.length;
        document.getElementById('stat-min').textContent = Helpers.formatNumber(Math.min(...values));
        document.getElementById('stat-max').textContent = Helpers.formatNumber(Math.max(...values));
        document.getElementById('stat-mean').textContent = Helpers.formatNumber(values.reduce((a, b) => a + b, 0) / values.length);

        document.getElementById('stats-panel').style.display = 'block';
    },

    /**
     * Display chart
     */
    displayChart() {
        const data = this.state.queryData;
        if (!data) return;

        document.getElementById('chart-panel').style.display = 'block';
        document.getElementById('chart-title').textContent = `指标: ${data.name}`;

        Charts.createTimeSeriesChart('main-chart', data, {
            title: '',
            trainStart: this.state.trainStart,
            trainEnd: this.state.trainEnd,
        });

        document.getElementById('training-panel').style.display = 'block';
    },

    /**
     * Set training range
     */
    setTrainRange() {
        const start = document.getElementById('train-start').value;
        const end = document.getElementById('train-end').value;

        if (!start || !end) {
            Helpers.showToast('请选择训练区间', 'error');
            return;
        }

        this.state.trainStart = new Date(start).toISOString();
        this.state.trainEnd = new Date(end + 'T23:59:59').toISOString();

        document.getElementById('train-range-text').textContent = `${start} ~ ${end}`;

        // Refresh chart
        if (this.state.queryData) {
            Charts.createTimeSeriesChart('main-chart', this.state.queryData, {
                trainStart: this.state.trainStart,
                trainEnd: this.state.trainEnd,
            });
        }

        Helpers.showToast('训练区间已设置', 'success');
    },

    /**
     * Auto set training range (80%)
     */
    autoTrainRange() {
        const data = this.state.queryData;
        if (!data || data.timestamps.length === 0) return;

        const splitIdx = Math.floor(data.timestamps.length * 0.8);
        const startDate = new Date(data.timestamps[0]);
        const endDate = new Date(data.timestamps[splitIdx]);

        document.getElementById('train-start').value = Helpers.formatDateOnly(startDate);
        document.getElementById('train-end').value = Helpers.formatDateOnly(endDate);

        this.state.trainStart = startDate.toISOString();
        this.state.trainEnd = endDate.toISOString();

        document.getElementById('train-range-text').textContent =
            `${Helpers.formatDateOnly(startDate)} ~ ${Helpers.formatDateOnly(endDate)}`;

        // Refresh chart
        Charts.createTimeSeriesChart('main-chart', data, {
            trainStart: this.state.trainStart,
            trainEnd: this.state.trainEnd,
        });
    },

    /**
     * Load models
     */
    async loadModels() {
        try {
            const models = await API.listModels();
            this.state.models = models;
            this.displayModelList();
        } catch (error) {
            Helpers.showToast('加载模型失败: ' + error.message, 'error');
        }
    },

    /**
     * Display model list
     */
    displayModelList() {
        const container = document.getElementById('model-list');
        container.innerHTML = '';

        this.state.models.forEach(model => {
            const item = document.createElement('div');
            item.className = 'model-item';
            item.dataset.modelId = model.id;

            const isSelected = this.state.selectedModels.includes(model.id);
            if (isSelected) item.classList.add('selected');

            item.innerHTML = `
                <input type="checkbox" ${isSelected ? 'checked' : ''}>
                <span class="model-color" style="background: ${model.color}"></span>
                <span class="model-name">${model.name}</span>
            `;

            item.addEventListener('click', () => this.toggleModelSelection(model.id));
            container.appendChild(item);
        });

        document.getElementById('comparison-panel').style.display = 'block';
    },

    /**
     * Toggle model selection
     */
    toggleModelSelection(modelId) {
        const index = this.state.selectedModels.indexOf(modelId);
        if (index === -1) {
            this.state.selectedModels.push(modelId);
        } else {
            this.state.selectedModels.splice(index, 1);
        }
        this.displayModelList();
    },

    /**
     * Run comparison
     */
    async runComparison() {
        if (this.state.selectedModels.length === 0) {
            Helpers.showToast('请选择至少一个模型', 'error');
            return;
        }

        if (!this.state.queryData || !this.state.trainStart || !this.state.trainEnd) {
            Helpers.showToast('请先查询数据并设置训练区间', 'error');
            return;
        }

        Helpers.showLoading(true, '正在运行模型对比...');

        try {
            const result = await API.compareModels(
                this.state.selectedModels,
                this.state.queryData.values,
                this.state.queryData.timestamps,
                this.state.trainStart,
                this.state.trainEnd
            );

            this.state.comparisonResults = result;
            this.displayComparisonResults(result);
            Helpers.showToast('对比完成', 'success');
        } catch (error) {
            Helpers.showToast('对比失败: ' + error.message, 'error');
        } finally {
            Helpers.showLoading(false);
        }
    },

    /**
     * Display comparison results
     */
    displayComparisonResults(result) {
        document.getElementById('results-panel').style.display = 'block';

        // Results table
        const tbody = document.getElementById('results-body');
        tbody.innerHTML = '';

        result.results.forEach(r => {
            const tr = document.createElement('tr');

            const mape = r.success ? Helpers.formatNumber(r.mape, 2) : '-';
            const mae = r.success ? Helpers.formatNumber(r.mae, 2) : '-';
            const coverage = r.success ? Helpers.formatPercent(r.coverage) : '-';
            const status = r.success
                ? '<span class="status-badge status-success">成功</span>'
                : `<span class="status-badge status-error">${r.error || '失败'}</span>`;

            tr.innerHTML = `
                <td>${r.model_name}</td>
                <td>${mape}</td>
                <td>${mae}</td>
                <td>${coverage}</td>
                <td>${status}</td>
            `;
            tbody.appendChild(tr);
        });

        // Comparison chart
        if (result.test_data) {
            const testData = {
                timestamps: result.test_data.data.map(d => d.timestamp),
                values: result.test_data.data.map(d => d.value),
            };

            Charts.createComparisonChart(
                'comparison-chart',
                testData,
                result.results,
                this.state.models
            );
        }
    },

    /**
     * Refresh dashboard
     */
    async refresh() {
        await this.loadDataSources();
        await this.loadModels();
        Helpers.showToast('刷新完成', 'success');
    },
};

// Make Dashboard globally available
window.Dashboard = Dashboard;