/**
 * Models Component
 */

const Models = {
    state: {
        models: [],
        editingModelId: null,
        tooltipEl: null,
    },

    /**
     * Initialize models page
     */
    async init() {
        this.bindEvents();
        await this.loadModels();
    },

    /**
     * Bind event listeners
     */
    bindEvents() {
        document.getElementById('btn-add-model')?.addEventListener('click', () => this.showAddPage());
        document.getElementById('btn-back-models')?.addEventListener('click', () => this.showModelsPage());
        document.getElementById('btn-save-model')?.addEventListener('click', () => this.saveModel());
    },

    /**
     * Navigate to model edit page
     */
    showEditPage(modelId = null) {
        const pageTitle = document.getElementById('edit-page-title');
        const nameInput = document.getElementById('edit-model-name');
        const descInput = document.getElementById('edit-model-desc');
        const typeSelect = document.getElementById('edit-model-type');

        this.navigateToModelEditPage();

        if (modelId) {
            const model = this.state.models.find(m => m.id === modelId);
            if (!model) return;

            pageTitle.textContent = '编辑模型';
            nameInput.value = model.name;
            descInput.value = model.description || '';
            typeSelect.value = model.model_type;
            typeSelect.disabled = true;

            this.state.editingModelId = modelId;
            this.onModelTypeChange();
            setTimeout(() => this.fillModelParams(model), 0);
        } else {
            pageTitle.textContent = '添加模型';
            nameInput.value = '';
            descInput.value = '';
            typeSelect.value = 'prophet';
            typeSelect.disabled = false;

            this.state.editingModelId = null;
            this.onModelTypeChange();
        }
    },

    /**
     * Fill model parameters into form
     */
    fillModelParams(model) {
        const type = model.model_type;
        const setVal = (id, val) => {
            const el = document.getElementById(id);
            if (el && val !== undefined && val !== null) {
                el.value = val;
            }
        };

        if (type === 'prophet') {
            setVal('edit-growth', model.growth);
            setVal('edit-seasonality-mode', model.seasonality_mode);
            setVal('edit-interval-width', model.interval_width);
            setVal('edit-n-changepoints', model.n_changepoints);
            setVal('edit-changepoint-range', model.changepoint_range);
            setVal('edit-changepoint-prior', model.changepoint_prior_scale);
            setVal('edit-seasonality-prior', model.seasonality_prior_scale);
            setVal('edit-yearly-seasonality', model.yearly_seasonality);
            setVal('edit-weekly-seasonality', model.weekly_seasonality ? 'true' : 'false');
            setVal('edit-daily-seasonality', model.daily_seasonality ? 'true' : 'false');

            const monthlyEl = document.getElementById('edit-add-monthly-seasonality');
            if (monthlyEl) monthlyEl.checked = !!model.add_monthly_seasonality;

            const nonNegativeEl = document.getElementById('edit-enforce-non-negative');
            if (nonNegativeEl) nonNegativeEl.checked = model.enforce_non_negative !== false;

        } else if (type === 'welford') {
            setVal('edit-sigma', model.sigma_multiplier);
            setVal('edit-rolling-window', model.use_rolling_window ? 'true' : 'false');
            setVal('edit-window-size', model.window_size);

        } else if (type === 'static') {
            setVal('edit-upper-percentile', model.upper_percentile);
            setVal('edit-lower-bound', model.lower_bound);
        }
    },

    /**
     * Navigate to model edit page for adding new model
     */
    showAddPage() {
        this.showEditPage(null);
    },

    /**
     * Navigate to model edit page
     */
    navigateToModelEditPage() {
        document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
        document.querySelectorAll('.nav-item').forEach(item => item.classList.remove('active'));
        const editPage = document.getElementById('page-model-edit');
        editPage?.classList.add('active');
        Sidebar.currentPage = 'model-edit';
    },

    /**
     * Navigate back to models list page
     */
    showModelsPage() {
        document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
        document.querySelectorAll('.nav-item').forEach(item => {
            item.classList.toggle('active', item.dataset.page === 'models');
        });

        const modelsPage = document.getElementById('page-models');
        modelsPage?.classList.add('active');
        Sidebar.currentPage = 'models';

        this.loadModels();
    },

    /**
     * Save model (create or update)
     */
    async saveModel() {
        const name = document.getElementById('edit-model-name').value;
        const description = document.getElementById('edit-model-desc').value;
        const modelType = document.getElementById('edit-model-type').value;

        if (!name) {
            Helpers.showToast('请输入模型名称', 'error');
            return;
        }

        const config = {
            name,
            description,
            model_type: modelType,
            ...this.getModelParams(modelType),
        };

        try {
            if (this.state.editingModelId) {
                await API.updateModel(this.state.editingModelId, config);
                Helpers.showToast('模型更新成功', 'success');
            } else {
                await API.createModel(config);
                Helpers.showToast('模型创建成功', 'success');
            }
            this.showModelsPage();
        } catch (error) {
            Helpers.showToast('保存失败：' + error.message, 'error');
        }
    },

    /**
     * Get model params based on type
     */
    getModelParams(type) {
        const getNum = (id, def) => {
            const el = document.getElementById(id);
            return el ? (parseFloat(el.value) || def) : def;
        };
        const getInt = (id, def) => {
            const el = document.getElementById(id);
            return el ? (parseInt(el.value, 10) || def) : def;
        };
        const getBool = (id) => {
            const el = document.getElementById(id);
            return el ? el.value === 'true' : false;
        };
        const getChecked = (id, def) => {
            const el = document.getElementById(id);
            return el ? el.checked : def;
        };
        const getVal = (id, def) => {
            const el = document.getElementById(id);
            return el ? el.value : def;
        };

        if (type === 'prophet') {
            return {
                growth: getVal('edit-growth', 'linear'),
                seasonality_mode: getVal('edit-seasonality-mode', 'additive'),
                interval_width: getNum('edit-interval-width', 0.95),
                n_changepoints: getInt('edit-n-changepoints', 25),
                changepoint_range: getNum('edit-changepoint-range', 0.8),
                changepoint_prior_scale: getNum('edit-changepoint-prior', 0.05),
                seasonality_prior_scale: getNum('edit-seasonality-prior', 10.0),
                yearly_seasonality: getVal('edit-yearly-seasonality', 'auto'),
                weekly_seasonality: getBool('edit-weekly-seasonality'),
                daily_seasonality: getBool('edit-daily-seasonality'),
                add_monthly_seasonality: getChecked('edit-add-monthly-seasonality', false),
                enforce_non_negative: getChecked('edit-enforce-non-negative', true),
            };
        } else if (type === 'welford') {
            return {
                sigma_multiplier: getNum('edit-sigma', 3.0),
                use_rolling_window: getBool('edit-rolling-window'),
                window_size: getInt('edit-window-size', null),
            };
        } else if (type === 'static') {
            return {
                upper_percentile: getNum('edit-upper-percentile', 99.0),
                lower_bound: getNum('edit-lower-bound', 0),
            };
        }
        return {};
    },

    /**
     * Load models
     */
    async loadModels() {
        try {
            const models = await API.listModels();
            this.state.models = models;
            this.displayModels();
        } catch (error) {
            Helpers.showToast('加载模型失败：' + error.message, 'error');
        }
    },

    /**
     * Display models
     */
    displayModels() {
        const container = document.getElementById('models-grid');
        if (!container) return;
        container.innerHTML = '';

        this.state.models.forEach(model => {
            const card = document.createElement('div');
            card.className = 'model-card';

            const typeClass = `model-type-badge ${model.model_type}`;
            const categoryTag = model.category === 'system'
                ? '<span class="tag tag-system">系统</span>'
                : '<span class="tag tag-custom">自定义</span>';

            card.innerHTML = `
                <div class="model-card-header">
                    <div class="model-card-title">
                        <span class="model-color" style="background: ${model.color}"></span>
                        ${model.name}
                    </div>
                    <span class="${typeClass}">${model.model_type}</span>
                </div>
                <div class="model-card-body">
                    <p class="model-card-desc">${model.description || '无描述'}</p>
                    <div class="divider"></div>
                    <div class="card-actions">
                        ${categoryTag}
                        <button class="btn btn-secondary" onclick="Models.showEditPage('${model.id}')">编辑</button>
                        ${model.category !== 'system' ? `
                            <button class="btn btn-danger" onclick="Models.deleteModel('${model.id}')">删除</button>
                        ` : ''}
                    </div>
                </div>
            `;
            container.appendChild(card);
        });
    },

    /**
     * Handle model type change
     */
    onModelTypeChange() {
        const type = document.getElementById('edit-model-type').value;
        const container = document.getElementById('edit-model-params');
        container.innerHTML = this.getParamHTML(type);
        this.bindTooltipEvents();
    },

    /**
     * Get param editor HTML
     */
    getParamHTML(type) {
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

        if (type === 'prophet') {
            return `
                <div class="param-editor prophet-params">
                    <div class="param-section">
                        <h4 class="param-section-title">基本参数</h4>
                        <div class="param-grid">
                            ${wrap('增长类型', '趋势增长模式：linear-线性增长，logistic-逻辑增长 (需设置容量上限)，flat-无趋势', `
                                <select id="edit-growth" class="form-control">
                                    <option value="linear">linear (线性)</option>
                                    <option value="logistic">logistic (逻辑)</option>
                                    <option value="flat">flat (平坦)</option>
                                </select>
                            `)}
                            ${wrap('季节性模式', '季节性叠加方式：additive-加法 (固定振幅)，multiplicative-乘法 (振幅随趋势变化)', `
                                <select id="edit-seasonality-mode" class="form-control">
                                    <option value="additive">additive (加法)</option>
                                    <option value="multiplicative">multiplicative (乘法)</option>
                                </select>
                            `)}
                            ${wrap('置信区间宽度', '预测置信区间宽度，表示预测值落在该区间内的概率。常用值：0.80/0.95/0.99', `
                                <input type="number" id="edit-interval-width" class="form-control" value="0.95" step="0.01" min="0.8" max="0.99">
                            `)}
                        </div>
                    </div>
                    <div class="param-section">
                        <h4 class="param-section-title">变点设置</h4>
                        <div class="param-grid">
                            ${wrap('变点数量', '模型自动检测的趋势变化点数量。太少会欠拟合，太多会过拟合。推荐 15-35', `
                                <input type="number" id="edit-n-changepoints" class="form-control" value="25" min="0" max="100">
                            `)}
                            ${wrap('变点范围', '变点在时间序列中的占比，表示在多少比例的数据范围内寻找变点。推荐 0.7-0.9', `
                                <input type="number" id="edit-changepoint-range" class="form-control" value="0.8" step="0.05" min="0.5" max="0.95">
                            `)}
                            ${wrap('变点灵活性', '控制趋势变化的灵活度。值越小趋势越平滑，值越大越能捕捉快速变化。推荐 0.001-0.5', `
                                <input type="number" id="edit-changepoint-prior" class="form-control" value="0.05" step="0.01" min="0.001" max="0.5">
                            `)}
                        </div>
                    </div>
                    <div class="param-section">
                        <h4 class="param-section-title">季节性设置</h4>
                        <div class="param-grid">
                            ${wrap('季节性强度', '季节性成分的先验尺度。值越大季节性越强，值越小越平滑。推荐 5-20', `
                                <input type="number" id="edit-seasonality-prior" class="form-control" value="10.0" step="1.0" min="0.1" max="100">
                            `)}
                            ${wrap('年度季节性', '是否启用年度季节性模式 (365 天周期)。auto 表示根据数据长度自动判断', `
                                <select id="edit-yearly-seasonality" class="form-control">
                                    <option value="auto">auto (自动)</option>
                                    <option value="true">启用</option>
                                    <option value="false">禁用</option>
                                </select>
                            `)}
                            ${wrap('周季节性', '是否启用周季节性模式 (7 天周期)。适用于有明显工作日/周末差异的数据', `
                                <select id="edit-weekly-seasonality" class="form-control">
                                    <option value="true">启用</option>
                                    <option value="false">禁用</option>
                                </select>
                            `)}
                            ${wrap('日季节性', '是否启用日季节性模式 (24 小时周期)。适用于小时级别采样的数据', `
                                <select id="edit-daily-seasonality" class="form-control">
                                    <option value="true">启用</option>
                                    <option value="false">禁用</option>
                                </select>
                            `)}
                            <div class="param-editor-item checkbox-item">
                                <label>
                                    <input type="checkbox" id="edit-add-monthly-seasonality">
                                    添加月度季节性
                                    ${help('是否启用月度季节性模式 (30.5 天周期)。适用：月初/月末效应、账单周期数据')}
                                </label>
                            </div>
                        </div>
                    </div>
                    <div class="param-section">
                        <h4 class="param-section-title">其他设置</h4>
                        <div class="param-grid">
                            <div class="param-editor-item checkbox-item">
                                <label>
                                    <input type="checkbox" id="edit-enforce-non-negative" checked>
                                    强制非负值
                                    ${help('强制预测值为非负，适用于不可能为负的指标 (如 QPS、连接数等)')}
                                </label>
                            </div>
                        </div>
                    </div>
                </div>
            `;
        } else if (type === 'welford') {
            return `
                <div class="param-editor">
                    ${wrap('Sigma 倍数', '阈值 = 均值 ± sigma × 标准差，倍数越大阈值范围越宽。3σ 对应 99.7% 置信区间', `
                        <input type="number" id="edit-sigma" class="form-control" value="3.0" step="0.1" min="1" max="5">
                    `)}
                    ${wrap('使用滚动窗口', '使用滚动窗口计算统计值，适用于非平稳序列。禁用时使用全部历史数据', `
                        <select id="edit-rolling-window" class="form-control">
                            <option value="false">禁用</option>
                            <option value="true">启用</option>
                        </select>
                    `)}
                    ${wrap('窗口大小', '滚动窗口的数据点数量，仅在启用滚动窗口时有效。推荐 500-2000', `
                        <input type="number" id="edit-window-size" class="form-control" value="1000" min="100">
                    `)}
                </div>
            `;
        } else if (type === 'static') {
            return `
                <div class="param-editor">
                    ${wrap('上限百分位', '使用历史数据的百分位作为静态阈值上限。99 表示 99% 的数据点低于此值', `
                        <input type="number" id="edit-upper-percentile" class="form-control" value="99.0" step="0.1" min="90" max="99.9">
                    `)}
                    ${wrap('下限', '固定下限值，低于此值将触发告警。适用于需要监控最小值的场景', `
                        <input type="number" id="edit-lower-bound" class="form-control" value="0" step="0.1">
                    `)}
                </div>
            `;
        }
        return '';
    },

    /**
     * Bind tooltip events - create global tooltip and handle hover
     */
    bindTooltipEvents() {
        // 创建全局 tooltip 元素
        if (!this.state.tooltipEl) {
            const tooltip = document.createElement('div');
            tooltip.className = 'help-tooltip';
            tooltip.id = 'global-help-tooltip';
            document.body.appendChild(tooltip);
            this.state.tooltipEl = tooltip;
        }

        document.querySelectorAll('.help-icon').forEach(icon => {
            icon.addEventListener('mouseenter', (e) => {
                const tooltipEl = this.state.tooltipEl;
                const text = e.target.dataset.tooltip;
                if (!text) return;

                tooltipEl.textContent = text;
                tooltipEl.style.visibility = 'visible';
                tooltipEl.style.opacity = '1';

                const rect = e.target.getBoundingClientRect();
                const tooltipRect = tooltipEl.getBoundingClientRect();
                const viewportWidth = window.innerWidth;

                // 默认在图标上方显示
                let left = rect.left + (rect.width / 2);
                let top = rect.top - tooltipRect.height - 8;

                // 如果超出上边界，则在图标下方显示
                if (top < 10) {
                    top = rect.bottom + 8;
                }

                // 检查右边界
                if (left + tooltipRect.width / 2 > viewportWidth - 10) {
                    left = viewportWidth - 10 - tooltipRect.width / 2;
                }

                // 检查左边界
                if (left - tooltipRect.width / 2 < 10) {
                    left = 10 + tooltipRect.width / 2;
                }

                tooltipEl.style.left = `${left}px`;
                tooltipEl.style.top = `${top}px`;
            });

            icon.addEventListener('mouseleave', () => {
                const tooltipEl = this.state.tooltipEl;
                tooltipEl.style.visibility = 'hidden';
                tooltipEl.style.opacity = '0';
            });
        });
    },

    /**
     * Delete model
     */
    async deleteModel(modelId) {
        if (!confirm('确定要删除此模型吗？')) return;

        try {
            await API.deleteModel(modelId);
            Helpers.showToast('模型已删除', 'success');
            await this.loadModels();
        } catch (error) {
            Helpers.showToast('删除失败：' + error.message, 'error');
        }
    },

    /**
     * Refresh models
     */
    async refresh() {
        await this.loadModels();
    },
};

// Make Models globally available
window.Models = Models;
