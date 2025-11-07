// Main application initialization (extracted from test.html)
$(document).ready(function () {
  console.log("🔧 Document ready, initializing...");

  // Load all chart data (exactly from test.html)
  Promise.all([
    fetch(CONFIG.dataFiles.appearances).then((res) => res.json()),
    fetch(CONFIG.dataFiles.captains).then((res) => res.json()),
    fetch(CONFIG.dataFiles.pointScorers).then((res) => res.json()),
    fetch(CONFIG.dataFiles.cards).then((res) => res.json()),
    fetch(CONFIG.dataFiles.teamSheets).then((res) => res.json()),
    fetch(CONFIG.dataFiles.results).then((res) => res.json()),
    fetch(CONFIG.dataFiles.lineout).then((res) => res.json()),
    fetch(CONFIG.dataFiles.scrum).then((res) => res.json()),
  ])
    .then(
      ([
        appearances,
        captains,
        pointScorers,
        cards,
        teamSheets,
        results,
        lineout,
        scrum,
      ]) => {
        // Set global variables (matching test.html exactly)
        appearancesSpec = appearances;
        captainsSpec = captains;
        pointScorersSpec = pointScorers;
        cardsSpec = cards;
        teamSheetsSpec = teamSheets;
        resultsSpec = results;
        lineoutSpec = lineout;
        scrumSpec = scrum;

        console.log("📊 All chart specifications loaded successfully");

        // Initialize components
        initializeComponents();

        // Set initial tab state
        Navigation.setInitialTab();

        // Initial render
        Charts.renderCharts();

        STATE.isInitialized = true;
        console.log("✅ EGRFC Stats initialized successfully");
      }
    )
    .catch((error) => {
      console.error("❌ Failed to load chart data:", error);
    });
});

// Initialize all components (extracted from test.html)
function initializeComponents() {
  console.log("🔧 Initializing components...");

  // Initialize selectpickers
  $(".selectpicker").selectpicker({
    dropupAuto: true,
    size: "auto",
    width: "100%",
    maxOptions: false,
  });

  // Initialize Bootstrap dropdowns properly
  Navigation.init();

  // Bind filter events
  bindFilterEvents();

  // Initialize filter panel
  initializeFilterPanel();

  // Handle touch optimization
  handleTouchOptimization();

  console.log("✅ All components initialized");
}

// Bind filter events (from test.html)
function bindFilterEvents() {
  console.log("🔧 Binding filter events...");

  // Season filter
  $("#seasonSelect").on("changed.bs.select", function () {
    console.log("Season changed");
    Charts.renderCharts();
  });

  // Position filter
  $("#positionSelect").on("changed.bs.select", function () {
    console.log("Position changed");
    Charts.renderCharts();
  });

  // Squad radio buttons
  document.querySelectorAll('input[name="squadRadio"]').forEach((radio) => {
    radio.addEventListener("change", function () {
      console.log("Squad changed");
      Charts.renderCharts();
    });
  });

  // Competition checkboxes
  document
    .querySelectorAll('input[name="gameTypeCheck"]')
    .forEach((checkbox) => {
      checkbox.addEventListener("change", function () {
        console.log("Competition changed");
        Charts.renderCharts();
      });
    });

  // Include bench switch
  document
    .getElementById("includeBenchSwitch")
    .addEventListener("change", function () {
      console.log("Bench toggle changed");
      Charts.renderCharts();
    });

  console.log("✅ Filter events bound");
}

// Initialize filter panel (from test.html)
function initializeFilterPanel() {
  console.log("🔧 Initializing filter panel...");

  const $filterPanelToggle = $("#filterPanelToggle");
  const $filterPanel = $("#filterPanel");
  const $backdrop = $("#filterPanelBackdrop");

  function toggleFilterPanel(e) {
    e.preventDefault();
    e.stopPropagation();

    const isCurrentlyExpanded = $filterPanel.hasClass("expanded");

    if (isCurrentlyExpanded) {
      $filterPanel.removeClass("expanded");
      $backdrop.removeClass("show");
    } else {
      $filterPanel.addClass("expanded");
      if (window.innerWidth <= 768) {
        $backdrop.addClass("show");
      }
    }

    localStorage.setItem(
      "filterPanelExpanded",
      $filterPanel.hasClass("expanded")
    );
  }

  $filterPanelToggle.on("click", toggleFilterPanel);
  $backdrop.on("click", function () {
    $filterPanel.removeClass("expanded");
    $backdrop.removeClass("show");
    localStorage.setItem("filterPanelExpanded", false);
  });

  // Restore panel state
  if (localStorage.getItem("filterPanelExpanded") === "true") {
    $filterPanel.addClass("expanded");
  }

  // Handle window resize
  window.addEventListener("resize", function () {
    if (window.innerWidth > 768) {
      $backdrop.removeClass("show");
    } else if ($filterPanel.hasClass("expanded")) {
      $backdrop.addClass("show");
    }
  });

  console.log("✅ Filter panel initialized");
}

// Handle touch optimization (from test.html)
function handleTouchOptimization() {
  if ("ontouchstart" in window) {
    console.log("📱 Touch device detected - adding chart touch optimization");

    $(document).on("touchend", ".vega-embed, .tab-content", function (e) {
      e.preventDefault();
    });
  }
}
