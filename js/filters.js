// Safely update selectpicker (from test.html)
// Helper function to safely update a selectpicker
function safeUpdateSelectpicker(selector, updateFunction) {
  const $element = $(selector);

  // Store the current value before update
  const currentValue = $element.val();

  // Apply the update function to modify options
  updateFunction($element);

  // Get the new value after update
  const newValue = $element.val();

  // Return whether the value changed
  return JSON.stringify(currentValue) !== JSON.stringify(newValue);
}

// Filter management (extracted from test.html)
const Filters = {
  // Apply filters to chart spec
  applyFilters(
    spec,
    applyBenchFilter = true,
    applyPositionFilter = true,
    applyCompetitionFilter = true
  ) {
    const filters = [];

    // Squad filter
    const selectedSquad = document.querySelector(
      '.btn-check[name="squadRadio"]:checked'
    );
    if (selectedSquad && selectedSquad.value && selectedSquad.value !== "") {
      filters.push(`datum.squad == '${selectedSquad.value}'`);
    }

    // Season filter
    const selectedSeasons = $("#seasonSelect").val();
    if (selectedSeasons && selectedSeasons.length > 0) {
      filters.push(
        `indexof(${JSON.stringify(selectedSeasons)}, datum.season) >= 0`
      );
    }

    // Position filter
    if (applyPositionFilter) {
      const selectedPositions = $("#positionSelect").val() || [];
      if (selectedPositions && selectedPositions.length > 0) {
        filters.push(
          `indexof(${JSON.stringify(selectedPositions)}, datum.position) >= 0`
        );
      }
    }

    // Competition filter
    if (applyCompetitionFilter) {
      const gameTypeCheckboxes = document.querySelectorAll(
        'input[name="gameTypeCheck"]:checked'
      );
      if (gameTypeCheckboxes.length > 0) {
        const selectedTypes = Array.from(gameTypeCheckboxes).map(
          (cb) => cb.value
        );
        filters.push(
          `(indexof(${JSON.stringify(
            selectedTypes
          )}, datum.game_type) >= 0 || datum.game_type == null || datum.game_type == '')`
        );
      }
    }

    // Bench filter
    if (
      applyBenchFilter &&
      !document.getElementById("includeBenchSwitch").checked
    ) {
      filters.push(`datum.is_starter == true`);
    }

    // Apply filters to spec
    spec.transform = spec.transform || [];
    spec.transform = spec.transform.filter((t) => !t._externalFilter);

    if (filters.length > 0) {
      const combinedFilter = filters.join(" && ");
      spec.transform.push({
        filter: combinedFilter,
        _externalFilter: true,
      });
    }

    return filters;
  },

  // Apply tab-specific logic (extracted from test.html)
  applyTabSpecificLogic(tabId) {
    console.log("Applying tab-specific logic for:", tabId);

    let needsRerender = false;

    if (tabId === "team-sheets-tab") {
      // Enable positions
      $("#positionSelect").prop("disabled", false);

      // Handle season restrictions
      const selectedSeasons = $("#seasonSelect").val() || [];
      const newSeasons = selectedSeasons.filter(
        (season) => season >= "2021/22"
      );

      const seasonChanged = safeUpdateSelectpicker(
        "#seasonSelect",
        function ($select) {
          $select.find("option").each(function () {
            const seasonValue = $(this).val();
            if (seasonValue < "2021/22" && seasonValue !== "2020/21") {
              $(this).prop("disabled", true);
            } else if (seasonValue !== "2020/21") {
              $(this).prop("disabled", false);
            }
          });

          if (newSeasons.length !== selectedSeasons.length) {
            $select.val(newSeasons);
            needsRerender = true;
          }
        }
      );

      safeUpdateSelectpicker("#positionSelect", function ($select) {
        // Position select doesn't need option changes, just enable
      });

      document.getElementById("includeBenchSwitch").disabled = false;
    } else if (tabId === "player-stats-tab") {
      if (currentPlayerStatsType === "appearances") {
        const selectedSeasons = $("#seasonSelect").val() || [];
        const hasOldSeasons =
          selectedSeasons &&
          selectedSeasons.some((season) => season < "2021/22");

        safeUpdateSelectpicker("#seasonSelect", function ($select) {
          $select.find("option").each(function () {
            if ($(this).val() !== "2020/21") {
              $(this).prop("disabled", false);
            }
          });
        });

        if (!hasOldSeasons) {
          $("#positionSelect").prop("disabled", false);
          document.getElementById("includeBenchSwitch").disabled = false;
          safeUpdateSelectpicker("#positionSelect", function ($select) {
            // No changes needed, just refresh
          });
        } else {
          const positionChanged = safeUpdateSelectpicker(
            "#positionSelect",
            function ($select) {
              $select.val([]).prop("disabled", true);
            }
          );
          if (positionChanged) needsRerender = true;
          document.getElementById("includeBenchSwitch").checked = true;
          document.getElementById("includeBenchSwitch").disabled = true;
        }
      } else if (currentPlayerStatsType === "captains") {
        const selectedSeasons = $("#seasonSelect").val() || [];
        const newSeasons = selectedSeasons.filter(
          (season) => season >= "2021/22"
        );

        const positionChanged = safeUpdateSelectpicker(
          "#positionSelect",
          function ($select) {
            $select.val([]).prop("disabled", true);
          }
        );
        if (positionChanged) needsRerender = true;

        const seasonChanged = safeUpdateSelectpicker(
          "#seasonSelect",
          function ($select) {
            $select.find("option").each(function () {
              const seasonValue = $(this).val();
              if (seasonValue < "2021/22" && seasonValue !== "2020/21") {
                $(this).prop("disabled", true);
              } else if (seasonValue !== "2020/21") {
                $(this).prop("disabled", false);
              }
            });

            if (newSeasons.length !== selectedSeasons.length) {
              $select.val(newSeasons);
              needsRerender = true;
            }
          }
        );

        document.getElementById("includeBenchSwitch").checked = true;
        document.getElementById("includeBenchSwitch").disabled = true;
      } else if (
        currentPlayerStatsType === "point-scorers" ||
        currentPlayerStatsType === "cards"
      ) {
        const positionChanged = safeUpdateSelectpicker(
          "#positionSelect",
          function ($select) {
            $select.val([]).prop("disabled", true);
          }
        );
        if (positionChanged) needsRerender = true;

        safeUpdateSelectpicker("#seasonSelect", function ($select) {
          $select.find("option").each(function () {
            if ($(this).val() !== "2020/21") {
              $(this).prop("disabled", false);
            }
          });
        });

        document.getElementById("includeBenchSwitch").checked = true;
        document.getElementById("includeBenchSwitch").disabled = true;
      }
    } else if (tabId === "results-tab" || tabId === "set-piece-tab") {
      const positionChanged = safeUpdateSelectpicker(
        "#positionSelect",
        function ($select) {
          $select.val([]).prop("disabled", true);
        }
      );
      if (positionChanged) needsRerender = true;

      safeUpdateSelectpicker("#seasonSelect", function ($select) {
        $select.find("option").each(function () {
          if ($(this).val() !== "2020/21") {
            $(this).prop("disabled", false);
          }
        });
      });

      document.getElementById("includeBenchSwitch").checked = true;
      document.getElementById("includeBenchSwitch").disabled = true;
    }

    return needsRerender;
  },
};
