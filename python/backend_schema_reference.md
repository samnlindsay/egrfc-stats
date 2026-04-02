# Backend Schema Reference

Generated from data/egrfc_backend.duckdb on 2026-04-01.

This document includes every base table with full column schema, plus a description and usage note.

Total tables: 25

## `games`

- Description: Canonical match register, one row per EGRFC game.
- Usage: Primary frontend match table and join anchor for appearances, set piece, and summaries.
- Primary key: `game_id`

| Column | Type | Nullable | Default |
|---|---|---|---|
| `game_id` | `VARCHAR` | `NO` | `` |
| `squad` | `VARCHAR` | `NO` | `` |
| `date` | `DATE` | `NO` | `` |
| `season` | `VARCHAR` | `YES` | `` |
| `competition` | `VARCHAR` | `YES` | `` |
| `game_type` | `VARCHAR` | `YES` | `` |
| `opposition` | `VARCHAR` | `YES` | `` |
| `home_away` | `VARCHAR` | `YES` | `` |
| `score_for` | `INTEGER` | `YES` | `` |
| `score_against` | `INTEGER` | `YES` | `` |
| `result` | `VARCHAR` | `YES` | `` |
| `captain` | `VARCHAR` | `YES` | `` |
| `motm` | `VARCHAR` | `YES` | `` |
| `vice_captain_1` | `VARCHAR` | `YES` | `` |
| `vice_captain_2` | `VARCHAR` | `YES` | `` |
| `tries_scorers` | `VARCHAR` | `YES` | `` |
| `conversions_scorers` | `VARCHAR` | `YES` | `` |
| `penalties_scorers` | `VARCHAR` | `YES` | `` |
| `drop_goals_scorers` | `VARCHAR` | `YES` | `` |
| `pitchero_match_url` | `VARCHAR` | `YES` | `` |

## `games_rfu`

- Description: RFU consolidated match records.
- Usage: Source for RFU continuity/squad-size derived views.
- Primary key: `match_id`

| Column | Type | Nullable | Default |
|---|---|---|---|
| `match_id` | `VARCHAR` | `NO` | `` |
| `season` | `VARCHAR` | `NO` | `` |
| `league` | `VARCHAR` | `YES` | `` |
| `tracked_squad` | `VARCHAR` | `YES` | `` |
| `date` | `DATE` | `NO` | `` |
| `home_team` | `VARCHAR` | `NO` | `` |
| `away_team` | `VARCHAR` | `NO` | `` |
| `home_score` | `INTEGER` | `YES` | `` |
| `away_score` | `INTEGER` | `YES` | `` |
| `home_walkover` | `BOOLEAN` | `YES` | `` |
| `away_walkover` | `BOOLEAN` | `YES` | `` |
| `lineup_available_home` | `BOOLEAN` | `YES` | `` |
| `lineup_available_away` | `BOOLEAN` | `YES` | `` |

## `lineouts`

- Description: Canonical attacking lineout events.
- Usage: Used for lineout performance analysis and charts.
- Primary key: `squad`, `date`, `seq_id`

| Column | Type | Nullable | Default |
|---|---|---|---|
| `squad` | `VARCHAR` | `NO` | `` |
| `date` | `DATE` | `NO` | `` |
| `seq_id` | `INTEGER` | `NO` | `` |
| `half` | `VARCHAR` | `YES` | `` |
| `numbers` | `VARCHAR` | `YES` | `` |
| `call` | `VARCHAR` | `YES` | `` |
| `call_type` | `VARCHAR` | `YES` | `` |
| `dummy` | `BOOLEAN` | `YES` | `` |
| `area` | `VARCHAR` | `YES` | `` |
| `drive` | `BOOLEAN` | `YES` | `` |
| `crusaders` | `BOOLEAN` | `YES` | `` |
| `transfer` | `BOOLEAN` | `YES` | `` |
| `flyby` | `BOOLEAN` | `YES` | `` |
| `thrower` | `VARCHAR` | `YES` | `` |
| `jumper` | `VARCHAR` | `YES` | `` |
| `won` | `BOOLEAN` | `YES` | `` |
| `game_id` | `VARCHAR` | `YES` | `` |
| `season` | `VARCHAR` | `YES` | `` |
| `opposition` | `VARCHAR` | `YES` | `` |

## `pitchero_appearance_backfill`

- Description: Positive-delta reconciliation rows indicating synthetic appearance backfill counts.
- Usage: Audit trail for backfilled appearance adjustments in canonical player_appearances.
- Primary key: `squad`, `season`, `player_join`

| Column | Type | Nullable | Default |
|---|---|---|---|
| `squad` | `VARCHAR` | `NO` | `` |
| `season` | `VARCHAR` | `NO` | `` |
| `player_join` | `VARCHAR` | `NO` | `` |
| `player` | `VARCHAR` | `YES` | `` |
| `missing_appearances` | `INTEGER` | `YES` | `` |
| `applied_fix` | `BOOLEAN` | `YES` | `` |

## `pitchero_appearance_reconciliation`

- Description: Comparison of historic Pitchero appearance totals vs scraped/merged appearance counts.
- Usage: Used for QA diagnostics and determining backfill requirements.
- Primary key: `squad`, `season`, `player_join`

| Column | Type | Nullable | Default |
|---|---|---|---|
| `squad` | `VARCHAR` | `NO` | `` |
| `season` | `VARCHAR` | `NO` | `` |
| `player_join` | `VARCHAR` | `NO` | `` |
| `player` | `VARCHAR` | `YES` | `` |
| `pitchero_appearances` | `INTEGER` | `YES` | `` |
| `scraped_appearances` | `INTEGER` | `YES` | `` |
| `delta` | `INTEGER` | `YES` | `` |
| `abs_delta` | `INTEGER` | `YES` | `` |
| `status` | `VARCHAR` | `YES` | `` |
| `fix_type` | `VARCHAR` | `YES` | `` |

## `pitchero_games_clean`

- Description: Cleaned historic Pitchero game records after opposition/name canonicalization.
- Usage: Merge-ready Pitchero game staging used to build canonical games.
- Primary key: `game_id`

| Column | Type | Nullable | Default |
|---|---|---|---|
| `game_id` | `VARCHAR` | `NO` | `` |
| `date` | `DATE` | `YES` | `` |
| `season` | `VARCHAR` | `YES` | `` |
| `squad` | `VARCHAR` | `YES` | `` |
| `competition` | `VARCHAR` | `YES` | `` |
| `game_type` | `VARCHAR` | `YES` | `` |
| `opposition` | `VARCHAR` | `YES` | `` |
| `home_away` | `VARCHAR` | `YES` | `` |
| `pf` | `INTEGER` | `YES` | `` |
| `pa` | `INTEGER` | `YES` | `` |
| `result` | `VARCHAR` | `YES` | `` |
| `margin` | `INTEGER` | `YES` | `` |
| `captain` | `VARCHAR` | `YES` | `` |
| `motm` | `VARCHAR` | `YES` | `` |
| `vc1` | `VARCHAR` | `YES` | `` |
| `vc2` | `VARCHAR` | `YES` | `` |
| `tries_scorers` | `VARCHAR` | `YES` | `` |
| `conversions_scorers` | `VARCHAR` | `YES` | `` |
| `penalties_scorers` | `VARCHAR` | `YES` | `` |
| `drop_goals_scorers` | `VARCHAR` | `YES` | `` |
| `pitchero_match_url` | `VARCHAR` | `YES` | `` |

## `pitchero_games_raw`

- Description: Raw historic Pitchero game extraction records.
- Usage: Staging input to pitchero_games_clean and audit views; preserves source-level fields.
- Primary key: `game_id`

| Column | Type | Nullable | Default |
|---|---|---|---|
| `game_id` | `VARCHAR` | `NO` | `` |
| `date` | `DATE` | `YES` | `` |
| `season` | `VARCHAR` | `YES` | `` |
| `squad` | `VARCHAR` | `YES` | `` |
| `competition` | `VARCHAR` | `YES` | `` |
| `game_type` | `VARCHAR` | `YES` | `` |
| `opposition` | `VARCHAR` | `YES` | `` |
| `home_away` | `VARCHAR` | `YES` | `` |
| `pf` | `INTEGER` | `YES` | `` |
| `pa` | `INTEGER` | `YES` | `` |
| `result` | `VARCHAR` | `YES` | `` |
| `margin` | `INTEGER` | `YES` | `` |
| `captain` | `VARCHAR` | `YES` | `` |
| `motm` | `VARCHAR` | `YES` | `` |
| `vc1` | `VARCHAR` | `YES` | `` |
| `vc2` | `VARCHAR` | `YES` | `` |
| `tries_scorers` | `VARCHAR` | `YES` | `` |
| `conversions_scorers` | `VARCHAR` | `YES` | `` |
| `penalties_scorers` | `VARCHAR` | `YES` | `` |
| `drop_goals_scorers` | `VARCHAR` | `YES` | `` |
| `pitchero_match_url` | `VARCHAR` | `YES` | `` |

## `pitchero_player_appearances_clean`

- Description: Cleaned historic Pitchero lineup appearance records with canonicalized names.
- Usage: Merge-ready Pitchero appearance staging used to build canonical player_appearances.
- Primary key: `appearance_id`

| Column | Type | Nullable | Default |
|---|---|---|---|
| `appearance_id` | `VARCHAR` | `NO` | `` |
| `game_id` | `VARCHAR` | `YES` | `` |
| `player` | `VARCHAR` | `YES` | `` |
| `shirt_number` | `INTEGER` | `YES` | `` |
| `position` | `VARCHAR` | `YES` | `` |
| `position_group` | `VARCHAR` | `YES` | `` |
| `unit` | `VARCHAR` | `YES` | `` |
| `is_starter` | `BOOLEAN` | `YES` | `` |
| `is_captain` | `BOOLEAN` | `YES` | `` |
| `is_vc` | `BOOLEAN` | `YES` | `` |
| `player_join` | `VARCHAR` | `YES` | `` |

## `pitchero_player_appearances_raw`

- Description: Raw historic Pitchero lineup appearance records.
- Usage: Staging input to pitchero_player_appearances_clean and cleaning audits.
- Primary key: `appearance_id`

| Column | Type | Nullable | Default |
|---|---|---|---|
| `appearance_id` | `VARCHAR` | `NO` | `` |
| `game_id` | `VARCHAR` | `YES` | `` |
| `player` | `VARCHAR` | `YES` | `` |
| `shirt_number` | `INTEGER` | `YES` | `` |
| `position` | `VARCHAR` | `YES` | `` |
| `position_group` | `VARCHAR` | `YES` | `` |
| `unit` | `VARCHAR` | `YES` | `` |
| `is_starter` | `BOOLEAN` | `YES` | `` |
| `is_captain` | `BOOLEAN` | `YES` | `` |
| `is_vc` | `BOOLEAN` | `YES` | `` |
| `player_join` | `VARCHAR` | `YES` | `` |

## `pitchero_stats_clean`

- Description: Cleaned Pitchero season-player event stats after sanitation/filtering.
- Usage: Used for season_scorers and pitchero_appearance_reconciliation construction.
- Primary key: none declared

| Column | Type | Nullable | Default |
|---|---|---|---|
| `season` | `VARCHAR` | `YES` | `` |
| `squad` | `VARCHAR` | `YES` | `` |
| `player_join` | `VARCHAR` | `YES` | `` |
| `appearances` | `INTEGER` | `YES` | `` |
| `event` | `VARCHAR` | `YES` | `` |
| `count` | `INTEGER` | `YES` | `` |

## `pitchero_stats_raw`

- Description: Raw Pitchero season-player event stats (appearances and scorer events).
- Usage: Staging input to pitchero_stats_clean and stats cleaning audits.
- Primary key: none declared

| Column | Type | Nullable | Default |
|---|---|---|---|
| `season` | `VARCHAR` | `YES` | `` |
| `squad` | `VARCHAR` | `YES` | `` |
| `player_join` | `VARCHAR` | `YES` | `` |
| `appearances` | `INTEGER` | `YES` | `` |
| `event` | `VARCHAR` | `YES` | `` |
| `count` | `INTEGER` | `YES` | `` |

## `player_appearances`

- Description: Canonical player-match appearances, one row per player per game (plus backfill rows where flagged).
- Usage: Primary frontend appearance table for profiles, squad stats, and season analytics.
- Primary key: `squad`, `date`, `player`

| Column | Type | Nullable | Default |
|---|---|---|---|
| `squad` | `VARCHAR` | `NO` | `` |
| `date` | `DATE` | `NO` | `` |
| `player` | `VARCHAR` | `NO` | `` |
| `number` | `INTEGER` | `YES` | `` |
| `position` | `VARCHAR` | `YES` | `` |
| `unit` | `VARCHAR` | `YES` | `` |
| `is_captain` | `BOOLEAN` | `YES` | `` |
| `is_vice_captain` | `BOOLEAN` | `YES` | `` |
| `game_id` | `VARCHAR` | `YES` | `` |
| `season` | `VARCHAR` | `YES` | `` |
| `game_type` | `VARCHAR` | `YES` | `` |
| `is_starter` | `BOOLEAN` | `YES` | `` |
| `is_backfill` | `BOOLEAN` | `YES` | `CAST('f' AS BOOLEAN)` |
| `club_appearance_number` | `INTEGER` | `YES` | `` |
| `first_xv_appearance_number` | `INTEGER` | `YES` | `` |

## `player_appearances_rfu`

- Description: RFU lineup appearances by match/team/player.
- Usage: Source for RFU retention and lineup coverage derived views.
- Primary key: `match_id`, `team`, `player`

| Column | Type | Nullable | Default |
|---|---|---|---|
| `match_id` | `VARCHAR` | `NO` | `` |
| `season` | `VARCHAR` | `NO` | `` |
| `league` | `VARCHAR` | `YES` | `` |
| `tracked_squad` | `VARCHAR` | `YES` | `` |
| `date` | `DATE` | `NO` | `` |
| `team` | `VARCHAR` | `NO` | `` |
| `opposition` | `VARCHAR` | `YES` | `` |
| `home_away` | `VARCHAR` | `YES` | `` |
| `player` | `VARCHAR` | `NO` | `` |
| `shirt_number` | `INTEGER` | `YES` | `` |
| `position` | `VARCHAR` | `YES` | `` |
| `unit` | `VARCHAR` | `YES` | `` |
| `is_starter` | `BOOLEAN` | `YES` | `` |
| `previous_match_id` | `VARCHAR` | `YES` | `` |
| `played_previous_game` | `BOOLEAN` | `YES` | `` |

## `player_profiles_canonical`

- Description: Canonical deduplicated profile payload per player.
- Usage: Primary player-profiles frontend dataset.
- Primary key: `name`

| Column | Type | Nullable | Default |
|---|---|---|---|
| `name` | `VARCHAR` | `NO` | `` |
| `short_name` | `VARCHAR` | `YES` | `` |
| `squad` | `VARCHAR` | `YES` | `` |
| `position` | `VARCHAR` | `YES` | `` |
| `photo_url` | `VARCHAR` | `YES` | `` |
| `sponsor` | `VARCHAR` | `YES` | `` |
| `totalAppearances` | `INTEGER` | `YES` | `` |
| `totalStarts` | `INTEGER` | `YES` | `` |
| `firstXVAppearances` | `INTEGER` | `YES` | `` |
| `firstXVStarts` | `INTEGER` | `YES` | `` |
| `seasonAppearances` | `INTEGER` | `YES` | `` |
| `seasonStarts` | `INTEGER` | `YES` | `` |
| `seasonCompetitiveAppearances` | `INTEGER` | `YES` | `` |
| `scoringCareer` | `VARCHAR` | `YES` | `` |
| `scoringThisSeason` | `VARCHAR` | `YES` | `` |
| `debutOverall` | `VARCHAR` | `YES` | `` |
| `debutFirstXV` | `VARCHAR` | `YES` | `` |
| `hasDifferentFirstXVDebut` | `BOOLEAN` | `YES` | `` |
| `otherPositions` | `VARCHAR` | `YES` | `` |
| `isActive` | `BOOLEAN` | `YES` | `` |
| `lastAppearanceDate` | `DATE` | `YES` | `` |

## `players`

- Description: Canonical player master and career aggregate metrics.
- Usage: Used by profile pages and canonical player exports.
- Primary key: `name`

| Column | Type | Nullable | Default |
|---|---|---|---|
| `name` | `VARCHAR` | `NO` | `` |
| `short_name` | `VARCHAR` | `YES` | `` |
| `position` | `VARCHAR` | `YES` | `` |
| `squad` | `VARCHAR` | `YES` | `` |
| `first_appearance_date` | `DATE` | `YES` | `` |
| `first_appearance_squad` | `VARCHAR` | `YES` | `` |
| `first_appearance_opposition` | `VARCHAR` | `YES` | `` |
| `photo_url` | `VARCHAR` | `YES` | `` |
| `sponsor` | `VARCHAR` | `YES` | `` |
| `total_appearances` | `INTEGER` | `YES` | `` |
| `total_starts` | `INTEGER` | `YES` | `` |
| `total_captaincies` | `INTEGER` | `YES` | `` |
| `total_vc_appointments` | `INTEGER` | `YES` | `` |
| `total_lineouts_jumped` | `INTEGER` | `YES` | `` |
| `lineouts_won_as_jumper` | `INTEGER` | `YES` | `` |
| `career_points` | `BIGINT` | `YES` | `` |

## `ref_pitchero_match_url_overrides`

- Description: Reference table for manual Pitchero match URL overrides keyed by canonical game_id.
- Usage: Used by enrichment/reconciliation workflows to fill missing or corrected match URLs.
- Primary key: `game_id`

| Column | Type | Nullable | Default |
|---|---|---|---|
| `game_id` | `VARCHAR` | `NO` | `` |
| `pitchero_match_url` | `VARCHAR` | `NO` | `` |

## `ref_pitchero_opposition_overrides`

- Description: Reference overrides mapping normalized opposition keys to canonical opposition names.
- Usage: Used during Pitchero game cleaning so opposition values align with Google Sheets naming.
- Primary key: `opposition_key`

| Column | Type | Nullable | Default |
|---|---|---|---|
| `opposition_key` | `VARCHAR` | `NO` | `` |
| `canonical_opposition` | `VARCHAR` | `NO` | `` |

## `ref_pitchero_player_name_overrides`

- Description: Reference overrides mapping Pitchero player display names to canonical names.
- Usage: Used during Pitchero cleaning to standardize player naming before merges and reconciliation.
- Primary key: `pitchero_name`

| Column | Type | Nullable | Default |
|---|---|---|---|
| `pitchero_name` | `VARCHAR` | `NO` | `` |
| `canonical_name` | `VARCHAR` | `NO` | `` |

## `season_scorers`

- Description: Canonical seasonal scoring aggregates by squad/player/game_type.
- Usage: Used in player profiles and season summary top-scorer calculations.
- Primary key: `squad`, `season`, `player`, `game_type`

| Column | Type | Nullable | Default |
|---|---|---|---|
| `squad` | `VARCHAR` | `NO` | `` |
| `season` | `VARCHAR` | `NO` | `` |
| `player` | `VARCHAR` | `NO` | `` |
| `game_type` | `VARCHAR` | `NO` | `` |
| `tries` | `BIGINT` | `YES` | `` |
| `conversions` | `BIGINT` | `YES` | `` |
| `penalties` | `BIGINT` | `YES` | `` |
| `drop_goals` | `BIGINT` | `YES` | `` |
| `points` | `BIGINT` | `YES` | `` |
| `source` | `VARCHAR` | `YES` | `` |

## `season_summary_enriched`

- Description: Pre-aggregated season summary metrics by season/gameTypeMode/squad.
- Usage: Frontend season-summary and red-zone trend source.
- Primary key: `season`, `gameTypeMode`, `squad`

| Column | Type | Nullable | Default |
|---|---|---|---|
| `season` | `VARCHAR` | `NO` | `` |
| `gameTypeMode` | `VARCHAR` | `NO` | `` |
| `squad` | `VARCHAR` | `NO` | `` |
| `gamesPlayed` | `INTEGER` | `YES` | `` |
| `gamesWon` | `INTEGER` | `YES` | `` |
| `gamesLost` | `INTEGER` | `YES` | `` |
| `gamesDrawn` | `INTEGER` | `YES` | `` |
| `avgPointsForHome` | `DOUBLE` | `YES` | `` |
| `avgPointsAgainstHome` | `DOUBLE` | `YES` | `` |
| `avgPointsForAway` | `DOUBLE` | `YES` | `` |
| `avgPointsAgainstAway` | `DOUBLE` | `YES` | `` |
| `avgPointsForOverall` | `DOUBLE` | `YES` | `` |
| `avgPointsAgainstOverall` | `DOUBLE` | `YES` | `` |
| `topPointScorerValue` | `BIGINT` | `YES` | `` |
| `topPointScorerPlayers` | `VARCHAR` | `YES` | `` |
| `topTryScorerValue` | `BIGINT` | `YES` | `` |
| `topTryScorerPlayers` | `VARCHAR` | `YES` | `` |
| `topAppearanceValue` | `INTEGER` | `YES` | `` |
| `topAppearancePlayers` | `VARCHAR` | `YES` | `` |
| `avgLineoutSuccessRate` | `DOUBLE` | `YES` | `` |
| `avgScrumSuccessRate` | `DOUBLE` | `YES` | `` |
| `avgPointsPer22mEntry` | `DOUBLE` | `YES` | `` |
| `avgTriesPer22mEntry` | `DOUBLE` | `YES` | `` |
| `gamesWithSetPieceData` | `INTEGER` | `YES` | `` |

## `set_piece`

- Description: Canonical per-team-per-game set piece and red-zone metrics.
- Usage: Used for scrum/lineout success and red-zone season summaries.
- Primary key: `squad`, `date`, `team`

| Column | Type | Nullable | Default |
|---|---|---|---|
| `squad` | `VARCHAR` | `NO` | `` |
| `date` | `DATE` | `NO` | `` |
| `team` | `VARCHAR` | `NO` | `` |
| `lineouts_won` | `INTEGER` | `YES` | `` |
| `lineouts_total` | `INTEGER` | `YES` | `` |
| `lineouts_success_rate` | `DOUBLE` | `YES` | `` |
| `scrums_won` | `INTEGER` | `YES` | `` |
| `scrums_total` | `INTEGER` | `YES` | `` |
| `scrums_success_rate` | `DOUBLE` | `YES` | `` |
| `entries_22m` | `INTEGER` | `YES` | `` |
| `points` | `INTEGER` | `YES` | `` |
| `tries` | `INTEGER` | `YES` | `` |
| `points_per_entry` | `DOUBLE` | `YES` | `` |
| `tries_per_entry` | `DOUBLE` | `YES` | `` |
| `game_id` | `VARCHAR` | `YES` | `` |
| `season` | `VARCHAR` | `YES` | `` |
| `opposition` | `VARCHAR` | `YES` | `` |

## `squad_continuity_enriched`

- Description: Pre-aggregated retained-starter continuity metrics.
- Usage: Frontend squad-stats continuity source.
- Primary key: `season`, `gameTypeMode`, `squad`, `unit`

| Column | Type | Nullable | Default |
|---|---|---|---|
| `season` | `VARCHAR` | `NO` | `` |
| `gameTypeMode` | `VARCHAR` | `NO` | `` |
| `squad` | `VARCHAR` | `NO` | `` |
| `unit` | `VARCHAR` | `NO` | `` |
| `retained` | `DOUBLE` | `YES` | `` |
| `gamePairs` | `INTEGER` | `YES` | `` |

## `squad_position_profiles_enriched`

- Description: Pre-aggregated starter usage by canonical position.
- Usage: Frontend squad-stats position profile source.
- Primary key: `season`, `gameTypeMode`, `squad`, `position`

| Column | Type | Nullable | Default |
|---|---|---|---|
| `season` | `VARCHAR` | `NO` | `` |
| `gameTypeMode` | `VARCHAR` | `NO` | `` |
| `squad` | `VARCHAR` | `NO` | `` |
| `position` | `VARCHAR` | `NO` | `` |
| `playerCounts` | `VARCHAR` | `YES` | `` |
| `playersUsed` | `INTEGER` | `YES` | `` |

## `squad_stats_enriched`

- Description: Pre-aggregated squad usage metrics by season/gameTypeMode/squad/unit.
- Usage: Frontend squad-stats source for players-used cards and counts.
- Primary key: `season`, `gameTypeMode`, `squad`, `unit`

| Column | Type | Nullable | Default |
|---|---|---|---|
| `season` | `VARCHAR` | `NO` | `` |
| `gameTypeMode` | `VARCHAR` | `NO` | `` |
| `squad` | `VARCHAR` | `NO` | `` |
| `unit` | `VARCHAR` | `NO` | `` |
| `playerCounts` | `VARCHAR` | `YES` | `` |
| `playersUsed` | `INTEGER` | `YES` | `` |

## `squad_stats_with_thresholds_enriched`

- Description: Precomputed thresholded player-count metrics across minimum appearance cutoffs.
- Usage: Frontend squad-stats threshold filtering source.
- Primary key: `season`, `gameTypeMode`, `squad`, `unit`, `minimumAppearances`

| Column | Type | Nullable | Default |
|---|---|---|---|
| `season` | `VARCHAR` | `NO` | `` |
| `gameTypeMode` | `VARCHAR` | `NO` | `` |
| `squad` | `VARCHAR` | `NO` | `` |
| `unit` | `VARCHAR` | `NO` | `` |
| `minimumAppearances` | `INTEGER` | `NO` | `` |
| `playerCount` | `INTEGER` | `YES` | `` |
| `totalPlayed` | `INTEGER` | `YES` | `` |

