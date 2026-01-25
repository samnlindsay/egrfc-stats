// ========================================
// CONFIGURATION & CONSTANTS
// ========================================
const SHEET_ID = "1y81JaTxj4gXbze4Oqc8THqGXXAE6Ht_F7ud2sucL4h0";
const SIGN_UP_FORM_NAME = "SignUpForm";
const PLAYERS_SHEET_NAME = "Players";
const POSITIONS_SHEET_NAME = "Positions";
const SCHEDULE_SHEET_NAME = "Schedule";
const AVAILABILITY_FORM_SHEET_NAME = "AvailabilityForm";
const AVAILABILITY_LATEST_SHEET_NAME = "AvailabilityLatest";
const AVAILABILITY_SHEET_NAME = "Availability";
const ATTENDANCE_SHEET_NAME = "Attendance";
const ATTENDANCE_HISTORY_SHEET_NAME = "AttendanceHistory";
const SELECTION_SHEET_NAME = "Selection";
// Sign-up form
const SIGN_UP_FORM_ID = "1fMIHEghHrhBtwDn86bOQ8lGEaRiJFXI3eFw10vPEYdQ";
// Availability form
const AVAILABILITY_FORM_ID = "110N_hDw4vP-9pGAtd_R-9HWWAtvwq1d-9Rk_Y362Flk";
const NAME_QUESTION_TITLE = "Name";
const WEEK_QUESTION_TITLE = "Week commencing";

// ========================================
// UTILITY FUNCTIONS
// ========================================

function boolToTick(b) {
  return b === true ? "✔" : b === false ? "✘" : "";
}
function getDaySuffix(day) {
  if (day > 3 && day < 21) return "th"; // 4th-20th special case
  switch (day % 10) {
    case 1:
      return "st";
    case 2:
      return "nd";
    case 3:
      return "rd";
    default:
      return "th";
  }
}
function formatDate(d, format = "d MMM YY") {
  return Utilities.formatDate(
    new Date(d),
    Session.getScriptTimeZone(),
    format,
    // "d'" + getDaySuffix(d.getDate()) + "' MMMM"
  );
}

function addWeeks(date, weeks) {
  const unix = new Date(date).getTime();
  const minusUnix = unix + 1000 * 60 * 60 * 24 * 7 * weeks;
  return new Date(minusUnix);
}
function getSortedPlayerNames(sheet) {
  const data = sheet.getDataRange().getValues();
  const headers = data[0];
  const rows = data.slice(1);
  const nameIdx = headers.indexOf("Name");

  if (nameIdx === -1) return [];

  return rows
    .map((row) => row[nameIdx]?.toString().trim())
    .filter((name) => name) // remove blanks
    .sort((a, b) => a.localeCompare(b));
}
function getEffectiveValue(attended, available) {
  // Add detailed logging
  const result = (() => {
    // If attended is explicitly set (including false), use it
    if (
      attended === true ||
      attended === false ||
      attended === "true" ||
      attended === "false"
    ) {
      return attended;
    }
    // If attended is null, undefined, or empty string, fall back to available
    if (attended !== "" && attended !== null && attended !== undefined) {
      return attended;
    }
    return available;
  })();

  return result;
}
function buildIndex(headers) {
  return headers.reduce((map, header, index) => {
    map[header] = index;
    return map;
  }, {});
}

function getFilteredPlayerNames(playersSheet, colts = false) {
  const data = playersSheet.getDataRange().getValues();
  const headers = data[0];
  const rows = data.slice(1);

  const nameIdx = headers.indexOf("Name");
  const coltsIdx = headers.indexOf("Colts");

  if (nameIdx === -1) return [];

  return rows
    .filter((row) => {
      const name = row[nameIdx]?.toString().trim();
      if (!name) return false; // Skip empty names

      // Exclude Colts players
      const isColts = row[coltsIdx] === true || row[coltsIdx] === "TRUE";
      return !isColts || colts;
    })
    .map((row) => row[nameIdx].toString().trim())
    .sort((a, b) => a.localeCompare(b));
}
function exportAvailabilityPublic() {
  const sourceSS = SpreadsheetApp.getActiveSpreadsheet();

  // Get or create destination spreadsheet
  const exportFileName = "EGRFC Availability";
  const props = PropertiesService.getScriptProperties();
  let destSS;
  const destFileId = props.getProperty("publicAvailabilitySheetId");

  if (destFileId) {
    destSS = SpreadsheetApp.openById(destFileId);
    // Keep one sheet to avoid errors, then delete others
    const sheets = destSS.getSheets();
    if (sheets.length > 1) {
      for (let i = 1; i < sheets.length; i++) {
        destSS.deleteSheet(sheets[i]);
      }
    }
    // Clear and rename the remaining sheet
    const remainingSheet = destSS.getSheets()[0];
    remainingSheet.clear();
    if (remainingSheet.getName() !== "Availability") {
      remainingSheet.setName("Availability");
    }
  } else {
    destSS = SpreadsheetApp.create(exportFileName);
    props.setProperty("publicAvailabilitySheetId", destSS.getId());
    // Rename the default sheet
    const defaultSheet = destSS.getSheets()[0];
    defaultSheet.setName("Availability");
  }

  // Get the target sheet
  const copiedSheet = destSS.getSheetByName("Availability");

  // Get the data we need
  const availabilityLatestSheet = sourceSS.getSheetByName(
    AVAILABILITY_LATEST_SHEET_NAME,
  );
  const scheduleSheet = sourceSS.getSheetByName(SCHEDULE_SHEET_NAME);

  if (!availabilityLatestSheet || !scheduleSheet) {
    Logger.log("Required source sheets not found");
    return;
  }

  const availabilityLatestData = availabilityLatestSheet
    .getDataRange()
    .getValues();
  const scheduleData = scheduleSheet.getDataRange().getValues();

  // Use the refactored buildAvailability function with public options
  buildAvailability(availabilityLatestData, scheduleData, copiedSheet, {
    isPublic: true,
    includeFilters: false,
    includeCharts: false,
    maxRows: 205,
  });

  // Sort by Name column (A) from row 5 to last used row
  const dataLastRow = Math.min(199, copiedSheet.getLastRow());
  if (dataLastRow > 4) {
    copiedSheet
      .getRange(5, 1, dataLastRow - 4, copiedSheet.getLastColumn())
      .sort({ column: 1, ascending: true });
  }

  // Remove rows after maxRows if they exist
  const finalLastRow = copiedSheet.getLastRow();
  if (finalLastRow > 205) {
    copiedSheet.deleteRows(206, finalLastRow - 205);
  }

  // Protect the sheet for view-only access
  try {
    const existingProtections = copiedSheet.getProtections(
      SpreadsheetApp.ProtectionType.SHEET,
    );
    existingProtections.forEach((protection) => protection.remove());

    const protection = copiedSheet.protect();
    const editors = protection.getEditors();
    if (editors.length > 0) {
      protection.removeEditors(editors);
    }
    protection.setWarningOnly(true);
  } catch (error) {
    Logger.log(`Warning: Could not set protection: ${error.toString()}`);
  }

  Logger.log("Public Availability Sheet URL: " + destSS.getUrl());
}

/**
 * Sets public view-only sharing on the exported Availability sheet.
 */
function setAvailabilityPublicSharing() {
  const destFileId = PropertiesService.getScriptProperties().getProperty(
    "publicAvailabilitySheetId",
  );
  if (!destFileId)
    throw new Error("Public Availability sheet hasn't been created yet.");
  const file = DriveApp.getFileById(destFileId);
  file.setSharing(DriveApp.Access.ANYONE_WITH_LINK, DriveApp.Permission.VIEW);
  Logger.log("Public Availability Sheet shared at: " + file.getUrl());
}

// ========================================
// TRIGGER SETUP FUNCTIONS
// ========================================
function createFormSubmitTriggers() {
  const form1 = FormApp.openById(SIGN_UP_FORM_ID);
  ScriptApp.newTrigger("updatePlayers").forForm(form1).onFormSubmit().create();

  const form2 = FormApp.openById(AVAILABILITY_FORM_ID);
  ScriptApp.newTrigger("onAvailabilityFormSubmit")
    .forForm(form2)
    .onFormSubmit()
    .create();
}
function createWeeklyTrigger() {
  // This creates a trigger that runs every Saturday at 5pm
  ScriptApp.newTrigger("updateForm")
    .timeBased()
    .onWeekDay(ScriptApp.WeekDay.SATURDAY)
    .atHour(17)
    .create();
}

// ========================================
// MAIN EVENT HANDLERS
// ========================================
function onEdit(e) {
  const ss = e.source;
  const sheetName = e.range.getSheet().getName();
  const cellA1 = e.range.getA1Notation();

  // Early exit for irrelevant edits
  const relevantSheets = [
    POSITIONS_SHEET_NAME,
    SCHEDULE_SHEET_NAME,
    SELECTION_SHEET_NAME,
    ATTENDANCE_SHEET_NAME,
  ];
  if (!relevantSheets.includes(sheetName)) return;

  // Lazy load sheets and data only when needed
  const sheetCache = {};
  const dataCache = {};

  const getSheet = (name) => {
    if (!sheetCache[name]) {
      sheetCache[name] = ss.getSheetByName(name) || ss.insertSheet(name);
    }
    return sheetCache[name];
  };

  const getData = (sheetName) => {
    if (!dataCache[sheetName]) {
      const sheet = getSheet(sheetName);
      dataCache[sheetName] =
        sheet.getLastRow() > 0 ? sheet.getDataRange().getValues() : [];
    }
    return dataCache[sheetName];
  };

  if (sheetName === POSITIONS_SHEET_NAME && cellA1 === "B1") {
    updatePositions(
      getData(PLAYERS_SHEET_NAME),
      getSheet(POSITIONS_SHEET_NAME),
    );
  } else if (sheetName === SCHEDULE_SHEET_NAME) {
    buildAvailability(
      getData(AVAILABILITY_LATEST_SHEET_NAME),
      getData(SCHEDULE_SHEET_NAME),
      getSheet(AVAILABILITY_SHEET_NAME),
    );

    // Update Selection dropdown when Schedule changes
    updateSelectionDropdown(
      getData(SCHEDULE_SHEET_NAME),
      getData(AVAILABILITY_LATEST_SHEET_NAME),
      getSheet(SELECTION_SHEET_NAME),
    );
  } else if (sheetName === SELECTION_SHEET_NAME && cellA1 === "A2") {
    buildSelection(
      getData(PLAYERS_SHEET_NAME),
      getData(AVAILABILITY_LATEST_SHEET_NAME),
      getSheet(SELECTION_SHEET_NAME),
    );
  } else if (sheetName === ATTENDANCE_SHEET_NAME) {
    if (cellA1 === "B1") {
      loadAttendanceSheet(
        getSheet(PLAYERS_SHEET_NAME),
        getSheet(ATTENDANCE_SHEET_NAME),
        getSheet(AVAILABILITY_LATEST_SHEET_NAME),
      );
    } else if (cellA1 === "E1" && e.range.getValue() === true) {
      // This is the most expensive operation - optimize with data arrays
      updateAttendanceHistory(
        getSheet(ATTENDANCE_SHEET_NAME),
        getSheet(ATTENDANCE_HISTORY_SHEET_NAME),
      );

      // Pass data arrays instead of sheets for these heavy operations
      updateAvailabilityLatest(
        getData(ATTENDANCE_HISTORY_SHEET_NAME),
        getData(SCHEDULE_SHEET_NAME),
        getData(AVAILABILITY_FORM_SHEET_NAME),
        getSheet(AVAILABILITY_LATEST_SHEET_NAME),
      );
      updateAvailability(
        getData(AVAILABILITY_LATEST_SHEET_NAME),
        getData(SCHEDULE_SHEET_NAME),
        getSheet(AVAILABILITY_SHEET_NAME),
      );
    } else {
      getSheet(ATTENDANCE_SHEET_NAME).getRange("E1").setValue(false);
    }
  }
}

function onAvailabilityFormSubmit(e) {
  const ss = SpreadsheetApp.openById(SHEET_ID);

  // Read all sheet data in one batch operation
  const sheets = {
    availabilityForm: ss.getSheetByName(AVAILABILITY_FORM_SHEET_NAME),
    players: ss.getSheetByName(PLAYERS_SHEET_NAME),
    schedule: ss.getSheetByName(SCHEDULE_SHEET_NAME),
    availabilityLatest:
      ss.getSheetByName(AVAILABILITY_LATEST_SHEET_NAME) ||
      ss.insertSheet(AVAILABILITY_LATEST_SHEET_NAME),
    availability: ss.getSheetByName(AVAILABILITY_SHEET_NAME),
    selection: ss.getSheetByName(SELECTION_SHEET_NAME),
    attendanceHistory: ss.getSheetByName(ATTENDANCE_HISTORY_SHEET_NAME),
  };

  // Read all data at once
  const sheetData = {};
  Object.keys(sheets).forEach((key) => {
    if (sheets[key] && sheets[key].getLastRow() > 0) {
      sheetData[key] = sheets[key].getDataRange().getValues();
    } else {
      sheetData[key] = [];
    }
  });

  updateAvailabilityLatest(
    sheetData.attendanceHistory,
    sheetData.schedule,
    sheetData.availabilityForm,
    sheets.availabilityLatest,
  );

  // Read fresh data after update
  const freshAvailabilityData = sheets.availabilityLatest
    .getDataRange()
    .getValues();

  updateAvailability(
    freshAvailabilityData,
    sheetData.schedule,
    sheets.availability,
  );

  buildSelection(sheetData.players, freshAvailabilityData, sheets.selection);
}

// ========================================
// FORM MANAGEMENT
// ========================================
function updateForm() {
  const ss = SpreadsheetApp.openById(SHEET_ID);
  const form = FormApp.openById(AVAILABILITY_FORM_ID);
  const playersSheet = ss.getSheetByName(PLAYERS_SHEET_NAME);
  const scheduleSheet = ss.getSheetByName(SCHEDULE_SHEET_NAME);

  const weekLabels = generateWeekLabels(scheduleSheet);
  setDropdownChoices(form, WEEK_QUESTION_TITLE, weekLabels.slice(0, 6));

  // Get filtered player names (exclude Colts)
  const names = getFilteredPlayerNames(playersSheet, (colts = true));
  setDropdownChoices(form, NAME_QUESTION_TITLE, names);
}

function generateWeekLabels(scheduleSheet) {
  const data = scheduleSheet.getDataRange().getValues();
  const now = new Date();
  const labels = [];
  const output = [];

  if (!data[0][7] || data[0][7].toString().trim() !== "Week Label") {
    data[0][7] = "Week Label";
  }

  for (let i = 1; i < data.length; i++) {
    const weekDate = new Date(data[i][1]);
    let label = "";

    // Calculate cutoff time: 5pm on Saturday of the week
    const saturdayOfWeek = new Date(weekDate);
    saturdayOfWeek.setDate(weekDate.getDate() + 5); // Saturday is 5 days after Monday
    saturdayOfWeek.setHours(17, 0, 0, 0); // Set to 5pm

    // Include week if it's current week (before 5pm Saturday) or future weeks
    if (now <= saturdayOfWeek) {
      const day = weekDate.getDate();
      const suffix = getDaySuffix(day);
      const weekStr = formatDate(weekDate, `d'${suffix}' MMM`);

      const game1 = data[i][5],
        game2 = data[i][6],
        matchDate = data[i][4];
      const matchStr = matchDate ? ` - ${formatDate(matchDate, "d MMM")}` : "";

      let gamesLabel = "";
      if (game1 && game2) gamesLabel = `1s v ${game1}, 2s v ${game2}`;
      else if (game1) gamesLabel = `1s v ${game1}`;
      else if (game2) gamesLabel = `2s v ${game2}`;
      else gamesLabel = "no games";

      label =
        gamesLabel === "no games"
          ? `w/c ${weekStr}: no games`
          : `w/c ${weekStr}: ${gamesLabel}${matchStr}`;

      labels.push(label);
    }

    output[i] = output[i] || Array(data[0].length).fill("");
    output[i][7] = label || ""; // column H = index 7
  }

  // Write all updated labels back in one go
  if (output.length > 1) {
    const labelValues = output.slice(1).map((row) => [row[7]]);
    scheduleSheet.getRange(2, 8, labelValues.length, 1).setValues(labelValues);
  }

  return labels;
}
function setDropdownChoices(form, questionTitle, choices) {
  const item = form
    .getItems()
    .find(
      (q) =>
        q.getTitle().trim() === questionTitle &&
        [FormApp.ItemType.LIST, FormApp.ItemType.DROPDOWN].includes(
          q.getType(),
        ),
    );

  if (!item) throw new Error(`Question titled "${questionTitle}" not found`);

  if (item.getType() === FormApp.ItemType.LIST) {
    item.asListItem().setChoiceValues(choices);
  } else {
    item.asDropdownItem().setChoiceValues(choices);
  }
}

// ========================================
// PLAYERS MANAGEMENT
// ========================================
function updatePlayers() {
  const ss = SpreadsheetApp.openById(SHEET_ID);
  const formSheet = ss.getSheetByName(SIGN_UP_FORM_NAME);
  const playersSheet = ss.getSheetByName(PLAYERS_SHEET_NAME);

  const formData = formSheet.getDataRange().getValues();
  const playersData = playersSheet.getDataRange().getValues();

  const positionsSheet = ss.getSheetByName(POSITIONS_SHEET_NAME);

  if (formData.length < 2 || playersData.length < 1) return;

  const [formHeaders, ...formRows] = formData;
  const [playersHeaders, ...playersRows] = playersData;

  const mIdx = playersHeaders.reduce((map, h, i) => ((map[h] = i), map), {});
  const fIdx = formHeaders.reduce((map, h, i) => ((map[h] = i), map), {});

  const fullNameSet = new Set(
    playersRows.map((r) => (r[mIdx["Name"]] || "").trim().toLowerCase()),
  );

  const numCols = playersHeaders.length;
  const combinedRows = [...playersRows]; // Start with existing data

  // Track if any new players were added
  let newPlayersAdded = false;

  for (const row of formRows) {
    const firstName = (row[fIdx["First Name"]] || "").trim();
    const lastName = (row[fIdx["Second Name"]] || "").trim();
    const fullName = `${firstName} ${lastName}`.trim();

    if (!firstName || !lastName || fullNameSet.has(fullName.toLowerCase()))
      continue;

    const mobile = row[fIdx["Mobile Number"]] || "";
    const positions = (row[fIdx["Preferred Playing Position"]] || "").trim();
    const primary = positions.includes(",") ? "" : positions;

    const newRow = Array(numCols).fill("");
    newRow[mIdx["Name"]] = fullName;
    if ("Phone" in mIdx) newRow[mIdx["Phone"]] = mobile;
    if ("Positions" in mIdx) newRow[mIdx["Positions"]] = positions;
    if ("Primary Position" in mIdx && mIdx["Primary Position"] < numCols) {
      newRow[mIdx["Primary Position"]] = primary;
    }

    combinedRows.push(newRow);
    newPlayersAdded = true; // Mark that a new player was added
  }

  // === Sorting Logic ===
  const getAvailabilityRank = (r) =>
    r[mIdx.Injured] ? 2 : r[mIdx.Unavailable] ? 1 : 0;
  const getTeamRank = (r) =>
    r[mIdx["1st"]] && !r[mIdx["2nd"]]
      ? 0
      : r[mIdx["1st"]] && r[mIdx["2nd"]]
        ? 1
        : r[mIdx["2nd"]] && !r[mIdx["1st"]]
          ? 2
          : 3;
  const getColtsRank = (r) => (r[mIdx.Colts] ? 1 : 0);

  combinedRows.sort((a, b) => {
    const rankA = [getAvailabilityRank(a), getTeamRank(a), getColtsRank(a)];
    const rankB = [getAvailabilityRank(b), getTeamRank(b), getColtsRank(b)];

    for (let i = 0; i < rankA.length; i++) {
      if (rankA[i] !== rankB[i]) return rankA[i] - rankB[i];
    }

    const nameA = (a[mIdx.Name] || "").toLowerCase();
    const nameB = (b[mIdx.Name] || "").toLowerCase();
    return nameA.localeCompare(nameB);
  });

  // === Final Sheet Update ===
  const finalData = [playersHeaders, ...combinedRows];
  playersSheet.getRange(1, 1, finalData.length, numCols).setValues(finalData);

  // Format newly added rows
  const newlyAdded = combinedRows.length - playersRows.length;
  if (newlyAdded > 0) {
    const startRow = playersRows.length + 2;
    const newRange = playersSheet.getRange(startRow, 1, newlyAdded, numCols);
    const formatSource = playersSheet.getRange(startRow - 1, 1, 1, numCols);
    formatSource.copyTo(newRange, { formatOnly: true });
  }

  // Reapply filter
  const existingFilter = playersSheet.getFilter();
  if (existingFilter) existingFilter.remove();
  playersSheet.getRange(1, 1, finalData.length, numCols).createFilter();

  updatePositions(playersData, positionsSheet); // Optional

  // Update availability form dropdowns if new players were added
  if (newPlayersAdded) {
    try {
      updateForm();
      Logger.log(
        `Updated availability form dropdowns with ${newlyAdded} new players`,
      );
    } catch (error) {
      Logger.log(`Error updating form dropdowns: ${error.toString()}`);
    }
  }
}
function updatePositions(playersData, positionsSh) {
  // 1) Batch‐read players data and summary UI inputs
  const headers = playersData[0];
  const rows = playersData.slice(1);
  const idx = headers.reduce((m, h, i) => ((m[h] = i), m), {});
  const filterVal = positionsSh.getRange("B1").getValue();

  // 2) Cache your “key” formatting cells once
  const keyCells = {
    available: positionsSh.getRange("H4"),
    availableBackup: positionsSh.getRange("H5"),
    unavailable: positionsSh.getRange("H6"),
    injured: positionsSh.getRange("H7"),
  };
  const keyFmt = Object.fromEntries(
    Object.entries(keyCells).map(([k, cell]) => [
      k,
      {
        bg: cell.getBackground(),
        fontColor: cell.getFontColor(),
        bold: cell.getFontWeight() === "bold",
      },
    ]),
  );

  // 3) Define positions and where they go
  const positionsTop = ["Prop", "Hooker", "Second Row", "Flanker", "Number 8"];
  const positionsBottom = [
    "Scrum Half",
    "Fly Half",
    "Centre",
    "Winger",
    "Fullback",
  ];
  const startCols = {
    Prop: 2,
    Hooker: 3,
    "Second Row": 4,
    Flanker: 5,
    "Number 8": 6,
    "Scrum Half": 2,
    "Fly Half": 3,
    Centre: 4,
    Winger: 5,
    Fullback: 6,
  };
  const startRows = {
    Prop: 3,
    Hooker: 3,
    "Second Row": 3,
    Flanker: 3,
    "Number 8": 3,
    "Scrum Half": 30,
    "Fly Half": 30,
    Centre: 30,
    Winger: 30,
    Fullback: 30,
  };

  // 4) Build in‐memory map of available players
  const positionMap = {};
  [...positionsTop, ...positionsBottom].forEach((p) => (positionMap[p] = []));
  rows.forEach((r) => {
    const name = `${r[idx["Name"]]} ${r[idx["Surname"]] || ""}`.trim();
    const primary = r[idx["Primary Position"]];
    const isInj = r[idx["Injured"]];
    const isUnav = r[idx["Unavailable"]];
    const isResp = r[idx["Last Updated"]]; // responded at all
    const isFirst = r[idx["1st"]],
      isSecond = r[idx["2nd"]];
    // filter by squad or team selection
    if (
      !(
        filterVal === "Squad" ||
        (filterVal === "1st XV" && isFirst) ||
        (filterVal === "2nd XV" && isSecond) ||
        (filterVal === "Colts" && r[idx["Colts"]])
      )
    )
      return;
    // assign to each declared position
    (r[idx["Positions"]].split(",").map((s) => s.trim()) || [])
      .filter((p) => positionMap[p])
      .forEach((pos) => {
        let statusRank, fmt;
        if (isInj) {
          fmt = keyFmt.injured;
          statusRank = 3;
        } else if (isUnav) {
          fmt = keyFmt.unavailable;
          statusRank = 2;
        } else if (primary === pos) {
          fmt = keyFmt.available;
          statusRank = 0;
        } else {
          fmt = keyFmt.availableBackup;
          statusRank = 1;
        }
        positionMap[pos].push({ name, fmt, statusRank });
      });
  });

  // 5) Clear existing blocks in one shot each
  positionsSh.getRange(3, 2, 26, 5).clearContent().setBackground("#b1b1b1"); // Top half B–F, rows 3–28
  positionsSh.getRange(30, 2, 26, 5).clearContent().setBackground("#b1b1b1"); // Bottom half

  // 6) Helper to write & format a group of players
  function writeGroup(list, col, startRow) {
    if (list.length === 0) return;
    // sort in-memory
    list.sort(
      (a, b) => a.statusRank - b.statusRank || a.name.localeCompare(b.name),
    );
    // batch‐write names
    const vals = list.map((p) => [p.name]);
    positionsSh.getRange(startRow, col, vals.length, 1).setValues(vals);
    // batch‐format backgrounds & fonts
    vals.forEach((_, i) => {
      const { bg, fontColor, bold } = list[i].fmt;
      positionsSh
        .getRange(startRow + i, col)
        .setBackground(bg)
        .setFontColor(fontColor)
        .setFontWeight(bold ? "bold" : "normal");
    });
  }

  // 7) Write each position in turn
  positionsTop.forEach((pos) => {
    writeGroup(positionMap[pos], startCols[pos], startRows[pos]);
  });
  positionsBottom.forEach((pos) => {
    writeGroup(positionMap[pos], startCols[pos], startRows[pos]);
  });
}

// ========================================
// AVAILABILITY SYSTEM
// ========================================
function updateAvailabilityLatest(
  attendanceHistoryData, // Now expects data array
  scheduleData, // Now expects data array
  formData, // Now expects data array
  availabilityLatestSh, // Still expects sheet object for writing
) {
  const headers = [
    "Name",
    "#",
    "Week commencing",
    "Event",
    "Date",
    "Available",
    "Attended",
    "Last updated",
  ];

  const existingData = availabilityLatestSh.getDataRange().getValues();

  // Build map: Form label -> { number, date, validSessions }
  const scheduleMap = {};
  for (let i = 1; i < scheduleData.length; i++) {
    const row = scheduleData[i];
    const label = (row[7] || "").trim(); // Form label
    if (!label) continue;

    // Determine which sessions are valid for this week
    const validSessions = [];
    if (row[scheduleData[0].indexOf("Tues")] === true)
      validSessions.push("Tues");
    if (row[scheduleData[0].indexOf("Thurs")] === true)
      validSessions.push("Thurs");
    if (
      row[scheduleData[0].indexOf("1st")] ||
      row[scheduleData[0].indexOf("2nd")]
    ) {
      validSessions.push("Sat");
    }

    scheduleMap[label] = {
      number: row[0],
      weekCommencing: formatDate(row[1]),
      matchDate: new Date(row[4]), // Match Date for Saturday
      validSessions: validSessions, // NEW: Track which sessions are valid
    };
  }

  // Column indexes in form
  const formHeaders = formData[0];
  const idx = {
    timestamp: formHeaders.indexOf("Timestamp"),
    name: formHeaders.indexOf("Name"),
    week: formHeaders.indexOf("Week commencing"),
    sel: formHeaders.indexOf(
      "Select your training attendance / match day availability",
    ),
    food: formHeaders.indexOf("Thursday post-training food?"),
  };

  // Latest submission per player per week
  const latestMap = new Map();
  for (let i = 1; i < formData.length; i++) {
    const row = formData[i];
    const name = (row[idx.name] || "").trim();
    const label = (row[idx.week] || "").trim();
    const timestamp = new Date(row[idx.timestamp]);
    if (!name || !label) continue;
    const key = `${name}||${label}`;
    if (!latestMap.has(key) || latestMap.get(key).timestamp < timestamp) {
      latestMap.set(key, { row, timestamp });
    }
  }

  // Build existing records map for updates
  const existingMap = new Map();
  for (let i = 1; i < existingData.length; i++) {
    const row = existingData[i];
    const key = `${row[0]}||${row[1]}||${row[3]}`; // Name || # || Event
    existingMap.set(key, { row, index: i + 1 });
  }

  // Get attendance data using AttendanceHistory structure
  const attendanceMap = new Map();
  if (attendanceHistoryData && attendanceHistoryData.length > 1) {
    const attendanceHeaders = attendanceHistoryData[0];
    const nameCol = attendanceHeaders.indexOf("Name");
    const weekCommencingCol = attendanceHeaders.indexOf("Week commencing");
    const sessionCol = attendanceHeaders.indexOf("Session");
    const attendedCol = attendanceHeaders.indexOf("Attended");

    // Logger.log(
    //   `Processing AttendanceHistory data: ${
    //     attendanceHistoryData.length - 1
    //   } rows`
    // );

    attendanceHistoryData.slice(1).forEach((row, index) => {
      const name = row[nameCol]?.toString().trim();
      const weekCommencing = row[weekCommencingCol];
      const session = row[sessionCol];
      const attended = row[attendedCol];

      if (name && weekCommencing && session) {
        // FIX: Ensure consistent date formatting
        const formattedWeekCommencing = formatDate(weekCommencing);
        const key = `${name}||${formattedWeekCommencing}||${session}`;

        // Log attendance data being stored
        // Logger.log(
        //   `AttendanceHistory row ${index}: original=${name}||${weekCommencing}||${session}, formatted=${key} => attended=${JSON.stringify(
        //     attended
        //   )} (type: ${typeof attended})`
        // );
        attendanceMap.set(key, attended);
      }
    });

    // Log all keys in attendance map for debugging
    // Logger.log("All attendance map keys:");
    // attendanceMap.forEach((value, key) => {
    //   Logger.log(`  ${key} => ${JSON.stringify(value)}`);
    // });
  }

  const updates = [];
  const appends = [];

  latestMap.forEach(({ row, timestamp }, key) => {
    const name = (row[idx.name] || "").trim();
    const label = (row[idx.week] || "").trim();
    const selection = (row[idx.sel] || "").toLowerCase();

    const schedule = scheduleMap[label] || {};
    const weekNumber = schedule.number || "";
    const weekCommencing = schedule.weekCommencing || "";
    const matchDate = schedule.matchDate;
    const validSessions = schedule.validSessions || []; // NEW: Get valid sessions

    // Parse availability for each event
    const availability = {
      Tues: selection.includes("tuesday"),
      Thurs: selection.includes("thursday"),
      Sat: selection.includes("saturday") || selection.includes("match"),
    };

    // Calculate actual dates for each event
    const scheduleRow = scheduleData.find((row) => row[7] === label); // Find by form label
    const weekCommencingDate = scheduleRow
      ? new Date(scheduleRow[1])
      : new Date(); // Use original Date

    const eventDates = {
      Tues: new Date(weekCommencingDate.getTime() + 1 * 86400000), // Tuesday
      Thurs: new Date(weekCommencingDate.getTime() + 3 * 86400000), // Thursday
      Sat: matchDate || new Date(weekCommencingDate.getTime() + 5 * 86400000), // Saturday
    };

    // Create one row per event - BUT ONLY FOR VALID SESSIONS
    Object.entries(availability).forEach(([event, available]) => {
      // NEW: Skip if this session doesn't exist for this week
      if (!validSessions.includes(event)) {
        return; // Skip this session
      }

      const attendanceKey = `${name}||${weekCommencing}||${event}`;
      const attended = attendanceMap.has(attendanceKey)
        ? attendanceMap.get(attendanceKey)
        : null;

      // Enhanced logging for attendance lookup
      // Logger.log(`Attendance lookup for ${attendanceKey}:`);
      // Logger.log(`  - Map has key: ${attendanceMap.has(attendanceKey)}`);
      // Logger.log(`  - Raw weekCommencing: ${JSON.stringify(weekCommencing)}`);
      // Logger.log(`  - All similar keys in map:`);
      // attendanceMap.forEach((val, mapKey) => {
      //   if (mapKey.includes(name) && mapKey.includes(event)) {
      //     Logger.log(`    - ${mapKey} => ${JSON.stringify(val)}`);
      //   }
      // });
      // Logger.log(
      //   `  - Final value: ${JSON.stringify(
      //     attended
      //   )} (type: ${typeof attended})`
      // );

      const eventDate = formatDate(eventDates[event]);

      const outRow = [
        name, // Name
        weekNumber, // #
        weekCommencing, // Week commencing
        event, // Event
        eventDate, // Date (NEW)
        available, // Available
        attended, // Attended
        formatDate(timestamp, "yyyy-MM-dd HH:mm:ss"), // Last updated
      ];

      // Log the final row being created
      // Logger.log(
      //   `Creating row for ${name}-${event}: available=${JSON.stringify(
      //     available
      //   )}, attended=${JSON.stringify(attended)}`
      // );

      const matchKey = `${name}||${weekNumber}||${event}`;
      const existing = existingMap.get(matchKey);

      if (existing) {
        const existingRow = existing.row;
        // Always update attendance data from AttendanceHistory
        const updatedRow = [...outRow];
        updatedRow[6] = attended !== null ? attended : existingRow[6]; // Use new attendance data if available

        // FIX: Check if any values have changed - handle boolean comparison properly
        if (
          updatedRow.some((val, i) => {
            if (i === 6) {
              // Attended column - handle boolean comparison
              const valStr =
                val === null || val === undefined ? "" : String(val);
              const existingStr =
                existingRow[i] === null || existingRow[i] === undefined
                  ? ""
                  : String(existingRow[i]);
              return valStr !== existingStr;
            }
            return `${val}` !== `${existingRow[i]}`;
          })
        ) {
          updates.push({ row: existing.index, values: updatedRow });
        }
      } else {
        appends.push(outRow);
      }
    });
  });

  // IMPORTANT: Also update existing records that don't have form submissions but have attendance data
  if (existingData.length > 1) {
    for (let i = 1; i < existingData.length; i++) {
      const existingRow = existingData[i];
      const name = existingRow[0];
      const weekCommencing = existingRow[2];
      const event = existingRow[3];

      const attendanceKey = `${name}||${weekCommencing}||${event}`;
      if (attendanceMap.has(attendanceKey)) {
        const attended = attendanceMap.get(attendanceKey);
        const currentAttended = existingRow[6];

        // FIX: Handle boolean comparison properly - convert both to strings
        const attendedStr =
          attended === null || attended === undefined ? "" : String(attended);
        const currentAttendedStr =
          currentAttended === null || currentAttended === undefined
            ? ""
            : String(currentAttended);

        // Only update if attendance has changed
        if (attendedStr !== currentAttendedStr) {
          const updatedRow = [...existingRow];
          updatedRow[6] = attended;

          // Check if this row is already being updated by form data
          const isAlreadyUpdating = updates.some(
            (update) => update.row === i + 1,
          );
          if (!isAlreadyUpdating) {
            updates.push({ row: i + 1, values: updatedRow });
          }
        }
      }
    }
  }

  // Add players from AttendanceHistory who aren't in availability data
  if (attendanceHistoryData && attendanceHistoryData.length > 1) {
    const attendanceHeaders = attendanceHistoryData[0];
    const nameCol = attendanceHeaders.indexOf("Name");
    const weekNumCol = attendanceHeaders.indexOf("#");
    const weekCommencingCol = attendanceHeaders.indexOf("Week commencing");
    const sessionCol = attendanceHeaders.indexOf("Session");
    const attendedCol = attendanceHeaders.indexOf("Attended");
    const lastUpdatedCol = attendanceHeaders.indexOf("Last updated");
    const dateCol = attendanceHeaders.indexOf("Date");

    attendanceHistoryData.slice(1).forEach((row) => {
      const name = row[nameCol]?.toString().trim();
      const weekNumber = row[weekNumCol];
      const weekCommencing = row[weekCommencingCol];
      const session = row[sessionCol];
      const attended = row[attendedCol];
      const lastUpdated = row[lastUpdatedCol];
      const sessionDate = row[dateCol];

      if (name && weekNumber && session) {
        // NEW: Validate that this session was actually scheduled
        const weekSchedule = scheduleData.find(
          (row) => formatDate(row[1]) === formatDate(weekCommencing),
        );

        if (weekSchedule) {
          const validSessions = [];
          if (weekSchedule[scheduleData[0].indexOf("Tues")] === true)
            validSessions.push("Tues");
          if (weekSchedule[scheduleData[0].indexOf("Thurs")] === true)
            validSessions.push("Thurs");
          if (
            weekSchedule[scheduleData[0].indexOf("1st")] ||
            weekSchedule[scheduleData[0].indexOf("2nd")]
          ) {
            validSessions.push("Sat");
          }

          // Skip if this session wasn't scheduled for this week
          if (!validSessions.includes(session)) {
            return;
          }
        }

        const matchKey = `${name}||${weekNumber}||${session}`;

        // Only add if not already in availability data
        if (
          !existingMap.has(matchKey) &&
          !appends.some(
            (app) =>
              app[0] === name && app[1] === weekNumber && app[3] === session,
          )
        ) {
          // Convert session date to display format - FIX THE FORMATTING HERE
          const eventDate = sessionDate ? formatDate(sessionDate) : "";

          const formattedWeekCommencing = formatDate(weekCommencing);
          const formattedLastUpdated = lastUpdated
            ? formatDate(lastUpdated, "yyyy-MM-dd HH:mm:ss")
            : formatDate(new Date(), "yyyy-MM-dd HH:mm:ss");

          const newRow = [
            name, // Name
            weekNumber?.toString() || "", // # (ensure it's a string/number, not a date)
            formattedWeekCommencing, // Week commencing (properly formatted)
            session, // Event
            eventDate, // Date (properly formatted)
            null, // Available (unknown)
            attended, // Attended
            formattedLastUpdated, // Last updated (properly formatted)
          ];
          appends.push(newRow);
        }
      }
    });
  }

  // Headers if first time
  if (existingData.length === 0) {
    availabilityLatestSh.getRange(1, 1, 1, headers.length).setValues([headers]);
  }

  // Apply updates
  updates.forEach(({ row, values }) => {
    availabilityLatestSh
      .getRange(row, 1, 1, headers.length)
      .setValues([values]);
  });

  // Append new rows
  if (appends.length > 0) {
    const start = availabilityLatestSh.getLastRow() + 1;
    availabilityLatestSh
      .getRange(start, 1, appends.length, headers.length)
      .setValues(appends);
  }

  // Set up checkboxes for Available column (updated indexes)
  const lastRow = availabilityLatestSh.getLastRow();
  if (lastRow > 1) {
    availabilityLatestSh.getRange(`F2:F`).insertCheckboxes(); // Updated range
  }

  // Sort by week number, name, then event order (Tues, Thurs, Sat)
  const dataRange = availabilityLatestSh.getRange(
    2,
    1,
    availabilityLatestSh.getLastRow() - 1,
    availabilityLatestSh.getLastColumn(),
  );

  if (dataRange.getNumRows() > 0) {
    dataRange.sort([
      { column: 2, ascending: true }, // Week number
      { column: 1, ascending: true }, // Name
      { column: 4, ascending: true }, // Event (alphabetical: Sat, Thurs, Tues)
    ]);
  }

  exportAvailabilityPublic();
}

// Updated buildAvailability function with options parameter
function buildAvailability(
  availabilityLatestData,
  scheduleData,
  availabilitySheet,
  options = {},
) {
  // Extract options with defaults
  const {
    isPublic = false,
    includeFilters = true,
    includeCharts = true,
    maxRows = 205,
  } = options;

  const today = new Date();

  // --- Step 1: Load schedule and define column structure (unchanged)
  const scheduleHeaders = scheduleData[0];
  const scheduleIndex = {};
  scheduleHeaders.forEach((h, i) => (scheduleIndex[h] = i));

  const weekCols = [];
  let firstVisibleCol = -1;

  for (let i = 1; i < scheduleData.length; i++) {
    const row = scheduleData[i];
    const weekNum = row[scheduleIndex["#"]];
    const matchDate = new Date(row[scheduleIndex["Match Date"]]);
    const includeCols = [];

    if (row[scheduleIndex["Tues"]] === true) includeCols.push("Tues");
    if (row[scheduleIndex["Thurs"]] === true) includeCols.push("Thurs");
    if (row[scheduleIndex["1st"]] || row[scheduleIndex["2nd"]])
      includeCols.push("Sat");

    if (includeCols.length > 0) {
      const hidden = matchDate < today || matchDate > addWeeks(today, 6);
      weekCols.push({
        week: weekNum,
        cols: includeCols,
        hidden: hidden,
      });

      if (!hidden && firstVisibleCol === -1) {
        firstVisibleCol = 2;
        weekCols.forEach((w, idx) => {
          if (idx < weekCols.length - 1) {
            firstVisibleCol += w.cols.length;
          }
        });
      }
    }
  }

  // --- Step 2: Process availability data (unchanged)
  if (availabilityLatestData.length < 2) return;

  const headers = availabilityLatestData[0];
  const colIndex = buildIndex(headers);

  const players = {};
  for (let i = 1; i < availabilityLatestData.length; i++) {
    const row = availabilityLatestData[i];
    const name = row[colIndex["Name"]];
    const week = row[colIndex["#"]];
    const event = row[colIndex["Event"]];
    const available = row[colIndex["Available"]];
    const attended = row[colIndex["Attended"]];

    if (!name || !week || !event) continue;

    if (!players[name]) players[name] = {};
    if (!players[name][week]) players[name][week] = {};

    const value = getEffectiveValue(attended, available);
    players[name][week][event] = value;
  }

  // --- Step 3: Build headers (unchanged)
  const headerRow0 = ["Week"];
  const headerRow1 = ["Commencing"];
  const headerRow2 = ["Match"];
  const headerRow3 = ["Player"];

  weekCols.forEach((week) => {
    const weekLabel = `Week ${week.week}`;
    const scheduleRow = scheduleData.find(
      (row) => row[scheduleIndex["#"]] === week.week,
    );
    const wcDate = scheduleRow
      ? scheduleRow[scheduleIndex["Week commencing"]]
      : "";
    const fixture1 = scheduleRow?.[scheduleIndex["1st"]]?.trim();
    const fixture2 = scheduleRow?.[scheduleIndex["2nd"]]?.trim();

    let fixturesText = "";
    if (fixture1 && fixture2) {
      fixturesText = `1s v ${fixture1} | 2s v ${fixture2}`;
    } else if (fixture1) {
      fixturesText = `1s v ${fixture1}`;
    } else if (fixture2) {
      fixturesText = `2s v ${fixture2}`;
    }

    week.cols.forEach((col) => {
      headerRow0.push(weekLabel);
      headerRow1.push(formatDate(wcDate));
      headerRow2.push(fixturesText);
      headerRow3.push(col);
    });
  });

  // Add summary column headers
  headerRow0.push("", "");
  headerRow1.push("", "");
  headerRow2.push("Total", "");
  headerRow3.push("Training", "Games");

  // --- Step 4: Build data rows with different filtering for public vs private
  let filteredPlayerNames;

  if (isPublic) {
    // Public: Show all players who have availability data (simple sort)
    filteredPlayerNames = Object.keys(players).sort();
  } else {
    // Private: Use existing complex filtering logic
    const ss = availabilitySheet.getParent();
    const playersSheet = ss.getSheetByName(PLAYERS_SHEET_NAME);
    const playersSheetData = playersSheet.getDataRange().getValues();
    const playersSheetHeaders = playersSheetData[0];
    const playersSheetIndex = buildIndex(playersSheetHeaders);

    filteredPlayerNames = playersSheetData
      .slice(1)
      .filter((row) => {
        const name = row[playersSheetIndex["Name"]]?.toString().trim();
        if (!name) return false;
        if (!players[name]) return false;

        const isColts =
          row[playersSheetIndex["Colts"]] === true ||
          row[playersSheetIndex["Colts"]] === "TRUE";
        if (isColts) return false;

        const isUnavailable =
          row[playersSheetIndex["Unavailable"]] === true ||
          row[playersSheetIndex["Unavailable"]] === "TRUE";
        if (isUnavailable) return false;

        return true;
      })
      .map((row) => row[playersSheetIndex["Name"]].toString().trim())
      .sort();
  }

  const dataRows = filteredPlayerNames.map((name) => {
    const row = [name];
    let trainingAttended = 0;
    let gamesAvailable = 0;

    weekCols.forEach((week) => {
      const pWeek = players[name][week.week] || {};
      week.cols.forEach((col) => {
        const val = pWeek[col];
        const symbol =
          val === true || val === "true" || val === "TRUE"
            ? "✔"
            : val === false || val === "false" || val === "FALSE"
              ? "✘"
              : "";

        row.push(symbol);

        // Count for summary totals
        if (col === "Tues" || col === "Thurs") {
          if (val === true || val === "true" || val === "TRUE") {
            trainingAttended++;
          }
        } else if (col === "Sat") {
          if (val === true || val === "true" || val === "TRUE") {
            gamesAvailable++;
          }
        }
      });
    });

    row.push(trainingAttended, gamesAvailable);
    return row;
  });

  // --- Step 5: Write data and apply formatting
  const outputData = [
    headerRow0,
    headerRow1,
    headerRow2,
    headerRow3,
    ...dataRows,
  ];

  availabilitySheet.clear();

  // --- Step 6: Apply formatting - ensure this happens for BOTH public and private
  if (outputData.length > 0 && outputData[0].length > 0) {
    const totalCols = outputData[0].length;

    // Break any existing merges
    try {
      availabilitySheet.getRange(1, 1, 4, totalCols).breakApart();
    } catch (e) {
      // Ignore errors if no merges exist
    }

    // Write the data
    availabilitySheet
      .getRange(1, 1, outputData.length, outputData[0].length)
      .setValues(outputData);

    // Apply formatting (ALWAYS apply this, regardless of public/private)
    applyAvailabilityFormatting(
      availabilitySheet,
      outputData,
      weekCols,
      isPublic,
    );

    // Add filters only for private sheets
    if (includeFilters && !isPublic) {
      addAvailabilityFilters(availabilitySheet, dataRows, totalCols);
    }

    // Add charts only for private sheets
    if (includeCharts && !isPublic) {
      createAttendanceChart(availabilitySheet);
    }

    // Call updateAvailability with the isPublic flag
    updateAvailability(
      availabilityLatestData,
      scheduleData,
      availabilitySheet,
      { isPublic },
    );

    // Remove rows after maxRows for public sheets
    if (isPublic) {
      const finalLastRow = availabilitySheet.getLastRow();
      if (finalLastRow > maxRows) {
        availabilitySheet.deleteRows(maxRows + 1, finalLastRow - maxRows);
      }
    }
  }
}

// Extract formatting logic into separate function
function applyAvailabilityFormatting(
  availabilitySheet,
  outputData,
  weekCols,
  isPublic = false,
) {
  if (!outputData || outputData.length === 0 || !outputData[0]) {
    Logger.log("No output data to format");
    return;
  }

  const totalCols = outputData[0].length;
  const dataStartRow = 5;
  const COUNTS_START_ROW = 200;

  availabilitySheet
    .getRange(1, 1, 4, availabilitySheet.getMaxColumns())
    .clearFormat();

  // Calculate summary column start - ensure it's within bounds
  const summaryColStart = Math.max(1, totalCols - 1); // Ensure at least column 1

  // Validate that we have enough columns before proceeding
  if (totalCols < 2) {
    Logger.log("Not enough columns to format properly");
    return;
  }

  // Headers formatting - only format if we have data
  availabilitySheet
    .getRange(1, 1, 4, totalCols)
    .setHorizontalAlignment("right")
    .setFontFamily("PT Sans Narrow")
    .setFontWeight("bold")
    .setFontSize(10);

  // Merge header cells - only if we have enough columns
  let col = 2;
  weekCols.forEach((week) => {
    const span = week.cols.length;
    if (
      span > 1 &&
      col + span - 1 <= totalCols &&
      col + span - 1 <= summaryColStart - 1
    ) {
      try {
        availabilitySheet.getRange(1, col, 1, span).merge();
        availabilitySheet.getRange(2, col, 1, span).merge();
        availabilitySheet.getRange(3, col, 1, span).merge();
      } catch (e) {
        Logger.log(
          `Failed to merge week ${week.week} columns: ${e.toString()}`,
        );
      }
    }
    col += span;
  });

  // Merge summary header - only if we have summary columns
  if (!isPublic && summaryColStart > 0 && summaryColStart + 1 <= totalCols) {
    try {
      availabilitySheet.getRange(3, summaryColStart, 1, 2).merge();
    } catch (e) {
      Logger.log(`Failed to merge Total header: ${e.toString()}`);
    }
  }

  availabilitySheet
    .getRange(1, 1, 1, totalCols)
    .setFontFamily("PT Sans Narrow")
    .setFontSize(14)
    .setFontWeight("bold");

  availabilitySheet
    .getRange(2, 1, 2, totalCols)
    .setFontFamily("PT Sans Narrow")
    .setFontSize(10)
    .setFontWeight("bold");

  // Set alignment and other formatting - only for week data columns
  const weekDataEndCol = Math.max(summaryColStart - 1, totalCols);
  if (weekDataEndCol >= 2) {
    availabilitySheet
      .getRange(1, 2, outputData.length, weekDataEndCol - 1)
      .setHorizontalAlignment("center");
  }

  // Format summary columns - only for private sheets with summary columns
  if (!isPublic && summaryColStart <= totalCols - 1) {
    const summaryColsAvailable = Math.min(2, totalCols - summaryColStart + 1);
    if (summaryColsAvailable > 0) {
      availabilitySheet
        .getRange(1, summaryColStart, 4, summaryColsAvailable)
        .setHorizontalAlignment("center")
        .setBackground("#f0f0f0");

      availabilitySheet
        .getRange(
          dataStartRow,
          summaryColStart,
          outputData.length - 4,
          summaryColsAvailable,
        )
        .setHorizontalAlignment("center")
        .setFontFamily("Lato")
        .setFontWeight("bold")
        .setBorder(
          false,
          true,
          false,
          true,
          false,
          false,
          "black",
          SpreadsheetApp.BorderStyle.SOLID,
        );
    }
  }

  // Format player names column
  if (outputData.length > 4) {
    availabilitySheet
      .getRange(dataStartRow, 1, outputData.length - 4, 1)
      .setHorizontalAlignment("left")
      .setFontFamily("Lato");
  }

  // Set frozen rows and columns
  availabilitySheet.setFrozenRows(4);
  availabilitySheet.setFrozenColumns(1);

  // Apply conditional formatting - ensure we have valid ranges
  applyAvailabilityConditionalFormatting(
    availabilitySheet,
    summaryColStart,
    COUNTS_START_ROW,
    weekDataEndCol,
  );

  // Apply borders and other visual formatting
  applyAvailabilityBorders(
    availabilitySheet,
    weekCols,
    summaryColStart,
    COUNTS_START_ROW,
    weekDataEndCol,
  );

  // Column visibility
  col = 2;
  weekCols.forEach((week) => {
    if (col + week.cols.length - 1 <= totalCols) {
      if (week.hidden) {
        availabilitySheet.hideColumns(col, week.cols.length);
      } else {
        availabilitySheet.showColumns(col, week.cols.length);
      }
    }
    col += week.cols.length;
  });

  // Ensure summary columns are visible - only for private sheets
  if (!isPublic && summaryColStart <= totalCols - 1) {
    const summaryColsToShow = Math.min(2, totalCols - summaryColStart + 1);
    if (summaryColsToShow > 0) {
      availabilitySheet.showColumns(summaryColStart, summaryColsToShow);
    }
  }
}

// Update the conditional formatting function to accept weekDataEndCol
function applyAvailabilityConditionalFormatting(
  availabilitySheet,
  summaryColStart,
  COUNTS_START_ROW,
  weekDataEndCol = null,
) {
  const lastWeekDataCol = weekDataEndCol || summaryColStart - 1;

  if (lastWeekDataCol >= 2) {
    const weekDataRange = availabilitySheet.getRange(
      5,
      2,
      COUNTS_START_ROW - 5,
      lastWeekDataCol - 1,
    );

    availabilitySheet.clearConditionalFormatRules();

    const tickRule = SpreadsheetApp.newConditionalFormatRule()
      .whenTextEqualTo("✔")
      .setBackground("#c6efce")
      .setFontColor("#006100")
      .setRanges([weekDataRange])
      .build();

    const crossRule = SpreadsheetApp.newConditionalFormatRule()
      .whenTextEqualTo("✘")
      .setBackground("#ffc7ce")
      .setFontColor("#9c0006")
      .setRanges([weekDataRange])
      .build();

    availabilitySheet.setConditionalFormatRules([tickRule, crossRule]);
  } else {
    availabilitySheet.clearConditionalFormatRules();
  }
}

// Update the borders function to accept weekDataEndCol
function applyAvailabilityBorders(
  availabilitySheet,
  weekCols,
  summaryColStart,
  COUNTS_START_ROW,
  weekDataEndCol = null,
) {
  const lastWeekDataCol = weekDataEndCol || summaryColStart - 1;

  if (lastWeekDataCol >= 2) {
    // Add borders above and below count rows
    availabilitySheet
      .getRange(COUNTS_START_ROW, 1, 1, lastWeekDataCol)
      .setBorder(
        true,
        false,
        false,
        false,
        false,
        false,
        "black",
        SpreadsheetApp.BorderStyle.SOLID_MEDIUM,
      );

    availabilitySheet
      .getRange(COUNTS_START_ROW + 2, 1, 1, lastWeekDataCol)
      .setBorder(
        false,
        false,
        true,
        false,
        false,
        false,
        "black",
        SpreadsheetApp.BorderStyle.SOLID_MEDIUM,
      );
  }

  // Apply vertical borders for multi-column weeks
  let col = 2;
  weekCols.forEach((week) => {
    if (week.cols.length > 1 && col + week.cols.length - 1 <= lastWeekDataCol) {
      availabilitySheet
        .getRange(1, col, COUNTS_START_ROW + 2, week.cols.length)
        .setBorder(
          null,
          true,
          null,
          true,
          null,
          null,
          "black",
          SpreadsheetApp.BorderStyle.SOLID,
        );
    }
    col += week.cols.length;
  });
}

// Extract filters logic
function addAvailabilityFilters(availabilitySheet, dataRows, totalCols) {
  const existingFilter = availabilitySheet.getFilter();
  if (existingFilter) {
    existingFilter.remove();
    Utilities.sleep(100);
  }

  if (dataRows.length > 0) {
    try {
      availabilitySheet
        .getRange(4, 1, dataRows.length + 1, totalCols)
        .createFilter();
    } catch (error) {
      Logger.log(`Filter creation failed: ${error.toString()}`);
      const stillExistingFilter = availabilitySheet.getFilter();
      if (stillExistingFilter) {
        stillExistingFilter.remove();
        Utilities.sleep(200);
      }
      try {
        availabilitySheet
          .getRange(4, 1, dataRows.length + 1, totalCols)
          .createFilter();
      } catch (secondError) {
        Logger.log(`Second filter creation failed: ${secondError.toString()}`);
      }
    }
  }
}

// Update the updateAvailability function signature
function updateAvailability(
  availabilityLatestData,
  scheduleData,
  availabilitySheet,
  options = {},
) {
  const { isPublic = false } = options;

  // Only proceed with the complex logic for private sheets
  if (isPublic) {
    // For public sheets, just ensure data is properly sorted
    const dataLastRow = Math.min(199, availabilitySheet.getLastRow());
    if (dataLastRow > 4) {
      availabilitySheet
        .getRange(5, 1, dataLastRow - 4, availabilitySheet.getLastColumn())
        .sort({ column: 1, ascending: true }); // Sort by name
    }
    return; // Exit early for public sheets
  }

  // Rest of the existing updateAvailability logic for private sheets only
  const today = new Date();
  const COUNTS_START_ROW = 200; // Fixed row for counts

  // --- Step 1: Load schedule and define column structure
  const scheduleHeaders = scheduleData[0];
  const scheduleIndex = {};
  scheduleHeaders.forEach((h, i) => (scheduleIndex[h] = i));

  const weekCols = [];
  let firstVisibleCol = -1;

  for (let i = 1; i < scheduleData.length; i++) {
    const row = scheduleData[i];
    const weekNum = row[scheduleIndex["#"]];
    const matchDate = new Date(row[scheduleIndex["Match Date"]]);
    const includeCols = [];

    if (row[scheduleIndex["Tues"]] === true) includeCols.push("Tues");
    if (row[scheduleIndex["Thurs"]] === true) includeCols.push("Thurs");
    if (row[scheduleIndex["1st"]] || row[scheduleIndex["2nd"]])
      includeCols.push("Sat");

    if (includeCols.length > 0) {
      const hidden = matchDate < today || matchDate > addWeeks(today, 6);
      weekCols.push({
        week: weekNum,
        cols: includeCols,
        hidden: hidden,
      });

      if (!hidden && firstVisibleCol === -1) {
        firstVisibleCol = 2;
        weekCols.forEach((w, idx) => {
          if (idx < weekCols.length - 1) {
            firstVisibleCol += w.cols.length;
          }
        });
      }
    }
  }

  // --- Step 2: Load data from availability latest
  if (availabilityLatestData.length < 2) return; // No data

  const headers = availabilityLatestData[0];
  const colIndex = buildIndex(headers);

  const players = {};
  for (let i = 1; i < availabilityLatestData.length; i++) {
    const row = availabilityLatestData[i];
    const name = row[colIndex["Name"]];
    if (!name) continue;
    const week = row[colIndex["#"]];
    if (!week) continue;
    const event = row[colIndex["Event"]];
    if (!event) continue;

    if (!players[name]) players[name] = {};
    if (!players[name][week]) players[name][week] = {};

    players[name][week][event] = getEffectiveValue(
      row[colIndex["Attended"]],
      row[colIndex["Available"]],
    );
  }

  // --- Step 3: Get filtered players from Players sheet (exclude Colts and Unavailable)
  const ss = availabilitySheet.getParent();
  const playersSheet = ss.getSheetByName(PLAYERS_SHEET_NAME);
  const playersData = playersSheet.getDataRange().getValues();
  const playersHeaders = playersData[0];
  const playersIndex = buildIndex(playersHeaders);

  const filteredPlayerNames = playersData
    .slice(1)
    .filter((row) => {
      const name = row[playersIndex["Name"]]?.toString().trim();
      if (!name) return false;

      // Exclude Colts players
      const isColts =
        row[playersIndex["Colts"]] === true ||
        row[playersIndex["Colts"]] === "TRUE";
      if (isColts) return false;

      // Exclude long-term unavailable players
      const isUnavailable =
        row[playersIndex["Unavailable"]] === true ||
        row[playersIndex["Unavailable"]] === "TRUE";
      if (isUnavailable) return false;

      return true;
    })
    .map((row) => row[playersIndex["Name"]].toString().trim())
    .sort();

  const dataRows = filteredPlayerNames.map((name) => {
    const row = [name];
    let trainingAttended = 0; // Count of training sessions attended (Tues/Thurs)
    let gamesAvailable = 0; // Count of games available for (Sat)

    weekCols.forEach((week) => {
      const pWeek = players[name]?.[week.week] || {};

      // Find the match date for this week to determine if it's current/past
      const scheduleRow = scheduleData.find(
        (r) => r[scheduleIndex["#"]] === week.week,
      );
      const matchDate = scheduleRow
        ? new Date(scheduleRow[scheduleIndex["Match Date"]])
        : null;
      const isCurrentOrPast = matchDate
        ? matchDate <= addWeeks(today, 1)
        : false;

      week.cols.forEach((col) => {
        const val = pWeek[col];
        // Convert boolean to tick/cross symbol
        const symbol =
          val === true || val === "true" || val === "TRUE"
            ? "✔"
            : val === false || val === "false" || val === "FALSE"
              ? "✘"
              : "";

        row.push(symbol);

        // Count for summary totals - ONLY for current and previous weeks
        if (isCurrentOrPast) {
          if (col === "Tues" || col === "Thurs") {
            if (val === true || val === "true" || val === "TRUE") {
              trainingAttended++;
            }
          } else if (col === "Sat") {
            if (val === true || val === "true" || val === "TRUE") {
              gamesAvailable++;
            }
          }
        }
      });
    });

    // Add summary totals to the row
    row.push(trainingAttended, gamesAvailable);
    return row;
  });

  // --- Step 4: Calculate total columns for count rows (excluding summary columns)
  const totalCols = dataRows.length > 0 ? dataRows[0].length : 1;
  const weekDataCols = totalCols - 2; // Exclude the 2 summary columns

  // --- Step 5: Calculate response counts for each column (excluding summary)
  const countRows = [
    Array(weekDataCols).fill(""), // Available counts
    Array(weekDataCols).fill(""), // Unavailable counts
    Array(weekDataCols).fill(""), // Not responded counts
  ];

  countRows[0][0] = "Available"; // Row labels
  countRows[1][0] = "Unavailable";
  countRows[2][0] = "Not responded";

  for (let col = 1; col < weekDataCols; col++) {
    let positive = 0,
      negative = 0,
      nullCount = 0;

    dataRows.forEach((row) => {
      const val = row[col];
      if (val === "✔") positive++;
      else if (val === "✘") negative++;
      else nullCount++;
    });

    countRows[0][col] = positive;
    countRows[1][col] = negative;
    countRows[2][col] = nullCount;
  }

  // --- Step 6: Clear existing data (preserve headers in rows 1-4)
  if (availabilitySheet.getLastRow() > 4) {
    availabilitySheet
      .getRange(5, 1, COUNTS_START_ROW - 5, availabilitySheet.getLastColumn())
      .clearContent();
  }

  // --- Step 7: Write data rows and count rows to FIXED positions
  if (dataRows.length > 0) {
    const dataStartRow = 5;
    const dataEndRow = dataStartRow + dataRows.length - 1;

    try {
      // --- Step 8: Sort by first visible column - CUSTOM SORT ORDER
      if (firstVisibleCol > 0) {
        dataRows.sort((a, b) => {
          const aVal = a[firstVisibleCol - 1];
          const bVal = b[firstVisibleCol - 1];

          const getSortValue = (val) => {
            if (val === "✔") return 0;
            if (val === "✘") return 1;
            return 2;
          };

          const aSortVal = getSortValue(aVal);
          const bSortVal = getSortValue(bVal);

          if (aSortVal !== bSortVal) {
            return aSortVal - bSortVal;
          }

          return a[0].localeCompare(b[0]);
        });
      }

      // Write data rows starting at row 5
      availabilitySheet
        .getRange(dataStartRow, 1, dataRows.length, totalCols)
        .setValues(dataRows);

      // Write count rows at FIXED positions (rows 200-202) - only for week data columns
      availabilitySheet
        .getRange(COUNTS_START_ROW, 1, countRows.length, weekDataCols)
        .setValues(countRows);

      // Format count rows (rows 200-202)
      const summaryColStart = totalCols - 1; // Position of summary columns

      // Apply count rows formatting - excluding summary columns
      availabilitySheet
        .getRange(COUNTS_START_ROW, 2, 2, summaryColStart - 2)
        .setHorizontalAlignment("center")
        .setFontFamily("Lato")
        .setFontColor("white");

      // Format the third row (Not responded) separately without white font
      availabilitySheet
        .getRange(COUNTS_START_ROW + 2, 2, 1, summaryColStart - 2)
        .setHorizontalAlignment("center")
        .setFontFamily("Lato");

      availabilitySheet
        .getRange(COUNTS_START_ROW, 1, 3, 1)
        .setHorizontalAlignment("right")
        .setFontFamily("PT Sans Narrow")
        .setFontWeight("bold");

      // Add border above count rows (top border of row 200) - excluding summary
      availabilitySheet
        .getRange(COUNTS_START_ROW, 1, 1, summaryColStart - 1)
        .setBorder(
          true,
          false,
          false,
          false,
          false,
          false,
          "black",
          SpreadsheetApp.BorderStyle.SOLID_MEDIUM,
        );

      // Add border below count rows (bottom border of row 202) - excluding summary
      availabilitySheet
        .getRange(COUNTS_START_ROW + 2, 1, 1, summaryColStart - 1)
        .setBorder(
          false,
          false,
          true,
          false,
          false,
          false,
          "black",
          SpreadsheetApp.BorderStyle.SOLID_MEDIUM,
        );

      // Apply conditional formatting to count rows
      const lastWeekDataCol = summaryColStart - 1;

      if (lastWeekDataCol >= 2) {
        // Count conditional formatting (FIXED rows 200-202, excluding summary)
        const positiveCountRange = availabilitySheet.getRange(
          COUNTS_START_ROW,
          2, // Start at B200
          1, // Just one row
          lastWeekDataCol - 1, // Columns from B to the last week data column
        );

        const negativeCountRange = availabilitySheet.getRange(
          COUNTS_START_ROW + 1,
          2, // Start at B201
          1, // Just one row
          lastWeekDataCol - 1, // Columns from B to the last week data column
        );

        // Summary columns count formatting (rows 5-199, summary columns only)
        const summaryCountRange = availabilitySheet.getRange(
          5,
          summaryColStart, // Start at first summary column
          200,
          2, // Two summary columns
        );

        // Get existing rules and add count formatting rules
        const existingRules = availabilitySheet.getConditionalFormatRules();

        // Count formatting rules for week data
        const positiveRule = SpreadsheetApp.newConditionalFormatRule()
          .setGradientMaxpoint("#006100")
          .setGradientMinpoint("#c6efce")
          .setRanges([positiveCountRange])
          .build();

        const negativeRule = SpreadsheetApp.newConditionalFormatRule()
          .setGradientMaxpoint("#9c0006")
          .setGradientMinpoint("#ffc7ce")
          .setRanges([negativeCountRange])
          .build();

        // Summary columns formatting rule (neutral blue gradient)
        const summaryRule = SpreadsheetApp.newConditionalFormatRule()
          .setGradientMaxpoint("#1c4587")
          .setGradientMinpoint("#cfe2f3")
          .setRanges([summaryCountRange])
          .build();

        // Apply all rules (existing + new count rules)
        availabilitySheet.setConditionalFormatRules([
          ...existingRules,
          positiveRule,
          negativeRule,
          summaryRule,
        ]);
      }

      // --- Step 9: Hide rows between data and counts
      if (dataEndRow < COUNTS_START_ROW - 1) {
        availabilitySheet.hideRows(
          dataEndRow + 1,
          COUNTS_START_ROW - dataEndRow - 1,
        );
      }
    } catch (error) {
      Logger.log(`Error writing data: ${error.toString()}`);
    }
  }

  // --- Step 10: Manage column visibility ONLY (no formatting) - excluding summary columns
  let col = 2;
  weekCols.forEach((week) => {
    if (week.hidden) {
      availabilitySheet.hideColumns(col, week.cols.length);
    } else {
      availabilitySheet.showColumns(col, week.cols.length);
    }
    col += week.cols.length;
  });

  // Ensure summary columns are always visible
  const summaryColStart = totalCols - 2;
  availabilitySheet.showColumns(summaryColStart + 1, 2); // Show both summary columns

  // Create attendance chart
  createAttendanceChart(availabilitySheet);
}

// ========================================
// CHART CREATION
// ========================================
function createAttendanceChart(availabilitySheet) {
  const lastCol = availabilitySheet.getLastColumn();
  const today = new Date();

  // Get the data we need from the availability sheet
  const weekDatesRow = availabilitySheet
    .getRange(2, 1, 1, lastCol)
    .getValues()[0]; // Row 2: week dates
  const sessionTypesRow = availabilitySheet
    .getRange(4, 1, 1, lastCol)
    .getValues()[0]; // Row 4: Tues/Thurs/Sat
  const attendanceCountsRow = availabilitySheet
    .getRange(200, 1, 1, lastCol)
    .getValues()[0]; // Row 200: attendance counts

  // Build chart data - only include Tues/Thurs columns that should be visible
  const chartData = [["Week Commencing", "Tuesday", "Thursday"]];
  const weekData = new Map(); // weekDateStr -> {tuesday: count, thursday: count}

  let weekDate = weekDatesRow[1]; // Use the first week date as a reference
  let minCol = 0;

  // Process each column (skip first column which is player names, exclude last 2 summary columns)
  for (let col = 1; col < lastCol - 2; col++) {
    // weekDate is max of weekDate and weekDatesRow[col]
    if (weekDatesRow[col]) {
      weekDate = weekDatesRow[col];
    }

    if (weekDate > today) {
      // Skip future dates
      break;
    } else {
      minCol = col;
    } // Update minCol to the first valid column

    const sessionType = sessionTypesRow[col];
    const attendanceCount = attendanceCountsRow[col];

    // Only process Tuesday and Thursday sessions
    if (sessionType !== "Tues" && sessionType !== "Thurs") continue;

    // Skip if no valid week date or attendance count
    if (!weekDate || typeof attendanceCount !== "number") continue;

    // Format the week date for grouping
    const weekKey = formatDate(weekDate, "d MMM");

    // Initialize week data if not exists
    if (!weekData.has(weekKey)) {
      weekData.set(weekKey, {
        tuesday: 0,
        thursday: 0,
        date: new Date(weekDate),
      });
      Logger.log(`Adding new week data for ${weekKey}`);
    }

    // Store the attendance count
    const currentWeekData = weekData.get(weekKey);
    if (sessionType === "Tues") {
      currentWeekData.tuesday = attendanceCount;
    } else if (sessionType === "Thurs") {
      currentWeekData.thursday = attendanceCount;
    }

    // update weekData with currentWeekData
    weekData.set(weekKey, currentWeekData);
  }

  // Convert to array and sort by date
  const sortedWeekData = Array.from(weekData.entries())
    .map(([dateStr, data]) => ({
      dateStr: dateStr,
      date: data.date,
      tuesday: data.tuesday,
      thursday: data.thursday,
    }))
    .sort((a, b) => a.date - b.date);

  // Build the final chart data
  sortedWeekData.forEach((week) => {
    chartData.push([week.dateStr, week.tuesday, week.thursday]);
  });

  // Write chart data starting at the first visible column, row 250
  const chartDataRange = availabilitySheet.getRange(
    250,
    minCol,
    chartData.length,
    3,
  );
  chartDataRange.setValues(chartData);

  // Remove any existing charts
  availabilitySheet.getCharts().forEach((chart) => {
    availabilitySheet.removeChart(chart);
  });

  // Create the chart
  const chart = availabilitySheet
    .newChart()
    .setChartType(Charts.ChartType.COLUMN)
    .addRange(chartDataRange)
    .setPosition(205, minCol, 0, 0)
    .setNumHeaders(1)
    .setOption("title", `Training Attendance`)
    .setOption("subtitleTextStyle", {
      fontSize: 14,
      italic: true,
      color: "#444444",
      alignment: "center",
    })
    .setOption("titleTextStyle", {
      fontSize: 16,
      bold: true,
      color: "#000000",
      alignment: "center",
    })
    .setOption("width", 600)
    .setOption("height", 400)
    .setOption("hAxis", {
      title: "Week Commencing",
      titleTextStyle: { fontSize: 14, bold: true },
      textStyle: { fontSize: 12, bold: false },
      // vertical text (90 deg) for x-axis labels
      slantedText: true,
      slantedTextAngle: 90,
    })
    .setOption("vAxis", {
      title: "",
      titleTextStyle: { fontSize: 14, bold: true },
      textStyle: { fontSize: 12 },
      minValue: 10,
      slantedText: true,
      slantedTextAngle: 0,
    })
    .setOption("series", {
      0: {
        name: "Tues",
        color: "#cfe2f3", // Light blue
        targetAxisIndex: 0,
      },
      1: {
        name: "Thurs",
        color: "#1c4587", // Dark blue
        targetAxisIndex: 0,
      },
    })
    .setOption("legend", {
      // inside (top left)
      position: "in",
      alignment: "start",
      textStyle: { fontSize: 12 },
    })
    // Add trendlines
    .setOption("trendlines", {
      0: {
        type: "movingAverage",
        color: "#6fa8dc",
        lineWidth: 2,
        opacity: 0.5,
        showR2: false,
      },
      1: {
        type: "movingAverage",
        color: "#0b5394",
        lineWidth: 2,
        opacity: 0.5,
        showR2: false,
      },
    })
    .build();

  availabilitySheet.insertChart(chart);

  Logger.log(
    `Training attendance chart created with ${sortedWeekData.length} weeks`,
  );
}

// ========================================
// ATTENDANCE SYSTEM
// ========================================
function updateTrainingDateDropdown() {
  const ss = SpreadsheetApp.openById(SHEET_ID);
  const scheduleSheet = ss.getSheetByName(SCHEDULE_SHEET_NAME);
  const attendanceSheet = ss.getSheetByName(ATTENDANCE_SHEET_NAME);

  const data = scheduleSheet.getDataRange().getValues();
  const header = data[0];
  const weekCol = header.indexOf("Week commencing");
  const tuesdayCol = header.indexOf("Tues");
  const thursdayCol = header.indexOf("Thurs");

  let sessionDates = [];

  for (let i = 1; i < data.length; i++) {
    const baseDate = new Date(data[i][weekCol]);
    if (data[i][tuesdayCol]) {
      sessionDates.push(new Date(baseDate.getTime() + 1 * 86400000)); // Tuesday
    }
    if (data[i][thursdayCol]) {
      sessionDates.push(new Date(baseDate.getTime() + 3 * 86400000)); // Thursday
    }
  }

  const rule = SpreadsheetApp.newDataValidation()
    .requireValueInList(
      sessionDates.map((d) => formatDate(d)),
      true,
    )
    .build();

  attendanceSheet.getRange("B1").setDataValidation(rule);
}
function loadAttendanceSheet(
  playersSheet,
  attendanceSheet,
  availabilityLatestSheet,
) {
  const dateStr = attendanceSheet.getRange("B1").getValue();
  const targetDate = new Date(dateStr);
  const targetDateStr = formatDate(targetDate);

  // Calculate the Monday of the same week
  const dayOfWeek = targetDate.getDay(); // 0 (Sun) to 6 (Sat)
  const monday = new Date(targetDate);
  monday.setDate(targetDate.getDate() - ((dayOfWeek + 6) % 7)); // Back to Monday

  // Determine session type
  const dayDelta = (targetDate - monday) / (1000 * 60 * 60 * 24);
  const session = dayDelta === 1 ? "Tues" : dayDelta === 3 ? "Thurs" : null;

  if (!session) {
    Logger.log("Date is not a valid training session (Tues/Thurs)");
    return;
  }

  // Get availability data
  const availData = availabilityLatestSheet.getDataRange().getValues();
  const availHeaders = availData[0];
  const availColIndex = buildIndex(availHeaders);

  // Get all player names from Players sheet for validation
  const playersData = playersSheet.getDataRange().getValues();
  const playersHeaders = playersData[0];
  const nameIndex = playersHeaders.indexOf("Name");
  const allPlayerNames = playersData
    .slice(1)
    .map((row) => row[nameIndex]?.toString().trim())
    .filter((name) => name);

  // Create a Set for fast lookup of valid player names
  const validPlayerNames = new Set(allPlayerNames);

  // Calculate week commencing for the target date to match records
  const weekCommencingStr = formatDate(monday);

  // Build list of players for this session - ONLY those who are available or have attendance history
  const playersForSession = new Map(); // name -> {available, attended, hasAttendanceHistory}
  let hasAnyAttendanceHistory = false;

  // Process availability data - match by week commencing AND session type
  availData.slice(1).forEach((row) => {
    const name = row[availColIndex.Name];
    const event = row[availColIndex.Event];
    const weekCommencing = row[availColIndex["Week commencing"]];
    const available = row[availColIndex.Available];
    const attended = row[availColIndex.Attended];

    // Match by week commencing and session type instead of exact date
    if (
      name &&
      event === session &&
      formatDate(weekCommencing) === weekCommencingStr
    ) {
      // IMPORTANT: Only process players that exist in the Players sheet
      if (!validPlayerNames.has(name)) {
        Logger.log(
          `Warning: Player "${name}" from availability data not found in Players sheet - skipping`,
        );
        return;
      }

      // Check if this player has actual attendance history (not just availability)
      const hasAttendanceHistory =
        attended !== "" && attended !== null && attended !== undefined;

      if (hasAttendanceHistory) {
        hasAnyAttendanceHistory = true;
      }

      // CHANGE: Only include players who are available OR have attendance history
      const isAvailable =
        available === true || available === "true" || available === "TRUE";

      if (isAvailable || hasAttendanceHistory) {
        playersForSession.set(name, {
          available: isAvailable,
          attended: hasAttendanceHistory ? attended : false, // Only use attended if it exists
          hasAttendanceHistory: hasAttendanceHistory,
        });
      }
    }
  });

  // Convert to array and sort - prioritize available players, then attendance status
  const allPlayers = Array.from(playersForSession.entries())
    .map(([name, data]) => ({
      name,
      available: data.available,
      attended: data.attended,
      hasAttendanceHistory: data.hasAttendanceHistory,
    }))
    .sort((a, b) => {
      // Sort order: available first, then by attendance (if any history exists), then by name
      if (a.available !== b.available) return b.available - a.available; // Available first
      if (a.hasAttendanceHistory && b.hasAttendanceHistory) {
        if (a.attended !== b.attended) return b.attended - a.attended; // Then by attendance
      }
      return a.name.localeCompare(b.name); // Finally by name
    });

  // Setup fixed ranges if not already done
  setupAttendanceRanges(attendanceSheet, playersSheet);

  // Clear all name selections and checkboxes (A4:C53)
  attendanceSheet.getRange("A4:C53").clearContent();

  // Reset fixed numbers 1-50 in column A
  const numbers = Array.from({ length: 50 }, (_, i) => [i + 1]);
  attendanceSheet.getRange("A4:A53").setValues(numbers);

  // Set the player names and attendance status
  allPlayers.slice(0, 50).forEach((player, index) => {
    const row = 4 + index;
    attendanceSheet.getRange(row, 2).setValue(player.name); // Column B
    attendanceSheet.getRange(row, 3).setValue(player.attended); // Column C - only checked if actual attendance exists
  });

  // Set the E1 checkbox to indicate if attendance was previously saved
  attendanceSheet.getRange("E1").setValue(hasAnyAttendanceHistory);
}
function setupAttendanceRanges(attendanceSheet, playersSheet) {
  // Check if already setup by looking for numbers in A4
  const isAlreadySetup = attendanceSheet.getRange("A4").getValue() === 1;

  // Setup fixed numbers 1-50 in column A (only if not already done)
  if (!isAlreadySetup) {
    const numbers = Array.from({ length: 50 }, (_, i) => [i + 1]);
    attendanceSheet.getRange("A4:A53").setValues(numbers);
  }

  // Get all player names for dropdown (ALWAYS refresh this)
  const playersData = playersSheet.getDataRange().getValues();
  const playersHeaders = playersData[0];
  const nameIndex = playersHeaders.indexOf("Name");
  const allPlayerNames = playersData
    .slice(1)
    .map((row) => row[nameIndex]?.toString().trim())
    .filter((name) => name)
    .sort();

  // ALWAYS refresh dropdown validation (even if already setup)
  const dropdownRule = SpreadsheetApp.newDataValidation()
    .requireValueInList(allPlayerNames, true)
    .setAllowInvalid(false)
    .build();

  attendanceSheet.getRange("B4:B53").setDataValidation(dropdownRule);

  // Setup fixed checkboxes in C4:C53 (only if not already done)
  if (!isAlreadySetup) {
    attendanceSheet.getRange("C4:C53").insertCheckboxes();

    // Apply consistent formatting
    attendanceSheet
      .getRange("A4:C")
      .setFontFamily("Lato")
      .setHorizontalAlignment("center");
    attendanceSheet.getRange("B4:B53").setHorizontalAlignment("left");

    // Setup headers if they don't exist
    const headers = ["#", "Player", "Attended"];
    const currentHeaders = attendanceSheet.getRange("A3:C3").getValues()[0];
    if (currentHeaders[0] !== "#") {
      attendanceSheet
        .getRange("A3:C3")
        .setValues([headers])
        .setFontSize(14)
        .setBackground("black")
        .setFontColor("white")
        .setFontFamily("PT Sans Narrow")
        .setFontWeight("bold");
    }
  }
}
function updateAttendanceHistory(attendanceSh, attendanceHistorySh) {
  const dateCell = attendanceSh.getRange("B1").getValue();
  const targetDate = new Date(dateCell);
  const dateStr = formatDate(targetDate, "yyyy-MM-dd");

  // Calculate "Week commencing" (Monday of that week)
  const dow = targetDate.getDay(); // 0 (Sun) - 6 (Sat)
  const monday = new Date(targetDate);
  monday.setDate(targetDate.getDate() - ((dow + 6) % 7));
  const weekCommencingStr = formatDate(monday);

  // Determine session type and week number
  const delta = (targetDate - monday) / (1000 * 60 * 60 * 24);
  const session = delta === 1 ? "Tues" : delta === 3 ? "Thurs" : null;
  if (!session) {
    Logger.log("Date is not a valid training session (Tues/Thurs)");
    return;
  }

  // Get week number from schedule
  const ss = attendanceSh.getParent();
  const scheduleSh = ss.getSheetByName(SCHEDULE_SHEET_NAME);
  const scheduleData = scheduleSh.getDataRange().getValues();
  let weekNumber = "";

  for (let i = 1; i < scheduleData.length; i++) {
    const scheduleWeekStart = new Date(scheduleData[i][1]); // Week commencing column
    const scheduleWeekStartStr = formatDate(scheduleWeekStart);
    if (scheduleWeekStartStr === weekCommencingStr) {
      weekNumber = scheduleData[i][0]; // Week # column
      break;
    }
  }

  // Read attendance data from the fixed range A4:C53
  const attendanceRange = attendanceSh.getRange("A4:C").getValues();

  // Filter out rows with no name and create records
  const allPlayers = attendanceRange
    .map(([number, name, attended]) => ({
      name: name ? name.toString().trim() : "",
      attended: attended === true || attended === "TRUE",
    }))
    .filter((row) => row.name) // Only include rows with names
    .map((row) => [
      weekNumber, // # (column 1)
      weekCommencingStr, // Week commencing (column 2)
      row.name, // Name (column 3)
      session, // Session (column 4)
      row.attended, // Attended (column 5)
      dateStr, // Date (column 6)
      formatDate(new Date(), "yyyy-MM-dd HH:mm:ss"), // Last updated (column 7)
    ]);

  // Ensure headers exist with exactly 7 columns
  const headers = [
    "#",
    "Week commencing",
    "Name",
    "Session",
    "Attended",
    "Date",
    "Last updated",
  ];

  if (attendanceHistorySh.getLastRow() === 0) {
    attendanceHistorySh.appendRow(headers);
  }

  // Load existing data and remove records for the same date+session
  const fullData = attendanceHistorySh.getDataRange().getValues();
  const existingHeaders = fullData[0];
  const existingData = fullData.slice(1);

  const filtered = existingData.filter((row) => {
    const rowDate = formatDate(row[5], "yyyy-MM-dd"); // Date column (index 5)
    const rowSession = row[3]; // Session column (index 3)
    return !(rowDate === dateStr && rowSession === session);
  });

  // Rebuild the sheet: headers + filtered data + new data
  const newData = [...filtered, ...allPlayers];
  attendanceHistorySh.clearContents();
  attendanceHistorySh.appendRow(headers);

  if (newData.length > 0) {
    // Ensure all rows have exactly 7 columns
    const paddedData = newData.map((row) => {
      const paddedRow = Array(7).fill("");
      for (let i = 0; i < Math.min(row.length, 7); i++) {
        paddedRow[i] = row[i];
      }
      return paddedRow;
    });

    attendanceHistorySh
      .getRange(2, 1, paddedData.length, headers.length)
      .setValues(paddedData);
  }

  // Sort by date, then by name
  if (attendanceHistorySh.getLastRow() > 1) {
    attendanceHistorySh
      .getRange(2, 1, attendanceHistorySh.getLastRow() - 1, headers.length)
      .sort([
        { column: 6, ascending: true }, // Date
        { column: 3, ascending: true }, // Name
      ]);
  }

  Logger.log(
    `Attendance for ${dateStr} (${session}) saved: ${allPlayers.length} players recorded.`,
  );
}

// ========================================
// SELECTION SYSTEM
// ========================================
function buildSelection(playersData, availabilityLatestData, selectionSh) {
  const weekLabel = selectionSh.getRange("A2").getValue();
  const weekNum = parseInt(weekLabel.match(/Week (\d+)/)[1], 10);

  if (availabilityLatestData.length < 2) return;

  const availHeaders = availabilityLatestData[0];
  const playersHeaders = playersData[0];

  // Use the utility function
  const colIndex = buildIndex(availHeaders);
  const playersIndex = buildIndex(playersHeaders);

  // Simplified player map building
  const playersMap = Object.fromEntries(
    playersData
      .slice(1)
      .filter((row) => row[playersIndex.Name])
      .map((row) => [
        row[playersIndex.Name],
        {
          primaryPosition: row[playersIndex["Primary Position"]] || "",
          positions: row[playersIndex.Positions] || "",
          first: row[playersIndex["1st"]] || false,
          second: row[playersIndex["2nd"]] || false,
        },
      ]),
  );

  // Simplified availability processing
  const players = {};
  availabilityLatestData.slice(1).forEach((row) => {
    const name = row[colIndex.Name];
    const week = row[colIndex["#"]];
    const event = row[colIndex.Event];

    if (week == weekNum && name && event) {
      if (!players[name]) {
        players[name] = { Tues: false, Thurs: false, Sat: false };
      }
      players[name][event] = getEffectiveValue(
        row[colIndex.Attended],
        row[colIndex.Available],
      );
    }
  });

  // Simplified data building and sorting
  const data = Object.entries(players)
    .map(([name, availability]) => {
      const playerInfo = playersMap[name] || {};
      return [
        name,
        boolToTick(availability.Tues),
        boolToTick(availability.Thurs),
        boolToTick(availability.Sat),
        playerInfo.primaryPosition,
        playerInfo.positions,
        boolToTick(playerInfo.first),
        boolToTick(playerInfo.second),
      ];
    })
    .sort((a, b) => {
      // Multi-level sort in one compact function
      const priorities = [
        (b[3] === "✔" ? 1 : 0) - (a[3] === "✔" ? 1 : 0), // Sat (desc)
        (b[2] === "✔" ? 1 : 0) - (a[2] === "✔" ? 1 : 0), // Thurs (desc)
        (b[1] === "✔" ? 1 : 0) - (a[1] === "✔" ? 1 : 0), // Tues (desc)
        a[0].localeCompare(b[0]), // Name (asc)
      ];
      return priorities.find((p) => p !== 0) || 0;
    });

  const startRow = 5;
  const cols = 8;
  selectionSh.getRange("A5:H").clearContent();

  if (data.length) {
    const range = selectionSh.getRange(startRow, 1, data.length, cols);
    range
      .setValues(data)
      .setFontFamily("Lato")
      .setHorizontalAlignment("center");
    // Override alignment for name column
    selectionSh
      .getRange(startRow, 1, data.length, 1)
      .setHorizontalAlignment("left");
  }

  displayAvailablePlayersGrouped(
    playersData,
    availabilityLatestData,
    selectionSh,
  );
}
function updateSelectionDropdown(
  scheduleData,
  availabilityLatestData,
  selectionSheet,
) {
  // Get weeks that have availability responses
  const weeksWithResponses = new Set();
  if (availabilityLatestData.length > 1) {
    availabilityLatestData.slice(1).forEach((row) => {
      const weekNum = row[1]; // # column
      if (weekNum) {
        weeksWithResponses.add(weekNum);
      }
    });
  }

  const today = new Date();
  const scheduleHeaders = scheduleData[0];
  const schedule = [];

  // Build the dropdown options
  scheduleData.slice(1).forEach((row) => {
    const weekNum = row[0]; // # column
    const matchDate = new Date(row[scheduleHeaders.indexOf("Match Date")]);
    const firsts = row[scheduleHeaders.indexOf("1st")];
    const seconds = row[scheduleHeaders.indexOf("2nd")];

    // Only include weeks that:
    // 1. Have a match date >= today
    // 2. Have availability responses
    // 3. Have at least one game (1st or 2nd team)
    if (
      matchDate >= today &&
      weeksWithResponses.has(weekNum) &&
      (firsts || seconds)
    ) {
      let label = `Week ${weekNum}:`;
      if (firsts) label += ` 1s v ${firsts}`;
      if (seconds) label += (firsts ? ` |` : ``) + ` 2s v ${seconds}`;
      schedule.push(label);
    }
  });

  // Get current selection to preserve it if still valid
  const currentSelection = selectionSheet.getRange("A2").getValue();

  // Update the dropdown validation
  if (schedule.length > 0) {
    const validationRule = SpreadsheetApp.newDataValidation()
      .requireValueInList(schedule, true)
      .build();

    selectionSheet.getRange("A2").setDataValidation(validationRule);

    // Set the selection: keep current if valid, otherwise use first option
    if (schedule.includes(currentSelection)) {
      // Current selection is still valid, keep it
      selectionSheet.getRange("A2").setValue(currentSelection);
    } else {
      // Current selection is no longer valid, use first option
      selectionSheet.getRange("A2").setValue(schedule[0]);
    }
  } else {
    // No valid weeks, clear the dropdown and selection
    selectionSheet.getRange("A2").clearDataValidations();
    selectionSheet.getRange("A2").setValue("");
  }
}

function displayAvailablePlayersGrouped(
  playersData,
  availabilityLatestData,
  selectionSheet,
) {
  const weekLabel = selectionSheet.getRange("A2").getValue();
  const weekNum = Number(weekLabel.match(/Week (\d+)/)[1]);

  // Read availability data in long format
  if (availabilityLatestData.length < 2) return; // No data

  const headers = availabilityLatestData[0];
  const colIndex = buildIndex(headers);

  // Get players sheet data for positions and Colts status
  const playersHeaders = playersData[0];
  const playersIndex = {
    Name: playersHeaders.indexOf("Name"),
    "Primary Position": playersHeaders.indexOf("Primary Position"),
    Colts: playersHeaders.indexOf("Colts"), // Add Colts column
  };

  // Create a map of player positions and Colts status
  const playersMap = {};
  playersData.slice(1).forEach((row) => {
    const name = row[playersIndex.Name];
    if (name) {
      playersMap[name] = {
        primaryPosition: row[playersIndex["Primary Position"]] || "",
        isColts:
          row[playersIndex.Colts] === true ||
          row[playersIndex.Colts] === "TRUE", // Add Colts check
      };
    }
  });

  const allPositions = [
    "Prop",
    "Hooker",
    "Second Row",
    "Flanker",
    "Number 8",
    "Scrum Half",
    "Fly Half",
    "Centre",
    "Winger",
    "Fullback",
  ];

  const groups = {};

  // Process availability data - convert long format to player-centric format
  const players = {};

  availabilityLatestData.slice(1).forEach((row) => {
    const name = row[colIndex.Name];
    const week = row[colIndex["#"]];
    const event = row[colIndex.Event];
    const available = row[colIndex.Available];
    const attended = row[colIndex.Attended];

    if (week == weekNum && name && event) {
      if (!players[name]) {
        players[name] = {
          Tues: false,
          Thurs: false,
          Sat: false,
        };
      }
      players[name][event] = getEffectiveValue(available, attended);
    }
  });

  // Group players by position who are available for Saturday
  Object.keys(players).forEach((name) => {
    const playerAvailability = players[name];
    const playerInfo = playersMap[name] || {};
    const primary = playerInfo.primaryPosition;

    // Only include players available for Saturday
    if (playerAvailability.Sat) {
      if (!groups[primary]) groups[primary] = [];
      groups[primary].push({
        name,
        tues: playerAvailability.Tues,
        thurs: playerAvailability.Thurs,
        isColts: playerInfo.isColts, // Add Colts status to player object
      });
    }
  });

  // Clear previous content
  selectionSheet.getRange("J5:K").clearContent().clearFormat();

  // Header
  selectionSheet
    .getRange("J3:K4")
    .merge()
    .setValue("Available Players")
    .setFontSize(18)
    .setFontWeight("bold")
    .setFontFamily("PT Sans Narrow")
    .setHorizontalAlignment("center")
    .setVerticalAlignment("middle")
    .setBorder(
      true,
      true,
      true,
      true,
      false,
      false,
      "black",
      SpreadsheetApp.BorderStyle.SOLID_MEDIUM,
    );

  // Reference key format cells
  const key = {
    both: selectionSheet.getRange("M7"),
    thursOnly: selectionSheet.getRange("M8"),
    tuesOnly: selectionSheet.getRange("M9"),
    none: selectionSheet.getRange("M10"),
    colts: selectionSheet.getRange("M11"), // Add Colts key reference
  };

  const applyKeyFormat = (cell, player) => {
    const { tues, thurs, isColts } = player;

    // Check Colts first - Colts formatting takes priority
    if (isColts) {
      key.colts.copyFormatToRange(
        selectionSheet,
        cell.getColumn(),
        cell.getColumn(),
        cell.getRow(),
        cell.getRow(),
      );
    } else if (tues && thurs) {
      key.both.copyFormatToRange(
        selectionSheet,
        cell.getColumn(),
        cell.getColumn(),
        cell.getRow(),
        cell.getRow(),
      );
    } else if (thurs) {
      key.thursOnly.copyFormatToRange(
        selectionSheet,
        cell.getColumn(),
        cell.getColumn(),
        cell.getRow(),
        cell.getRow(),
      );
    } else if (tues) {
      key.tuesOnly.copyFormatToRange(
        selectionSheet,
        cell.getColumn(),
        cell.getColumn(),
        cell.getRow(),
        cell.getRow(),
      );
    } else {
      key.none.copyFormatToRange(
        selectionSheet,
        cell.getColumn(),
        cell.getColumn(),
        cell.getRow(),
        cell.getRow(),
      );
    }
  };

  let currentRow = 5;
  const positionCol = 10; // Column J
  const playersCol = 11; // Column K
  let headerColors = "#d0d0d0"; // Light grey for headers

  // Process each position in order
  allPositions.forEach((position) => {
    const playersInPosition = groups[position] || [];
    const blockHeight = Math.max(playersInPosition.length, 2); // Minimum 2 rows per position

    // Create merged position header cell spanning the block height
    const positionCell = selectionSheet.getRange(
      currentRow,
      positionCol,
      blockHeight,
      1,
    );

    // Update color for scrum half and retain for all subsequent positions
    if (position === "Scrum Half") {
      headerColors = "#f0f0f0";
    }

    positionCell
      .merge()
      .setValue(position)
      .setFontFamily("PT Sans Narrow")
      .setFontWeight("bold")
      .setFontSize(16)
      .setBackground(headerColors)
      .setHorizontalAlignment("center")
      .setVerticalAlignment("middle")
      .setBorder(
        true,
        true,
        true,
        true,
        false,
        false,
        "black",
        SpreadsheetApp.BorderStyle.SOLID,
      );

    // Fill player cells
    for (let i = 0; i < blockHeight; i++) {
      const playerRow = currentRow + i;
      const playerCell = selectionSheet.getRange(playerRow, playersCol);

      if (i < playersInPosition.length && playersInPosition[i]) {
        // Player exists for this row
        playerCell.setValue(playersInPosition[i].name);
        applyKeyFormat(playerCell, playersInPosition[i]);
      } else {
        // Empty row - set light grey background
        playerCell.setValue("").setBackground(headerColors);
      }
    }

    // Add thick border around the entire position block (both columns)
    selectionSheet
      .getRange(currentRow, positionCol, blockHeight, 2)
      .setBorder(
        true,
        true,
        true,
        true,
        false,
        false,
        "black",
        SpreadsheetApp.BorderStyle.SOLID_MEDIUM,
      );

    // Move to next position
    currentRow += blockHeight;
  });
}

// === Initialise Sheets (once only) === //
function buildSelectionLayout() {
  const ss = SpreadsheetApp.openById(SHEET_ID);

  const selectionSheet =
    ss.getSheetByName(SELECTION_SHEET_NAME) ||
    ss.insertSheet(SELECTION_SHEET_NAME);
  const scheduleSheet = ss
    .getSheetByName(SCHEDULE_SHEET_NAME)
    .getDataRange()
    .getValues();
  const availabilityLatestSheet = ss
    .getSheetByName(AVAILABILITY_LATEST_SHEET_NAME)
    .getDataRange()
    .getValues();

  const weeksWithResponses = new Set(
    availabilityLatestSheet.slice(1).map((r) => r[0]),
  ); // '#' is col A
  const today = new Date();
  const scheduleHeaders = scheduleSheet[0];

  const schedule = [];

  scheduleSheet.slice(1).forEach((row) => {
    const weekNum = row[0];
    const matchDate = new Date(row[scheduleHeaders.indexOf("Match Date")]);
    const firsts = row[scheduleHeaders.indexOf("1st")];
    const seconds = row[scheduleHeaders.indexOf("2nd")];

    if (
      matchDate >= today &&
      weeksWithResponses.has(weekNum) &&
      (firsts || seconds)
    ) {
      let label = `Week ${weekNum}:`;
      if (firsts) label += ` 1s v ${firsts}`;
      if (seconds) label += (firsts ? ` |` : ``) + ` 2s v ${seconds}`;
      schedule.push(label);
    }
  });

  selectionSheet
    .getRange("A1")
    .setValue("Select game week:")
    .setBackground("#b1b1b1");
  selectionSheet.getRange(1, 2, 1, 3).merge();
  const dd = selectionSheet.getRange("A2");
  selectionSheet.getRange(2, 2, 1, 3).merge();
  dd.setDataValidation(
    SpreadsheetApp.newDataValidation()
      .requireValueInList(schedule, true)
      .build(),
  );
  dd.setValue(schedule[0]);
  dd.setFontSize(14);

  const borderRange = selectionSheet.getRange("A1:A2");
  borderRange.setBorder(
    true,
    true,
    true,
    true,
    true,
    false,
    "black",
    SpreadsheetApp.BorderStyle.SOLID_THICK,
  );

  const headers = [
    "Name",
    "Tues",
    "Thurs",
    "Sat",
    "Primary Position",
    "Positions",
    "1st",
    "2nd",
  ];
  selectionSheet
    .getRange(4, 1, 1, headers.length)
    .setValues([headers])
    .setFontSize(14)
    .setBackground("black")
    .setFontColor("white");
  selectionSheet.getRange(4, headers.length - 1, 1, 1).setBackground("#1c4587");
  selectionSheet
    .getRange(4, headers.length, 1, 1)
    .setBackground("white")
    .setFontColor("black");
  selectionSheet
    .getRange(1, 1, 4, headers.length)
    .setFontFamily("PT Sans Narrow");
  selectionSheet.getRange(2, 1, 3, headers.length).setFontWeight("bold");

  const ruleTick = SpreadsheetApp.newConditionalFormatRule()
    .whenTextEqualTo("✔")
    .setBackground("#c6efce") // light green
    .setFontColor("#006100") // dark green
    .setRanges([selectionSheet.getRange("B5:D")])
    .build();

  const ruleCross = SpreadsheetApp.newConditionalFormatRule()
    .whenTextEqualTo("✘")
    .setBackground("#ffc7ce") // light red
    .setFontColor("#9c0006") // dark red
    .setRanges([selectionSheet.getRange("B5:D")])
    .build();

  selectionSheet.clearConditionalFormatRules();
  selectionSheet.setConditionalFormatRules([ruleTick, ruleCross]);

  // Make header row sortable (filter)
  const lastCol = headers.length;
  // Clear existing filters to avoid stacking
  if (selectionSheet.getFilter()) selectionSheet.getFilter().remove();
  selectionSheet.getRange(4, 1, 1, lastCol).createFilter();

  selectionSheet.setFrozenRows(4);
  selectionSheet.setFrozenColumns(4);
}
