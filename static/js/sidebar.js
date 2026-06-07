// Centralized sidebar controls — handles toggle + user click
(function(){
  function initSidebarToggle() {
    const sidebar = document.getElementById('sidebar');
    const toggleBtn = document.getElementById('sidebarToggleBtn');
    if (!sidebar || !toggleBtn) return;

    const isCollapsed = localStorage.getItem('smartcopy-sidebar-collapsed') === 'true';
    if (isCollapsed) sidebar.classList.add('collapsed');

    // Ensure ARIA reflects current state
    toggleBtn.setAttribute('aria-expanded', String(!sidebar.classList.contains('collapsed')));

    toggleBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      sidebar.classList.toggle('collapsed');
      const collapsed = sidebar.classList.contains('collapsed');
      localStorage.setItem('smartcopy-sidebar-collapsed', collapsed);
      // Update ARIA for screen readers
      toggleBtn.setAttribute('aria-expanded', String(!collapsed));
    });
  }

  function initSidebarUserClick() {
    const sidebarUser = document.querySelector('.sidebar-user');
    if (sidebarUser) {
      sidebarUser.addEventListener('click', () => { window.location.href = '/dashboard'; });
      sidebarUser.setAttribute('role', 'button');
      sidebarUser.setAttribute('tabindex', '0');
      sidebarUser.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') window.location.href = '/dashboard'; });
    }
  }

  // Expose to global scope so existing scripts can call on DOMContentLoaded
  window.initSidebarToggle = initSidebarToggle;
  window.initSidebarUserClick = initSidebarUserClick;
})();
