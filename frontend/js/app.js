/**
 * SmartThreshold Frontend Application
 * Main entry point
 */

const App = {
    /**
     * Initialize application
     */
    async init() {
        console.log('SmartThreshold App initializing...');

        // Initialize components
        await Sidebar.init();

        // Initialize page-specific components
        await Predict.init();
        await Models.init();
        await DataSources.init();
        await Pipelines.init();
        await Jobs.init();

        // Bind modal close
        document.getElementById('modal-close').addEventListener('click', () => {
            Helpers.hideModal();
        });

        // Close modal on outside click
        document.getElementById('modal').addEventListener('click', (e) => {
            if (e.target.id === 'modal') {
                Helpers.hideModal();
            }
        });

        console.log('SmartThreshold App initialized');

        // Load initial page data (default to Predict page)
        Predict.refresh();
    },

    /**
     * Navigate to a page
     */
    showPage(page) {
        // Hide all pages
        document.querySelectorAll('.page').forEach(p => {
            p.classList.remove('active');
        });

        // Update nav items
        document.querySelectorAll('.nav-item').forEach(item => {
            item.classList.toggle('active', item.dataset.page === page);
        });

        // Show target page
        const targetPage = document.getElementById(`page-${page}`);
        if (targetPage) {
            targetPage.classList.add('active');
        }

        // Update sidebar
        Sidebar.currentPage = page;

        // Trigger page-specific init
        if (page === 'predict') {
            Predict.refresh();
        } else if (page === 'models') {
            Models.refresh();
        } else if (page === 'datasources') {
            DataSources.refresh();
        } else if (page === 'pipelines') {
            Pipelines.refresh();
        } else if (page === 'jobs') {
            Jobs.refresh();
        }
    },

    /**
     * Navigate to model edit page
     */
    showModelEditPage() {
        // Hide all pages
        document.querySelectorAll('.page').forEach(p => {
            p.classList.remove('active');
        });

        // Clear nav selection
        document.querySelectorAll('.nav-item').forEach(item => {
            item.classList.remove('active');
        });

        // Show model edit page
        const editPage = document.getElementById('page-model-edit');
        if (editPage) {
            editPage.classList.add('active');
        }

        // Update sidebar
        Sidebar.currentPage = 'model-edit';
    },
};

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', () => {
    App.init();
});