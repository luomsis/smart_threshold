/**
 * API Client for SmartThreshold Backend
 */

const API = {
    // Base URL - will be configurable
    baseUrl: window.location.protocol + '//' + window.location.hostname + ':8000',

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
        const url = `${this.baseUrl}${path}`;
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
            console.error('API Error:', error);
            throw error;
        }
    },

    // ==================== Data Sources ====================

    /**
     * List all data sources
     */
    async listDataSources() {
        return this.request('GET', '/api/v1/datasources');
    },

    /**
     * Get data source by ID
     */
    async getDataSource(id) {
        return this.request('GET', `/api/v1/datasources/${id}`);
    },

    /**
     * Create data source
     */
    async createDataSource(data) {
        return this.request('POST', '/api/v1/datasources', { body: data });
    },

    /**
     * Delete data source
     */
    async deleteDataSource(id) {
        return this.request('DELETE', `/api/v1/datasources/${id}`);
    },

    /**
     * List metrics from data source
     */
    async listMetrics(dataSourceId) {
        return this.request('GET', `/api/v1/datasources/${dataSourceId}/metrics`);
    },

    /**
     * List labels from data source
     */
    async listLabels(dataSourceId) {
        return this.request('GET', `/api/v1/datasources/${dataSourceId}/labels`);
    },

    /**
     * Get label values
     */
    async getLabelValues(dataSourceId, labelName) {
        return this.request('GET', `/api/v1/datasources/${dataSourceId}/labels/${encodeURIComponent(labelName)}`);
    },

    /**
     * Query data
     */
    async queryData(dataSourceId, query, timeRange) {
        return this.request('POST', `/api/v1/datasources/${dataSourceId}/query`, {
            body: {
                query,
                time_range: timeRange,
            },
        });
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
        return this.request('GET', `/api/v1/models${query}`);
    },

    /**
     * Get model by ID
     */
    async getModel(id) {
        return this.request('GET', `/api/v1/models/${id}`);
    },

    /**
     * Create model
     */
    async createModel(data) {
        return this.request('POST', '/api/v1/models', { body: data });
    },

    /**
     * Update model
     */
    async updateModel(id, data) {
        return this.request('PUT', `/api/v1/models/${id}`, { body: data });
    },

    /**
     * Delete model
     */
    async deleteModel(id) {
        return this.request('DELETE', `/api/v1/models/${id}`);
    },

    // ==================== Predictions ====================

    /**
     * Analyze features
     */
    async analyzeFeatures(data, timestamps) {
        return this.request('POST', '/api/v1/predictions/analyze', {
            body: { data, timestamps },
        });
    },

    /**
     * Run prediction
     */
    async predict(modelId, data, timestamps, periods = 1440, freq = '1min') {
        return this.request('POST', '/api/v1/predictions/predict', {
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
        return this.request('POST', '/api/v1/predictions/compare', {
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
        return this.request('GET', '/api/health');
    },
};

// Make API globally available
window.API = API;