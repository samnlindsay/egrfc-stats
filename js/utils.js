// Utility functions
const Utils = {
  // Deep clone object
  deepClone(obj) {
    return JSON.parse(JSON.stringify(obj));
  },

  // Debounce function
  debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
      const later = () => {
        clearTimeout(timeout);
        func(...args);
      };
      clearTimeout(timeout);
      timeout = setTimeout(later, wait);
    };
  },

  // Get current screen size category
  getScreenSize() {
    const width = window.innerWidth;
    if (width <= CONFIG.breakpoints.small) return "small";
    if (width <= CONFIG.breakpoints.mobile) return "mobile";
    return "desktop";
  },

};
