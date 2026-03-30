/**
 * Pipeline Management Component
 */

const Pipelines = {
    pipelines: [],
    runningJobs: [],
    models: [],
    currentPipeline: null,
    pollInterval: null,
    globalPollInterval: null,
    dataQuery: null,
    tooltipEl: null,

    init() {
        this.bindEvents();
    },

    bindEvents() {
        // Add pipeline button
        const btnAdd = document.getElementById('btn-add-pipeline');
        if (btnAdd) {
            btnAdd.addEventListener('click', () => this.showCreateForm());
        }

        // Back button
        const btnBack = document.getElementById('btn-back-pipelines');
        if (btnBack) {
            btnBack.addEventListener('click', () => Sidebar.navigateTo('pipelines'));
        }

        // Save pipeline button
        const btnSave = document.getElementById('btn-save-pipeline');
        if (btnSave) {
            btnSave.addEventListener('click', () => this.savePipeline());
        }

        // Run pipeline button
        const btnRun = document.getElementById('btn-run-pipeline');
        if (btnRun) {
            btnRun.addEventListener('click', () => this.runCurrentPipeline());
        }

        // Model change handler
        const modelSelect = document.getElementById('edit-pipeline-model');
        if (modelSelect) {
            modelSelect.addEventListener('change', () => this.onModelChange());
        }
    },

    async refresh() {
        try {
            Helpers.showLoading();
            await Promise.all([
                this.loadPipelines(),
                this.loadModels(),
                this.loadRunningJobs(),
            ]);
            this.render();
            this.startGlobalPolling();
        } catch (error) {
            Helpers.showToast('加载失败: ' + error.message, 'error');
        } finally {
            Helpers.hideLoading();
        }
    },

    async loadPipelines() {
        this.pipelines = await API.listPipelines();
    },

    async loadRunningJobs() {
        this.runningJobs = await API.listRunningJobs();
    },

    getRunningJobForPipeline(pipelineId) {
        return this.runningJobs.find(j => j.pipeline_id === pipelineId);
    },

    async loadModels() {
        this.models = await API.listModels();
    },

    render() {
        const container = document.getElementById('pipelines-grid');
        if (!container) return;

        if (this.pipelines.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <span class="empty-icon">🔧</span>
                    <p>暂无 Pipeline</p>
                    <button class="btn btn-primary" onclick="Pipelines.showCreateForm()">
                        创建第一个 Pipeline
                    </button>
                </div>
            `;
            return;
        }

        container.innerHTML = this.pipelines.map(p => this.renderPipelineCard(p)).join('');
    },

    renderPipelineCard(pipeline) {
        const statusClass = pipeline.enabled ? 'enabled' : 'disabled';
        const statusText = pipeline.enabled ? '已启用' : '已禁用';
        const runningJob = this.getRunningJobForPipeline(pipeline.id);

        let jobStatusHtml = '';
        if (runningJob) {
            const jobStatusColors = {
                pending: '#f0ad4e',
                running: '#5bc0de',
            };
            const jobStatusTexts = {
                pending: '等待中',
                running: '运行中',
            };
            const jobColor = jobStatusColors[runningJob.status] || '#777';
            const jobText = jobStatusTexts[runningJob.status] || runningJob.status;

            jobStatusHtml = `
                <div class="pipeline-job-status">
                    <div class="job-mini-progress">
                        <div class="progress-bar-mini">
                            <div class="progress-fill-mini" style="width: ${runningJob.progress}%; background-color: ${jobColor}"></div>
                        </div>
                        <span class="progress-text-mini">${runningJob.progress}%</span>
                        <span class="job-status-mini" style="color: ${jobColor}">${jobText}</span>
                    </div>
                    ${runningJob.current_step ? `<span class="current-step-mini">${runningJob.current_step}</span>` : ''}
                    <button class="btn btn-xs btn-view-job" onclick="Pipelines.viewRunningJob('${runningJob.id}', '${pipeline.id}')">
                        查看
                    </button>
                </div>
            `;
        }

        // Get model name from model_info or use algorithm as fallback
        const modelName = pipeline.model_info?.name || pipeline.algorithm;

        return `
            <div class="pipeline-card" data-id="${pipeline.id}">
                <div class="pipeline-header">
                    <h4 class="pipeline-name">${pipeline.name}</h4>
                    <span class="pipeline-status ${statusClass}">${statusText}</span>
                </div>
                <div class="pipeline-body">
                    <div class="pipeline-info">
                        <span class="info-label">指标:</span>
                        <span class="info-value">${pipeline.metric_id}</span>
                    </div>
                    <div class="pipeline-info">
                        <span class="info-label">模型:</span>
                        <span class="info-value algo-badge">${modelName}</span>
                    </div>
                    <div class="pipeline-info">
                        <span class="info-label">训练时间:</span>
                        <span class="info-value">${this.formatTimeRange(pipeline.train_start, pipeline.train_end)}</span>
                    </div>
                    ${jobStatusHtml}
                </div>
                <div class="pipeline-footer">
                    <button class="btn btn-sm btn-primary" onclick="Pipelines.runPipeline('${pipeline.id}')">
                        ▶ 运行
                    </button>
                    <button class="btn btn-sm btn-secondary" onclick="Pipelines.showEditForm('${pipeline.id}')">
                        ✏ 编辑
                    </button>
                    <button class="btn btn-sm btn-danger" onclick="Pipelines.deletePipeline('${pipeline.id}')">
                        🗑 删除
                    </button>
                </div>
            </div>
        `;
    },

    formatTimeRange(start, end) {
        const s = new Date(start);
        const e = new Date(end);
        const days = Math.ceil((e - s) / (1000 * 60 * 60 * 24));
        return `${s.toLocaleDateString()} ~ ${e.toLocaleDateString()} (${days}天)`;
    },

    showCreateForm() {
        this.currentPipeline = null;
        document.getElementById('edit-pipeline-title').textContent = '创建 Pipeline';
        this.clearForm();
        this.initDataQuery();
        this.populateModels();
        Sidebar.navigateToPipelineEdit();
    },

    async showEditForm(pipelineId) {
        try {
            Helpers.showLoading();
            const pipeline = await API.getPipeline(pipelineId);
            this.currentPipeline = pipeline;
            document.getElementById('edit-pipeline-title').textContent = '编辑 Pipeline';
            await this.initDataQuery();  // 等待数据源加载完成
            this.populateModels();
            await this.fillForm(pipeline);
            Sidebar.navigateToPipelineEdit();
        } catch (error) {
            Helpers.showToast('加载失败: ' + error.message, 'error');
        } finally {
            Helpers.hideLoading();
        }
    },

    async initDataQuery() {
        if (!this.dataQuery) {
            this.dataQuery = Object.assign({}, DataQuery);
        }
        await this.dataQuery.init('edit-pipeline-');

        this.dataQuery.onQuerySuccess = () => {
            this.showPreview();
        };
    },

    populateModels() {
        const modelSelect = document.getElementById('edit-pipeline-model');
        if (modelSelect) {
            modelSelect.innerHTML = '<option value="">选择模型...</option>' +
                this.models.map(model =>
                    `<option value="${model.id}" data-type="${model.model_type}">${model.name} (${model.model_type})</option>`
                ).join('');
        }
    },

    async fillForm(pipeline) {
        document.getElementById('edit-pipeline-name').value = pipeline.name || '';
        document.getElementById('edit-pipeline-desc').value = pipeline.description || '';

        // Set data source and wait for endpoints/metrics to load
        if (pipeline.datasource_id) {
            await this.dataQuery.setDataSource(pipeline.datasource_id);
        }

        // Set endpoint if exists
        if (pipeline.endpoint) {
            await this.dataQuery.setEndpoint(pipeline.endpoint);
        }

        // Set metric
        if (pipeline.metric_id) {
            this.dataQuery.setMetric(pipeline.metric_id);
        }

        // Set step
        if (pipeline.step) {
            const stepSelect = document.getElementById('edit-pipeline-step');
            if (stepSelect) stepSelect.value = pipeline.step;
        }

        // Set model selection
        if (pipeline.model_id) {
            document.getElementById('edit-pipeline-model').value = pipeline.model_id;
            this.onModelChange(pipeline.override_params || {});
        } else if (pipeline.algorithm) {
            // Fallback: find a model with matching type
            const matchingModel = this.models.find(m => m.model_type === pipeline.algorithm);
            if (matchingModel) {
                document.getElementById('edit-pipeline-model').value = matchingModel.id;
                this.onModelChange(pipeline.algorithm_params || {});
            }
        }

        // Set train range dates if exists
        if (pipeline.train_start) {
            const trainStartInput = document.getElementById('edit-pipeline-train-start');
            if (trainStartInput) {
                trainStartInput.value = Helpers.formatDateOnly(new Date(pipeline.train_start));
            }
        }
        if (pipeline.train_end) {
            const trainEndInput = document.getElementById('edit-pipeline-train-end');
            if (trainEndInput) {
                trainEndInput.value = Helpers.formatDateOnly(new Date(pipeline.train_end));
            }
        }
    },

    clearForm() {
        document.getElementById('edit-pipeline-name').value = '';
        document.getElementById('edit-pipeline-desc').value = '';
        document.getElementById('edit-pipeline-model').value = '';
        document.getElementById('edit-pipeline-model-params').innerHTML = '';
        document.getElementById('edit-pipeline-model-params-section').style.display = 'none';
        document.getElementById('edit-pipeline-train-start').value = '';
        document.getElementById('edit-pipeline-train-end').value = '';

        // Hide preview panels
        document.getElementById('edit-pipeline-stats-panel').style.display = 'none';
        document.getElementById('edit-pipeline-chart-panel').style.display = 'none';
        document.getElementById('edit-pipeline-training-panel').style.display = 'none';

        // Reset data query state
        if (this.dataQuery) {
            this.dataQuery.reset();
        }
    },

    onModelChange(overrideParams = null) {
        const modelSelect = document.getElementById('edit-pipeline-model');
        const modelId = modelSelect.value;
        const paramsSection = document.getElementById('edit-pipeline-model-params-section');
        const paramsContainer = document.getElementById('edit-pipeline-model-params');

        if (!modelId) {
            paramsSection.style.display = 'none';
            paramsContainer.innerHTML = '';
            return;
        }

        const model = this.models.find(m => m.id === modelId);
        if (!model) return;

        paramsSection.style.display = 'block';
        paramsContainer.innerHTML = this.getModelParamsHTML(model, overrideParams || {});
        this.bindTooltipEvents();
    },

    getModelParamsHTML(model, overrideParams) {
        const type = model.model_type;
        const help = (text) => `<span class="help-icon" data-tooltip="${text}">?</span>`;
        const wrap = (label, tooltip, input) => `
            <div class="param-editor-item">
                <div class="param-label-wrapper">
                    <label>${label}</label>
                    ${help(tooltip)}
                </div>
                ${input}
            </div>
        `;

        // Helper to get value: override > model default
        const getVal = (key, def) => overrideParams[key] !== undefined ? overrideParams[key] : (model[key] !== undefined ? model[key] : def);

        if (type === 'prophet') {
            return `
                <div class="param-section">
                    <h4 class="param-section-title">基本参数</h4>
                    <div class="param-grid">
                        ${wrap('增长类型', '趋势增长模式：linear-线性增长，logistic-逻辑增长 (需设置容量上限)，flat-无趋势', `
                            <select id="pipeline-param-growth" class="form-control">
                                <option value="linear" ${getVal('growth', 'linear') === 'linear' ? 'selected' : ''}>linear (线性)</option>
                                <option value="logistic" ${getVal('growth', 'linear') === 'logistic' ? 'selected' : ''}>logistic (逻辑)</option>
                                <option value="flat" ${getVal('growth', 'linear') === 'flat' ? 'selected' : ''}>flat (平坦)</option>
                            </select>
                        `)}
                        ${wrap('季节性模式', '季节性叠加方式：additive-加法 (固定振幅)，multiplicative-乘法 (振幅随趋势变化)', `
                            <select id="pipeline-param-seasonality-mode" class="form-control">
                                <option value="additive" ${getVal('seasonality_mode', 'additive') === 'additive' ? 'selected' : ''}>additive (加法)</option>
                                <option value="multiplicative" ${getVal('seasonality_mode', 'additive') === 'multiplicative' ? 'selected' : ''}>multiplicative (乘法)</option>
                            </select>
                        `)}
                        ${wrap('置信区间宽度', '预测置信区间宽度，表示预测值落在该区间内的概率', `
                            <input type="number" id="pipeline-param-interval-width" class="form-control" value="${getVal('interval_width', 0.95)}" step="0.01" min="0.8" max="0.99">
                        `)}
                    </div>
                </div>
                <div class="param-section">
                    <h4 class="param-section-title">变点设置</h4>
                    <div class="param-grid">
                        ${wrap('变点数量', '模型自动检测的趋势变化点数量', `
                            <input type="number" id="pipeline-param-n-changepoints" class="form-control" value="${getVal('n_changepoints', 25)}" min="0" max="100">
                        `)}
                        ${wrap('变点范围', '变点在时间序列中的占比', `
                            <input type="number" id="pipeline-param-changepoint-range" class="form-control" value="${getVal('changepoint_range', 0.8)}" step="0.05" min="0.5" max="0.95">
                        `)}
                        ${wrap('变点灵活性', '控制趋势变化的灵活度', `
                            <input type="number" id="pipeline-param-changepoint-prior" class="form-control" value="${getVal('changepoint_prior_scale', 0.05)}" step="0.01" min="0.001" max="0.5">
                        `)}
                    </div>
                </div>
                <div class="param-section">
                    <h4 class="param-section-title">季节性设置</h4>
                    <div class="param-grid">
                        ${wrap('季节性强度', '季节性成分的先验尺度', `
                            <input type="number" id="pipeline-param-seasonality-prior" class="form-control" value="${getVal('seasonality_prior_scale', 10.0)}" step="1.0" min="0.1" max="100">
                        `)}
                        ${wrap('年度季节性', '是否启用年度季节性模式 (365 天周期)', `
                            <select id="pipeline-param-yearly-seasonality" class="form-control">
                                <option value="auto" ${getVal('yearly_seasonality', 'auto') === 'auto' ? 'selected' : ''}>auto (自动)</option>
                                <option value="true" ${getVal('yearly_seasonality', 'auto') === true || getVal('yearly_seasonality', 'auto') === 'true' ? 'selected' : ''}>启用</option>
                                <option value="false" ${getVal('yearly_seasonality', 'auto') === false || getVal('yearly_seasonality', 'auto') === 'false' ? 'selected' : ''}>禁用</option>
                            </select>
                        `)}
                        ${wrap('周季节性', '是否启用周季节性模式 (7 天周期)', `
                            <select id="pipeline-param-weekly-seasonality" class="form-control">
                                <option value="true" ${getVal('weekly_seasonality', false) ? 'selected' : ''}>启用</option>
                                <option value="false" ${!getVal('weekly_seasonality', false) ? 'selected' : ''}>禁用</option>
                            </select>
                        `)}
                        ${wrap('日季节性', '是否启用日季节性模式 (24 小时周期)', `
                            <select id="pipeline-param-daily-seasonality" class="form-control">
                                <option value="true" ${getVal('daily_seasonality', true) ? 'selected' : ''}>启用</option>
                                <option value="false" ${!getVal('daily_seasonality', true) ? 'selected' : ''}>禁用</option>
                            </select>
                        `)}
                        <div class="param-editor-item checkbox-item">
                            <label>
                                <input type="checkbox" id="pipeline-param-add-monthly" ${getVal('add_monthly_seasonality', false) ? 'checked' : ''}>
                                添加月度季节性
                                ${help('是否启用月度季节性模式 (30.5 天周期)')}
                            </label>
                        </div>
                    </div>
                </div>
                <div class="param-section">
                    <h4 class="param-section-title">其他设置</h4>
                    <div class="param-grid">
                        <div class="param-editor-item checkbox-item">
                            <label>
                                <input type="checkbox" id="pipeline-param-non-negative" ${getVal('enforce_non_negative', true) ? 'checked' : ''}>
                                强制非负值
                                ${help('强制预测值为非负，适用于不可能为负的指标')}
                            </label>
                        </div>
                    </div>
                </div>
            `;
        } else if (type === 'welford') {
            return `
                <div class="param-editor">
                    ${wrap('Sigma 倍数', '阈值 = 均值 ± sigma × 标准差，倍数越大阈值范围越宽', `
                        <input type="number" id="pipeline-param-sigma" class="form-control" value="${getVal('sigma_multiplier', 3.0)}" step="0.1" min="1" max="5">
                    `)}
                    ${wrap('使用滚动窗口', '使用滚动窗口计算统计值，适用于非平稳序列', `
                        <select id="pipeline-param-rolling-window" class="form-control">
                            <option value="false" ${!getVal('use_rolling_window', false) ? 'selected' : ''}>禁用</option>
                            <option value="true" ${getVal('use_rolling_window', false) ? 'selected' : ''}>启用</option>
                        </select>
                    `)}
                    ${wrap('窗口大小', '滚动窗口的数据点数量，仅在启用滚动窗口时有效', `
                        <input type="number" id="pipeline-param-window-size" class="form-control" value="${getVal('window_size', 1000) || ''}" min="100" placeholder="1000">
                    `)}
                </div>
            `;
        } else if (type === 'static') {
            return `
                <div class="param-editor">
                    ${wrap('上限百分位', '使用历史数据的百分位作为静态阈值上限', `
                        <input type="number" id="pipeline-param-upper-percentile" class="form-control" value="${getVal('upper_percentile', 99.0)}" step="0.1" min="90" max="99.9">
                    `)}
                    ${wrap('下限', '固定下限值，低于此值将触发告警', `
                        <input type="number" id="pipeline-param-lower-bound" class="form-control" value="${getVal('lower_bound', 0)}" step="0.1">
                    `)}
                </div>
            `;
        }
        return '';
    },

    collectOverrideParams() {
        const modelSelect = document.getElementById('edit-pipeline-model');
        const modelId = modelSelect.value;
        if (!modelId) return {};

        const model = this.models.find(m => m.id === modelId);
        if (!model) return {};

        const type = model.model_type;
        const params = {};

        const getVal = (id) => {
            const el = document.getElementById(id);
            return el ? el.value : null;
        };

        const getNum = (id) => {
            const el = document.getElementById(id);
            return el ? parseFloat(el.value) : null;
        };

        const getBool = (id) => {
            const el = document.getElementById(id);
            if (!el) return null;
            return el.value === 'true' || el.checked;
        };

        if (type === 'prophet') {
            const growth = getVal('pipeline-param-growth');
            const seasonalityMode = getVal('pipeline-param-seasonality-mode');
            const intervalWidth = getNum('pipeline-param-interval-width');
            const nChangepoints = getNum('pipeline-param-n-changepoints');
            const changepointRange = getNum('pipeline-param-changepoint-range');
            const changepointPrior = getNum('pipeline-param-changepoint-prior');
            const seasonalityPrior = getNum('pipeline-param-seasonality-prior');
            const yearlySeasonality = getVal('pipeline-param-yearly-seasonality');
            const weeklySeasonality = getBool('pipeline-param-weekly-seasonality');
            const dailySeasonality = getBool('pipeline-param-daily-seasonality');
            const addMonthly = getBool('pipeline-param-add-monthly');
            const nonNegative = getBool('pipeline-param-non-negative');

            if (growth !== model.growth) params.growth = growth;
            if (seasonalityMode !== model.seasonality_mode) params.seasonality_mode = seasonalityMode;
            if (intervalWidth !== model.interval_width) params.interval_width = intervalWidth;
            if (nChangepoints !== model.n_changepoints) params.n_changepoints = nChangepoints;
            if (changepointRange !== model.changepoint_range) params.changepoint_range = changepointRange;
            if (changepointPrior !== model.changepoint_prior_scale) params.changepoint_prior_scale = changepointPrior;
            if (seasonalityPrior !== model.seasonality_prior_scale) params.seasonality_prior_scale = seasonalityPrior;
            const yearlyVal = yearlySeasonality === 'true' ? true : (yearlySeasonality === 'false' ? false : yearlySeasonality);
            if (yearlyVal !== model.yearly_seasonality) params.yearly_seasonality = yearlyVal;
            if (weeklySeasonality !== !!model.weekly_seasonality) params.weekly_seasonality = weeklySeasonality;
            if (dailySeasonality !== !!model.daily_seasonality) params.daily_seasonality = dailySeasonality;
            if (addMonthly !== !!model.add_monthly_seasonality) params.add_monthly_seasonality = addMonthly;
            if (nonNegative !== !!model.enforce_non_negative) params.enforce_non_negative = nonNegative;

        } else if (type === 'welford') {
            const sigma = getNum('pipeline-param-sigma');
            const rollingWindow = getBool('pipeline-param-rolling-window');
            const windowSize = getNum('pipeline-param-window-size');

            if (sigma !== model.sigma_multiplier) params.sigma_multiplier = sigma;
            if (rollingWindow !== !!model.use_rolling_window) params.use_rolling_window = rollingWindow;
            if (windowSize && windowSize !== model.window_size) params.window_size = windowSize;

        } else if (type === 'static') {
            const upperPercentile = getNum('pipeline-param-upper-percentile');
            const lowerBound = getNum('pipeline-param-lower-bound');

            if (upperPercentile !== model.upper_percentile) params.upper_percentile = upperPercentile;
            if (lowerBound !== model.lower_bound) params.lower_bound = lowerBound;
        }

        return params;
    },

    showPreview() {
        const data = this.dataQuery.getQueryData();
        if (!data) return;

        const values = data.values;
        document.getElementById('edit-pipeline-stat-count').textContent = values.length;
        document.getElementById('edit-pipeline-stat-min').textContent = Helpers.formatNumber(Math.min(...values));
        document.getElementById('edit-pipeline-stat-max').textContent = Helpers.formatNumber(Math.max(...values));
        document.getElementById('edit-pipeline-stat-mean').textContent = Helpers.formatNumber(values.reduce((a, b) => a + b, 0) / values.length);
        document.getElementById('edit-pipeline-stats-panel').style.display = 'block';

        // Auto set train range (80% of data) if not already set
        const trainStartInput = document.getElementById('edit-pipeline-train-start');
        const trainEndInput = document.getElementById('edit-pipeline-train-end');
        if (data.timestamps.length > 0 && (!trainStartInput.value || !trainEndInput.value)) {
            const splitIdx = Math.floor(data.timestamps.length * 0.8);
            const startDate = new Date(data.timestamps[0]);
            const endDate = new Date(data.timestamps[splitIdx]);
            trainStartInput.value = Helpers.formatDateOnly(startDate);
            trainEndInput.value = Helpers.formatDateOnly(endDate);
        }

        // Get train range from inputs for chart display
        const trainStart = trainStartInput.value ? new Date(trainStartInput.value).toISOString() : null;
        const trainEnd = trainEndInput.value ? new Date(trainEndInput.value + 'T23:59:59').toISOString() : null;

        if (typeof echarts !== 'undefined') {
            document.getElementById('edit-pipeline-chart-panel').style.display = 'block';
            document.getElementById('edit-pipeline-chart-title').textContent = `指标: ${data.name}`;

            Charts.createTimeSeriesChart('edit-pipeline-main-chart', data, {
                title: '',
                trainStart: trainStart,
                trainEnd: trainEnd,
            });
        }

        document.getElementById('edit-pipeline-training-panel').style.display = 'block';
    },

    refreshPreviewChart() {
        const data = this.dataQuery.getQueryData();
        if (!data || typeof echarts === 'undefined') return;

        const trainStartInput = document.getElementById('edit-pipeline-train-start');
        const trainEndInput = document.getElementById('edit-pipeline-train-end');
        const trainStart = trainStartInput.value ? new Date(trainStartInput.value).toISOString() : null;
        const trainEnd = trainEndInput.value ? new Date(trainEndInput.value + 'T23:59:59').toISOString() : null;

        Charts.createTimeSeriesChart('edit-pipeline-main-chart', data, {
            title: '',
            trainStart: trainStart,
            trainEnd: trainEnd,
        });
    },

    bindTooltipEvents() {
        if (!this.tooltipEl) {
            const tooltip = document.createElement('div');
            tooltip.className = 'help-tooltip';
            tooltip.id = 'pipeline-help-tooltip';
            document.body.appendChild(tooltip);
            this.tooltipEl = tooltip;
        }

        document.querySelectorAll('.help-icon').forEach(icon => {
            icon.addEventListener('mouseenter', (e) => {
                const tooltipEl = this.tooltipEl;
                const text = e.target.dataset.tooltip;
                if (!text) return;

                tooltipEl.textContent = text;
                tooltipEl.style.visibility = 'visible';
                tooltipEl.style.opacity = '1';

                const rect = e.target.getBoundingClientRect();
                tooltipEl.style.left = `${rect.left + rect.width / 2}px`;
                tooltipEl.style.top = `${rect.top - tooltipEl.offsetHeight - 8}px`;
            });

            icon.addEventListener('mouseleave', () => {
                const tooltipEl = this.tooltipEl;
                tooltipEl.style.visibility = 'hidden';
                tooltipEl.style.opacity = '0';
            });
        });
    },

    collectFormData() {
        const modelId = document.getElementById('edit-pipeline-model').value;
        const model = this.models.find(m => m.id === modelId);

        // Get train range from date inputs
        const trainStartInput = document.getElementById('edit-pipeline-train-start');
        const trainEndInput = document.getElementById('edit-pipeline-train-end');
        const trainStart = trainStartInput && trainStartInput.value
            ? new Date(trainStartInput.value).toISOString()
            : null;
        const trainEnd = trainEndInput && trainEndInput.value
            ? new Date(trainEndInput.value + 'T23:59:59').toISOString()
            : null;

        const data = {
            name: document.getElementById('edit-pipeline-name').value,
            description: document.getElementById('edit-pipeline-desc').value,
            datasource_id: this.dataQuery.getDataSourceId(),
            endpoint: this.dataQuery.getEndpoint(),
            metric_id: this.dataQuery.getMetric(),
            model_id: modelId,
            algorithm: model ? model.model_type : null,
            train_start: trainStart,
            train_end: trainEnd,
            step: this.dataQuery.getStep(),
            enabled: true,
            schedule_type: 'manual',
            labels: {},
            exclude_periods: [],
            override_params: this.collectOverrideParams(),
        };
        return data;
    },

    async savePipeline() {
        try {
            Helpers.showLoading();
            const data = this.collectFormData();

            if (!data.name || !data.datasource_id || !data.metric_id || !data.model_id) {
                Helpers.showToast('请填写所有必填字段', 'error');
                return;
            }

            if (!data.train_start || !data.train_end) {
                Helpers.showToast('请先查询数据并设置训练区间', 'error');
                return;
            }

            if (this.currentPipeline) {
                await API.updatePipeline(this.currentPipeline.id, data);
                Helpers.showToast('Pipeline 更新成功', 'success');
            } else {
                await API.createPipeline(data);
                Helpers.showToast('Pipeline 创建成功', 'success');
            }

            Sidebar.navigateTo('pipelines');
            this.refresh();
        } catch (error) {
            Helpers.showToast('保存失败: ' + error.message, 'error');
        } finally {
            Helpers.hideLoading();
        }
    },

    async runPipeline(pipelineId) {
        try {
            Helpers.showLoading();
            const result = await API.runPipeline(pipelineId);
            Helpers.showToast('训练任务已启动', 'success');
            this.showJobStatus(result.job_id, pipelineId);
        } catch (error) {
            Helpers.showToast('启动失败: ' + error.message, 'error');
        } finally {
            Helpers.hideLoading();
        }
    },

    async runCurrentPipeline() {
        if (!this.currentPipeline) {
            Helpers.showToast('请先保存 Pipeline', 'error');
            return;
        }
        await this.runPipeline(this.currentPipeline.id);
    },

    async deletePipeline(pipelineId) {
        if (!confirm('确定要删除此 Pipeline 吗？相关任务记录也会被删除。')) {
            return;
        }

        try {
            Helpers.showLoading();
            await API.deletePipeline(pipelineId);
            Helpers.showToast('Pipeline 已删除', 'success');
            this.refresh();
        } catch (error) {
            Helpers.showToast('删除失败: ' + error.message, 'error');
        } finally {
            Helpers.hideLoading();
        }
    },

    async showJobStatus(jobId, pipelineId) {
        this.currentJobId = jobId;
        this.currentPipelineId = pipelineId;
        Sidebar.navigateToJobStatus();
        this.startJobPolling(jobId);
    },

    async getPipelineForJob(pipelineId) {
        if (!pipelineId) return null;
        try {
            return await API.getPipeline(pipelineId);
        } catch (error) {
            console.error('Failed to load pipeline:', error);
            return null;
        }
    },

    renderPipelineInfo(pipeline) {
        if (!pipeline) {
            return `
                <div class="pipeline-detail-section">
                    <h4>Pipeline 配置</h4>
                    <p class="text-secondary">无法加载 Pipeline 信息</p>
                </div>
            `;
        }

        const statusClass = pipeline.enabled ? 'enabled' : 'disabled';
        const statusText = pipeline.enabled ? '已启用' : '已禁用';
        const modelName = pipeline.model_info?.name || pipeline.algorithm || '-';

        // Format time range
        const trainRange = this.formatTimeRange(pipeline.train_start, pipeline.train_end);

        // Format step
        const stepText = pipeline.step || '1m';

        // Data cleaning config
        const cleaningEnabled = pipeline.cleaning_config?.enabled || false;
        const cleaningHtml = cleaningEnabled ? `
            <div class="pipeline-detail-row">
                <div class="pipeline-detail-item">
                    <span class="detail-label">数据清洗</span>
                    <span class="detail-value"><span class="tag tag-success">已启用</span></span>
                </div>
                <div class="pipeline-detail-item">
                    <span class="detail-label">异常检测</span>
                    <span class="detail-value">${pipeline.cleaning_config?.anomaly_detection_method || '-'}</span>
                </div>
            </div>
        ` : `
            <div class="pipeline-detail-row">
                <div class="pipeline-detail-item">
                    <span class="detail-label">数据清洗</span>
                    <span class="detail-value"><span class="tag tag-disabled">未启用</span></span>
                </div>
            </div>
        `;

        return `
            <div class="pipeline-detail-section">
                <h4>Pipeline 配置</h4>
                <div class="pipeline-detail-grid">
                    <div class="pipeline-detail-row">
                        <div class="pipeline-detail-item">
                            <span class="detail-label">名称</span>
                            <span class="detail-value">${pipeline.name}</span>
                        </div>
                        <div class="pipeline-detail-item">
                            <span class="detail-label">状态</span>
                            <span class="detail-value"><span class="pipeline-status ${statusClass}">${statusText}</span></span>
                        </div>
                    </div>
                    <div class="pipeline-detail-row">
                        <div class="pipeline-detail-item">
                            <span class="detail-label">数据源</span>
                            <span class="detail-value">${pipeline.datasource_name || pipeline.datasource_id || '-'}</span>
                        </div>
                        <div class="pipeline-detail-item">
                            <span class="detail-label">Endpoint</span>
                            <span class="detail-value">${pipeline.endpoint || '-'}</span>
                        </div>
                    </div>
                    <div class="pipeline-detail-row">
                        <div class="pipeline-detail-item">
                            <span class="detail-label">指标 ID</span>
                            <span class="detail-value">${pipeline.metric_id}</span>
                        </div>
                        <div class="pipeline-detail-item">
                            <span class="detail-label">采样间隔</span>
                            <span class="detail-value">${stepText}</span>
                        </div>
                    </div>
                    <div class="pipeline-detail-row">
                        <div class="pipeline-detail-item">
                            <span class="detail-label">模型</span>
                            <span class="detail-value algo-badge">${modelName}</span>
                        </div>
                        <div class="pipeline-detail-item">
                            <span class="detail-label">算法类型</span>
                            <span class="detail-value"><span class="model-type-badge ${pipeline.algorithm}">${pipeline.algorithm || '-'}</span></span>
                        </div>
                    </div>
                    <div class="pipeline-detail-row">
                        <div class="pipeline-detail-item full-width">
                            <span class="detail-label">训练时间范围</span>
                            <span class="detail-value">${trainRange}</span>
                        </div>
                    </div>
                    ${cleaningHtml}
                </div>
                ${pipeline.description ? `<p class="pipeline-desc">${pipeline.description}</p>` : ''}
            </div>
        `;
    },

    startJobPolling(jobId) {
        this.stopJobPolling();

        const poll = async () => {
            try {
                const job = await API.getJob(jobId);
                this.renderJobStatus(job);

                if (job.status === 'pending' || job.status === 'running') {
                    this.pollInterval = setTimeout(poll, 2000);
                }
            } catch (error) {
                console.error('Job poll error:', error);
                this.renderJobError(error.message);
            }
        };

        poll();
    },

    stopJobPolling() {
        if (this.pollInterval) {
            clearTimeout(this.pollInterval);
            this.pollInterval = null;
        }
    },

    startGlobalPolling() {
        this.stopGlobalPolling();

        const poll = async () => {
            if (Sidebar.currentPage === 'pipelines' && this.runningJobs.length > 0) {
                try {
                    await this.loadRunningJobs();
                    this.render();
                } catch (error) {
                    console.error('Global job poll error:', error);
                }
            }

            if (this.runningJobs.length > 0) {
                this.globalPollInterval = setTimeout(poll, 3000);
            }
        };

        if (this.runningJobs.length > 0) {
            this.globalPollInterval = setTimeout(poll, 3000);
        }
    },

    stopGlobalPolling() {
        if (this.globalPollInterval) {
            clearTimeout(this.globalPollInterval);
            this.globalPollInterval = null;
        }
    },

    viewRunningJob(jobId, pipelineId) {
        this.currentJobId = jobId;
        this.currentPipelineId = pipelineId;
        Sidebar.navigateToJobStatus();
        this.startJobPolling(jobId);
    },

    async renderJobStatus(job) {
        const container = document.getElementById('job-status-content');
        if (!container) return;

        const statusColors = {
            pending: '#f0ad4e',
            running: '#5bc0de',
            success: '#5cb85c',
            failed: '#d9534f',
            cancelled: '#777',
        };

        const statusTexts = {
            pending: '等待中',
            running: '运行中',
            success: '成功',
            failed: '失败',
            cancelled: '已取消',
        };

        const statusColor = statusColors[job.status] || '#777';
        const statusText = statusTexts[job.status] || job.status;

        // Get Pipeline info
        const pipeline = await this.getPipelineForJob(job.pipeline_id);
        const pipelineInfoHtml = this.renderPipelineInfo(pipeline);

        let html = `
            ${pipelineInfoHtml}

            <div class="job-status-panel">
                <div class="job-status-header">
                    <div class="job-info">
                        <span class="job-id">Job ID: ${job.id}</span>
                        <span class="job-status-badge" style="background-color: ${statusColor}">${statusText}</span>
                    </div>
                    ${job.status === 'running' ? `
                        <button class="btn btn-sm btn-danger" onclick="Pipelines.cancelJob('${job.id}')">
                            取消任务
                        </button>
                    ` : ''}
                </div>

                <div class="job-progress">
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: ${job.progress}%; background-color: ${statusColor}"></div>
                    </div>
                    <span class="progress-text">${job.progress}%</span>
                    ${job.current_step ? `<span class="current-step">${job.current_step}</span>` : ''}
                </div>
            </div>
        `;

        if (job.status === 'success' && job.preview_data) {
            html += this.renderJobResults(job);
        }

        if (job.status === 'failed' && job.error_message) {
            html += `
                <div class="job-error">
                    <h4>错误信息</h4>
                    <pre>${job.error_message}</pre>
                </div>
            `;
        }

        container.innerHTML = html;

        if (job.status === 'success' && job.preview_data) {
            this.renderPreviewChartFromJob(job.preview_data, job.train_start, job.train_end);
        }
    },

    renderJobResults(job) {
        const metrics = job.preview_data?.validation_metrics || {};

        const retryButton = job.status === 'failed' && (job.retry_count || 0) < 3
            ? `<button class="btn btn-secondary" onclick="Pipelines.retryJob('${job.id}')">
                🔄 重试
               </button>`
            : '';

        return `
            <div class="job-metrics-panel">
                <h4>训练指标</h4>
                <div class="metrics-grid">
                    <div class="metric-card">
                        <span class="metric-label">RMSE</span>
                        <span class="metric-value">${job.rmse ? job.rmse.toFixed(4) : '-'}</span>
                    </div>
                    <div class="metric-card">
                        <span class="metric-label">MAE</span>
                        <span class="metric-value">${job.mae ? job.mae.toFixed(4) : '-'}</span>
                    </div>
                    <div class="metric-card">
                        <span class="metric-label">MAPE</span>
                        <span class="metric-value">${job.mape ? job.mape.toFixed(2) + '%' : '-'}</span>
                    </div>
                    <div class="metric-card">
                        <span class="metric-label">覆盖率</span>
                        <span class="metric-value">${job.coverage ? (job.coverage * 100).toFixed(1) + '%' : '-'}</span>
                    </div>
                    <div class="metric-card">
                        <span class="metric-label">误报数</span>
                        <span class="metric-value">${job.false_alerts || '-'}</span>
                    </div>
                    <div class="metric-card">
                        <span class="metric-label">训练样本</span>
                        <span class="metric-value">${metrics.train_samples || '-'}</span>
                    </div>
                </div>
            </div>

            <div class="job-actions">
                <button class="btn btn-primary" onclick="Pipelines.publishThreshold('${job.id}')">
                    📤 发布到 Redis
                </button>
                ${retryButton}
                <button class="btn btn-secondary" onclick="Pipelines.showJobLogs('${job.id}')">
                    📋 查看日志
                </button>
            </div>

            <div class="job-chart-panel">
                <h4>阈值预览图表</h4>
                <div id="job-preview-chart" class="chart-container" style="height: 400px;"></div>
            </div>
        `;
    },

    renderPreviewChartFromJob(previewData, trainStart = null, trainEnd = null) {
        const chartDom = document.getElementById('job-preview-chart');
        if (!chartDom || !previewData.timestamps) return;

        // Prepare data for Charts component
        const timestamps = previewData.timestamps.slice(0, 480);
        const predicted = previewData.predicted || [];
        const upper = previewData.upper || [];
        const lower = previewData.lower || [];

        // Create chart using Charts component with base options
        const chart = Charts.getChart('job-preview-chart');
        if (!chart) return;

        const series = [];

        // Predicted values line
        series.push({
            name: '预测值',
            type: 'line',
            data: predicted.slice(0, timestamps.length),
            smooth: true,
            symbol: 'none',
            lineStyle: { color: '#56a4ff', width: 2 },
            itemStyle: { color: '#56a4ff' },
            z: 10,
        });

        // Upper bound (confidence interval)
        if (upper.length > 0) {
            series.push({
                name: '上限',
                type: 'line',
                data: upper.slice(0, timestamps.length),
                symbol: 'none',
                lineStyle: { color: '#73bf69', width: 1, type: 'dashed' },
                itemStyle: { color: '#73bf69' },
                z: 5,
            });
        }

        // Lower bound (confidence interval)
        if (lower.length > 0) {
            series.push({
                name: '下限',
                type: 'line',
                data: lower.slice(0, timestamps.length),
                symbol: 'none',
                lineStyle: { color: '#73bf69', width: 1, type: 'dashed' },
                itemStyle: { color: '#73bf69' },
                z: 5,
            });
        }

        // Confidence interval area (between upper and lower)
        if (upper.length > 0 && lower.length > 0) {
            // For stacked area chart to show confidence band
            const lowerBaseline = lower.slice(0, timestamps.length);
            const diffData = upper.slice(0, timestamps.length).map((u, i) => u - lowerBaseline[i]);

            series.push({
                name: '下限基线',
                type: 'line',
                data: lowerBaseline,
                symbol: 'none',
                lineStyle: { width: 0, opacity: 0 },
                itemStyle: { opacity: 0 },
                areaStyle: { opacity: 0 },
                stack: 'confidence',
                z: 2,
                tooltip: { show: false },
            });

            series.push({
                name: '置信区间',
                type: 'line',
                data: diffData,
                symbol: 'none',
                lineStyle: { width: 0, opacity: 0 },
                areaStyle: { color: 'rgba(115, 207, 105, 0.2)' },
                stack: 'confidence',
                z: 3,
                tooltip: {
                    formatter: function(params) {
                        const idx = params.dataIndex;
                        if (idx !== undefined && upper[idx] !== undefined && lower[idx] !== undefined) {
                            return `置信区间: [${lower[idx].toFixed(2)}, ${upper[idx].toFixed(2)}]`;
                        }
                        return '置信区间';
                    }
                },
            });
        }

        // Training range mark area
        if (trainStart && trainEnd) {
            series[0].markArea = {
                silent: true,
                itemStyle: { color: 'rgba(250, 173, 20, 0.15)' },
                data: [[
                    { xAxis: trainStart },
                    { xAxis: trainEnd },
                ]],
            };
        }

        const chartOptions = Charts.getBaseChartOptions();
        chartOptions.xAxis.data = timestamps;
        chartOptions.xAxis.axisLabel = {
            color: '#8b9199',
            formatter: (value) => Helpers.formatChartDate(value),
        };
        chartOptions.yAxis.axisLabel = { color: '#8b9199' };
        chartOptions.series = series;
        chartOptions.legend = {
            data: ['预测值', '上限', '下限', '置信区间'],
            top: 10,
            textStyle: { color: '#8b9199' },
        };
        chartOptions.grid.top = '15%';

        chart.setOption(chartOptions, true);
    },

    async cancelJob(jobId) {
        if (!confirm('确定要取消此任务吗？')) return;

        try {
            await API.cancelJob(jobId);
            Helpers.showToast('任务已取消', 'success');
            this.startJobPolling(jobId);
        } catch (error) {
            Helpers.showToast('取消失败: ' + error.message, 'error');
        }
    },

    async publishThreshold(jobId) {
        const metricId = prompt('请输入要发布的 Metric ID:', this.currentPipeline?.metric_id || '');
        if (!metricId) return;

        try {
            Helpers.showLoading();
            await API.publishThreshold(metricId, jobId);
            Helpers.showToast(`阈值已发布到 Redis: ${metricId}`, 'success');
        } catch (error) {
            Helpers.showToast('发布失败: ' + error.message, 'error');
        } finally {
            Helpers.hideLoading();
        }
    },

    async retryJob(jobId) {
        if (!confirm('确定要重试此任务吗？')) return;

        try {
            Helpers.showLoading();
            const result = await API.retryJob(jobId);
            Helpers.showToast('重试任务已启动', 'success');
            this.showJobStatus(result.job_id, this.currentPipelineId);
        } catch (error) {
            Helpers.showToast('重试失败: ' + error.message, 'error');
        } finally {
            Helpers.hideLoading();
        }
    },

    async showJobLogs(jobId) {
        try {
            Helpers.showLoading();
            const result = await API.getJobLogs(jobId, 200);
            const logs = result.logs || [];

            const content = `
                <div class="job-logs">
                    <div class="logs-header">
                        <span>Job ID: ${jobId}</span>
                        <span>共 ${logs.length} 条日志</span>
                    </div>
                    <div class="logs-content">
                        ${logs.map(log => `
                            <div class="log-entry log-${log.level.toLowerCase()}">
                                <span class="log-time">${log.timestamp}</span>
                                <span class="log-level">[${log.level}]</span>
                                <span class="log-message">${log.message}</span>
                            </div>
                        `).join('')}
                    </div>
                </div>
            `;

            Helpers.showModal('任务执行日志', content);
        } catch (error) {
            Helpers.showToast('获取日志失败: ' + error.message, 'error');
        } finally {
            Helpers.hideLoading();
        }
    },

    renderJobError(message) {
        const container = document.getElementById('job-status-content');
        if (container) {
            container.innerHTML = `
                <div class="job-error">
                    <span class="error-icon">❌</span>
                    <p>加载任务状态失败: ${message}</p>
                </div>
            `;
        }
    },
};

// Make Pipelines globally available
window.Pipelines = Pipelines;