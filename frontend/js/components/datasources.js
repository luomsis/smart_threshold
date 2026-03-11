/**
 * DataSources Component
 */

const DataSources = {
    state: {
        dataSources: [],
    },

    /**
     * Initialize datasources page
     */
    async init() {
        this.bindEvents();
        await this.loadDataSources();
    },

    /**
     * Bind event listeners
     */
    bindEvents() {
        document.getElementById('btn-add-datasource').addEventListener('click', () => this.showAddModal());
    },

    /**
     * Load data sources
     */
    async loadDataSources() {
        try {
            const dataSources = await API.listDataSources();
            this.state.dataSources = dataSources;
            this.displayDataSources();
        } catch (error) {
            Helpers.showToast('加载数据源失败: ' + error.message, 'error');
        }
    },

    /**
     * Display data sources
     */
    displayDataSources() {
        const container = document.getElementById('datasources-list');
        container.innerHTML = '';

        this.state.dataSources.forEach(ds => {
            const card = document.createElement('div');
            card.className = 'datasource-card';

            const typeTag = ds.source_type === 'mock'
                ? '<span class="tag tag-custom">Mock</span>'
                : '<span class="tag tag-system">Prometheus</span>';

            card.innerHTML = `
                <div class="datasource-info">
                    <div class="datasource-name">${ds.name} ${typeTag}</div>
                    <div class="datasource-url">${ds.url}</div>
                </div>
                <div class="datasource-actions">
                    ${ds.source_type !== 'mock' ? `
                        <button class="btn btn-secondary" onclick="DataSources.testConnection('${ds.id}')">测试连接</button>
                        <button class="btn btn-danger" onclick="DataSources.deleteDataSource('${ds.id}')">删除</button>
                    ` : ''}
                </div>
            `;

            container.appendChild(card);
        });
    },

    /**
     * Show add datasource modal
     */
    showAddModal() {
        const content = `
            <div class="form-group">
                <label>数据源名称</label>
                <input type="text" id="ds-name" class="form-control" placeholder="输入数据源名称">
            </div>
            <div class="form-group">
                <label>数据源类型</label>
                <select id="ds-type" class="form-control">
                    <option value="prometheus">Prometheus</option>
                </select>
            </div>
            <div class="form-group">
                <label>URL</label>
                <input type="text" id="ds-url" class="form-control" placeholder="http://localhost:9090">
            </div>
            <div class="form-group">
                <label>认证令牌 (可选)</label>
                <input type="text" id="ds-token" class="form-control" placeholder="Bearer token">
            </div>
        `;

        const footer = `
            <button class="btn btn-secondary" onclick="Helpers.hideModal()">取消</button>
            <button class="btn btn-primary" onclick="DataSources.createDataSource()">创建</button>
        `;

        Helpers.showModal('添加数据源', content, footer);
    },

    /**
     * Create data source
     */
    async createDataSource() {
        const name = document.getElementById('ds-name').value;
        const type = document.getElementById('ds-type').value;
        const url = document.getElementById('ds-url').value;
        const token = document.getElementById('ds-token').value;

        if (!name || !url) {
            Helpers.showToast('请填写必要信息', 'error');
            return;
        }

        try {
            await API.createDataSource({
                name,
                source_type: type,
                url,
                auth_token: token || null,
            });

            Helpers.hideModal();
            Helpers.showToast('数据源创建成功', 'success');
            await this.loadDataSources();
        } catch (error) {
            Helpers.showToast('创建失败: ' + error.message, 'error');
        }
    },

    /**
     * Test connection
     */
    async testConnection(dsId) {
        Helpers.showLoading(true, '正在测试连接...');
        try {
            // Try to list metrics as connection test
            await API.listMetrics(dsId);
            Helpers.showToast('连接成功', 'success');
        } catch (error) {
            Helpers.showToast('连接失败: ' + error.message, 'error');
        } finally {
            Helpers.showLoading(false);
        }
    },

    /**
     * Delete data source
     */
    async deleteDataSource(dsId) {
        if (!confirm('确定要删除此数据源吗？')) return;

        try {
            await API.deleteDataSource(dsId);
            Helpers.showToast('数据源已删除', 'success');
            await this.loadDataSources();
        } catch (error) {
            Helpers.showToast('删除失败: ' + error.message, 'error');
        }
    },

    /**
     * Refresh datasources
     */
    async refresh() {
        await this.loadDataSources();
    },
};

// Make DataSources globally available
window.DataSources = DataSources;