/**
 * Models Component
 */

const Models = {
    state: {
        models: [],
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
        document.getElementById('btn-add-model').addEventListener('click', () => this.showAddModal());
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
            Helpers.showToast('加载模型失败: ' + error.message, 'error');
        }
    },

    /**
     * Display models
     */
    displayModels() {
        const container = document.getElementById('models-grid');
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
                    <div class="model-card-params">
                        ${this.renderParams(model)}
                    </div>
                    <div class="divider"></div>
                    <div class="card-actions">
                        ${categoryTag}
                        <button class="btn btn-secondary" onclick="Models.showEditModal('${model.id}')">编辑</button>
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
     * Render model parameters
     */
    renderParams(model) {
        const params = [];

        if (model.model_type === 'prophet') {
            params.push({ name: '置信区间', value: model.interval_width });
            params.push({ name: '变化点数量', value: model.n_changepoints });
            params.push({ name: '日季节性', value: model.daily_seasonality ? '是' : '否' });
        } else if (model.model_type === 'welford') {
            params.push({ name: 'Sigma倍数', value: model.sigma_multiplier });
            params.push({ name: '滚动窗口', value: model.use_rolling_window ? '是' : '否' });
        } else if (model.model_type === 'static') {
            params.push({ name: '上限百分位', value: model.upper_percentile });
        }

        return params.map(p => `
            <div class="param-row">
                <span class="param-name">${p.name}</span>
                <span class="param-value">${p.value}</span>
            </div>
        `).join('');
    },

    /**
     * Show add model modal
     */
    showAddModal() {
        const content = `
            <div class="form-group">
                <label>模型名称</label>
                <input type="text" id="model-name" class="form-control" placeholder="输入模型名称">
            </div>
            <div class="form-group">
                <label>描述</label>
                <textarea id="model-desc" class="form-control" rows="2" placeholder="输入描述"></textarea>
            </div>
            <div class="form-group">
                <label>模型类型</label>
                <select id="model-type" class="form-control" onchange="Models.onModelTypeChange()">
                    <option value="prophet">Prophet</option>
                    <option value="welford">Welford</option>
                    <option value="static">Static</option>
                </select>
            </div>
            <div id="model-params-container"></div>
        `;

        const footer = `
            <button class="btn btn-secondary" onclick="Helpers.hideModal()">取消</button>
            <button class="btn btn-primary" onclick="Models.createModel()">创建</button>
        `;

        Helpers.showModal('添加模型', content, footer);
        this.onModelTypeChange();
    },

    /**
     * Handle model type change
     */
    onModelTypeChange() {
        const type = document.getElementById('model-type').value;
        const container = document.getElementById('model-params-container');

        if (type === 'prophet') {
            container.innerHTML = `
                <div class="param-editor">
                    <div class="param-editor-item">
                        <label>置信区间宽度</label>
                        <input type="number" id="param-interval-width" class="form-control" value="0.95" step="0.01" min="0.8" max="0.99">
                        <span class="help-text">预测置信区间 (0.8-0.99)</span>
                    </div>
                    <div class="param-editor-item">
                        <label>变化点数量</label>
                        <input type="number" id="param-n-changepoints" class="form-control" value="25" min="0" max="100">
                    </div>
                    <div class="param-editor-item">
                        <label>日季节性</label>
                        <select id="param-daily-seasonality" class="form-control">
                            <option value="true">启用</option>
                            <option value="false">禁用</option>
                        </select>
                    </div>
                    <div class="param-editor-item">
                        <label>周季节性</label>
                        <select id="param-weekly-seasonality" class="form-control">
                            <option value="false">禁用</option>
                            <option value="true">启用</option>
                        </select>
                    </div>
                </div>
            `;
        } else if (type === 'welford') {
            container.innerHTML = `
                <div class="param-editor">
                    <div class="param-editor-item">
                        <label>Sigma 倍数</label>
                        <input type="number" id="param-sigma" class="form-control" value="3.0" step="0.1" min="1" max="5">
                        <span class="help-text">阈值 = 均值 ± sigma × 标准差</span>
                    </div>
                    <div class="param-editor-item">
                        <label>使用滚动窗口</label>
                        <select id="param-rolling-window" class="form-control">
                            <option value="false">禁用 (使用全部数据)</option>
                            <option value="true">启用</option>
                        </select>
                    </div>
                    <div class="param-editor-item">
                        <label>窗口大小</label>
                        <input type="number" id="param-window-size" class="form-control" value="1000" min="100">
                        <span class="help-text">滚动窗口的数据点数量</span>
                    </div>
                </div>
            `;
        } else if (type === 'static') {
            container.innerHTML = `
                <div class="param-editor">
                    <div class="param-editor-item">
                        <label>上限百分位</label>
                        <input type="number" id="param-upper-percentile" class="form-control" value="99.0" step="0.1" min="90" max="99.9">
                        <span class="help-text">使用历史数据的百分位作为上限</span>
                    </div>
                    <div class="param-editor-item">
                        <label>下限</label>
                        <input type="number" id="param-lower-bound" class="form-control" value="0" step="0.1">
                        <span class="help-text">固定下限值</span>
                    </div>
                </div>
            `;
        }
    },

    /**
     * Show edit model modal
     */
    showEditModal(modelId) {
        const model = this.state.models.find(m => m.id === modelId);
        if (!model) return;

        const content = `
            <div class="form-group">
                <label>模型名称</label>
                <input type="text" id="edit-model-name" class="form-control" value="${model.name}">
            </div>
            <div class="form-group">
                <label>描述</label>
                <textarea id="edit-model-desc" class="form-control" rows="2">${model.description || ''}</textarea>
            </div>
            <div class="form-group">
                <label>模型类型</label>
                <input type="text" class="form-control" value="${model.model_type.toUpperCase()}" disabled>
            </div>
            <div id="edit-model-params-container"></div>
        `;

        const footer = `
            <button class="btn btn-secondary" onclick="Helpers.hideModal()">取消</button>
            <button class="btn btn-primary" onclick="Models.updateModel('${modelId}')">保存</button>
        `;

        Helpers.showModal('编辑模型', content, footer);

        // 渲染参数编辑器
        setTimeout(() => this.renderEditParams(model), 0);
    },

    /**
     * Render edit parameters
     */
    renderEditParams(model) {
        const container = document.getElementById('edit-model-params-container');
        const type = model.model_type;

        if (type === 'prophet') {
            container.innerHTML = `
                <div class="param-editor">
                    <div class="param-editor-item">
                        <label>置信区间宽度</label>
                        <input type="number" id="edit-interval-width" class="form-control" value="${model.interval_width}" step="0.01" min="0.8" max="0.99">
                    </div>
                    <div class="param-editor-item">
                        <label>变化点数量</label>
                        <input type="number" id="edit-n-changepoints" class="form-control" value="${model.n_changepoints}" min="0" max="100">
                    </div>
                    <div class="param-editor-item">
                        <label>日季节性</label>
                        <select id="edit-daily-seasonality" class="form-control">
                            <option value="true" ${model.daily_seasonality ? 'selected' : ''}>启用</option>
                            <option value="false" ${!model.daily_seasonality ? 'selected' : ''}>禁用</option>
                        </select>
                    </div>
                    <div class="param-editor-item">
                        <label>周季节性</label>
                        <select id="edit-weekly-seasonality" class="form-control">
                            <option value="false" ${!model.weekly_seasonality ? 'selected' : ''}>禁用</option>
                            <option value="true" ${model.weekly_seasonality ? 'selected' : ''}>启用</option>
                        </select>
                    </div>
                    <div class="param-editor-item">
                        <label>变化点先验尺度</label>
                        <input type="number" id="edit-changepoint-prior" class="form-control" value="${model.changepoint_prior_scale}" step="0.01" min="0.001" max="0.5">
                    </div>
                </div>
            `;
        } else if (type === 'welford') {
            container.innerHTML = `
                <div class="param-editor">
                    <div class="param-editor-item">
                        <label>Sigma 倍数</label>
                        <input type="number" id="edit-sigma" class="form-control" value="${model.sigma_multiplier}" step="0.1" min="1" max="5">
                    </div>
                    <div class="param-editor-item">
                        <label>使用滚动窗口</label>
                        <select id="edit-rolling-window" class="form-control">
                            <option value="false" ${!model.use_rolling_window ? 'selected' : ''}>禁用</option>
                            <option value="true" ${model.use_rolling_window ? 'selected' : ''}>启用</option>
                        </select>
                    </div>
                    <div class="param-editor-item">
                        <label>窗口大小</label>
                        <input type="number" id="edit-window-size" class="form-control" value="${model.window_size || 1000}" min="100">
                    </div>
                </div>
            `;
        } else if (type === 'static') {
            container.innerHTML = `
                <div class="param-editor">
                    <div class="param-editor-item">
                        <label>上限百分位</label>
                        <input type="number" id="edit-upper-percentile" class="form-control" value="${model.upper_percentile}" step="0.1" min="90" max="99.9">
                    </div>
                    <div class="param-editor-item">
                        <label>下限</label>
                        <input type="number" id="edit-lower-bound" class="form-control" value="${model.lower_bound}" step="0.1">
                    </div>
                </div>
            `;
        }
    },

    /**
     * Create model
     */
    async createModel() {
        const name = document.getElementById('model-name').value;
        const description = document.getElementById('model-desc').value;
        const modelType = document.getElementById('model-type').value;

        if (!name) {
            Helpers.showToast('请输入模型名称', 'error');
            return;
        }

        const config = {
            name,
            description,
            model_type: modelType,
        };

        // 添加模型参数
        if (modelType === 'prophet') {
            config.interval_width = parseFloat(document.getElementById('param-interval-width')?.value) || 0.95;
            config.n_changepoints = parseInt(document.getElementById('param-n-changepoints')?.value) || 25;
            config.daily_seasonality = document.getElementById('param-daily-seasonality')?.value === 'true';
            config.weekly_seasonality = document.getElementById('param-weekly-seasonality')?.value === 'true';
        } else if (modelType === 'welford') {
            config.sigma_multiplier = parseFloat(document.getElementById('param-sigma')?.value) || 3.0;
            config.use_rolling_window = document.getElementById('param-rolling-window')?.value === 'true';
            config.window_size = parseInt(document.getElementById('param-window-size')?.value) || null;
        } else if (modelType === 'static') {
            config.upper_percentile = parseFloat(document.getElementById('param-upper-percentile')?.value) || 99.0;
            config.lower_bound = parseFloat(document.getElementById('param-lower-bound')?.value) || 0;
        }

        try {
            await API.createModel(config);

            Helpers.hideModal();
            Helpers.showToast('模型创建成功', 'success');
            await this.loadModels();
        } catch (error) {
            Helpers.showToast('创建失败: ' + error.message, 'error');
        }
    },

    /**
     * Update model
     */
    async updateModel(modelId) {
        const model = this.state.models.find(m => m.id === modelId);
        if (!model) return;

        const name = document.getElementById('edit-model-name').value;
        const description = document.getElementById('edit-model-desc').value;

        if (!name) {
            Helpers.showToast('请输入模型名称', 'error');
            return;
        }

        const config = {
            name,
            description,
        };

        // 添加模型参数
        const type = model.model_type;
        if (type === 'prophet') {
            config.interval_width = parseFloat(document.getElementById('edit-interval-width')?.value);
            config.n_changepoints = parseInt(document.getElementById('edit-n-changepoints')?.value);
            config.daily_seasonality = document.getElementById('edit-daily-seasonality')?.value === 'true';
            config.weekly_seasonality = document.getElementById('edit-weekly-seasonality')?.value === 'true';
            config.changepoint_prior_scale = parseFloat(document.getElementById('edit-changepoint-prior')?.value);
        } else if (type === 'welford') {
            config.sigma_multiplier = parseFloat(document.getElementById('edit-sigma')?.value);
            config.use_rolling_window = document.getElementById('edit-rolling-window')?.value === 'true';
            config.window_size = parseInt(document.getElementById('edit-window-size')?.value) || null;
        } else if (type === 'static') {
            config.upper_percentile = parseFloat(document.getElementById('edit-upper-percentile')?.value);
            config.lower_bound = parseFloat(document.getElementById('edit-lower-bound')?.value);
        }

        try {
            await API.updateModel(modelId, config);

            Helpers.hideModal();
            Helpers.showToast('模型更新成功', 'success');
            await this.loadModels();
        } catch (error) {
            Helpers.showToast('更新失败: ' + error.message, 'error');
        }
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
            Helpers.showToast('删除失败: ' + error.message, 'error');
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