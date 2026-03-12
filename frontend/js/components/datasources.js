/**
 * DataSources Component
 */

const DataSources = {
    state: {
        dataSources: [],
        currentDsId: localStorage.getItem('currentDataSourceId') || null,
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
            const isCurrent = ds.id === this.state.currentDsId;
            card.className = 'datasource-card' + (isCurrent ? ' current' : '');

            const typeTag = ds.source_type === 'mock'
                ? '<span class="tag tag-custom">Mock</span>'
                : '<span class="tag tag-system">' + ds.source_type + '</span>';

            const enabledTag = ds.enabled
                ? '<span class="tag tag-success">已启用</span>'
                : '<span class="tag tag-disabled">已禁用</span>';

            const currentBadge = isCurrent
                ? '<span class="tag tag-primary">当前数据源</span>'
                : '';

            card.innerHTML = `
                <div class="datasource-info">
                    <div class="datasource-name">${ds.name} ${typeTag} ${enabledTag} ${currentBadge}</div>
                    <div class="datasource-url">${ds.url}</div>
                </div>
                <div class="datasource-actions">
                    ${!isCurrent ? `<button class="btn btn-primary" onclick="DataSources.setCurrent('${ds.id}')">设为当前</button>` : ''}
                    <button class="btn btn-secondary" onclick="DataSources.showEditModal('${ds.id}')">编辑</button>
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
     * Set current data source
     */
    setCurrent(dsId) {
        this.state.currentDsId = dsId;
        localStorage.setItem('currentDataSourceId', dsId);
        this.displayDataSources();
        Helpers.showToast('已切换数据源', 'success');

        // Notify Dashboard to switch data source
        if (typeof Dashboard !== 'undefined') {
            Dashboard.switchDataSource(dsId);
        }
    },

    /**
     * Get current data source ID
     */
    getCurrentId() {
        return this.state.currentDsId;
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
     * Show edit datasource modal
     */
    async showEditModal(dsId) {
        const ds = this.state.dataSources.find(d => d.id === dsId);
        if (!ds) {
            Helpers.showToast('数据源不存在', 'error');
            return;
        }

        // 解析 URL 中的数据库信息（如果是 timescaledb）
        let dbHost = ds.db_host || 'localhost';
        let dbPort = ds.db_port || 5432;
        let dbName = ds.db_name || 'postgres';
        let dbUser = ds.db_user || 'postgres';
        let dbPassword = ds.db_password || '';

        if (ds.source_type === 'timescaledb' && ds.url) {
            const match = ds.url.match(/postgresql:\/\/([^:]+):(\d+)\/(.+)/);
            if (match) {
                dbHost = match[1];
                dbPort = parseInt(match[2]);
                dbName = match[3];
            }
        }

        const content = `
            <div class="form-group">
                <label>数据源名称</label>
                <input type="text" id="ds-name" class="form-control" value="${ds.name}" placeholder="输入数据源名称">
            </div>
            <div class="form-group">
                <label>数据源类型</label>
                <select id="ds-type" class="form-control" onchange="DataSources.onTypeChange()" ${ds.source_type === 'mock' ? 'disabled' : ''}>
                    <option value="prometheus" ${ds.source_type === 'prometheus' ? 'selected' : ''}>Prometheus</option>
                    <option value="timescaledb" ${ds.source_type === 'timescaledb' ? 'selected' : ''}>TimescaleDB</option>
                    <option value="mock" ${ds.source_type === 'mock' ? 'selected' : ''}>Mock (测试用)</option>
                </select>
            </div>
            <div class="form-group">
                <label>启用状态</label>
                <select id="ds-enabled" class="form-control">
                    <option value="true" ${ds.enabled ? 'selected' : ''}>启用</option>
                    <option value="false" ${!ds.enabled ? 'selected' : ''}>禁用</option>
                </select>
            </div>
            <div id="prometheus-config">
                <div class="form-group">
                    <label>URL</label>
                    <input type="text" id="ds-url" class="form-control" value="${ds.url || ''}" placeholder="http://localhost:9090">
                </div>
                <div class="form-group">
                    <label>认证令牌 (可选)</label>
                    <input type="text" id="ds-token" class="form-control" value="${ds.auth_token || ''}" placeholder="Bearer token">
                </div>
            </div>
            <div id="timescaledb-config" style="display: none;">
                <div class="form-group">
                    <label>主机</label>
                    <input type="text" id="ds-db-host" class="form-control" value="${dbHost}" placeholder="数据库主机">
                </div>
                <div class="form-group">
                    <label>端口</label>
                    <input type="number" id="ds-db-port" class="form-control" value="${dbPort}" placeholder="数据库端口">
                </div>
                <div class="form-group">
                    <label>数据库名称</label>
                    <input type="text" id="ds-db-name" class="form-control" value="${dbName}" placeholder="数据库名称">
                </div>
                <div class="form-group">
                    <label>用户名</label>
                    <input type="text" id="ds-db-user" class="form-control" value="${dbUser}" placeholder="数据库用户">
                </div>
                <div class="form-group">
                    <label>密码</label>
                    <input type="password" id="ds-db-password" class="form-control" value="${dbPassword}" placeholder="数据库密码">
                </div>
            </div>
            <div id="mock-config" style="display: none;">
                <p class="text-muted">Mock 数据源用于测试，无需额外配置。</p>
            </div>
        `;

        const footer = `
            <button class="btn btn-secondary" onclick="Helpers.hideModal()">取消</button>
            <button class="btn btn-primary" onclick="DataSources.updateDataSource('${dsId}')">保存</button>
        `;

        Helpers.showModal('编辑数据源', content, footer);

        // 初始化类型选择
        this.onTypeChange();
    },

    /**
     * Update data source
     */
    async updateDataSource(dsId) {
        const name = document.getElementById('ds-name').value;
        const type = document.getElementById('ds-type').value;
        const enabled = document.getElementById('ds-enabled').value === 'true';

        if (!name) {
            Helpers.showToast('请填写数据源名称', 'error');
            return;
        }

        let config = {
            name,
            enabled,
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
        }

        try {
            await API.updateDataSource(dsId, config);

            Helpers.hideModal();
            Helpers.showToast('数据源更新成功', 'success');
            await this.loadDataSources();
        } catch (error) {
            Helpers.showToast('更新失败: ' + error.message, 'error');
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