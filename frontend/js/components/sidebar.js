/**
 * Sidebar Component
 */

const Sidebar = {
    currentPage: 'dashboard',

    init() {
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
        if (page === 'dashboard') {
            Dashboard.refresh();
        } else if (page === 'models') {
            Models.refresh();
        } else if (page === 'datasources') {
            DataSources.refresh();
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

    updateCurrentDataSource(name) {
        document.getElementById('current-datasource').textContent = name;
    },
};

// Make Sidebar globally available
window.Sidebar = Sidebar;