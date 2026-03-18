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

  getPrimarySelectedSeason() {
    const selectedSeasons = $("#seasonSelect").val() || [];
    if (selectedSeasons.length === 0) {
      return "2025/26";
    }

    const sortedSeasons = [...selectedSeasons].sort((a, b) => {
      const aYear = parseInt(String(a).split("/")[0], 10) || 0;
      const bYear = parseInt(String(b).split("/")[0], 10) || 0;
      return bYear - aYear;
    });

    return sortedSeasons[0];
  },

  getSelectedLeagueSquad() {
    const selectedSquad = document.querySelector('input[name="squadRadio"]:checked')?.value;
    return selectedSquad === "2nd" ? "2nd" : "1st";
  },

  getLeagueResultsFile(squad, season) {
    return "Charts/league/results.html";
  },

  getLeagueTableFile(squad, season) {
    return "Charts/league/table.html";
  },

  isLeagueResultsSeasonAvailable(season, squad = "1st") {
    const availableBySquad = {
      "1st": new Set(["2022/23", "2023/24", "2024/25", "2025/26"]),
      "2nd": new Set(["2024/25", "2025/26"]),
    };

    const availableSeasons = availableBySquad[squad] || availableBySquad["1st"];

    return availableSeasons.has(season);
  },

  toLeagueSeasonFormat(season) {
    if (!season || !season.includes("/")) {
      return season;
    }

    const [startYear, endShort] = String(season).split("/");
    return `${startYear}-20${endShort}`;
  },

  buildLeagueResultsUrl(baseFile, season, includeCompetition = true, squad = null) {
    if (!baseFile) {
      return null;
    }

    const selectedTypes = Array.from(
      document.querySelectorAll('input[name="gameTypeCheck"]:checked')
    ).map((checkbox) => checkbox.value);

    const leagueSeason = this.toLeagueSeasonFormat(season);
    const url = new URL(baseFile, window.location.href);

    if (leagueSeason) {
      url.searchParams.set("season", leagueSeason);
    }

    if (squad) {
      const squadValue = squad === "2nd" ? "2" : "1";
      url.searchParams.set("squad", squadValue);
    }

    if (includeCompetition && selectedTypes.length > 0) {
      url.searchParams.set("competition", selectedTypes.join(","));
    }

    return `${url.pathname}${url.search}`;
  },

  createAutoHeightLeagueIframe(src, className, minHeight = 300, options = {}) {
    const iframe = document.createElement("iframe");
    iframe.src = src;
    iframe.className = className;
    iframe.style.height = `${minHeight}px`;
    iframe.style.overflow = "hidden";
    iframe.setAttribute("scrolling", "no");

    const updateHeight = () => {
      try {
        const doc = iframe.contentDocument || iframe.contentWindow?.document;
        if (!doc) {
          return;
        }

        const primaryContent =
          doc.querySelector("#vis") ||
          doc.querySelector("#tableRoot") ||
          doc.querySelector(".table-wrap") ||
          null;

        if (options.fitToWidth && primaryContent) {
          const contentWidth = Math.max(
            primaryContent.scrollWidth || 0,
            primaryContent.offsetWidth || 0,
            primaryContent.getBoundingClientRect
              ? primaryContent.getBoundingClientRect().width
              : 0
          );

          const availableWidth =
            iframe.clientWidth || iframe.getBoundingClientRect().width || 0;

          if (contentWidth > 0 && availableWidth > 0) {
            const baseScale = Math.min(1, (availableWidth - 8) / contentWidth);
            const configuredMinScale = Number(options.minScale);
            const nextScale = Number.isFinite(configuredMinScale)
              ? Math.max(baseScale, configuredMinScale)
              : baseScale;

            if (nextScale < 0.999) {
              primaryContent.style.transformOrigin = "top left";
              primaryContent.style.transform = `scale(${nextScale})`;
            } else {
              primaryContent.style.transform = "none";
            }
          }
        }

        const contentHeight = primaryContent?.getBoundingClientRect
          ? primaryContent.getBoundingClientRect().height
          : 0;

        const svg = doc.querySelector("#vis svg, .vega-embed svg, svg");
        const bindings = doc.querySelector(".vega-bindings");
        const svgRect = svg?.getBoundingClientRect ? svg.getBoundingClientRect() : null;
        const bindingsRect = bindings?.getBoundingClientRect
          ? bindings.getBoundingClientRect()
          : null;

        const visualTop = Math.min(
          Number.isFinite(svgRect?.top) ? svgRect.top : Number.POSITIVE_INFINITY,
          Number.isFinite(bindingsRect?.top)
            ? bindingsRect.top
            : Number.POSITIVE_INFINITY
        );

        const visualBottom = Math.max(
          Number.isFinite(svgRect?.bottom) ? svgRect.bottom : 0,
          Number.isFinite(bindingsRect?.bottom) ? bindingsRect.bottom : 0
        );

        const visualHeight =
          Number.isFinite(visualTop) && visualBottom > visualTop
            ? visualBottom - visualTop
            : 0;

        let scaleY = 1;
        const transformTarget = primaryContent || doc.body;
        if (transformTarget && transformTarget.ownerDocument?.defaultView) {
          const computedStyle = transformTarget.ownerDocument.defaultView.getComputedStyle(transformTarget);
          const transform = computedStyle?.transform;

          if (transform && transform !== "none") {
            const matrix3dMatch = transform.match(/^matrix3d\((.+)\)$/);
            const matrixMatch = transform.match(/^matrix\((.+)\)$/);

            if (matrix3dMatch) {
              const values = matrix3dMatch[1].split(",").map((value) => Number(value.trim()));
              if (values.length === 16 && !Number.isNaN(values[5]) && values[5] > 0) {
                scaleY = values[5];
              }
            } else if (matrixMatch) {
              const values = matrixMatch[1].split(",").map((value) => Number(value.trim()));
              if (values.length === 6 && !Number.isNaN(values[3]) && values[3] > 0) {
                scaleY = values[3];
              }
            }
          }
        }

        const bodyHeight = doc.body ? doc.body.scrollHeight : 0;
        const htmlHeight = doc.documentElement ? doc.documentElement.scrollHeight : 0;

        const measuredHeight =
          visualHeight > 0
            ? visualHeight + 4
            : contentHeight > 0
            ? contentHeight * scaleY + 4
            : Math.max(bodyHeight, htmlHeight);

        const nextHeight = Math.ceil(measuredHeight);
        if (nextHeight > 0) {
          iframe.style.height = `${nextHeight}px`;
        }
      } catch (error) {
        // Silent fail: keep fallback height
      }
    };

    iframe.addEventListener("load", () => {
      updateHeight();
      [150, 500, 1000, 1800].forEach((delay) => {
        window.setTimeout(updateHeight, delay);
      });

      window.addEventListener("resize", updateHeight);
    });

    return iframe;
  },

  createLeagueResultsPanel(resultsHtmlFile, tableHtmlFile = null, emptyMessage = null) {
    const panel = document.createElement("div");
    panel.className = "league-results-panel";

    if (resultsHtmlFile) {
      const resultsIframe = this.createAutoHeightLeagueIframe(
        resultsHtmlFile,
        "league-results-iframe",
        320,
        {
          fitToWidth: true,
        }
      );
      panel.appendChild(resultsIframe);

      if (tableHtmlFile) {
        const tableIframe = this.createAutoHeightLeagueIframe(
          tableHtmlFile,
          "league-table-iframe",
          420
        );
        panel.appendChild(tableIframe);
      }

      return panel;
    }

    const emptyState = document.createElement("div");
    emptyState.className = "league-results-empty";
    emptyState.textContent =
      emptyMessage || "No league results chart is available for this selection.";
    panel.appendChild(emptyState);
    return panel;
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
    newContainer.style.minHeight = "calc(100vh - 200px)";
    parentContainer.appendChild(newContainer);

    if (currentLeagueType === "league-results") {
      const selectedSeason = this.getPrimarySelectedSeason();
      const squad = this.getSelectedLeagueSquad();
      const squadLabel = squad === "2nd" ? "2nd XV" : "1st XV";
      const seasonOptions =
        squad === "2nd"
          ? "2024/25, 2025/26"
          : "2022/23, 2023/24, 2024/25, 2025/26";

      const grid = document.createElement("div");
      grid.className = "league-results-grid";

      if (!this.isLeagueResultsSeasonAvailable(selectedSeason, squad)) {
        const panel = this.createLeagueResultsPanel(
          null,
          `No ${squadLabel} league results data is available for ${selectedSeason}. Please select one of: ${seasonOptions}.`
        );
        grid.appendChild(panel);
        newContainer.appendChild(grid);
        return;
      }

      const baseFile = this.getLeagueResultsFile(squad, selectedSeason);
      const resultsHtmlFile = this.buildLeagueResultsUrl(baseFile, selectedSeason, true, squad);
      const tableHtmlFile = this.buildLeagueResultsUrl(
        this.getLeagueTableFile(squad, selectedSeason),
        selectedSeason,
        true,
        squad
      );
      const panel = this.createLeagueResultsPanel(resultsHtmlFile, tableHtmlFile);
      grid.appendChild(panel);

      newContainer.appendChild(grid);
      return;
    }

    const chartFiles = {
      "league-analysis": "Charts/league/squad_analysis_1s.html",
    };

    const htmlFile = chartFiles[currentLeagueType];
    if (!htmlFile) {
      newContainer.innerHTML = '<p style="padding: 20px;">Chart not found</p>';
      return;
    }

    if (currentLeagueType === "league-analysis") {
      const selectedSeason = this.getPrimarySelectedSeason();
      const squad = "1st";
      const squadLabel = "1st XV";
      const seasonOptions = "2022/23, 2023/24, 2024/25, 2025/26";

      if (!this.isLeagueResultsSeasonAvailable(selectedSeason, squad)) {
        const panel = this.createLeagueResultsPanel(
          null,
          null,
          `No ${squadLabel} squad analysis data is available for ${selectedSeason}. Please select one of: ${seasonOptions}.`
        );
        newContainer.appendChild(panel);
        return;
      }

      const analysisUrl = this.buildLeagueResultsUrl(
        htmlFile,
        selectedSeason,
        false
      );
      const minHeight = Math.max(500, window.innerHeight - 220);
      const iframe = this.createAutoHeightLeagueIframe(
        analysisUrl,
        "league-results-iframe",
        minHeight,
        {
          fitToWidth: true,
        }
      );
      newContainer.appendChild(iframe);
      return;
    }

    const iframe = this.createAutoHeightLeagueIframe(
      htmlFile,
      "league-results-iframe",
      420
    );
    newContainer.appendChild(iframe);
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
