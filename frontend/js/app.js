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
        Sidebar.init();

        // Initialize page-specific components
        await Dashboard.init();
        await Models.init();
        await DataSources.init();

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
    },
};

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', () => {
    App.init();
});