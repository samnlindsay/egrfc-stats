// Configuration and constants
const CONFIG = {
  charts: {
    minWidth: 600,
    mobileScaleFactor: 0.8,
    smallScaleFactor: 0.65,
  },
  breakpoints: {
    mobile: 768,
    small: 480,
  },
  dataFiles: {
    appearances: "data/charts/player_appearances.json",
    captains: "data/charts/captains.json",
    pointScorers: "data/charts/point_scorers.json",
    cards: "data/charts/cards.json",
    teamSheets: "data/charts/team_sheets.json",
    results: "data/charts/results.json",
    lineout: "data/charts/lineout_success.json",
    scrum: "data/charts/scrum_success.json",
  },
};

// Global state variables (matching test.html)
let appearancesSpec,
  captainsSpec,
  pointScorersSpec,
  cardsSpec,
  teamSheetsSpec,
  resultsSpec,
  lineoutSpec,
  scrumSpec;
let currentPlayerStatsType = "appearances";
let currentSetPieceType = "lineout";

// Global state object
const STATE = {
  isInitialized: false,
  currentTab: "player-stats-dropdown",
};
