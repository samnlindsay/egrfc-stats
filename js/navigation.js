// Navigation and dropdown handling (extracted from test.html)
const Navigation = {
  // Initialize all navigation components
  init() {
    this.initDropdowns();
    this.bindTabEvents();
    this.bindDropdownEvents();
  },

  // Initialize Bootstrap dropdowns
  initDropdowns() {
    $(".nav-tabs .dropdown-toggle").dropdown();
    this.handleDropdownPositioning();
  },

  // Handle dropdown positioning for narrow screens
  handleDropdownPositioning() {
    $(".nav-tabs .dropdown-toggle").on("show.bs.dropdown", function (e) {
      console.log("Dropdown showing for:", this.id);
    });

    $(".nav-tabs .dropdown-toggle").on("shown.bs.dropdown", function (e) {
      console.log("Dropdown shown for:", this.id);

      // Handle positioning for very narrow screens
      if (window.innerWidth <= CONFIG.breakpoints.small) {
        const $menu = $(this).siblings(".dropdown-menu");
        const buttonRect = this.getBoundingClientRect();
        const menuWidth = $menu.outerWidth();
        const viewportWidth = window.innerWidth;

        // Position the dropdown
        let leftPosition = buttonRect.left;

        // Adjust if dropdown would go off the right edge
        if (leftPosition + menuWidth > viewportWidth - 10) {
          leftPosition = viewportWidth - menuWidth - 10;
        }

        // Ensure it doesn't go off the left edge
        if (leftPosition < 10) {
          leftPosition = 10;
        }

        $menu.css({
          position: "fixed",
          top: buttonRect.bottom + 2 + "px",
          left: leftPosition + "px",
          right: "auto",
        });

        console.log(
          "Positioned dropdown at:",
          leftPosition,
          "Button rect:",
          buttonRect
        );
      }
    });

    $(".nav-tabs .dropdown-toggle").on("hide.bs.dropdown", function (e) {
      console.log("Dropdown hiding for:", this.id);
    });
  },

  // Bind tab click events for regular tabs (not dropdowns)
  bindTabEvents() {
    document
      .querySelectorAll("#chartTabs button:not(.dropdown-toggle)")
      .forEach((tab) => {
        tab.addEventListener("click", (event) => {
          event.preventDefault();
          const targetId = tab.getAttribute("data-bs-target");

          // Update tab content visibility
          this.showTabContent(targetId);

          // Update tab button active state
          this.setActiveTab(tab);

          // Render the newly active chart
          setTimeout(() => Charts.renderCharts(), 50);
        });
      });
  },

  // Bind dropdown item click events
  bindDropdownEvents() {
    // Dropdown item click handlers - using event delegation for reliability
    $(document).on("click", ".dropdown-item[data-chart-type]", function (e) {
      e.preventDefault();
      e.stopPropagation();

      const chartType = this.getAttribute("data-chart-type");
      const targetId = this.getAttribute("data-bs-target");

      console.log("Dropdown clicked:", chartType, "Target:", targetId);

      // Update the current chart type
      if (targetId === "#player-stats-content") {
        currentPlayerStatsType = chartType;
      } else if (targetId === "#set-piece-content") {
        currentSetPieceType = chartType;
      }

      // Update tab content visibility
      Navigation.showTabContent(targetId);

      // Update tab button active state
      Navigation.setActiveDropdownTab(targetId);

      // Render the newly active chart
      setTimeout(() => Charts.renderCharts(), 50);
    });
  },

  // Show specific tab content
  showTabContent(targetId) {
    // Hide all tab panes
    document.querySelectorAll(".tab-pane").forEach((pane) => {
      pane.classList.remove("show", "active");
    });

    // Show target tab pane
    const targetPane = document.querySelector(targetId);
    if (targetPane) {
      targetPane.classList.add("show", "active");
    }
  },

  // Set active tab for regular tabs
  setActiveTab(activeTab) {
    // Remove active class from all nav links
    document.querySelectorAll("#chartTabs .nav-link").forEach((tab) => {
      tab.classList.remove("active");
    });

    // Add active class to clicked tab
    activeTab.classList.add("active");
  },

  // Set active tab for dropdown items
  setActiveDropdownTab(targetId) {
    // Remove active class from all nav links
    document.querySelectorAll("#chartTabs .nav-link").forEach((tab) => {
      tab.classList.remove("active");
    });

    // Add active class to appropriate dropdown toggle
    if (targetId === "#player-stats-content") {
      document.getElementById("player-stats-dropdown").classList.add("active");
    } else if (targetId === "#set-piece-content") {
      document.getElementById("set-piece-dropdown").classList.add("active");
    }
  },

  // Set initial tab state
  setInitialTab() {
    // Set default to player stats with appearances
    const playerStatsTab = document.getElementById("player-stats-dropdown");
    const playerStatsContent = document.getElementById("player-stats-content");

    if (playerStatsTab && playerStatsContent) {
      // Clear all active states
      document.querySelectorAll("#chartTabs .nav-link").forEach((tab) => {
        tab.classList.remove("active");
      });
      document.querySelectorAll(".tab-pane").forEach((pane) => {
        pane.classList.remove("show", "active");
      });

      // Set player stats as active
      playerStatsTab.classList.add("active");
      playerStatsContent.classList.add("show", "active");

      // Set default chart types
      currentPlayerStatsType = "appearances";
      currentSetPieceType = "lineout";
    }
  },
};
