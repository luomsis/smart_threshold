/**
 * Pipeline Management Component
 */

const Pipelines = {
    pipelines: [],
    runningJobs: [], // Map of pipeline_id -> running job
    algorithms: [],
    datasources: [],
    currentPipeline: null,
    pollInterval: null,
    globalPollInterval: null, // Global polling for running jobs

    init() {
        this.bindEvents();
        this.loadAlgorithms();
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

        // Algorithm change handler
        const algoSelect = document.getElementById('edit-pipeline-algorithm');
        if (algoSelect) {
            algoSelect.addEventListener('change', () => this.onAlgorithmChange());
        }

        // Data source change handler
        const dsSelect = document.getElementById('edit-pipeline-datasource');
        if (dsSelect) {
            dsSelect.addEventListener('change', () => this.onDataSourceChange());
        }
    },

    async refresh() {
        try {
            Helpers.showLoading();
            await Promise.all([
                this.loadPipelines(),
                this.loadAlgorithms(),
                this.loadDataSources(),
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

    async loadAlgorithms() {
        const result = await API.listAlgorithms();
        this.algorithms = result.algorithms || [];
    },

    async loadDataSources() {
        this.datasources = await API.listDataSources();
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

        // Build job status section if there's a running job
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
                        <span class="info-label">算法:</span>
                        <span class="info-value algo-badge">${pipeline.algorithm}</span>
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
        this.populateFormDropdowns();
        Sidebar.navigateToPipelineEdit();
    },

    async showEditForm(pipelineId) {
        try {
            Helpers.showLoading();
            const pipeline = await API.getPipeline(pipelineId);
            this.currentPipeline = pipeline;
            document.getElementById('edit-pipeline-title').textContent = '编辑 Pipeline';
            await this.populateFormDropdowns();
            this.fillForm(pipeline);
            Sidebar.navigateToPipelineEdit();
        } catch (error) {
            Helpers.showToast('加载失败: ' + error.message, 'error');
        } finally {
            Helpers.hideLoading();
        }
    },

    async populateFormDropdowns() {
        // Populate data sources
        const dsSelect = document.getElementById('edit-pipeline-datasource');
        if (dsSelect) {
            dsSelect.innerHTML = '<option value="">选择数据源...</option>' +
                this.datasources.map(ds =>
                    `<option value="${ds.id}">${ds.name} (${ds.source_type})</option>`
                ).join('');
        }

        // Populate algorithms
        const algoSelect = document.getElementById('edit-pipeline-algorithm');
        if (algoSelect) {
            algoSelect.innerHTML = '<option value="">选择算法...</option>' +
                this.algorithms.map(algo =>
                    `<option value="${algo.id}">${algo.name}</option>`
                ).join('');
        }
    },

    fillForm(pipeline) {
        document.getElementById('edit-pipeline-name').value = pipeline.name || '';
        document.getElementById('edit-pipeline-desc').value = pipeline.description || '';
        document.getElementById('edit-pipeline-datasource').value = pipeline.datasource_id || '';
        document.getElementById('edit-pipeline-metric').value = pipeline.metric_id || '';
        document.getElementById('edit-pipeline-algorithm').value = pipeline.algorithm || '';

        // Time range
        if (pipeline.train_start) {
            document.getElementById('edit-pipeline-train-start').value =
                new Date(pipeline.train_start).toISOString().slice(0, 16);
        }
        if (pipeline.train_end) {
            document.getElementById('edit-pipeline-train-end').value =
                new Date(pipeline.train_end).toISOString().slice(0, 16);
        }

        // Render algorithm params
        this.onAlgorithmChange(pipeline.algorithm_params);
    },

    clearForm() {
        document.getElementById('edit-pipeline-name').value = '';
        document.getElementById('edit-pipeline-desc').value = '';
        document.getElementById('edit-pipeline-datasource').value = '';
        document.getElementById('edit-pipeline-metric').value = '';
        document.getElementById('edit-pipeline-algorithm').value = '';
        document.getElementById('edit-pipeline-train-start').value = '';
        document.getElementById('edit-pipeline-train-end').value = '';
        document.getElementById('edit-pipeline-params').innerHTML = '';
    },

    onAlgorithmChange(existingParams = null) {
        const algoId = document.getElementById('edit-pipeline-algorithm').value;
        const container = document.getElementById('edit-pipeline-params');

        if (!algoId) {
            container.innerHTML = '';
            return;
        }

        const algo = this.algorithms.find(a => a.id === algoId);
        if (!algo) return;

        container.innerHTML = this.renderParamForm(algo.param_schema, existingParams || {});
    },

    renderParamForm(schema, values) {
        if (!schema || !schema.properties) return '';

        const props = schema.properties;
        let html = '<div class="param-form-section"><h4>算法参数</h4><div class="param-grid">';

        for (const [key, prop] of Object.entries(props)) {
            const value = values[key] !== undefined ? values[key] : (prop.default || '');
            html += `
                <div class="form-group">
                    <label for="param-${key}">${prop.title || key}</label>
                    ${this.renderParamInput(key, prop, value)}
                    ${prop.description ? `<small class="param-help">${prop.description}</small>` : ''}
                </div>
            `;
        }

        html += '</div></div>';
        return html;
    },

    renderParamInput(key, prop, value) {
        const inputId = `param-${key}`;
        const commonAttrs = `id="${inputId}" name="${key}"`;

        if (prop.enum) {
            return `
                <select ${commonAttrs} class="form-control">
                    ${prop.enum.map(v => `
                        <option value="${v}" ${value === v ? 'selected' : ''}>${v}</option>
                    `).join('')}
                </select>
            `;
        }

        if (prop.type === 'boolean') {
            return `
                <label class="toggle-switch">
                    <input type="checkbox" ${commonAttrs} ${value ? 'checked' : ''}>
                    <span class="toggle-slider"></span>
                </label>
            `;
        }

        if (prop.type === 'integer') {
            return `
                <input type="number" ${commonAttrs} class="form-control"
                    value="${value}"
                    min="${prop.minimum || ''}"
                    max="${prop.maximum || ''}"
                    step="1">
            `;
        }

        if (prop.type === 'number') {
            return `
                <input type="number" ${commonAttrs} class="form-control"
                    value="${value}"
                    min="${prop.minimum || ''}"
                    max="${prop.maximum || ''}"
                    step="${prop.multipleOf || 0.1}">
            `;
        }

        return `
            <input type="text" ${commonAttrs} class="form-control" value="${value}">
        `;
    },

    collectFormData() {
        const data = {
            name: document.getElementById('edit-pipeline-name').value,
            description: document.getElementById('edit-pipeline-desc').value,
            datasource_id: document.getElementById('edit-pipeline-datasource').value,
            metric_id: document.getElementById('edit-pipeline-metric').value,
            algorithm: document.getElementById('edit-pipeline-algorithm').value,
            train_start: document.getElementById('edit-pipeline-train-start').value,
            train_end: document.getElementById('edit-pipeline-train-end').value,
            step: '1m',
            enabled: true,
            schedule_type: 'manual',
            labels: {},
            exclude_periods: [],
            algorithm_params: this.collectParamValues(),
        };
        return data;
    },

    collectParamValues() {
        const params = {};
        const container = document.getElementById('edit-pipeline-params');
        const inputs = container.querySelectorAll('input, select');

        inputs.forEach(input => {
            const key = input.name || input.id.replace('param-', '');
            if (input.type === 'checkbox') {
                params[key] = input.checked;
            } else if (input.type === 'number') {
                params[key] = parseFloat(input.value);
            } else {
                params[key] = input.value;
            }
        });

        return params;
    },

    async savePipeline() {
        try {
            Helpers.showLoading();
            const data = this.collectFormData();

            if (!data.name || !data.datasource_id || !data.metric_id || !data.algorithm) {
                Helpers.showToast('请填写所有必填字段', 'error');
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

            // Navigate to job status page
            this.showJobStatus(result.job_id, pipelineId);
        } catch (error) {
            Helpers.showToast('启动失败: ' + error.message, 'error');
        } finally {
            Helpers.hideLoading();
        }
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

    showJobStatus(jobId, pipelineId) {
        // Store job info and navigate to status page
        this.currentJobId = jobId;
        this.currentPipelineId = pipelineId;
        Sidebar.navigateToJobStatus();
        this.startJobPolling(jobId);
    },

    startJobPolling(jobId) {
        this.stopJobPolling();

        const poll = async () => {
            try {
                const job = await API.getJob(jobId);
                this.renderJobStatus(job);

                // Continue polling if not finished
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
            // Only poll if we're on the pipelines page and there are running jobs
            if (Sidebar.currentPage === 'pipelines' && this.runningJobs.length > 0) {
                try {
                    await this.loadRunningJobs();
                    this.render();
                } catch (error) {
                    console.error('Global job poll error:', error);
                }
            }

            // Continue polling if there are still running jobs
            if (this.runningJobs.length > 0) {
                this.globalPollInterval = setTimeout(poll, 3000);
            }
        };

        // Start polling if there are running jobs
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

    renderJobStatus(job) {
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

        let html = `
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
        `;

        // Show metrics if job succeeded
        if (job.status === 'success' && job.preview_data) {
            html += this.renderJobResults(job);
        }

        // Show error if failed
        if (job.status === 'failed' && job.error_message) {
            html += `
                <div class="job-error">
                    <h4>错误信息</h4>
                    <pre>${job.error_message}</pre>
                </div>
            `;
        }

        container.innerHTML = html;

        // Render chart if preview data exists
        if (job.status === 'success' && job.preview_data) {
            this.renderPreviewChart(job.preview_data);
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
            <div class="job-metrics">
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

            <div class="job-chart">
                <h4>阈值预览</h4>
                <div id="job-preview-chart" class="chart-container"></div>
            </div>
        `;
    },

    renderPreviewChart(previewData) {
        const chartDom = document.getElementById('job-preview-chart');
        if (!chartDom || !previewData.timestamps) return;

        const chart = echarts.init(chartDom);

        const option = {
            tooltip: {
                trigger: 'axis',
            },
            legend: {
                data: ['预测值', '上限', '下限'],
                textStyle: { color: '#ccc' },
            },
            grid: {
                left: '3%',
                right: '4%',
                bottom: '3%',
                containLabel: true,
            },
            xAxis: {
                type: 'category',
                data: previewData.timestamps.slice(0, 480),
                axisLabel: {
                    color: '#888',
                    rotate: 45,
                },
            },
            yAxis: {
                type: 'value',
                axisLabel: { color: '#888' },
                splitLine: { lineStyle: { color: '#333' } },
            },
            series: [
                {
                    name: '预测值',
                    type: 'line',
                    data: previewData.predicted,
                    lineStyle: { color: '#5470c6' },
                    symbol: 'none',
                },
                {
                    name: '上限',
                    type: 'line',
                    data: previewData.upper,
                    lineStyle: { color: '#91cc75', type: 'dashed' },
                    symbol: 'none',
                    areaStyle: { opacity: 0.1 },
                },
                {
                    name: '下限',
                    type: 'line',
                    data: previewData.lower,
                    lineStyle: { color: '#91cc75', type: 'dashed' },
                    symbol: 'none',
                    areaStyle: { opacity: 0.1 },
                },
            ],
        };

        chart.setOption(option);
        window.addEventListener('resize', () => chart.resize());
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

    async onDataSourceChange() {
        const dsId = document.getElementById('edit-pipeline-datasource').value;
        // Could load endpoints/metrics for the selected datasource
    },
};

// Make Pipelines globally available
window.Pipelines = Pipelines;