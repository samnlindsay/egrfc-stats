(function () {
    let performanceStatsAnalysisRailInitialised = false;

    function initialisePerformanceStatsAnalysisRail() {
        if (performanceStatsAnalysisRailInitialised || typeof initialiseAnalysisRail !== 'function') {
            return;
        }
        performanceStatsAnalysisRailInitialised = initialiseAnalysisRail({
            railId: 'performanceStatsAnalysisRail',
        });
    }

    document.addEventListener('DOMContentLoaded', () => {
        initialisePerformanceStatsAnalysisRail();
    });
})();
