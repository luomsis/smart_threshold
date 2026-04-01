/**
 * Sidebar Component
 */

const Sidebar = {
    currentPage: 'predict',

    async init() {
        this.bindEvents();
    },

    bindEvents() {
        const navItems = document.querySelectorAll('.nav-item');
        navItems.forEach(item => {
            item.addEventListener('click', () => {
                const page = item.dataset.page;
                this.navigateTo(page);
            });
        });
    },

    navigateTo(page) {
        if (this.currentPage === page) return;

        // Update nav items
        document.querySelectorAll('.nav-item').forEach(item => {
            item.classList.toggle('active', item.dataset.page === page);
        });

        // Update pages
        document.querySelectorAll('.page').forEach(p => {
            p.classList.toggle('active', p.id === `page-${page}`);
        });

        this.currentPage = page;

        // Trigger page-specific init
        if (page === 'predict') {
            Predict.refresh();
        } else if (page === 'models') {
            Models.refresh();
        } else if (page === 'pipelines') {
            Pipelines.refresh();
        } else if (page === 'jobs') {
            Jobs.refresh();
        }
    },

    /**
     * Navigate to model edit page (called from Models component)
     */
    navigateToModelEdit() {
        // Hide all pages
        document.querySelectorAll('.page').forEach(p => {
            p.classList.remove('active');
        });

        // Show model edit page
        const editPage = document.getElementById('page-model-edit');
        if (editPage) {
            editPage.classList.add('active');
        }

        // Clear nav selection
        document.querySelectorAll('.nav-item').forEach(item => {
            item.classList.remove('active');
        });

        this.currentPage = 'model-edit';
    },

    /**
     * Navigate to pipeline edit page
     */
    navigateToPipelineEdit() {
        document.querySelectorAll('.page').forEach(p => {
            p.classList.remove('active');
        });

        const editPage = document.getElementById('page-pipeline-edit');
        if (editPage) {
            editPage.classList.add('active');
        }

        document.querySelectorAll('.nav-item').forEach(item => {
            item.classList.remove('active');
        });

        this.currentPage = 'pipeline-edit';
    },

    /**
     * Navigate to job status page
     */
    navigateToJobStatus() {
        document.querySelectorAll('.page').forEach(p => {
            p.classList.remove('active');
        });

        const statusPage = document.getElementById('page-job-status');
        if (statusPage) {
            statusPage.classList.add('active');
        }

        document.querySelectorAll('.nav-item').forEach(item => {
            item.classList.remove('active');
        });

        this.currentPage = 'job-status';
    },
};

// Make Sidebar globally available
window.Sidebar = Sidebar;