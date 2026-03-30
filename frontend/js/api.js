/**
 * API Client for SmartThreshold Backend
 */

const API = {
    // Base URL - from config.js or default to localhost:8010
    baseUrl: window.BACKEND_URL || 'http://localhost:8010',

    /**
     * Set base URL
     */
    setBaseUrl(url) {
        this.baseUrl = url.replace(/\/$/, '');
    },

    /**
     * Make HTTP request
     */
    async request(method, path, options = {}) {
        // 移除路径中可能存在的 /api/v1 前缀，避免重复
        const cleanPath = path.replace(/^\/api\/v1/, '');
        const url = `${this.baseUrl}/api/v1${cleanPath}`;
        const config = {
            method,
            headers: {
                'Content-Type': 'application/json',
                ...options.headers,
            },
        };

        if (options.body) {
            config.body = JSON.stringify(options.body);
        }

        try {
            const response = await fetch(url, config);
            if (!response.ok) {
                const error = await response.json().catch(() => ({ detail: 'Request failed' }));
                throw new Error(error.detail || `HTTP ${response.status}`);
            }
            return await response.json();
        } catch (error) {
            throw error;
        }
    },

    // ==================== Data Sources ====================

    /**
     * List all data sources
     */
    async listDataSources() {
        return this.request('GET', '/datasources');
    },

    /**
     * Get default data source
     */
    async getDefaultDataSource() {
        return this.request('GET', '/datasources/default');
    },

    /**
     * Get data source by ID
     */
    async getDataSource(id) {
        return this.request('GET', `/datasources/${id}`);
    },

    /**
     * Get data time range
     */
    async getTimeRange(dataSourceId, endpoint = null) {
        const params = endpoint ? `?endpoint=${encodeURIComponent(endpoint)}` : '';
        return this.request('GET', `/datasources/${dataSourceId}/time-range${params}`);
    },

    /**
     * Create data source
     */
    async createDataSource(data) {
        return this.request('POST', '/datasources', { body: data });
    },

    /**
     * Update data source
     */
    async updateDataSource(id, data) {
        return this.request('PUT', `/datasources/${id}`, { body: data });
    },

    /**
     * Delete data source
     */
    async deleteDataSource(id) {
        return this.request('DELETE', `/datasources/${id}`);
    },

    /**
     * List endpoints (endpoint label values) from data source
     */
    async listEndpoints(dataSourceId) {
        return this.request('GET', `/datasources/${dataSourceId}/endpoints`);
    },

    /**
     * List metrics for a specific endpoint
     */
    async listEndpointMetrics(dataSourceId, endpoint) {
        return this.request('GET', `/datasources/${dataSourceId}/endpoints/${encodeURIComponent(endpoint)}/metrics`);
    },

    /**
     * List metrics from data source
     */
    async listMetrics(dataSourceId) {
        return this.request('GET', `/datasources/${dataSourceId}/metrics`);
    },

    /**
     * List labels from data source
     */
    async listLabels(dataSourceId) {
        return this.request('GET', `/datasources/${dataSourceId}/labels`);
    },

    /**
     * Get label values
     */
    async getLabelValues(dataSourceId, labelName) {
        return this.request('GET', `/datasources/${dataSourceId}/labels/${encodeURIComponent(labelName)}`);
    },

    /**
     * Query data
     */
    async queryData(dataSourceId, query, timeRange, endpoint = null) {
        const body = {
            query,
            time_range: timeRange,
        };
        if (endpoint) {
            body.endpoint = endpoint;
        }
        return this.request('POST', `/datasources/${dataSourceId}/query`, { body });
    },

    // ==================== Models ====================

    /**
     * List all models
     */
    async listModels(filters = {}) {
        const params = new URLSearchParams();
        if (filters.model_type) params.append('model_type', filters.model_type);
        if (filters.category) params.append('category', filters.category);
        const query = params.toString() ? `?${params.toString()}` : '';
        return this.request('GET', `/models${query}`);
    },

    /**
     * Get model by ID
     */
    async getModel(id) {
        return this.request('GET', `/models/${id}`);
    },

    /**
     * Create model
     */
    async createModel(data) {
        return this.request('POST', '/models', { body: data });
    },

    /**
     * Update model
     */
    async updateModel(id, data) {
        return this.request('PUT', `/models/${id}`, { body: data });
    },

    /**
     * Delete model
     */
    async deleteModel(id) {
        return this.request('DELETE', `/models/${id}`);
    },

    // ==================== Predictions ====================

    /**
     * Analyze features
     */
    async analyzeFeatures(data, timestamps) {
        return this.request('POST', '/predictions/analyze', {
            body: { data, timestamps },
        });
    },

    /**
     * Run prediction
     */
    async predict(modelId, data, timestamps, periods = 1440, freq = '1min') {
        return this.request('POST', '/predictions/predict', {
            body: {
                model_id: modelId,
                data,
                timestamps,
                periods,
                freq,
            },
        });
    },

    /**
     * Compare models
     */
    async compareModels(modelIds, data, timestamps, trainStart, trainEnd) {
        return this.request('POST', '/predictions/compare', {
            body: {
                model_ids: modelIds,
                data,
                timestamps,
                train_start: trainStart,
                train_end: trainEnd,
            },
        });
    },

    // ==================== Health ====================

    /**
     * Health check
     */
    async healthCheck() {
        return this.request('GET', '/health');
    },

    // ==================== Algorithms ====================

    /**
     * List all available algorithms with parameter schemas
     */
    async listAlgorithms() {
        return this.request('GET', '/algorithms');
    },

    /**
     * Get algorithm by ID
     */
    async getAlgorithm(algorithmId) {
        return this.request('GET', `/algorithms/${algorithmId}`);
    },

    // ==================== Pipelines ====================

    /**
     * Create a new pipeline
     */
    async createPipeline(data) {
        return this.request('POST', '/pipelines', { body: data });
    },

    /**
     * List all pipelines
     */
    async listPipelines(filters = {}) {
        const params = new URLSearchParams();
        if (filters.enabled !== undefined) params.append('enabled', filters.enabled);
        if (filters.algorithm) params.append('algorithm', filters.algorithm);
        const query = params.toString() ? `?${params.toString()}` : '';
        return this.request('GET', `/pipelines${query}`);
    },

    /**
     * Get pipeline by ID
     */
    async getPipeline(pipelineId) {
        return this.request('GET', `/pipelines/${pipelineId}`);
    },

    /**
     * Update pipeline
     */
    async updatePipeline(pipelineId, data) {
        return this.request('PUT', `/pipelines/${pipelineId}`, { body: data });
    },

    /**
     * Delete pipeline
     */
    async deletePipeline(pipelineId) {
        return this.request('DELETE', `/pipelines/${pipelineId}`);
    },

    /**
     * Run a pipeline (trigger training job)
     */
    async runPipeline(pipelineId, overrideParams = null) {
        const body = { pipeline_id: pipelineId };
        if (overrideParams) {
            body.override_params = overrideParams;
        }
        return this.request('POST', '/pipelines/run', { body });
    },

    /**
     * Get job status and results
     */
    async getJob(jobId) {
        return this.request('GET', `/pipelines/jobs/${jobId}`);
    },

    /**
     * List jobs for a pipeline
     */
    async listPipelineJobs(pipelineId, status = null, limit = 10) {
        const params = new URLSearchParams();
        if (status) params.append('status', status);
        params.append('limit', limit);
        return this.request('GET', `/pipelines/${pipelineId}/jobs?${params.toString()}`);
    },

    /**
     * List all running jobs (pending or running status)
     */
    async listRunningJobs() {
        return this.request('GET', '/pipelines/jobs/running');
    },

    /**
     * List all jobs with filters
     */
    async listAllJobs(filters = {}) {
        const params = new URLSearchParams();
        if (filters.status) params.append('status', filters.status);
        if (filters.pipeline_id) params.append('pipeline_id', filters.pipeline_id);
        if (filters.limit) params.append('limit', filters.limit);
        if (filters.offset) params.append('offset', filters.offset);
        const query = params.toString() ? `?${params.toString()}` : '';
        return this.request('GET', `/pipelines/jobs/all${query}`);
    },

    /**
     * Cancel a running job
     */
    async cancelJob(jobId) {
        return this.request('POST', `/pipelines/jobs/${jobId}/cancel`);
    },

    /**
     * Retry a failed job
     */
    async retryJob(jobId) {
        return this.request('POST', `/pipelines/jobs/${jobId}/retry`);
    },

    /**
     * Get job execution logs
     */
    async getJobLogs(jobId, limit = 100) {
        return this.request('GET', `/pipelines/jobs/${jobId}/logs?limit=${limit}`);
    },

    // ==================== Thresholds ====================

    /**
     * Publish threshold to Redis
     */
    async publishThreshold(metricId, jobId, ttl = null) {
        const body = { metric_id: metricId, job_id: jobId };
        if (ttl) body.ttl = ttl;
        return this.request('POST', '/thresholds/publish', { body });
    },

    /**
     * Get cached threshold for a metric
     */
    async getThreshold(metricId) {
        return this.request('GET', `/thresholds/${metricId}`);
    },

    /**
     * Delete cached threshold
     */
    async deleteThreshold(metricId) {
        return this.request('DELETE', `/thresholds/${metricId}`);
    },

    /**
     * List all cached thresholds
     */
    async listCachedThresholds() {
        return this.request('GET', '/thresholds');
    },
};

// Make API globally available
window.API = API;