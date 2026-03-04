// Chart rendering functions (extracted from test.html)
const Charts = {
  // Embed chart with responsive scaling
  embedChart(selector, spec, customOptions = {}) {
    console.log("📊 embedChart called for:", selector);
    console.log(
      "📊 Spec filters:",
      spec.transform?.filter((t) => t._externalFilter)
    );

    // Make chart responsive by removing fixed width/height
    if (spec.width) {
      spec.width = Math.max(600, spec.width); // Minimum width of 600px
    }
    if (spec.height && window.innerWidth <= 768) {
      spec.height = Math.max(spec.height * 0.8, 400); // Slightly reduce height on mobile
    }

    const defaultOptions = {
      actions: true,
      renderer: "svg",
      scaleFactor: 1,
      config: {
        autosize: {
          resize: true,
          type: "fit",
        },
      },
    };

    const embedOptions = { ...defaultOptions, ...customOptions };

    console.log("📊 About to call vegaEmbed for:", selector);
    return vegaEmbed(selector, spec, embedOptions)
      .then((result) => {
        console.log("✅ vegaEmbed completed for:", selector);
        return result;
      })
      .catch((error) => {
        console.error("❌ vegaEmbed failed for:", selector, error);
        throw error;
      });
  },

  // Render Player Stats chart
  renderPlayerStatsChart() {
    console.log("🎯 Rendering Player Stats chart:", currentPlayerStatsType);

    const parentContainer = document.getElementById("player-stats-content");
    const oldContainer = document.getElementById("player-stats-vis");

    // Remove old container completely
    if (oldContainer) {
      oldContainer.remove();
    }

    // Create fresh container
    const newContainer = document.createElement("div");
    newContainer.id = "player-stats-vis";
    parentContainer.appendChild(newContainer);

    // Select the appropriate spec based on current type
    let spec;
    let applyBench = true;
    let applyPosition = true;
    let applyCompetition = true;

    switch (currentPlayerStatsType) {
      case "appearances":
        spec = appearancesSpec;
        applyBench = true;
        applyPosition = true;
        applyCompetition = true;
        break;
      case "captains":
        spec = captainsSpec;
        applyBench = false;
        applyPosition = false;
        applyCompetition = true;
        break;
      case "point-scorers":
        spec = pointScorersSpec;
        applyBench = false;
        applyPosition = false;
        applyCompetition = false;
        break;
      case "cards":
        spec = cardsSpec;
        applyBench = false;
        applyPosition = false;
        applyCompetition = false;
        break;
      default:
        spec = appearancesSpec;
        applyBench = true;
        applyPosition = true;
        applyCompetition = true;
    }

    console.log("Player Stats type:", currentPlayerStatsType);

    let chartSpec = JSON.parse(JSON.stringify(spec)); // deep copy
    Filters.applyFilters(
      chartSpec,
      applyBench,
      applyPosition,
      applyCompetition
    );
    this.embedChart("#player-stats-vis", chartSpec);
  },

  // Render Results chart
  renderResultsChart() {
    console.log("🎯 Rendering Results chart...");

    const parentContainer = document.getElementById("results-content");
    const oldContainer = document.getElementById("results-vis");

    // Remove old container completely
    if (oldContainer) {
      oldContainer.remove();
    }

    // Create fresh container
    const newContainer = document.createElement("div");
    newContainer.id = "results-vis";
    parentContainer.appendChild(newContainer);

    let spec = JSON.parse(JSON.stringify(resultsSpec)); // deep copy
    Filters.applyFilters(spec, false, false, true); // Apply squad, season, and competition filters (no bench, no position)
    this.embedChart("#results-vis", spec);
  },

  // Render Team Sheets chart
  renderTeamSheetsChart() {
    console.log("🎯 Rendering Team Sheets chart...");

    const parentContainer = document.getElementById("team-sheets-content");
    const oldContainer = document.getElementById("team-sheets-vis");

    // Remove old container completely
    if (oldContainer) {
      oldContainer.remove();
    }

    // Create fresh container
    const newContainer = document.createElement("div");
    newContainer.id = "team-sheets-vis";
    parentContainer.appendChild(newContainer);

    let spec = JSON.parse(JSON.stringify(teamSheetsSpec)); // deep copy
    let filters = Filters.applyFilters(spec, true, true, true); // Apply all filters
    console.log("Team Sheets Filters:", filters);
    this.embedChart("#team-sheets-vis", spec);
  },

  // Render Set Piece chart
  renderSetPieceChart() {
    console.log("🎯 Rendering Set Piece chart...");

    const parentContainer = document.getElementById("set-piece-content");
    const oldContainer = document.getElementById("set-piece-vis");

    // Remove old container completely
    if (oldContainer) {
      oldContainer.remove();
    }

    // Create fresh container
    const newContainer = document.createElement("div");
    newContainer.id = "set-piece-vis";
    parentContainer.appendChild(newContainer);

    // Use the stored set piece type
    const spec = currentSetPieceType === "lineout" ? lineoutSpec : scrumSpec;

    console.log("Set piece type:", currentSetPieceType);

    let chartSpec = JSON.parse(JSON.stringify(spec)); // deep copy

    // Apply filters to all parts of the set piece chart
    const filters = Filters.applyFilters(chartSpec, false, false, true);

    // EXPLICITLY apply filters to area chart layers if they exist
    if (chartSpec.hconcat && chartSpec.hconcat.length >= 3) {
      const successRateChart = chartSpec.hconcat[2];

      if (successRateChart && successRateChart.layer) {
        successRateChart.layer.forEach((layer) => {
          layer.transform = layer.transform || [];
          layer.transform = layer.transform.filter((t) => !t._externalFilter);

          if (filters.length > 0) {
            const combinedFilter = filters.join(" && ");
            layer.transform.push({
              filter: combinedFilter,
              _externalFilter: true,
            });
          }
        });
      }
    }

    this.embedChart("#set-piece-vis", chartSpec);
  },

  // Add to Charts object
  renderLeagueChart() {
    console.log("🎯 Rendering League chart:", currentLeagueType);

    const parentContainer = document.getElementById("league-content");
    const oldContainer = document.getElementById("league-vis");

    if (oldContainer) {
      oldContainer.remove();
    }

    const newContainer = document.createElement("div");
    newContainer.id = "league-vis";
    parentContainer.appendChild(newContainer);

    const spec =
      currentLeagueType === "league-results"
        ? leagueResultsSpec
        : leagueAnalysisSpec;
    let chartSpec = JSON.parse(JSON.stringify(spec));

    // League charts may not need the same filters as EGRFC charts
    this.embedChart("#league-vis", chartSpec);
  },

  // Render League chart (loads HTML file in iframe)
  renderLeagueChart() {
    console.log("🎯 Rendering League chart:", currentLeagueType);

    const parentContainer = document.getElementById("league-content");
    const oldContainer = document.getElementById("league-vis");

    // Remove old container
    if (oldContainer) {
      oldContainer.remove();
    }

    // Create fresh container
    const newContainer = document.createElement("div");
    newContainer.id = "league-vis";
    newContainer.style.width = "100%";
    newContainer.style.height = "calc(100vh - 200px)";
    parentContainer.appendChild(newContainer);

    // Map chart type to HTML file
    const chartFiles = {
      "league-results": "Charts/league/results_1s_combined.html",
      "league-analysis": "Charts/league/squad_analysis_1s.html"
    };

    const htmlFile = chartFiles[currentLeagueType];
    if (htmlFile) {
      // Create iframe to load the HTML file
      const iframe = document.createElement("iframe");
      iframe.src = htmlFile;
      iframe.style.width = "100%";
      iframe.style.height = "100%";
      iframe.style.border = "none";
      newContainer.appendChild(iframe);
    } else {
      newContainer.innerHTML = '<p style="padding: 20px;">Chart not found</p>';
    }
  },

  // Function to render only the currently active chart with current filters
  renderCharts() {
    console.log("🔄 renderCharts called at:", new Date().toISOString());

    // Find the active tab and render only that chart
    const activeTab = document.querySelector("#chartTabs .nav-link.active");
    if (!activeTab) {
      console.log("🔄 No active tab found");
      return;
    }

    const tabId = activeTab.getAttribute("id");
    console.log("🔄 Rendering chart for active tab:", tabId);

    // Apply tab-specific logic first
    Filters.applyTabSpecificLogic(tabId);

    // Small delay to ensure selectpicker updates are processed
    setTimeout(() => {
      // Render only the active chart
      switch (tabId) {
        case "results-tab":
          this.renderResultsChart();
          break;
        case "team-sheets-tab":
          this.renderTeamSheetsChart();
          break;
        case "player-stats-dropdown":
          this.renderPlayerStatsChart();
          break;
        case "set-piece-dropdown":
          this.renderSetPieceChart();
          break;
        case "league-dropdown":
          this.renderLeagueChart();
          break;
        default:
          console.log("🔄 Unknown tab ID:", tabId);
      }

      console.log("🔄 Active chart rendered");
    }, 10);
  },
};

// Global aliases for backward compatibility
window.embedChart = Charts.embedChart.bind(Charts);
window.renderCharts = Charts.renderCharts.bind(Charts);
