/**
 * Jobs Management Component
 * Display all training jobs with filters and actions.
 */

const Jobs = {
    jobs: [],
    pipelines: [],
    statusFilter: '',
    pipelineFilter: '',
    pollInterval: null,

    init() {
        this.bindEvents();
    },

    bindEvents() {
        // Status filter
        const statusFilter = document.getElementById('jobs-status-filter');
        if (statusFilter) {
            statusFilter.addEventListener('change', (e) => {
                this.statusFilter = e.target.value;
                this.loadJobs();
            });
        }

        // Pipeline filter
        const pipelineFilter = document.getElementById('jobs-pipeline-filter');
        if (pipelineFilter) {
            pipelineFilter.addEventListener('change', (e) => {
                this.pipelineFilter = e.target.value;
                this.loadJobs();
            });
        }
    },

    async refresh() {
        try {
            Helpers.showLoading();
            await Promise.all([
                this.loadPipelines(),
                this.loadJobs(),
            ]);
            this.populatePipelineFilter();
            this.startPolling();
        } catch (error) {
            Helpers.showToast('加载失败: ' + error.message, 'error');
        } finally {
            Helpers.hideLoading();
        }
    },

    async loadPipelines() {
        this.pipelines = await API.listPipelines();
    },

    async loadJobs() {
        const filters = {};
        if (this.statusFilter) filters.status = this.statusFilter;
        if (this.pipelineFilter) filters.pipeline_id = this.pipelineFilter;
        filters.limit = 100;

        this.jobs = await API.listAllJobs(filters);
        this.render();
    },

    populatePipelineFilter() {
        const select = document.getElementById('jobs-pipeline-filter');
        if (!select) return;

        select.innerHTML = '<option value="">全部 Pipeline</option>' +
            this.pipelines.map(p => `<option value="${p.id}">${p.name}</option>`).join('');
    },

    startPolling() {
        this.stopPolling();

        // Check if there are running jobs
        const hasRunningJobs = this.jobs.some(j =>
            j.status === 'pending' || j.status === 'running'
        );

        if (hasRunningJobs) {
            this.pollInterval = setTimeout(async () => {
                try {
                    await this.loadJobs();
                } catch (error) {
                    console.error('Jobs poll error:', error);
                }
            }, 3000);
        }
    },

    stopPolling() {
        if (this.pollInterval) {
            clearTimeout(this.pollInterval);
            this.pollInterval = null;
        }
    },

    render() {
        const tableBody = document.getElementById('jobs-table-body');
        const emptyState = document.getElementById('jobs-empty');
        const tableContainer = document.querySelector('.jobs-table-container');

        if (!tableBody) return;

        if (this.jobs.length === 0) {
            tableContainer.style.display = 'none';
            emptyState.style.display = 'flex';
            return;
        }

        tableContainer.style.display = 'block';
        emptyState.style.display = 'none';

        tableBody.innerHTML = this.jobs.map(job => this.renderJobRow(job)).join('');
    },

    renderJobRow(job) {
        const pipeline = this.pipelines.find(p => p.id === job.pipeline_id);
        const pipelineName = pipeline ? pipeline.name : job.pipeline_id;
        const algorithm = pipeline ? pipeline.algorithm : '-';

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

        // Format time
        const startTime = job.started_at
            ? Helpers.formatChartDate(new Date(job.started_at))
            : '-';
        const duration = job.duration_seconds
            ? this.formatDuration(job.duration_seconds)
            : (job.status === 'running' ? '运行中...' : '-');

        // Actions based on status
        let actions = '';
        if (job.status === 'running' || job.status === 'pending') {
            actions = `
                <button class="btn btn-xs btn-view" onclick="Jobs.viewJob('${job.id}')">查看</button>
                <button class="btn btn-xs btn-cancel" onclick="Jobs.showCancelConfirm('${job.id}')">取消</button>
            `;
        } else if (job.status === 'success') {
            actions = `
                <button class="btn btn-xs btn-view" onclick="Jobs.viewJob('${job.id}')">查看</button>
                <button class="btn btn-xs btn-publish" onclick="Jobs.publishThreshold('${job.id}', '${job.pipeline_id}')">发布</button>
            `;
        } else if (job.status === 'failed') {
            actions = `
                <button class="btn btn-xs btn-view" onclick="Jobs.viewJob('${job.id}')">查看</button>
                <button class="btn btn-xs btn-retry" onclick="Jobs.showRetryConfirm('${job.id}')">重试</button>
            `;
        } else if (job.status === 'cancelled') {
            actions = `
                <button class="btn btn-xs btn-view" onclick="Jobs.viewJob('${job.id}')">查看</button>
                <button class="btn btn-xs btn-retry" onclick="Jobs.showRetryConfirm('${job.id}')">重试</button>
            `;
        } else {
            actions = `<button class="btn btn-xs btn-view" onclick="Jobs.viewJob('${job.id}')">查看</button>`;
        }

        return `
            <tr class="job-row job-row-${job.status}">
                <td class="job-id-col">${this.shortenId(job.id)}</td>
                <td class="job-pipeline-col">${pipelineName}</td>
                <td class="job-status-col">
                    <span class="job-status-badge" style="background-color: ${statusColor}">${statusText}</span>
                </td>
                <td class="job-progress-col">
                    ${job.status === 'running' || job.status === 'pending'
                        ? `<div class="job-progress-mini">
                            <div class="progress-bar-mini">
                                <div class="progress-fill-mini" style="width: ${job.progress}%; background-color: ${statusColor}"></div>
                            </div>
                            <span class="progress-text-mini">${job.progress}%</span>
                           </div>`
                        : '-'
                    }
                </td>
                <td class="job-algo-col">${algorithm}</td>
                <td class="job-time-col">${startTime}</td>
                <td class="job-duration-col">${duration}</td>
                <td class="job-actions-col">${actions}</td>
            </tr>
        `;
    },

    shortenId(id) {
        return id.substring(0, 8);
    },

    formatDuration(seconds) {
        if (seconds < 60) {
            return `${Math.round(seconds)}s`;
        } else if (seconds < 3600) {
            const mins = Math.floor(seconds / 60);
            const secs = Math.round(seconds % 60);
            return `${mins}m ${secs}s`;
        } else {
            const hours = Math.floor(seconds / 3600);
            const mins = Math.floor((seconds % 3600) / 60);
            return `${hours}h ${mins}m`;
        }
    },

    async viewJob(jobId) {
        try {
            Helpers.showLoading();
            const job = await API.getJob(jobId);
            this.currentJobId = jobId;
            this.currentPipelineId = job.pipeline_id;

            // Use Pipelines component to show job status
            Pipelines.currentJobId = jobId;
            Pipelines.currentPipelineId = job.pipeline_id;
            Sidebar.navigateToJobStatus();
            Pipelines.startJobPolling(jobId);
        } catch (error) {
            Helpers.showToast('加载失败: ' + error.message, 'error');
        } finally {
            Helpers.hideLoading();
        }
    },

    /**
     * Show cancel confirmation modal
     */
    showCancelConfirm(jobId) {
        const job = this.jobs.find(j => j.id === jobId);
        if (!job) return;

        const statusText = job.status === 'pending' ? '等待中' : '运行中';
        const progressText = job.status === 'running' ? `进度: ${job.progress}%` : '';
        const warningText = job.status === 'running'
            ? '任务正在运行中，取消后当前进度将丢失，需要重新执行。'
            : '任务正在队列中等待，取消后可以稍后重新执行。';

        const content = `
            <div class="confirm-modal-content">
                <div class="confirm-icon warning">⚠️</div>
                <div class="confirm-title">取消任务确认</div>
                <div class="confirm-info">
                    <p><strong>任务 ID:</strong> ${this.shortenId(jobId)}</p>
                    <p><strong>当前状态:</strong> ${statusText}</p>
                    ${progressText ? `<p><strong>${progressText}</strong></p>` : ''}
                </div>
                <div class="confirm-warning">
                    ${warningText}
                </div>
                <div class="confirm-question">确定要取消此任务吗？</div>
            </div>
        `;

        const footer = `
            <button class="btn btn-secondary" onclick="Helpers.hideModal()">取消</button>
            <button class="btn btn-danger" onclick="Jobs.executeCancel('${jobId}')">确认取消任务</button>
        `;

        Helpers.showModal('取消任务', content, footer);
    },

    /**
     * Execute cancel after confirmation
     */
    async executeCancel(jobId) {
        Helpers.hideModal();
        try {
            Helpers.showLoading('正在取消任务...');
            await API.cancelJob(jobId);
            Helpers.showToast('任务已取消', 'success');
            await this.loadJobs();
            // Continue polling to update status
            this.startPolling();
        } catch (error) {
            Helpers.showToast('取消失败: ' + error.message, 'error');
        } finally {
            Helpers.hideLoading();
        }
    },

    /**
     * Old cancelJob method (kept for backward compatibility)
     */
    async cancelJob(jobId) {
        this.showCancelConfirm(jobId);
    },

    /**
     * Show retry confirmation modal
     */
    showRetryConfirm(jobId) {
        const job = this.jobs.find(j => j.id === jobId);
        if (!job) return;

        const pipeline = this.pipelines.find(p => p.id === job.pipeline_id);
        const pipelineName = pipeline ? pipeline.name : job.pipeline_id;
        const statusText = job.status === 'failed' ? '失败' : '已取消';
        const retryCount = job.retry_count || 0;
        const maxRetries = job.max_retries || 3;

        const content = `
            <div class="confirm-modal-content">
                <div class="confirm-icon info">🔄</div>
                <div class="confirm-title">重试任务确认</div>
                <div class="confirm-info">
                    <p><strong>任务 ID:</strong> ${this.shortenId(jobId)}</p>
                    <p><strong>Pipeline:</strong> ${pipelineName}</p>
                    <p><strong>原状态:</strong> ${statusText}</p>
                    <p><strong>已重试次数:</strong> ${retryCount}/${maxRetries}</p>
                </div>
                <div class="confirm-question">确定要重新执行此任务吗？</div>
            </div>
        `;

        const footer = `
            <button class="btn btn-secondary" onclick="Helpers.hideModal()">取消</button>
            <button class="btn btn-warning" onclick="Jobs.executeRetry('${jobId}')">确认重试</button>
        `;

        Helpers.showModal('重试任务', content, footer);
    },

    /**
     * Execute retry after confirmation
     */
    async executeRetry(jobId) {
        Helpers.hideModal();
        try {
            Helpers.showLoading('正在启动重试...');
            const result = await API.retryJob(jobId);
            Helpers.showToast('重试任务已启动', 'success');
            await this.loadJobs();
            // Start polling for new running job
            this.startPolling();
        } catch (error) {
            Helpers.showToast('重试失败: ' + error.message, 'error');
        } finally {
            Helpers.hideLoading();
        }
    },

    async retryJob(jobId) {
        this.showRetryConfirm(jobId);
    },

    async publishThreshold(jobId, pipelineId) {
        const pipeline = this.pipelines.find(p => p.id === pipelineId);
        const metricId = pipeline ? pipeline.metric_id : '';

        const inputMetricId = prompt('请输入要发布的 Metric ID:', metricId);
        if (!inputMetricId) return;

        try {
            Helpers.showLoading();
            await API.publishThreshold(inputMetricId, jobId);
            Helpers.showToast(`阈值已发布到 Redis: ${inputMetricId}`, 'success');
        } catch (error) {
            Helpers.showToast('发布失败: ' + error.message, 'error');
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
};

// Make Jobs globally available
window.Jobs = Jobs;