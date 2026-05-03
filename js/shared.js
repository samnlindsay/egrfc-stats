// Shared constants, utilities and chart helpers used across all pages.

const VEGA_EMBED_ACTIONS = false;
const FORWARD_POSITIONS = [
  "Prop",
  "Hooker",
  "Second Row",
  "Flanker",
  "Number 8",
];
const BACK_POSITIONS = [
  "Scrum Half",
  "Fly Half",
  "Centre",
  "Wing",
  "Full Back",
];
const SQUAD_POSITION_ORDER = [...FORWARD_POSITIONS, ...BACK_POSITIONS];
let availableSeasons = [
  "2025/26",
  "2024/25",
  "2023/24",
  "2022/23",
  "2021/22",
  "2019/20",
  "2018/19",
  "2017/18",
  "2016/17",
];
const chartSpecCache = new Map();
const chartSpecRequestVersion = String(Date.now());
let responsiveChartResizeBound = false;
const SET_PIECE_LAYOUT_ENTRY = Object.freeze({
  narrowMax: 760,
  responsiveScaleMin: 0.62,
  responsiveScaleMinXs: 0.56,
  narrow: { legendOrient: "bottom", width: 250 },
  wide: { legendOrient: "right", width: 300 },
});

// Methodical inventory of chart containers present across HTML pages.
// Use this to track responsive layout coverage in CHART_LAYOUT_INVENTORY.
const CHART_CONTAINER_INVENTORY = Object.freeze([
  "leagueContinuityContextChart",
  "leagueSquadSizeContextChart",
  "lineoutPerfBreakdownAreaChart",
  "lineoutPerfBreakdownJumperChart",
  "lineoutPerfBreakdownNumbersChart",
  "lineoutPerfBreakdownPlayChart",
  "lineoutPerfBreakdownSeasonChart",
  "lineoutPerfBreakdownThrowerChart",
  "lineoutTrendAreaBarChart",
  "lineoutTrendAreaLineChart",
  "lineoutTrendJumperBarChart",
  "lineoutTrendJumperLineChart",
  "lineoutTrendNumbersBarChart",
  "lineoutTrendNumbersLineChart",
  "lineoutTrendPlayBarChart",
  "lineoutTrendPlayLineChart",
  "lineoutTrendThrowerBarChart",
  "lineoutTrendThrowerLineChart",
  "oppositionLineoutH2HChart",
  "oppositionResultsChart",
  "oppositionScrumH2HChart",
  "oppositionTeamSheetsChart",
  "playerStatsAppearancesChart",
  "playerStatsCaptainsChart",
  "playerStatsMotmChart",
  "playerStatsMotmUnitsChart",
  "playerStatsPointsChart",
  "playerStatsStartingCombinationsChart",
  "rzPointsChart",
  "rzSeasonalEntriesEfficiencyChart",
  "setPieceAttackingLineoutVolumeChart",
  "setPieceAttackingScrumVolumeChart",
  "setPiece1stLineoutChart",
  "setPiece1stScrumChart",
  "setPiece2ndLineoutChart",
  "setPiece2ndScrumChart",
  "squadContinuityTrendChart",
  "squadOverlapChart",
  "squadPositionCompositionChart",
  "squadResultsChart",
  "squadSizeTrendChart",
  "teamSheetsChart",
  "leagueResultsChart1",
  "leagueResultsChart2",
]);

// Centralized responsive layout inventory for chart-level structural tweaks.
// Rules are opt-in per chart container id and applied at render time.
//
// Supported profile fields:
// - legendOrient: 'bottom' | 'right' | ... (legend orient)
// - legendTitleOrient: 'top' | 'bottom' | 'left' | 'right' | ... (legend title orient)
// - facetColumns: number
// - facetHeaderLabels: boolean (show/hide facet headers)
// - concat: 'vertical' | 'horizontal'
// - width / height: root chart dimensions (number or Vega-Lite sizing object)
// - innerWidth / innerHeight: dimensions for faceted/repeated child spec (spec.spec)
// - spacing / padding / autosize: top-level layout values
// - specPath: override chart spec path for a given mode
// - panelSizing: per-panel width/height for concat charts
// - responsiveScaleMin / responsiveScaleMinXs: minimum scale thresholds used by applyResponsiveChartScale
//
// Supported entry-level fields:
// - narrowMax / wideMin: mode breakpoints
// - specPaths: { narrow, default, wide } for Python-generated chart variants
const CHART_LAYOUT_INVENTORY = {
  squadPositionCompositionChart: {
    narrowMax: 680,
    wideMin: 1000,
    narrow: {
      legendOrient: "bottom",
      facetColumns: 1,
      facetHeaderLabels: false,
    },
    wide: { legendOrient: "right", facetColumns: 2, innerHeight: { step: 25 } },
  },
  squadOverlapChart: {
    narrowMax: 680,
    wideMin: 1000,
    narrow: { legendOrient: "bottom", legendTitleOrient: "left" },
      innerWidth: 275,
    wide: { legendOrient: "right", width: 500 },
  },
  squadSizeTrendChart: {
    narrowMax: 680,
    wideMin: 1080,
    wide: { legendOrient: "right", innerWidth: 275 },
  },
  squadContinuityTrendChart: {
    narrowMax: 680,
      innerWidth: 400,
    narrow: { legendOrient: "bottom" },
    wide: { legendOrient: "right", innerWidth: 275 },
  },
  leagueSquadSizeContextChart: {
    narrowMax: 760,
    wideMin: 1000,
    narrow: {
      concat: "vertical",
      legendOrient: "bottom",
      panelSizing: {
        sharedWidthPadding: 20,
        vertical: {
          spacing: 10,
          panels: [
            { width: "shared", height: { step: 25 } },
            { width: "shared", height: 300 },
          ],
        },
      },
    },
    wide: {
      concat: "horizontal",
      legendOrient: "right",
      panelSizing: {
        horizontal: {
          spacing: 20,
          panels: [
            { width: 300, height: 300 },
            { width: { step: 60 }, height: 300 },
          ],
        },
      },
    },
  },
  leagueContinuityContextChart: {
    narrowMax: 760,
    wideMin: 1080,
    narrow: {
      concat: "vertical",
      legendOrient: "bottom",
      panelSizing: {
        sharedWidthPadding: 20,
        vertical: {
          spacing: 10,
          panels: [
            { width: "shared", height: { step: 25 } },
            { width: "shared", height: 300 },
          ],
        },
      },
    },
    wide: {
      concat: "horizontal",
      legendOrient: "right",
      panelSizing: {
        horizontal: {
          spacing: 20,
          panels: [
            { width: 300, height: 300 },
            { width: { step: 60 }, height: 300 },
          ],
        },
      },
    },
  },
  leagueResultsChart1: {
    narrowMax: 760,
    narrow: { legendOrient: "bottom" , width: { step: 42 }, height: { step: 32 } },
    wide: { legendOrient: "right" },
  },
  leagueResultsChart2: {
    narrowMax: 760,
    narrow: { legendOrient: "bottom", width: { step: 42 }, height: { step: 32 } },
    wide: { legendOrient: "right" },
  },
  scrumH2HChart: {
    narrowMax: 760,
    narrow: { legendOrient: "bottom" },
    wide: { legendOrient: "right" },
  },
  oppositionResultsChart: {
    narrowMax: 760,
    narrow: { legendOrient: "bottom", innerWidth: 275 },
    wide: { legendOrient: "right"},
  },
  squadResultsChart: {
    narrowMax: 760,
    narrow: {
      legendOrient: "bottom",
      innerWidth: 275,
      panelSizing: {
        vertical: {
          spacing: 18,
          panels: [{ width: 275 }, { width: 275 }],
        },
      },
    },
    wide: {
      legendOrient: "right",
      innerWidth: 400,
      panelSizing: {
        vertical: {
          spacing: 24,
          panels: [{ width: 400 }, { width: 400 }],
        },
      },
    },
  },
  oppositionLineoutH2HChart: {
    narrowMax: 760,
    narrow: { legendOrient: "bottom" },
    wide: { legendOrient: "right" },
  },
  oppositionScrumH2HChart: {
    narrowMax: 760,
    narrow: { legendOrient: "bottom" },
    wide: { legendOrient: "right" },
  },
  playerStatsAppearancesChart: {
    narrowMax: 760,
    wideMin: 1000,
    narrow: {
      legendOrient: "bottom-right",
      legendTitleOrient: "left",
      facetColumns: 1,
      facetHeaderLabels: false,
      width: 275,
    },
    wide: {
      legendOrient: "right",
      width: 500,
    },
  },
  playerStatsPointsChart: {
    narrowMax: 760,
    narrow: { legendOrient: "bottom-right", legendTitleOrient: "left", width: 275 },
    wide: { legendOrient: "right", width: 500 },
  },
  playerStatsCaptainsChart: {
    narrowMax: 760,
    narrow: { legendOrient: "bottom-right", legendTitleOrient: "left", width: 275 },
    wide: { legendOrient: "right", width: 500, height: { step: 20 } },
  },
  playerStatsMotmChart: {
    narrowMax: 760,
    narrow: { legendOrient: "bottom", legendTitleOrient: "left", width: 275 },
    wide: { legendOrient: "right", width: 500 },
  },
  playerStatsMotmUnitsChart: {
    narrowMax: 760,
    narrow: { legendOrient: "bottom", legendTitleOrient: "left" },
    wide: { legendOrient: "right", width: 500, height: { step: 50 } },
  },
  playerStatsStartingCombinationsChart: {
    narrowMax: 760,
    narrow: { legendOrient: "bottom", legendTitleOrient: "left", width: 250 },
    wide: { legendOrient: "right", width: 400 },
  },
  redZone1stChart: {
    narrowMax: 720,
    responsiveScaleMin: 0.62,
    responsiveScaleMinXs: 0.56,
    narrow: { legendOrient: "bottom" },
    wide: { legendOrient: "right" },
  },
  rzPointsChart: {
    narrowMax: 720,
    responsiveScaleMin: 0.62,
    responsiveScaleMinXs: 0.56,
    narrow: { legendOrient: "bottom", legendTitleOrient: "top" },
    wide: { legendOrient: "right", legendTitleOrient: "left", width: 600, height: 500 },
  },
  rzSeasonalEntriesEfficiencyChart: {
    narrowMax: 720,
    responsiveScaleMin: 0.64,
    responsiveScaleMinXs: 0.58,
    narrow: {
      legendOrient: "bottom",
      legendTitleOrient: "top",
      padding: { top: 8, right: 96, bottom: 8, left: 8 },
    },
    wide: {
      legendOrient: "right",
      legendTitleOrient: "left",
      width: { step: 50 },
      height: 360,
      padding: { top: 8, right: 96, bottom: 8, left: 8 },
    },
  },
  setPieceAttackingLineoutVolumeChart: {
    narrowMax: 760,
    responsiveScaleMin: 0.62,
    responsiveScaleMinXs: 0.56,
    narrow: { legendOrient: "bottom", legendTitleOrient: "top" },
    wide: { legendOrient: "right", legendTitleOrient: "top", width: 300, height: 300 },
  },
  setPieceAttackingScrumVolumeChart: {
    narrowMax: 760,
    responsiveScaleMin: 0.62,
    responsiveScaleMinXs: 0.56,
    narrow: { legendOrient: "bottom", legendTitleOrient: "top" },
    wide: { legendOrient: "right", legendTitleOrient: "top", width: 300, height: 300 },
  },
  setPieceLineoutChart: { ...SET_PIECE_LAYOUT_ENTRY },
  setPiece1stLineoutChart: { ...SET_PIECE_LAYOUT_ENTRY },
  setPiece2ndLineoutChart: { ...SET_PIECE_LAYOUT_ENTRY },
  setPieceScrumChart: { ...SET_PIECE_LAYOUT_ENTRY },
  setPiece1stScrumChart: { ...SET_PIECE_LAYOUT_ENTRY },
  setPiece2ndScrumChart: { ...SET_PIECE_LAYOUT_ENTRY },
  lineoutPerfBreakdownNumbersChart: {
    narrowMax: 760,
    responsiveScaleMin: 0.62,
    responsiveScaleMinXs: 0.56,
    narrow: { width: 280 },
    wide: { width: 250 },
  },
  lineoutPerfBreakdownAreaChart: {
    narrowMax: 760,
    responsiveScaleMin: 0.62,
    responsiveScaleMinXs: 0.56,
    narrow: { width: 280 },
    wide: { width: 460 },
  },
  lineoutPerfBreakdownJumperChart: {
    narrowMax: 760,
    responsiveScaleMin: 0.62,
    responsiveScaleMinXs: 0.56,
    narrow: { width: 350 },
    wide: { width: 460 },
  },
  lineoutPerfBreakdownThrowerChart: {
    narrowMax: 760,
    responsiveScaleMin: 0.62,
    responsiveScaleMinXs: 0.56,
    narrow: { width: 350 },
    wide: { width: 460 },
  },
  lineoutPerfBreakdownPlayChart: {
    narrowMax: 760,
    responsiveScaleMin: 0.62,
    responsiveScaleMinXs: 0.56,
    narrow: { width: 280 },
    wide: { width: 460 },
  },
  lineoutPerfBreakdownSeasonChart: {
    narrowMax: 760,
    responsiveScaleMin: 0.62,
    responsiveScaleMinXs: 0.56,
    narrow: { width: 280 },
    wide: { width: 500 },
  },
  lineoutTrendNumbersBarChart: {
    narrowMax: 760,
    responsiveScaleMin: 0.62,
    responsiveScaleMinXs: 0.56,
    narrow: { width: 280 },
    wide: { width: 320 },
  },
  lineoutTrendNumbersLineChart: {
    narrowMax: 760,
    responsiveScaleMin: 0.62,
    responsiveScaleMinXs: 0.56,
    narrow: { width: 280 },
    wide: { width: 320 },
  },
  lineoutTrendAreaBarChart: {
    narrowMax: 760,
    responsiveScaleMin: 0.62,
    responsiveScaleMinXs: 0.56,
    narrow: { width: 280 },
    wide: { width: 320 },
  },
  lineoutTrendAreaLineChart: {
    narrowMax: 760,
    responsiveScaleMin: 0.62,
    responsiveScaleMinXs: 0.56,
    narrow: { width: 280 },
    wide: { width: 320 },
  },
  lineoutTrendJumperBarChart: {
    narrowMax: 760,
    responsiveScaleMin: 0.62,
    responsiveScaleMinXs: 0.56,
    narrow: { width: 280 },
    wide: { width: 320 },
  },
  lineoutTrendJumperLineChart: {
    narrowMax: 760,
    responsiveScaleMin: 0.62,
    responsiveScaleMinXs: 0.56,
    narrow: { width: 280 },
    wide: { width: 320 },
  },
  lineoutTrendThrowerBarChart: {
    narrowMax: 760,
    responsiveScaleMin: 0.62,
    responsiveScaleMinXs: 0.56,
    narrow: { width: 280 },
    wide: { width: 320 },
  },
  lineoutTrendThrowerLineChart: {
    narrowMax: 760,
    responsiveScaleMin: 0.62,
    responsiveScaleMinXs: 0.56,
    narrow: { width: 280 },
    wide: { width: 320 },
  },
  lineoutTrendPlayBarChart: {
    narrowMax: 760,
    responsiveScaleMin: 0.62,
    responsiveScaleMinXs: 0.56,
    narrow: { width: 280 },
    wide: { width: 320 },
  },
  lineoutTrendPlayLineChart: {
    narrowMax: 760,
    responsiveScaleMin: 0.62,
    responsiveScaleMinXs: 0.56,
    narrow: { width: 280 },
    wide: { width: 320 },
  },
};

function getChartLayoutCoverage() {
  const configured = CHART_CONTAINER_INVENTORY.filter((id) =>
    Object.prototype.hasOwnProperty.call(CHART_LAYOUT_INVENTORY, id),
  );
  const missing = CHART_CONTAINER_INVENTORY.filter(
    (id) => !Object.prototype.hasOwnProperty.call(CHART_LAYOUT_INVENTORY, id),
  );
  return {
    total: CHART_CONTAINER_INVENTORY.length,
    configuredCount: configured.length,
    missingCount: missing.length,
    configured,
    missing,
  };
}

function attachChartSpecMetadata(spec, metadata = {}) {
  if (!spec || typeof spec !== "object") return spec;
  if (metadata.sourcePath) {
    Object.defineProperty(spec, "__sourcePath", {
      value: metadata.sourcePath,
      writable: true,
      configurable: true,
      enumerable: false,
    });
  }
  return spec;
}

function cloneChartSpec(spec) {
  const cloned = JSON.parse(JSON.stringify(spec));
  return attachChartSpecMetadata(cloned, { sourcePath: spec?.__sourcePath });
}

function resolveChartLayoutState(containerId, width) {
  if (!containerId || !Number.isFinite(width))
    return { entry: null, mode: null, profile: null };
  const entry = CHART_LAYOUT_INVENTORY[containerId] || null;
  if (!entry) return { entry: null, mode: null, profile: null };
  const narrowMax = Number.isFinite(entry.narrowMax) ? entry.narrowMax : 680;
  const wideMin = Number.isFinite(entry.wideMin) ? entry.wideMin : 1100;
  if (width <= narrowMax)
    return { entry, mode: "narrow", profile: entry.narrow || null };
  if (width >= wideMin)
    return { entry, mode: "wide", profile: entry.wide || null };

  // Width is between narrowMax and wideMin.
  // If no explicit default profile exists, choose the nearest available profile
  // so responsive overrides still apply in the breakpoint gap.
  if (entry.default) return { entry, mode: "default", profile: entry.default };

  const hasNarrow = !!entry.narrow;
  const hasWide = !!entry.wide;
  if (hasNarrow && hasWide) {
    const gapSpan = wideMin - narrowMax;
    const midpoint = gapSpan > 0 ? narrowMax + gapSpan / 2 : narrowMax;
    return width >= midpoint
      ? { entry, mode: "wide", profile: entry.wide }
      : { entry, mode: "narrow", profile: entry.narrow };
  }
  if (hasWide) return { entry, mode: "wide", profile: entry.wide };
  if (hasNarrow) return { entry, mode: "narrow", profile: entry.narrow };
  return { entry, mode: "default", profile: null };
}

function resolveChartLayoutProfile(containerId, width) {
  return resolveChartLayoutState(containerId, width).profile;
}

function getChartLayoutWidth(container) {
  if (!container) return Number(window?.innerWidth || 0) || 0;
  const direct = Number(container.clientWidth || 0);
  const chartSection = Number(
    container.closest(
      ".chart-section-content, .chart-section-block, .chart-panel-card",
    )?.clientWidth || 0,
  );
  const mainColumn = Number(
    container.closest(".squad-stats-main, .page-shell, .main-content")
      ?.clientWidth || 0,
  );
  const viewport = Number(window?.innerWidth || 0);
  return Math.max(
    direct,
    chartSection,
    mainColumn,
    viewport ? viewport * 0.75 : 0,
  );
}

function applyLegendOrientationDeep(spec, orient) {
  if (!spec || typeof spec !== "object" || !orient) return;
  const legendChannels = [
    "color",
    "fill",
    "stroke",
    "shape",
    "size",
    "opacity",
  ];
  if (spec.encoding && typeof spec.encoding === "object") {
    legendChannels.forEach((channel) => {
      const enc = spec.encoding[channel];
      if (!enc || enc.legend === null) return;
      enc.legend = { ...(enc.legend || {}), orient };
    });
  }
  ["layer", "hconcat", "vconcat", "concat"].forEach((key) => {
    const childSpecs = spec[key];
    if (Array.isArray(childSpecs))
      childSpecs.forEach((child) => applyLegendOrientationDeep(child, orient));
  });
  if (spec.spec) applyLegendOrientationDeep(spec.spec, orient);
}


function applyLegendTitleOrientDeep(spec, titleOrient) {
  if (!spec || typeof spec !== "object" || !titleOrient) return;
  const legendChannels = [
    "color",
    "fill",
    "stroke",
    "shape",
    "size",
    "opacity",
  ];
  if (spec.encoding && typeof spec.encoding === "object") {
    legendChannels.forEach((channel) => {
      const enc = spec.encoding[channel];
      if (!enc || enc.legend === null) return;
      enc.legend = { ...(enc.legend || {}), titleOrient };
    });
  }
  ["layer", "hconcat", "vconcat", "concat"].forEach((key) => {
    const childSpecs = spec[key];
    if (Array.isArray(childSpecs))
      childSpecs.forEach((child) =>
        applyLegendTitleOrientDeep(child, titleOrient),
      );
  });
  if (spec.spec) applyLegendTitleOrientDeep(spec.spec, titleOrient);
}

function applyFacetColumnsDeep(spec, columns) {
  if (
    !spec ||
    typeof spec !== "object" ||
    !Number.isFinite(columns) ||
    columns < 1
  )
    return;
  if (spec.facet && typeof spec.facet === "object") {
    // Vega-Lite ignores top-level `columns` when facet is declared as `{ column: {...} }`.
    // Normalize to wrapped facet syntax so `columns` takes effect.
    const facetDef = spec.facet;
    if (
      !Array.isArray(facetDef) &&
      facetDef.column &&
      !facetDef.row &&
      typeof facetDef.column === "object"
    ) {
      const wrappedFacet = { ...facetDef.column };
      if (
        Object.prototype.hasOwnProperty.call(facetDef, "title") &&
        !Object.prototype.hasOwnProperty.call(wrappedFacet, "title")
      ) {
        wrappedFacet.title = facetDef.title;
      }
      spec.facet = wrappedFacet;
    }
    spec.columns = Math.max(1, Math.floor(columns));
  }
  ["layer", "hconcat", "vconcat", "concat"].forEach((key) => {
    const childSpecs = spec[key];
    if (Array.isArray(childSpecs))
      childSpecs.forEach((child) => applyFacetColumnsDeep(child, columns));
  });
  if (spec.spec) applyFacetColumnsDeep(spec.spec, columns);
}

function applyFacetHeaderLabelsDeep(spec, showLabels) {
  if (!spec || typeof spec !== "object") return;
  if (spec.facet && typeof spec.facet === "object") {
    if (showLabels === false) {
      // log if removing facet header labels from a spec that has title text defined at the facet level, since this may be unintentional
      console.log(
        `Applying facet header label removal to spec${spec.__sourcePath ? ` from ${spec.__sourcePath}` : ""}${spec.facet.title ? " with facet title" : ""}`,
      );
      // spec.facet.header = { labels: false, title: null };
      console.log(spec.facet);
    } else if (
      typeof spec.facet.header === "object" &&
      spec.facet.header !== null &&
      spec.facet.header.labels === false
    ) {
      delete spec.facet.header;
    }
  }

  ["layer", "hconcat", "vconcat", "concat"].forEach((key) => {
    const childSpecs = spec[key];
    if (Array.isArray(childSpecs))
      childSpecs.forEach((child) =>
        applyFacetHeaderLabelsDeep(child, showLabels),
      );
  });
  if (spec.spec) applyFacetHeaderLabelsDeep(spec.spec, showLabels);
}

function applyConcatOrientationDeep(spec, orientation) {
  if (!spec || typeof spec !== "object" || !orientation) return;
  if (orientation === "vertical" && Array.isArray(spec.hconcat)) {
    spec.vconcat = spec.hconcat;
    delete spec.hconcat;
  } else if (orientation === "horizontal" && Array.isArray(spec.vconcat)) {
    spec.hconcat = spec.vconcat;
    delete spec.vconcat;
  }
  ["layer", "hconcat", "vconcat", "concat"].forEach((key) => {
    const childSpecs = spec[key];
    if (Array.isArray(childSpecs))
      childSpecs.forEach((child) =>
        applyConcatOrientationDeep(child, orientation),
      );
  });
  if (spec.spec) applyConcatOrientationDeep(spec.spec, orientation);
}

function applyConcatPanelSizing(spec, panelSizing, layoutWidth) {
  if (
    !spec ||
    typeof spec !== "object" ||
    !panelSizing ||
    typeof panelSizing !== "object"
  )
    return;
  const hasVertical = Array.isArray(spec.vconcat);
  const hasHorizontal = Array.isArray(spec.hconcat);
  const modeKey = hasVertical
    ? "vertical"
    : hasHorizontal
      ? "horizontal"
      : null;
  if (!modeKey) return;

  const modeSizing = panelSizing[modeKey];
  if (!modeSizing || !Array.isArray(modeSizing.panels)) return;

  const concatPanels = hasVertical ? spec.vconcat : spec.hconcat;
  const sharedWidthPadding = Number.isFinite(panelSizing.sharedWidthPadding)
    ? panelSizing.sharedWidthPadding
    : 24;
  const sharedWidth = Math.max(
    180,
    Math.floor((Number(layoutWidth || 0) || 0) - sharedWidthPadding),
  );
  const resolveDim = (value) => {
    if (value === "shared") return sharedWidth;
    return value;
  };

  modeSizing.panels.forEach((panelDims, index) => {
    const panelSpec = concatPanels[index];
    if (!panelSpec || typeof panelSpec !== "object" || !panelDims) return;
    if (panelDims.width !== undefined)
      panelSpec.width = resolveDim(panelDims.width);
    if (panelDims.height !== undefined)
      panelSpec.height = resolveDim(panelDims.height);
  });

  if (Number.isFinite(modeSizing.spacing)) spec.spacing = modeSizing.spacing;
}

function applyRootChartSizing(spec, profile) {
  if (
    !spec ||
    typeof spec !== "object" ||
    !profile ||
    typeof profile !== "object"
  )
    return;
  if (profile.width !== undefined) spec.width = profile.width;
  if (profile.height !== undefined) spec.height = profile.height;
  if (profile.spacing !== undefined) spec.spacing = profile.spacing;
  if (profile.padding !== undefined) spec.padding = profile.padding;
  if (profile.autosize !== undefined) spec.autosize = profile.autosize;
  if (spec.spec && typeof spec.spec === "object") {
    if (profile.innerWidth !== undefined) spec.spec.width = profile.innerWidth;
    if (profile.innerHeight !== undefined)
      spec.spec.height = profile.innerHeight;
  }
}

function applyChartLayoutProfile(spec, profile, layoutWidth) {
  if (!spec || !profile || typeof profile !== "object") return spec;
  applyRootChartSizing(spec, profile);
  if (profile.legendOrient)
    applyLegendOrientationDeep(spec, profile.legendOrient);
  if (profile.legendTitleOrient)
    applyLegendTitleOrientDeep(spec, profile.legendTitleOrient);
  if (Number.isFinite(profile.facetColumns))
    applyFacetColumnsDeep(spec, profile.facetColumns);
  if (profile.facetHeaderLabels !== undefined)
    applyFacetHeaderLabelsDeep(spec, !!profile.facetHeaderLabels);
  if (profile.concat) applyConcatOrientationDeep(spec, profile.concat);
  if (profile.panelSizing)
    applyConcatPanelSizing(spec, profile.panelSizing, layoutWidth);
  return spec;
}

function resetResponsiveChartScale(embed) {
  if (!embed) return;
  embed.style.transform = "none";
  embed.style.transformOrigin = "top left";
  embed.classList.remove("chart-responsive-scaled");
  const wrapper = embed.parentElement;
  if (wrapper) {
    wrapper.style.zoom = "";
    wrapper.style.width = "";
    wrapper.style.height = "";
  }
  const boundary = getResponsiveChartBoundary(embed);
  if (boundary) {
    boundary.style.overflowX = "";
    boundary.style.overflowY = "";
  }
}

function getResponsiveChartBoundary(embed) {
  if (!embed) return null;
  return (
    embed.closest(".player-stats-chart-container") ||
    embed.closest(".chart-host--intrinsic") ||
    embed.closest(".chart-host") ||
    embed.parentElement
  );
}

function getResponsiveChartMinScale(embed, boundary) {
  if (!window || typeof window.innerWidth !== "number") return null;
  const target =
    boundary?.closest?.("[data-chart-scale-min], [data-chart-scale-min-xs]") ||
    embed?.closest?.("[data-chart-scale-min], [data-chart-scale-min-xs]") ||
    null;
  if (!target) return null;

  const xsValue = Number.parseFloat(
    target.getAttribute("data-chart-scale-min-xs") || "",
  );
  const defaultValue = Number.parseFloat(
    target.getAttribute("data-chart-scale-min") || "",
  );
  const value = window.innerWidth <= 480 && Number.isFinite(xsValue)
    ? xsValue
    : defaultValue;
  return Number.isFinite(value) ? value : null;
}

function applyResponsiveChartScale(rootElement = document) {
  if (!rootElement || !window || typeof window.innerWidth !== "number") return;

  rootElement.querySelectorAll(".vega-embed").forEach((embed) => {
    const wrapper = embed.parentElement;
    embed.style.transform = "none";
    embed.style.transformOrigin = "top left";
    embed.classList.remove("chart-responsive-scaled");
    if (wrapper) {
      wrapper.style.zoom = "";
      wrapper.style.width = "";
      wrapper.style.height = "";
    }

    if (
      embed.closest(
        "#teamSheetsChart, .chart-embed-host--team-sheets, .team-sheets-chart-shell",
      )
    ) {
      resetResponsiveChartScale(embed);
      return;
    }

    if (embed.closest("#leagueResultsChart1, #leagueResultsChart2")) {
      // League Results uses dedicated page-level scaling in league-tables.js.
      return;
    }

    const boundary = getResponsiveChartBoundary(embed);
    if (!boundary) {
      resetResponsiveChartScale(embed);
      return;
    }

    const boundaryStyles = window.getComputedStyle(boundary);
    const boundaryPaddingLeft = Number.parseFloat(boundaryStyles.paddingLeft) || 0;
    const boundaryPaddingRight = Number.parseFloat(boundaryStyles.paddingRight) || 0;
    const boundaryContentWidth = Math.max(
      0,
      (boundary.clientWidth || 0) - boundaryPaddingLeft - boundaryPaddingRight,
    );
    const widthSafetyGutter = window.innerWidth <= 768 ? 6 : 2;
    const availableWidth = Math.max(
      0,
      Math.floor(
        Math.min(
          boundaryContentWidth,
          window.innerWidth || Number.MAX_SAFE_INTEGER,
        ) - widthSafetyGutter,
      ),
    );
    if (!availableWidth || window.innerWidth > 900) {
      resetResponsiveChartScale(embed);
      return;
    }

    const intrinsicWidth = Math.ceil(
      embed.scrollWidth || embed.getBoundingClientRect().width || 0,
    );
    const intrinsicHeight = Math.ceil(
      embed.scrollHeight || embed.getBoundingClientRect().height || 0,
    );
    if (!intrinsicWidth || intrinsicWidth <= availableWidth) {
      resetResponsiveChartScale(embed);
      return;
    }

    const rawScale = availableWidth / intrinsicWidth;
    const customMinScale = getResponsiveChartMinScale(embed, boundary);
    const minReadableScale = Number.isFinite(customMinScale)
      ? customMinScale
      : window.innerWidth <= 480
        ? 0.58
        : 0.68;
    if (rawScale < minReadableScale) {
      resetResponsiveChartScale(embed);
      return;
    }

    const scale = Math.min(1, rawScale);
    embed.classList.add("chart-responsive-scaled");

    if (wrapper) {
      wrapper.style.zoom = `${scale}`;
      wrapper.style.width = `${intrinsicWidth}px`;
      wrapper.style.height = `${intrinsicHeight}px`;
    }

    boundary.style.overflowX = "hidden";
    boundary.style.overflowY = "hidden";
  });
}

function bindResponsiveChartResizeHandler() {
  if (responsiveChartResizeBound) return;
  responsiveChartResizeBound = true;
  window.addEventListener("resize", () => applyResponsiveChartScale(document));
}

function getCurrentSeasonLabel() {
  const now = new Date();
  const year = now.getFullYear();
  const month = now.getMonth() + 1;
  const startYear = month >= 7 ? year : year - 1;
  const endSuffix = String((startYear + 1) % 100).padStart(2, "0");
  return `${startYear}/${endSuffix}`;
}

async function loadAvailableSeasons() {
  try {
    const response = await fetch("data/league_tables.json");
    if (!response.ok) {
      console.warn(
        `Failed to fetch league_tables.json (${response.status}), using default seasons`,
      );
      return;
    }
    const data = await response.json();
    if (
      data.seasons &&
      Array.isArray(data.seasons) &&
      data.seasons.length > 0
    ) {
      availableSeasons = data.seasons;
    }
  } catch (err) {
    console.error(
      "Failed to load seasons from league_tables.json:",
      err.message,
    );
  }
}

function normalizeSeasonLabel(value) {
  if (!value) return null;
  const season = String(value).trim().replace("-", "/");
  const match = season.match(/^(\d{4})\/(\d{2}|\d{4})$/);
  if (!match) return null;
  const startYear = match[1];
  const endPart = match[2];
  const endSuffix = endPart.length === 4 ? endPart.slice(-2) : endPart;
  return `${startYear}/${endSuffix}`;
}

function getSortedSquadStatsSeasons(dataBySeason) {
  const seasons = Object.keys(dataBySeason || {});
  if (seasons.length === 0) return [];
  return seasons.sort((a, b) => {
    const startA = parseInt(String(a).split("/")[0], 10);
    const startB = parseInt(String(b).split("/")[0], 10);
    if (!Number.isFinite(startA) || !Number.isFinite(startB))
      return String(b).localeCompare(String(a));
    return startB - startA;
  });
}

function getAllowedGameTypes(mode) {
  if (mode === "League + Cup") return new Set(["League", "Cup"]);
  if (mode === "League only") return new Set(["League"]);
  return null;
}

function createGameLink(gameId) {
  if (!gameId) return null;
  return `match-info.html?game=${encodeURIComponent(String(gameId || "").trim())}`;
}

function createPlayerLink(playerName) {
  if (!playerName) return null;
  return `player-profile.html?player=${encodeURIComponent(String(playerName || "").trim())}`;
}

function pinVegaActionsInElement(rootElement) {
  if (!rootElement) return;
  bindResponsiveChartResizeHandler();
  const run = () => {
    rootElement.querySelectorAll(".vega-embed").forEach((embed) => {
      embed.style.display = "block";
      embed.style.position = "relative";
      const details = embed.querySelector(
        'details[title="Click to view actions"], details',
      );
      if (!details) return;
      details.style.position = "absolute";
      details.style.top = "8px";
      details.style.right = "8px";
      details.style.left = "auto";
      details.style.margin = "0";
      details.style.float = "none";
      details.style.zIndex = "10";
      const actions = details.querySelector(".vega-actions");
      if (actions) {
        actions.style.position = "absolute";
        actions.style.top = "100%";
        actions.style.right = "0";
        actions.style.left = "auto";
        actions.style.zIndex = "11";
      }
    });

    applyResponsiveChartScale(rootElement);
  };
  run();
  [50, 150, 400, 900].forEach((delay) => window.setTimeout(run, delay));
}

async function loadChartSpec(path) {
  if (chartSpecCache.has(path)) return chartSpecCache.get(path);
  const separator = path.includes("?") ? "&" : "?";
  const requestPath = `${path}${separator}v=${encodeURIComponent(chartSpecRequestVersion)}`;
  const response = await fetch(requestPath, { cache: "no-store" });
  if (!response.ok)
    throw new Error(`Failed to fetch ${path} (${response.status})`);
  const spec = attachChartSpecMetadata(await response.json(), {
    sourcePath: path,
  });
  chartSpecCache.set(path, spec);
  return spec;
}

async function renderChartSpecFromPath(containerId, path, emptyMessage, options = {}) {
  const container = document.getElementById(containerId);
  if (!container) return null;
  try {
    const spec = await loadChartSpec(path);
    return await embedChartSpec(container, spec, {
      ...options,
      containerId,
      emptyMessage,
    });
  } catch (error) {
    console.error(`Unable to render chart from ${path}:`, error);
    container.innerHTML = `<div class="text-center text-muted py-4">${emptyMessage}</div>`;
    return null;
  }
}

async function renderSplitSetPiecePanelsFromSingleSpec(path, panelConfigs) {
  let baseSpec = null;
  try {
    baseSpec = await loadChartSpec(path);
  } catch (error) {
    console.error(`Unable to load shared chart spec from ${path}:`, error);
    panelConfigs.forEach(({ containerId, emptyMessage }) => {
      const container = document.getElementById(containerId);
      if (container) {
        container.innerHTML = `<div class="text-center text-muted py-4">${emptyMessage}</div>`;
      }
    });
    return;
  }

  await Promise.all(panelConfigs.map(async ({ containerId, squad, emptyMessage }) => {
    const container = document.getElementById(containerId);
    if (!container) return;

    try {
      const spec = cloneChartSpec(baseSpec);
      const view = await embedChartSpec(container, spec, { containerId, emptyMessage });
      if (view) {
        view.signal("spSquadParam", squad);
        await view.runAsync();
      }
    } catch (error) {
      console.error(`Unable to render split set-piece panel for ${containerId}:`, error);
      container.innerHTML = `<div class="text-center text-muted py-4">${emptyMessage}</div>`;
    }
  }));
}

function filterChartSpecDataset(spec, predicate) {
  const clonedSpec = cloneChartSpec(spec);
  const filteredRows = [];

  if (clonedSpec.datasets) {
    Object.keys(clonedSpec.datasets).forEach((key) => {
      const rows = clonedSpec.datasets[key];
      if (Array.isArray(rows)) {
        const filtered = rows.filter(predicate);
        clonedSpec.datasets[key] = filtered;
        filteredRows.push(...filtered);
      }
    });
  }
  if (clonedSpec.data && Array.isArray(clonedSpec.data.values)) {
    const filtered = clonedSpec.data.values.filter(predicate);
    clonedSpec.data.values = filtered;
    filteredRows.push(...filtered);
  }

  // Filter color scale to only include values present in filtered data
  if (
    filteredRows.length > 0 &&
    clonedSpec.encoding &&
    clonedSpec.encoding.color &&
    clonedSpec.encoding.color.scale
  ) {
    const colorScale = clonedSpec.encoding.color.scale;
    if (
      colorScale.domain &&
      colorScale.range &&
      colorScale.domain.length === colorScale.range.length
    ) {
      const colorField = clonedSpec.encoding.color.field
        ? clonedSpec.encoding.color.field.split(":")[0]
        : null;
      if (colorField) {
        const uniqueColorValues = new Set();
        filteredRows.forEach((row) => {
          const value = row[colorField];
          if (value !== undefined && value !== null) {
            uniqueColorValues.add(String(value));
          }
        });

        if (
          uniqueColorValues.size > 0 &&
          uniqueColorValues.size < colorScale.domain.length
        ) {
          const valuesToIndices = new Map();
          colorScale.domain.forEach((val, idx) => {
            valuesToIndices.set(String(val), idx);
          });

          const filteredDomain = [];
          const filteredRange = [];
          colorScale.domain.forEach((val, idx) => {
            if (uniqueColorValues.has(String(val))) {
              filteredDomain.push(val);
              filteredRange.push(colorScale.range[idx]);
            }
          });

          colorScale.domain = filteredDomain;
          colorScale.range = filteredRange;
        }
      }
    }
  }

  return clonedSpec;
}

function collectChartDatasetNames(spec, datasetNames = new Set()) {
  if (!spec || typeof spec !== "object") return datasetNames;
  if (spec.data && typeof spec.data.name === "string")
    datasetNames.add(spec.data.name);
  ["layer", "hconcat", "vconcat", "concat"].forEach((key) => {
    const childSpecs = spec[key];
    if (Array.isArray(childSpecs))
      childSpecs.forEach((child) =>
        collectChartDatasetNames(child, datasetNames),
      );
  });
  if (spec.spec) collectChartDatasetNames(spec.spec, datasetNames);
  return datasetNames;
}

function filterNamedDatasetsInSpec(spec, datasetNames, predicate) {
  if (!spec || typeof spec !== "object") return spec;
  if (spec.datasets) {
    datasetNames.forEach((name) => {
      const rows = spec.datasets[name];
      if (Array.isArray(rows)) spec.datasets[name] = rows.filter(predicate);
    });
  }
  return spec;
}

function filterLeagueContextCombinedSpec(
  spec,
  comparisonPredicate,
  trendPredicate,
) {
  const clonedSpec = cloneChartSpec(spec);
  const combinedCharts = Array.isArray(clonedSpec.hconcat)
    ? clonedSpec.hconcat
    : null;
  if (!combinedCharts || combinedCharts.length < 2) {
    return filterChartSpecDataset(clonedSpec, comparisonPredicate);
  }
  const comparisonDatasetNames = collectChartDatasetNames(combinedCharts[0]);
  const trendDatasetNames = collectChartDatasetNames(combinedCharts[1]);
  filterNamedDatasetsInSpec(
    clonedSpec,
    comparisonDatasetNames,
    comparisonPredicate,
  );
  filterNamedDatasetsInSpec(clonedSpec, trendDatasetNames, trendPredicate);
  return clonedSpec;
}

function chartSpecHasRows(spec) {
  if (!spec) return false;
  if (spec.datasets)
    return Object.values(spec.datasets).some(
      (rows) => Array.isArray(rows) && rows.length > 0,
    );
  if (spec.data && Array.isArray(spec.data.values))
    return spec.data.values.length > 0;
  return true;
}

function stripTitlesDeep(spec) {
  if (!spec || typeof spec !== "object") return;
  delete spec.title;
  ["layer", "hconcat", "vconcat", "concat"].forEach((key) => {
    const childSpecs = spec[key];
    if (Array.isArray(childSpecs))
      childSpecs.forEach((child) => stripTitlesDeep(child));
  });
  if (spec.spec) stripTitlesDeep(spec.spec);
}

function prepareChartSpecForEmbed(spec, options = {}) {
  const processedSpec = cloneChartSpec(spec);
  if (options.hideTitle !== false) {
    stripTitlesDeep(processedSpec);
    if (
      options.containerId === "leagueSquadSizeContextChart" ||
      options.containerId === "leagueContinuityContextChart"
    ) {
      processedSpec.padding = { top: 0, right: 8, bottom: 0, left: 8 };
    }
  }
  const profile = resolveChartLayoutProfile(
    options.containerId,
    Number(options.containerWidth || 0),
  );
  if (profile)
    applyChartLayoutProfile(
      processedSpec,
      profile,
      Number(options.containerWidth || 0),
    );
  return processedSpec;
}

function resolveChartVariantPath(
  containerId,
  containerWidth,
  fallbackSourcePath = null,
) {
  const { entry, mode, profile } = resolveChartLayoutState(
    containerId,
    containerWidth,
  );
  if (!entry) return null;
  if (profile?.specPath) return profile.specPath;
  if (entry.specPaths && typeof entry.specPaths === "object") {
    return (
      entry.specPaths[mode] ||
      entry.specPaths.default ||
      fallbackSourcePath ||
      null
    );
  }
  return fallbackSourcePath || null;
}

function shouldDisableVegaTooltips() {
  if (typeof window === "undefined") return false;
  const coarsePointer =
    typeof window.matchMedia === "function" &&
    window.matchMedia("(hover: none), (pointer: coarse)").matches;
  const narrowViewport = Number(window.innerWidth || 0) <= 900;
  return coarsePointer || narrowViewport;
}

function applyChartSpecCustomizer(spec, options = {}) {
  const customizer =
    typeof options.specCustomizer === "function"
      ? options.specCustomizer
      : typeof options.customizeSpec === "function"
        ? options.customizeSpec
        : null;
  if (!customizer) return spec;
  try {
    const customResult = customizer(cloneChartSpec(spec), {
      containerId: options.containerId || null,
      layoutContainerId: options.layoutContainerId || options.containerId || null,
      sourcePath: options.sourcePath || spec?.__sourcePath || null,
      customizerData: options.specCustomizerData,
    });
    if (customResult && typeof customResult === "object") return customResult;
  } catch (error) {
    console.error("Chart spec customization failed:", error);
  }
  return spec;
}

async function embedChartSpec(containerOrId, spec, options = {}) {
  const container =
    typeof containerOrId === "string"
      ? document.getElementById(containerOrId)
      : containerOrId;
  if (!container) return null;

  const containerId = options.containerId || container.id || null;
  const layoutContainerId = options.layoutContainerId || containerId;
  const layoutWidth = getChartLayoutWidth(container);
  const layoutState = resolveChartLayoutState(layoutContainerId, layoutWidth);
  const emptyMessage = options.emptyMessage || "No chart data available.";
  const containerClasses = []
    .concat(options.containerClasses || [])
    .filter(Boolean);

  if (containerClasses.length) {
    container.classList.add(...containerClasses);
  }

  if (Number.isFinite(options.responsiveScaleMin)) {
    container.setAttribute(
      "data-chart-scale-min",
      String(options.responsiveScaleMin),
    );
  }
  if (Number.isFinite(options.responsiveScaleMinXs)) {
    container.setAttribute(
      "data-chart-scale-min-xs",
      String(options.responsiveScaleMinXs),
    );
  }

  if (!Number.isFinite(options.responsiveScaleMin)) {
    const inventoryScaleMin = Number.isFinite(layoutState?.profile?.responsiveScaleMin)
      ? layoutState.profile.responsiveScaleMin
      : layoutState?.entry?.responsiveScaleMin;
    if (Number.isFinite(inventoryScaleMin)) {
      container.setAttribute("data-chart-scale-min", String(inventoryScaleMin));
    }
  }

  if (!Number.isFinite(options.responsiveScaleMinXs)) {
    const inventoryScaleMinXs = Number.isFinite(layoutState?.profile?.responsiveScaleMinXs)
      ? layoutState.profile.responsiveScaleMinXs
      : layoutState?.entry?.responsiveScaleMinXs;
    if (Number.isFinite(inventoryScaleMinXs)) {
      container.setAttribute(
        "data-chart-scale-min-xs",
        String(inventoryScaleMinXs),
      );
    }
  }

  if (!spec || !chartSpecHasRows(spec)) {
    container.innerHTML = `<div class="text-center text-muted py-4">${emptyMessage}</div>`;
    return null;
  }

  // Preserve the current height before clearing to prevent layout collapse
  // during async re-render, which would cause the page to jump to the next section.
  const _prevHeight = container.offsetHeight;
  if (_prevHeight > 0) container.style.minHeight = `${_prevHeight}px`;

  container.innerHTML = "";
  const embedHost = document.createElement("div");
  embedHost.className = "chart-embed-host";
  const embedHostClasses = []
    .concat(options.embedHostClasses || [])
    .filter(Boolean);
  if (containerId === "teamSheetsChart")
    embedHost.classList.add("chart-embed-host--team-sheets");
  if (embedHostClasses.length) embedHost.classList.add(...embedHostClasses);
  container.appendChild(embedHost);

  const sourcePath = options.sourcePath || spec?.__sourcePath || null;
  const variantPath = resolveChartVariantPath(
    layoutContainerId,
    layoutWidth,
    sourcePath,
  );
  const variantSpec =
    variantPath && variantPath !== sourcePath
      ? await loadChartSpec(variantPath)
      : spec;
  const customizedSpec = applyChartSpecCustomizer(variantSpec, {
    ...options,
    containerId: layoutContainerId,
    layoutContainerId,
    sourcePath: variantPath || sourcePath,
  });
  const chartSpec = prepareChartSpecForEmbed(customizedSpec, {
    ...options,
    containerId: layoutContainerId,
    containerWidth: layoutWidth,
  });

  const embedOptions = {
    actions:
      options.actions !== undefined ? options.actions : VEGA_EMBED_ACTIONS,
    renderer: "svg",
    tooltip: shouldDisableVegaTooltips() ? false : true,
  };

  const result = await vegaEmbed(embedHost, chartSpec, embedOptions);

  container.style.minHeight = "";
  pinVegaActionsInElement(container);
  return result?.view || null;
}

function renderStaticSpecChart(containerId, spec, emptyMessage, options = {}) {
  const container = document.getElementById(containerId);
  if (!container) return;
  embedChartSpec(container, spec, {
    ...options,
    containerId,
    emptyMessage,
  }).catch((error) => {
    console.error(`Error rendering ${containerId}:`, error);
    container.innerHTML =
      '<div class="text-center text-danger py-4">Unable to render chart.</div>';
  });
}

function rebuildBootstrapSelect(select, options = {}) {
  if (
    !select ||
    !window.jQuery ||
    !window.jQuery.fn ||
    !window.jQuery.fn.selectpicker
  ) {
    return false;
  }

  const $select = window.jQuery(select);
  const currentValue = select.multiple
    ? Array.from(select.selectedOptions || []).map((option) => option.value)
    : select.value;

  if ($select.data("selectpicker")) {
    $select.selectpicker("destroy");
  }

  $select.selectpicker(options);

  if (select.multiple) {
    $select.selectpicker(
      "val",
      Array.isArray(currentValue) ? currentValue : [],
    );
  } else if (
    currentValue !== undefined &&
    currentValue !== null &&
    currentValue !== ""
  ) {
    $select.selectpicker("val", currentValue);
  }

  return true;
}

function toLeagueSeasonFormat(season) {
  if (!season || !season.includes("/")) return season;
  const [startYear, endShort] = String(season).split("/");
  return `${startYear}-20${endShort}`;
}


function initialiseAnalysisRail(options = {}) {
  const {
    railId,
    layoutSelector = ".squad-stats-layout",
    sectionSelector = ".analysis-section[id]",
    initialHashDelay = 80,
  } = options;

  const rail = railId
    ? document.getElementById(railId)
    : document.querySelector(`${layoutSelector} .analysis-rail`);
  if (!rail || rail.__analysisRailInitialised) return false;

  const layout = rail.closest(layoutSelector) || rail.closest(".squad-stats-layout");
  if (!layout) return false;

  const placeholder = document.createElement("div");
  placeholder.className = "analysis-rail-placeholder";
  rail.insertAdjacentElement("afterend", placeholder);

  const links = rail.querySelectorAll('.rail-link[href^="#"]');
  if (!links.length) return false;

  const pinState = {
    triggerScrollY: 0,
    hysteresis: 8,
  };

  const updateActive = (sectionId) => {
    rail.querySelectorAll(".rail-link").forEach((link) => {
      const isMatch = link.getAttribute("href") === `#${sectionId}`;
      link.classList.toggle("active", isMatch);
      if (isMatch) link.setAttribute("aria-current", "true");
      else link.removeAttribute("aria-current");
    });
  };

  const updateActiveOnScroll = () => {
    const sections = Array.from(layout.querySelectorAll(sectionSelector)).filter(
      (section) => section.getClientRects().length > 0,
    );
    if (!sections.length) return;

    let currentSection = sections[0]?.id;
    for (const section of sections) {
      const rect = section.getBoundingClientRect();
      if (rect.top < window.innerHeight / 2) {
        currentSection = section.id;
      }
    }

    if (currentSection) updateActive(currentSection);
  };

  const updatePinnedState = () => {
    const triggerScrollY = Number(pinState.triggerScrollY ?? 0);
    const hysteresis = Number(pinState.hysteresis ?? 0);
    const isPinned = rail.classList.contains("is-pinned");
    const scrollY = window.scrollY;
    const shouldPin = isPinned
      ? scrollY >= triggerScrollY - hysteresis
      : scrollY >= triggerScrollY + hysteresis;

    if (!shouldPin) {
      rail.classList.remove("is-pinned");
      rail.style.removeProperty("--analysis-rail-fixed-left");
      rail.style.removeProperty("--analysis-rail-fixed-width");
      placeholder.style.display = "none";
      placeholder.style.height = "0px";
      return;
    }

    const layoutRect = layout.getBoundingClientRect();
    const viewportPadding = 8;
    const left = Math.max(viewportPadding, layoutRect.left);
    const available = window.innerWidth - viewportPadding * 2;
    const width = Math.max(220, Math.min(layoutRect.width, available));

    rail.classList.add("is-pinned");
    rail.style.setProperty("--analysis-rail-fixed-left", `${left}px`);
    rail.style.setProperty("--analysis-rail-fixed-width", `${width}px`);
    placeholder.style.display = "block";
    placeholder.style.height = `${Math.ceil(rail.offsetHeight)}px`;
  };

  const recalculatePinTrigger = () => {
    const navOffset =
      parseFloat(
        getComputedStyle(document.documentElement).getPropertyValue(
          "--nav-offset",
        ),
      ) || 74;
    const pinTop = navOffset + 7;
    const wasPinned = rail.classList.contains("is-pinned");

    if (wasPinned) {
      rail.classList.remove("is-pinned");
      rail.style.removeProperty("--analysis-rail-fixed-left");
      rail.style.removeProperty("--analysis-rail-fixed-width");
      placeholder.style.display = "none";
      placeholder.style.height = "0px";
    }

    const naturalTop = rail.getBoundingClientRect().top + window.scrollY;
    pinState.triggerScrollY = Math.max(0, naturalTop - pinTop);

    if (wasPinned) updatePinnedState();
  };

  links.forEach((link) => {
    link.addEventListener("click", (event) => {
      const targetId = link.getAttribute("href")?.replace("#", "");
      const targetSection = targetId ? document.getElementById(targetId) : null;
      if (!targetSection) return;
      event.preventDefault();
      targetSection.scrollIntoView({ behavior: "smooth", block: "start" });
      if (window.location.hash !== `#${targetId}`) {
        window.history.replaceState(null, "", `#${targetId}`);
      }
      window.setTimeout(() => {
        recalculatePinTrigger();
        updatePinnedState();
        updateActiveOnScroll();
      }, 120);
    });
  });

  const navOffset =
    parseFloat(
      getComputedStyle(document.documentElement).getPropertyValue(
        "--nav-offset",
      ),
    ) || 74;

  const refreshRail = () => {
    updatePinnedState();
    updateActiveOnScroll();
  };

  let refreshRaf = null;
  const scheduleRefresh = () => {
    if (refreshRaf !== null) return;
    refreshRaf = window.requestAnimationFrame(() => {
      refreshRaf = null;
      refreshRail();
    });
  };

  let recalcRaf = null;
  const scheduleRecalculate = () => {
    if (recalcRaf !== null) return;
    recalcRaf = window.requestAnimationFrame(() => {
      recalcRaf = null;
      recalculatePinTrigger();
      refreshRail();
    });
  };

  window.addEventListener("scroll", scheduleRefresh, { passive: true });
  window.addEventListener("resize", scheduleRecalculate);
  window.addEventListener("hashchange", scheduleRecalculate);

  recalculatePinTrigger();
  refreshRail();
  window.setTimeout(scheduleRecalculate, 250);
  window.setTimeout(scheduleRecalculate, 900);

  const initialHash = String(window.location.hash || "").replace("#", "");
  if (initialHash) {
    const targetSection = document.getElementById(initialHash);
    if (targetSection) {
      window.setTimeout(() => {
        targetSection.scrollIntoView({ behavior: "smooth", block: "start" });
        recalculatePinTrigger();
        refreshRail();
      }, initialHashDelay);
    }
  }

  rail.__analysisRailInitialised = true;
  return true;
}

// ============================================================
// Captain Cards - Unified Shared Functions
// ============================================================

/**
 * Escape HTML special characters to prevent XSS.
 * @param {*} value - The value to escape
 * @returns {string} Escaped HTML-safe string
 */
function escapeHtml(value) {
  if (value === null || value === undefined) return '';
  const div = document.createElement('div');
  div.textContent = String(value);
  return div.innerHTML;
}

// ============================================================
// Shared UI Helpers - Segment Controls, Chips, and Steppers
// ============================================================

const sharedUi = window.sharedUi || (window.sharedUi = {});

sharedUi.resolveElement = function resolveElement(elementOrId) {
  if (!elementOrId) return null;
  if (typeof elementOrId === 'string') return document.getElementById(elementOrId);
  return elementOrId;
};

sharedUi.syncSegmentButtons = function syncSegmentButtons(segmentOrId, value, options = {}) {
  const segment = sharedUi.resolveElement(segmentOrId);
  if (!segment) return;

  const {
    multi = Array.isArray(value),
    activeClass = 'is-active',
    valueAttribute = 'data-value',
    buttonSelector = '.squad-filter-segment-btn',
  } = options;

  const selectedValues = multi
    ? new Set((Array.isArray(value) ? value : []).map((v) => String(v)))
    : new Set([String(value ?? '')]);

  segment.querySelectorAll(buttonSelector).forEach((button) => {
    const buttonValue = String(button.getAttribute(valueAttribute) ?? button.dataset.value ?? '');
    button.classList.toggle(activeClass, selectedValues.has(buttonValue));
  });
};

sharedUi.bindSegmentToSelect = function bindSegmentToSelect(config = {}) {
  const segment = sharedUi.resolveElement(config.segment);
  const select = sharedUi.resolveElement(config.select);
  if (!segment || !select) return null;

  const {
    multi = !!select.multiple,
    activeClass = 'is-active',
    valueAttribute = 'data-value',
    buttonSelector = '.squad-filter-segment-btn',
    dispatchChange = true,
    requireOne = false,
    onSync,
  } = config;

  const getSelectValue = () => {
    if (multi) return Array.from(select.selectedOptions).map((option) => String(option.value));
    return String(select.value ?? '');
  };

  const setSelectValue = (nextValue) => {
    if (multi) {
      const nextSet = new Set((Array.isArray(nextValue) ? nextValue : []).map((v) => String(v)));
      Array.from(select.options).forEach((option) => {
        option.selected = nextSet.has(String(option.value));
      });
    } else {
      select.value = String(nextValue ?? '');
    }
  };

  const syncFromSelect = () => {
    const value = getSelectValue();
    sharedUi.syncSegmentButtons(segment, value, { multi, activeClass, valueAttribute, buttonSelector });
    if (typeof onSync === 'function') onSync(value, { segment, select });
    return value;
  };

  const segmentBindKey = `__sharedSegmentBind_${select.id || 'select'}`;
  if (!segment[segmentBindKey]) {
    segment[segmentBindKey] = true;
    segment.addEventListener('click', (event) => {
      const button = event.target.closest(buttonSelector);
      if (!button || !segment.contains(button)) return;

      const clickedValue = String(button.getAttribute(valueAttribute) ?? button.dataset.value ?? '');
      if (!clickedValue) return;

      if (multi) {
        const nextValues = new Set(getSelectValue());
        if (nextValues.has(clickedValue)) nextValues.delete(clickedValue);
        else nextValues.add(clickedValue);
        if (requireOne && nextValues.size === 0) nextValues.add(clickedValue);
        setSelectValue(Array.from(nextValues));
      } else {
        setSelectValue(clickedValue);
      }

      syncFromSelect();
      if (dispatchChange) select.dispatchEvent(new Event('change', { bubbles: true }));
    });
  }

  const selectBindKey = `__sharedSegmentSelectBind_${segment.id || 'segment'}`;
  if (!select[selectBindKey]) {
    select[selectBindKey] = true;
    select.addEventListener('change', syncFromSelect);
  }

  syncFromSelect();
  return { segment, select, sync: syncFromSelect };
};

sharedUi.renderOffcanvasFilterChips = function renderOffcanvasFilterChips(config = {}) {
  const host = sharedUi.resolveElement(config.host);
  if (!host) return '';

  const offcanvasId = String(config.offcanvasId || '').trim();
  const chipClass = String(config.chipClass || 'squad-stats-filter-chip squad-stats-filter-chip-btn').trim();
  const chips = Array.isArray(config.chips) ? config.chips : [];

  const html = chips
    .map((chip) => {
      const label = String(chip?.label || '').trim();
      const value = chip?.value === undefined || chip?.value === null ? '' : String(chip.value);
      const mobileValue = chip?.mobileValue === undefined || chip?.mobileValue === null
        ? value
        : String(chip.mobileValue);
      const clickable = chip?.clickable !== false && !!offcanvasId;
      const labelHtml = `<strong>${escapeHtml(label)}</strong>`;
      const valueHtml = mobileValue !== value
        ? `<span class="d-none d-md-inline">${escapeHtml(value)}</span><span class="d-inline d-md-none">${escapeHtml(mobileValue)}</span>`
        : escapeHtml(value);
      const contentHtml = `${labelHtml}${valueHtml ? ` ${valueHtml}` : ''}`;

      if (!clickable) return `<span class="squad-stats-filter-chip">${contentHtml}</span>`;

      return `<button type="button" class="${chipClass}" data-bs-toggle="offcanvas" data-bs-target="#${escapeHtml(offcanvasId)}" aria-controls="${escapeHtml(offcanvasId)}">${contentHtml}</button>`;
    })
    .join('');

  host.innerHTML = html;
  return html;
};

sharedUi.attachSeasonStepper = function attachSeasonStepper(config = {}) {
  const select = sharedUi.resolveElement(config.select);
  const label = sharedUi.resolveElement(config.label);
  const prevButton = sharedUi.resolveElement(config.prevButton || config.prev);
  const nextButton = sharedUi.resolveElement(config.nextButton || config.next);
  if (!select || !label) return null;

  const {
    prevDelta = 1,
    nextDelta = -1,
    dispatchChange = true,
    formatLabel,
    onChange,
  } = config;

  const update = () => {
    const index = select.selectedIndex;
    const values = Array.from(select.options).map((option) => String(option.value));
    const selectedValue = index >= 0 ? values[index] : String(select.value || '');

    label.textContent = typeof formatLabel === 'function'
      ? String(formatLabel(selectedValue, select) || '')
      : selectedValue;

    if (prevButton) {
      const prevIndex = index + prevDelta;
      prevButton.disabled = prevIndex < 0 || prevIndex >= values.length;
    }
    if (nextButton) {
      const nextIndex = index + nextDelta;
      nextButton.disabled = nextIndex < 0 || nextIndex >= values.length;
    }
    if (typeof onChange === 'function') onChange(selectedValue, { select, index });
  };

  const moveBy = (delta) => {
    const values = Array.from(select.options).map((option) => String(option.value));
    const nextIndex = select.selectedIndex + delta;
    if (nextIndex < 0 || nextIndex >= values.length) return;
    select.value = values[nextIndex];
    update();
    if (dispatchChange) select.dispatchEvent(new Event('change', { bubbles: true }));
  };

  const prevBindKey = `__sharedSeasonPrev_${select.id || 'select'}`;
  if (prevButton && !prevButton[prevBindKey]) {
    prevButton[prevBindKey] = true;
    prevButton.addEventListener('click', () => moveBy(prevDelta));
  }

  const nextBindKey = `__sharedSeasonNext_${select.id || 'select'}`;
  if (nextButton && !nextButton[nextBindKey]) {
    nextButton[nextBindKey] = true;
    nextButton.addEventListener('click', () => moveBy(nextDelta));
  }

  const selectBindKey = `__sharedSeasonSelect_${label.id || 'label'}`;
  if (!select[selectBindKey]) {
    select[selectBindKey] = true;
    select.addEventListener('change', update);
  }

  update();
  return { select, label, prevButton, nextButton, refresh: update };
};

/**
 * Determine the headshot background class based on player's squad.
 * @param {Object} profile - Player profile object
 * @returns {string} CSS class for background styling
 */
function headshotBackgroundClass(profile) {
  const squad = String(profile?.squad || '').trim().toLowerCase();
  return squad === '2nd'
    ? 'player-profile-headshot-wrap-2nd'
    : 'player-profile-headshot-wrap-1st';
}

/**
 * Create avatar markup with image or initials fallback.
 * @param {Object} profile - Player profile object
 * @returns {string} HTML markup for avatar
 */
function createAvatarMarkup(profile) {
  const name = escapeHtml(profile?.name || 'Player');
  const photoUrl = String(profile?.photo_url || '').trim();

  if (photoUrl) {
    return `<img src="${escapeHtml(photoUrl)}" alt="${name}" class="player-profile-avatar" loading="lazy">`;
  }

  return '<div class="player-profile-avatar-placeholder"><i class="bi bi-person-fill" aria-hidden="true"></i></div>';
}

/**
 * Check if a value represents a captain appearance.
 * @param {*} value - The is_captain value to check
 * @returns {boolean} True if this is a captain appearance
 */
function isCaptainAppearance(value) {
  if (typeof value === 'boolean') return value;
  if (typeof value === 'number') return value === 1;
  const normalized = String(value || '').trim().toLowerCase();
  return normalized === 'true' || normalized === '1' || normalized === 'y' || normalized === 'yes';
}

/**
 * Find the current captain for a given squad from games data.
 * @param {string} squad - Squad identifier ('1st' or '2nd')
 * @param {Map} gamesById - Map of game_id to game objects
 * @param {Map} appearancesByGame - Map of game_id to array of appearance objects
 * @param {Map} profilesByName - Map of player name to profile object
 * @returns {Object|null} Current captain profile or null
 */
function findCurrentCaptainProfile(squad, gamesById, appearancesByGame, profilesByName) {
  const games = Array.from(gamesById.values())
    .filter(game => String(game?.squad || '').trim() === squad)
    .sort((a, b) => String(b?.date || '').localeCompare(String(a?.date || '')));

  for (const game of games) {
    const gameId = String(game?.game_id || '').trim();
    const appearances = appearancesByGame.get(gameId) || [];
    const captainAppearance = appearances.find(row => (
      String(row?.squad || '').trim() === squad && isCaptainAppearance(row?.is_captain)
    ));

    const captainName = String(captainAppearance?.player || game?.captain || '').trim();
    if (!captainName) continue;

    const profile = profilesByName.get(captainName);
    if (profile) return profile;
  }

  return null;
}

/**
 * Generate HTML markup for a single captain card.
 * @param {Object} profile - Captain profile object
 * @param {string} squad - Squad identifier ('1st' or '2nd')
 * @returns {string} HTML markup for captain card
 */
function generateCaptainCardMarkup(profile, squad) {
  const label = `${squad} XV Captain`;

  if (!profile) {
    return `
      <article class="player-gallery-captain-card player-gallery-captain-card-empty">
        <p class="player-gallery-captain-label">${escapeHtml(label)}</p>
        <p class="player-gallery-captain-empty">No captain data available.</p>
      </article>
    `;
  }

  const playerName = escapeHtml(profile.name || 'Unknown');
  const position = escapeHtml(profile.position || 'Unknown');
  const apps = Number(profile.totalAppearances || 0);
  const playerHref = `player-profile.html?player=${encodeURIComponent(String(profile.name || ''))}`;
  const squadClass = String(profile.squad || '').trim().toLowerCase() === '2nd' ? '2nd' : '1st';

  return `
  <div class="flex-column align-items-center m-0 p-0">
    <p class="player-gallery-captain-label">${escapeHtml(label)}</p>
    <article class="player-gallery-captain-card player-gallery-captain-card-${squadClass} p-0">
      <a class="player-gallery-captain-main" href="${playerHref}">
        <div class="player-gallery-captain-headshot ${headshotBackgroundClass(profile)}">
          ${createAvatarMarkup(profile)}
        </div>
        <div class="player-gallery-captain-meta">
          <p class="player-gallery-captain-name">${playerName}</p>
          <p class="player-gallery-captain-position">${position}</p>
          <p class="player-gallery-captain-apps">${apps} apps</p>
        </div>
      </a>
    </article>
  </div>
  `;
}

/**
 * Render captain cards to a specified container element.
 * @param {string} containerId - ID of the container element
 * @param {Map} gamesById - Map of game_id to game objects
 * @param {Map} appearancesByGame - Map of game_id to array of appearance objects
 * @param {Map} profilesByName - Map of player name to profile object
 */
function renderCaptainCards(containerId, gamesById, appearancesByGame, profilesByName) {
  const host = document.getElementById(containerId);
  if (!host) return;

  const firstCaptain = findCurrentCaptainProfile('1st', gamesById, appearancesByGame, profilesByName);
  const secondCaptain = findCurrentCaptainProfile('2nd', gamesById, appearancesByGame, profilesByName);

  host.innerHTML = [
    generateCaptainCardMarkup(firstCaptain, '1st'),
    generateCaptainCardMarkup(secondCaptain, '2nd')
  ].join('');
}

function analyticsReady() {
  return typeof window !== "undefined" && typeof window.gtag === "function";
}

function getAnalyticsPagePath() {
  if (typeof window === "undefined" || !window.location) return "";
  return String(window.location.pathname || "") || "/";
}

function sanitizeAnalyticsText(value, maxLength = 80) {
  const text = String(value || "").replace(/\s+/g, " ").trim();
  return text.slice(0, maxLength);
}

function trackAnalyticsEvent(eventName, params = {}) {
  if (!analyticsReady() || !eventName) return;
  window.gtag("event", eventName, params);
}

function getLinkArea(link) {
  if (!link || !link.closest) return "content";
  if (link.closest(".app-top-navbar, .navbar")) return "top_nav";
  if (link.closest(".analysis-rail")) return "analysis_rail";
  if (link.closest(".app-footer, footer")) return "footer";
  if (link.closest(".page-header-filters, .filter-item, .offcanvas, .filters-row"))
    return "filters";
  return "content";
}

function parseInternalTarget(link) {
  if (!link || typeof window === "undefined") return null;
  const href = String(link.getAttribute("href") || "").trim();
  if (!href || href.startsWith("javascript:") || href.startsWith("mailto:") || href.startsWith("tel:")) {
    return null;
  }

  try {
    const url = new URL(href, window.location.href);
    if (url.origin !== window.location.origin) return null;
    return {
      path: String(url.pathname || "") || "/",
      hash: String(url.hash || ""),
    };
  } catch (_error) {
    return null;
  }
}

function initAnalyticsTracking() {
  if (typeof document === "undefined" || document.__analyticsTrackingInitialised)
    return;
  document.__analyticsTrackingInitialised = true;

  if (analyticsReady()) {
    trackAnalyticsEvent("page_context", {
      page_path: getAnalyticsPagePath(),
      page_title: sanitizeAnalyticsText(document.title, 120),
    });
  }

  document.addEventListener("click", (event) => {
    const link = event.target.closest("a[href]");
    if (!link) return;

    const target = parseInternalTarget(link);
    if (!target) return;

    const fromPath = getAnalyticsPagePath();
    const toPath = target.path;
    const targetHash = String(target.hash || "").replace("#", "");
    const linkText = sanitizeAnalyticsText(
      link.getAttribute("data-short") || link.getAttribute("aria-label") || link.textContent,
    );

    if (targetHash && fromPath === toPath) {
      trackAnalyticsEvent("section_navigation_click", {
        page_path: fromPath,
        section_id: targetHash,
        link_area: getLinkArea(link),
        link_text: linkText || "(no label)",
      });
      return;
    }

    trackAnalyticsEvent("internal_navigation_click", {
      from_path: fromPath,
      to_path: toPath,
      to_has_hash: targetHash ? "yes" : "no",
      link_area: getLinkArea(link),
      link_text: linkText || "(no label)",
    });
  });

  document.addEventListener("change", (event) => {
    const control = event.target;
    if (!(control instanceof HTMLElement)) return;
    if (!control.matches("select, input[type='radio'], input[type='checkbox'], input[type='range']"))
      return;
    if (!control.closest(".filter-item, .page-header-filters, .offcanvas, .squad-filter-segment, .filters-row"))
      return;

    const controlId = sanitizeAnalyticsText(control.id || control.name || "(anonymous_filter)", 60);
    const controlType = control instanceof HTMLSelectElement
      ? (control.multiple ? "select_multiple" : "select_single")
      : control.getAttribute("type") || control.tagName.toLowerCase();

    let selectedCount = 0;
    if (control instanceof HTMLSelectElement) {
      selectedCount = Array.from(control.selectedOptions || []).filter((option) => option.value !== "").length;
    } else if (control instanceof HTMLInputElement && (control.type === "checkbox" || control.type === "radio")) {
      selectedCount = control.checked ? 1 : 0;
    } else if (control instanceof HTMLInputElement) {
      selectedCount = String(control.value || "").trim() ? 1 : 0;
    }

    trackAnalyticsEvent("filter_change", {
      page_path: getAnalyticsPagePath(),
      filter_id: controlId,
      filter_type: controlType,
      selected_count: selectedCount,
    });
  });

  document.addEventListener("click", (event) => {
    const toggle = event.target.closest(".chart-panel-toggle");
    if (!toggle) return;

    const panel = toggle.closest(".chart-panel");
    const panelId = sanitizeAnalyticsText(panel?.id || toggle.getAttribute("aria-controls") || "(panel)", 80);
    window.setTimeout(() => {
      const expanded = toggle.classList.contains("is-open") || toggle.getAttribute("aria-expanded") === "true";
      trackAnalyticsEvent("panel_toggle", {
        page_path: getAnalyticsPagePath(),
        panel_id: panelId,
        state: expanded ? "open" : "closed",
      });
    }, 0);
  });
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initAnalyticsTracking);
} else {
  initAnalyticsTracking();
}
