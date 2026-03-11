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
                        ${model.category !== 'system' ? `
                            <button class="btn btn-secondary" onclick="Models.deleteModel('${model.id}')">删除</button>
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
                <select id="model-type" class="form-control">
                    <option value="prophet">Prophet</option>
                    <option value="welford">Welford</option>
                    <option value="static">Static</option>
                </select>
            </div>
        `;

        const footer = `
            <button class="btn btn-secondary" onclick="Helpers.hideModal()">取消</button>
            <button class="btn btn-primary" onclick="Models.createModel()">创建</button>
        `;

        Helpers.showModal('添加模型', content, footer);
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

        try {
            await API.createModel({
                name,
                description,
                model_type: modelType,
            });

            Helpers.hideModal();
            Helpers.showToast('模型创建成功', 'success');
            await this.loadModels();
        } catch (error) {
            Helpers.showToast('创建失败: ' + error.message, 'error');
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