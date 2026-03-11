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
                <select id="ds-type" class="form-control" onchange="DataSources.onTypeChange()">
                    <option value="prometheus">Prometheus</option>
                    <option value="timescaledb">TimescaleDB</option>
                    <option value="mock">Mock (测试用)</option>
                </select>
            </div>
            <div id="prometheus-config">
                <div class="form-group">
                    <label>URL</label>
                    <input type="text" id="ds-url" class="form-control" placeholder="http://localhost:9090">
                </div>
                <div class="form-group">
                    <label>认证令牌 (可选)</label>
                    <input type="text" id="ds-token" class="form-control" placeholder="Bearer token">
                </div>
            </div>
            <div id="timescaledb-config" style="display: none;">
                <div class="form-group">
                    <label>主机</label>
                    <input type="text" id="ds-db-host" class="form-control" value="localhost" placeholder="数据库主机">
                </div>
                <div class="form-group">
                    <label>端口</label>
                    <input type="number" id="ds-db-port" class="form-control" value="5432" placeholder="数据库端口">
                </div>
                <div class="form-group">
                    <label>数据库名称</label>
                    <input type="text" id="ds-db-name" class="form-control" value="postgres" placeholder="数据库名称">
                </div>
                <div class="form-group">
                    <label>用户名</label>
                    <input type="text" id="ds-db-user" class="form-control" value="postgres" placeholder="数据库用户">
                </div>
                <div class="form-group">
                    <label>密码</label>
                    <input type="password" id="ds-db-password" class="form-control" placeholder="数据库密码">
                </div>
            </div>
            <div id="mock-config" style="display: none;">
                <p class="text-muted">Mock 数据源用于测试，无需额外配置。</p>
            </div>
        `;

        const footer = `
            <button class="btn btn-secondary" onclick="Helpers.hideModal()">取消</button>
            <button class="btn btn-primary" onclick="DataSources.createDataSource()">创建</button>
        `;

        Helpers.showModal('添加数据源', content, footer);
    },

    /**
     * Handle data source type change
     */
    onTypeChange() {
        const type = document.getElementById('ds-type').value;
        document.getElementById('prometheus-config').style.display = type === 'prometheus' ? 'block' : 'none';
        document.getElementById('timescaledb-config').style.display = type === 'timescaledb' ? 'block' : 'none';
        document.getElementById('mock-config').style.display = type === 'mock' ? 'block' : 'none';
    },

    /**
     * Create data source
     */
    async createDataSource() {
        const name = document.getElementById('ds-name').value;
        const type = document.getElementById('ds-type').value;

        if (!name) {
            Helpers.showToast('请填写数据源名称', 'error');
            return;
        }

        let config = {
            name,
            source_type: type,
        };

        if (type === 'prometheus') {
            const url = document.getElementById('ds-url').value;
            if (!url) {
                Helpers.showToast('请填写 URL', 'error');
                return;
            }
            config.url = url;
            config.auth_token = document.getElementById('ds-token').value || null;
        } else if (type === 'timescaledb') {
            const dbHost = document.getElementById('ds-db-host').value;
            const dbName = document.getElementById('ds-db-name').value;
            if (!dbHost || !dbName) {
                Helpers.showToast('请填写数据库连接信息', 'error');
                return;
            }
            config.url = `postgresql://${dbHost}:${document.getElementById('ds-db-port').value}/${dbName}`;
            config.db_host = dbHost;
            config.db_port = parseInt(document.getElementById('ds-db-port').value) || 5432;
            config.db_name = dbName;
            config.db_user = document.getElementById('ds-db-user').value || 'postgres';
            config.db_password = document.getElementById('ds-db-password').value || '';
        } else if (type === 'mock') {
            config.url = 'mock://localhost';
        }

        try {
            await API.createDataSource(config);

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