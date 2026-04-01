/**
 * DataQuery Component - Reusable data query logic for Pipeline creation
 */

const DataQuery = {
    // State
    state: {
        endpoints: [],
        metrics: [],
        queryData: null,
        trainStart: null,
        trainEnd: null,
        dataTimeRange: null,
    },

    // Prefix for element IDs (allows multiple instances)
    prefix: '',

    /**
     * Initialize data query component
     * @param {string} prefix - Prefix for element IDs (e.g., 'edit-pipeline-' or '')
     */
    init(prefix = '') {
        this.prefix = prefix;
        this.bindEvents();
        return this.loadData();
    },

    /**
     * Get element ID with prefix
     */
    getElementId(baseId) {
        return this.prefix ? `${this.prefix}${baseId}` : baseId;
    },

    /**
     * Get element by base ID
     */
    getElement(baseId) {
        return document.getElementById(this.getElementId(baseId));
    },

    /**
     * Bind event listeners
     */
    bindEvents() {
        // Endpoint selection
        const endpointSelect = this.getElement('endpoint');
        if (endpointSelect) {
            endpointSelect.addEventListener('change', (e) => this.onEndpointChange(e.target.value));
        }

        // Metric selection
        const metricSelect = this.getElement('metric');
        if (metricSelect) {
            metricSelect.addEventListener('change', () => this.onMetricChange());
        }

        // Query button (optional - for pages that have preview)
        const btnQuery = this.getElement('btn-query');
        if (btnQuery) {
            btnQuery.addEventListener('click', () => this.executeQuery());
        }

        // Period select change
        const periodSelect = this.getElement('period');
        if (periodSelect) {
            periodSelect.addEventListener('change', () => {
                if (this.state.queryData) this.executeQuery();
            });
        }

        // Step select change
        const stepSelect = this.getElement('step');
        if (stepSelect) {
            stepSelect.addEventListener('change', () => {
                if (this.state.queryData) this.executeQuery();
            });
        }
    },

    /**
     * Load initial data (endpoints, metrics, time range)
     */
    async loadData() {
        try {
            // Load time range
            await this.loadDataTimeRange();

            // Load endpoints
            await this.loadEndpoints();
        } catch (error) {
            Helpers.showToast('加载数据失败: ' + error.message, 'error');
        }
    },

    /**
     * Load data time range from global TimescaleDB
     */
    async loadDataTimeRange(endpoint = null) {
        try {
            const timeRange = await API.getTimeRange(endpoint);
            this.state.dataTimeRange = timeRange;
        } catch (e) {
            this.state.dataTimeRange = null;
        }
    },

    /**
     * Get query time range based on data's max_time and selected period
     */
    getQueryTimeRange(days) {
        let endTime;
        if (this.state.dataTimeRange && this.state.dataTimeRange.max_time) {
            endTime = new Date(this.state.dataTimeRange.max_time);
        } else {
            endTime = new Date();
        }

        const startTime = new Date(endTime.getTime() - days * 24 * 60 * 60 * 1000);
        return { start: startTime, end: endTime };
    },

    /**
     * Load endpoints (endpoint label values)
     */
    async loadEndpoints() {
        const select = this.getElement('endpoint');
        if (!select) {
            // No endpoint select, load metrics directly
            await this.loadMetrics();
            return;
        }

        select.innerHTML = '<option value="">请选择 Endpoint...</option>';
        select.disabled = false;

        try {
            const result = await API.listEndpoints();
            this.state.endpoints = result.values || [];

            this.state.endpoints.forEach(endpoint => {
                const option = document.createElement('option');
                option.value = endpoint;
                option.textContent = endpoint;
                select.appendChild(option);
            });

            if (this.state.endpoints.length > 0) {
                select.value = this.state.endpoints[0];
                await this.onEndpointChange(this.state.endpoints[0]);
            } else {
                select.disabled = true;
                await this.loadMetrics();
            }
        } catch (error) {
            select.disabled = true;
            select.innerHTML = '<option value="">-</option>';
            await this.loadMetrics();
        }
    },

    /**
     * Handle endpoint change
     */
    async onEndpointChange(endpoint) {
        const metricSelect = this.getElement('metric');
        if (!endpoint) {
            if (metricSelect) {
                metricSelect.innerHTML = '<option value="">请选择指标...</option>';
            }
            return;
        }

        // Reload time range for this specific endpoint
        await this.loadDataTimeRange(endpoint);

        // Load metrics for this endpoint
        await this.loadMetrics();
    },

    /**
     * Handle metric change - auto execute query if query button exists
     */
    async onMetricChange() {
        const metricSelect = this.getElement('metric');
        if (!metricSelect) return;

        const metric = metricSelect.value;
        const btnQuery = this.getElement('btn-query');

        if (metric && btnQuery) {
            await this.executeQuery();
        }
    },

    /**
     * Load metrics for current endpoint
     */
    async loadMetrics() {
        try {
            const metrics = await API.listMetrics();
            this.state.metrics = metrics;

            const select = this.getElement('metric');
            if (!select) return;

            select.innerHTML = '<option value="">请选择指标...</option>';

            metrics.forEach(m => {
                const option = document.createElement('option');
                option.value = m.name;
                option.textContent = m.name;
                select.appendChild(option);
            });

            // Auto-select first metric
            if (metrics.length > 0) {
                select.value = metrics[0].name;
                const btnQuery = this.getElement('btn-query');
                if (btnQuery) {
                    await this.executeQuery();
                }
            }
        } catch (error) {
            Helpers.showToast('加载指标失败: ' + error.message, 'error');
        }
    },

    /**
     * Execute query
     */
    async executeQuery() {
        const metricSelect = this.getElement('metric');
        const metric = metricSelect ? metricSelect.value : null;

        if (!metric) {
            Helpers.showToast('请选择指标', 'error');
            return;
        }

        // Get period and step from dropdowns
        const periodSelect = this.getElement('period');
        const stepSelect = this.getElement('step');
        const days = periodSelect ? parseInt(periodSelect.value) || 1 : 1;
        const step = stepSelect ? stepSelect.value || '1m' : '1m';

        // Get selected endpoint
        const endpointSelect = this.getElement('endpoint');
        const endpoint = endpointSelect && !endpointSelect.disabled ? endpointSelect.value : null;

        const { start, end } = this.getQueryTimeRange(days);

        Helpers.showLoading(true, '正在查询数据...');

        try {
            const result = await API.queryData(metric, {
                start: start.toISOString(),
                end: end.toISOString(),
                step,
            }, endpoint);

            if (result.success && result.data && result.data.length > 0) {
                const metricData = result.data[0];
                this.state.queryData = {
                    name: metricData.name,
                    timestamps: metricData.data.map(d => d.timestamp),
                    values: metricData.data.map(d => d.value),
                };

                this.onQuerySuccess();
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
     * Handle query success - can be overridden by caller
     */
    onQuerySuccess() {
        // Default: trigger auto train range if elements exist
        this.autoTrainRange();
    },

    /**
     * Auto set training range (full data range)
     */
    autoTrainRange() {
        const data = this.state.queryData;
        if (!data || data.timestamps.length === 0) return;

        const startDate = new Date(data.timestamps[0]);
        const endDate = new Date(data.timestamps[data.timestamps.length - 1]);

        // Update state
        this.state.trainStart = startDate.toISOString();
        this.state.trainEnd = endDate.toISOString();

        // Try to update UI elements if they exist
        const trainStartInput = this.getElement('train-start');
        const trainEndInput = this.getElement('train-end');
        const trainRangeText = this.getElement('train-range-text');

        if (trainStartInput) {
            trainStartInput.value = Helpers.formatDateOnly(startDate);
        }
        if (trainEndInput) {
            trainEndInput.value = Helpers.formatDateOnly(endDate);
        }
        if (trainRangeText) {
            trainRangeText.textContent = `${Helpers.formatDateOnly(startDate)} ~ ${Helpers.formatDateOnly(endDate)}`;
        }
    },

    /**
     * Set training range manually from UI
     */
    setTrainRange() {
        const trainStartInput = this.getElement('train-start');
        const trainEndInput = this.getElement('train-end');

        if (!trainStartInput || !trainEndInput) return;

        const start = trainStartInput.value;
        const end = trainEndInput.value;

        if (!start || !end) {
            Helpers.showToast('请选择训练区间', 'error');
            return;
        }

        this.state.trainStart = new Date(start).toISOString();
        this.state.trainEnd = new Date(end + 'T23:59:59').toISOString();

        const trainRangeText = this.getElement('train-range-text');
        if (trainRangeText) {
            trainRangeText.textContent = `${start} ~ ${end}`;
        }

        Helpers.showToast('训练区间已设置', 'success');
    },

    /**
     * Get current metric
     */
    getMetric() {
        const metricSelect = this.getElement('metric');
        return metricSelect ? metricSelect.value : null;
    },

    /**
     * Get current endpoint
     */
    getEndpoint() {
        const endpointSelect = this.getElement('endpoint');
        return endpointSelect && !endpointSelect.disabled ? endpointSelect.value : null;
    },

    /**
     * Get current step
     */
    getStep() {
        const stepSelect = this.getElement('step');
        return stepSelect ? stepSelect.value : '1m';
    },

    /**
     * Get query data
     */
    getQueryData() {
        return this.state.queryData;
    },

    /**
     * Get train range
     */
    getTrainRange() {
        return {
            start: this.state.trainStart,
            end: this.state.trainEnd,
        };
    },

    /**
     * Set endpoint programmatically
     */
    async setEndpoint(endpoint) {
        const endpointSelect = this.getElement('endpoint');
        if (endpointSelect && endpoint) {
            endpointSelect.value = endpoint;
            await this.onEndpointChange(endpoint);
        }
    },

    /**
     * Set metric programmatically
     */
    setMetric(metric) {
        const metricSelect = this.getElement('metric');
        if (metricSelect && metric) {
            metricSelect.value = metric;
        }
    },

    /**
     * Reset state
     */
    reset() {
        this.state = {
            endpoints: [],
            metrics: [],
            queryData: null,
            trainStart: null,
            trainEnd: null,
            dataTimeRange: null,
        };
    },
};

// Make DataQuery globally available
window.DataQuery = DataQuery;