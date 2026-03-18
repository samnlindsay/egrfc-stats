This document serves as a current data inventory for the EGRFC stats project, outlining the various data sources, types of data collected, and how they are processed and visualized. It is intended to provide a comprehensive overview of the data landscape for the project, including both tabular and graphical data, as well as the UI features that will be built on top of this data.

# Data sources

## Google Sheets Data 

EG Stats workbook (gid: 1206624226)

| Sheet name | Description |
| --- | --- |
| 25/26 Scorers | Point scorers for all games in the 25/26 season, with points breakdown by type (try, conversion, penalty, drop goal) - required because this data stopped being recorded on Pitchero after the 24/25 season |
| 1st XV Players / 2nd XV Players | Main source of game data, including date, opposition, game type, and team sheet (one column per shirt number 1-18+) including captain and vice captain |
| 1st XV Set piece / 2nd XV Set piece | Set piece performance per game (where available), including lineout and scrum success rates, and red zone entries and points scored from red zone entries |
| 1st XV Lineouts / 2nd XV Lineouts | Individual attacking lineout records, including number of players in the lineout, the calls made, the thrower and jumper, and the outcome of the lineout |

### 25/26 Scorers

| Column ID | Column name (row 1) | Description |
| --- | --- | --- |
| B | Squad | "1st" or "2nd" |
| C | Date | Date of the game (YYYY-MM-DD) |
| D | Opposition | Name of the opposing team |
| E | Score | Score type ("Try", "Con", "Pen") |
| F | Player | Name of the player who scored |
| G | Points | Number of points scored from the score type in column E (e.g. 5 for a try, 2 for a conversion, 3 for a penalty) |

### 1st XV Players / 2nd XV Players

| Column ID | Column name (row 4) | Description |
| --- | --- | --- |
| A | Date | Date of the game (YYYY-MM-DD) |
| B | Season | Season of the game (e.g. 2025/26) |
| C | Competition | Competition name (or "Friendly") |
| D | Opposition | Name of the opposing team and home/away status (e.g. "Team A (H)" or "Team B (A)") |
| E | Score | Final score of the game, home team first (e.g. "20 - 15") |
| F | Captain | Name of the team captain for the game |
| G | Vice Captain | Name of the team vice captain for the game |
| H | Vice Captain | Name of the team vice captain for the game (if more than one) |
| I (1st XV) / J (2nd XV) and onwards | 1, 2, 3... | Player names for each shirt number (1-15 for starting players, 16-18+ for substitutes) |

### 1st XV Set piece / 2nd XV Set piece

Columns Y-AH (Red zone efficiency) are new columns added in the 25/26 season, for 1st XV only so far.

| Column ID | Column name (row 3 and 4) | Description |
| --- | --- | --- |
| B | Season | Season of the game (e.g. 2025/26) |
| C | Date | Date of the game (YYYY-MM-DD) |
| D | Opposition | Name of the opposing team |
| E | H/A | Home or away game ("H" for home, "A" for away) |
| F | PF | Points scored by EGRFC in the game |
| G | PA | Points scored by the opposition in the game |
| H | PD | Points difference (PF - PA) |
| I | East Grinstead: Won | Lineouts won by EGRFC |
| J | East Grinstead: Total | Total lineouts for EGRFC |
| K | East Grinstead: % | Lineout success rate for EGRFC (Won / Total) |
| L | Opposition: Won | Lineouts won by the opposition |
| M | Opposition: Total | Total lineouts for the opposition |
| N | Opposition: % | Lineout success rate for the opposition (Won / Total) |
| O | Overall: Total | Total lineouts in the game (EGRFC + opposition) |
| P | Overall: Net gain | Net gain/loss of lineouts for EGRFC (lost by opposition - lost by EGRFC) |
| Q | East Grinstead: Won | Scrums won by EGRFC |
| R | East Grinstead: Total | Total scrums for EGRFC |
| S | East Grinstead: % | Scrum success rate for EGRFC (Won / Total) |
| T | Opposition: Won | Scrums won by the opposition |
| U | Opposition: Total | Total scrums for the opposition |
| V | Opposition: % | Scrum success rate for the opposition (Won / Total) |
| W | Overall: Total | Total scrums in the game (EGRFC + opposition) |
| X | Overall: Net gain | Net gain/loss of scrums for EGRFC (lost by opposition - lost by EGRFC) |
| Y | East Grinstead: 22m Entries | Number of times EGRFC entered the opposition 22m |
| Z | East Grinstead: Pts per visit | Average points scored by EGRFC per opposition 22m entry (PF / 22m Entries) |
| AA | East Grinstead: Tries | Number of tries scored by EGRFC |
| AB | East Grinstead: Try rate | Try scoring rate for EGRFC per opposition 22m entry (Tries / 22m Entries) |
| AC | Opposition: 22m Entries | Number of times the opposition entered EGRFC's 22m |
| AD | Opposition: Pts per visit | Average points scored by the opposition per EGRFC 22m entry (PA / 22m Entries) |
| AE | Opposition: Tries | Number of tries scored by the opposition |
| AF | Opposition: Try rate | Try scoring rate for the opposition per EGRFC 22m entry (Tries / 22m Entries) |
| AG | Difference: 22m Entries | Difference in 22m entries (EGRFC - opposition) |
| AH | Difference: Pts per visit | Difference in points per 22m entry (EGRFC - opposition) |


### 1st XV Lineouts / 2nd XV Lineouts

| Column ID | Column name (row 3) | Description |
| --- | --- | --- |
| A | # | Sequence number per gamee (1 to N, where N is the total number of attackinglineouts in the game) |
| B | Half | First or second half of the game ("1" or "2") |
| C | Season | Season of the game (e.g. 2025/26) |
| D | Date | Date of the game (YYYY-MM-DD) |
| E | Opposition | Name of the opposing team |
| F | Numbers | Number of players in the lineout (e.g. 4, 5, 7) |
| G | Call | Call made for the lineout (various formats, e.g. "", "*", "2+", "C2", "Snap") |
| H | Dummy | Whether the call includes a dummy jump ("x" (TRUE) or empty) |
| I | Front | Whether the lineout is at the front of the line ("x" (TRUE) or empty) |
| J | Middle | Whether the lineout is in the middle of the line ("x" (TRUE) or empty) |
| K | Back | Whether the lineout is at the back of the line ("x" (TRUE) or empty) |
| L | Drive | Whether the lineout is mauled ("x" (TRUE) or empty) |
| M | Crusaders | Whether a Crusaders play is run ("x" (TRUE) or empty) |
| N | Transfer | Whether a "Transfer" is made ("x" (TRUE) or empty) |
| O | Flyby | Whether a "Flyby" is made ("1", "2" or empty) |
| P | Hooker | Name of the player throwing in for the lineout |
| Q | Jumper | Name of the player jumping for the lineout |
| R | Won | Outcome of the lineout ("Y" for won by EGRFC, "N" for lost by EGRFC) |


## Pitchero data

End-of-season stats tables for 1st and 2nd XV squads, extracted from the Pitchero website using a web scraper. These tables include player names, and various performance metrics (e.g. appearances, tries scored, etc.) for each season.

--- 

| Column name | Description |
| --- | --- |
|TABLE | Player name (initial and surname, e.g. "J Smith") |
| A | Appearances |
| ON | _not needed_ |
| Off | _not needed_ |
| T | Tries scored |
| Con | Conversions scored |
| PK | Penalties scored |
| DG | Drop goals scored |
| YC | Yellow cards received |
| RC | Red cards received |
| Pla | _not needed_ |
| PT | _not needed_ |
| TA | _not needed_ |

## RFU data

League tables and individual game results and other data including those for other clubs in the same league, extracted from the RFU website using a web scraper. This data is used to provide context and comparison for EGRFC's performance in the league.

This data is extracted by python/league_data.py for league stats only.

# Derived database tables

All of the tables below should be easily joinable with each other using the primary keys.

## `games` (Primary key: squad + date)

A summary of each game played by EGRFC, with key details about the game and the team sheet.

| Column name | Description |
| --- | --- |
| squad | "1st" or "2nd" |
| date | Date of the game (YYYY-MM-DD) |
| season | Season of the game (e.g. 2025/26) |
| competition | Competition name (or "Friendly") |
| opposition | Name of the opposing team |
| home_away | Home or away game ("H" for home, "A" for away) |
| score_for | Points scored by EGRFC in the game |
| score_against | Points scored by the opposition in the game |
| captain | Name of the team captain for the game |
| vice_captain_1 | Name of the team vice captain for the game (if applicable) |
| vice_captain_2 | Name of the team vice captain for the game (if applicable) |
| game_type | Type of the game ("League", "Cup", "Friendly") |

## `set_piece` (Primary key: squad + date)

A summary of set piece performance for each game (one row per game), including lineout and scrum success rates, and red zone efficiency (for 1st XV 2025/26 season only so far).

| Column name | Description |
| --- | --- |
| squad | "1st" or "2nd" |
| date | Date of the game (YYYY-MM-DD) |
| team | "EGRFC" or "Opposition" |
| lineouts_won | Lineouts won |
| lineouts_total | Total lineouts |
| lineouts_success_rate | Lineout success rate (lineouts_won / lineouts_total) |
| scrums_won | Scrums won |
| scrums_total | Total scrums |
| scrums_success_rate | Scrum success rate (scrums_won / scrums_total) |
| 22m_entries | Number of entries into the opposition 22m |
| points_per_22m_entry | Average points scored per opposition 22m entry (points_for / 22m_entries) |
| tries_per_22m_entry | Try scoring rate per opposition 22m entry (tries_for / 22m_entries) |

## `lineouts` (Primary key: squad + date + seq_id)

This is a slight restructuring of the lineout data from the google sheets, with some additional processing to create new columns for call type and area of the lineout based on the existing columns. This will allow for more detailed analysis of lineout performance by different factors.

| Column name | Description |
| --- | --- |
| squad | "1st" or "2nd" |
| date | Date of the game (YYYY-MM-DD) |
| seq_id | Sequence number per game (1 to N, where N is the total number of attacking lineouts in the game) |
| half | First or second half of the game ("1" or "2") |
| numbers | Number of players in the lineout (e.g. 4, 5, 7) |
| call | Call made for the lineout (various formats, e.g. "", "*", "2+", "C2", "Snap") |
| call_type | Type of call based on the call column (based on mapping of calls to call types) |
| dummy | Whether the call includes a dummy jump ("x" (TRUE) or empty) |
| area | Area of the lineout (Front/Middle/Back) |
| drive | Whether the lineout is mauled (True or False) |
| crusaders | Whether a Crusaders play is run (True or False) |
| transfer | Whether a "Transfer" is made (True or False) |
| flyby | Whether a "Flyby" is made (True or False) |
| thrower | Name of the player throwing in for the lineout |
| jumper | Name of the player jumping for the lineout |
| won | Outcome of the lineout (True for won, False for lost) |

## `player_appearances` (Primary key: squad + date + player)

This table contains one row per player per appearance in a game, with the shirt number and position for that game. This allows for detailed analysis of player appearances over time, including position changes, captaincy, and other factors.

| Column name | Description |
| --- | --- |
| squad | "1st" or "2nd" |
| date | Date of the game (YYYY-MM-DD) |
| player | Player name (full name, e.g. "John Smith") |
| number | Shirt number for the game (1-15 for starting players, 16-18+ for substitutes) |
| position | Position corresponding to the number (e.g. "Prop", "Centre", "Bench" etc.) |
| unit | Player position group (e.g. "Forwards", "Backs", etc.) |
| is_captain | Whether the player was captain for the game (True or False) |
| is_vice_captain | Whether the player was vice captain for the game (True or False) |

## `season_scorers` (Primary key: squad + season + player)

This will need to be built from the 25/26 Scorers sheet combined with historical data from the Pitchero tables for previous seasons. The 25/26 season scorers data will be used as the source of truth for that season, and the Pitchero data will be used for previous seasons, with some cleaning and processing to ensure consistency in player names and other details.

| Column name | Description |
| --- | --- |
| squad | "1st" or "2nd" |
| season | Season of the game (e.g. 2025/26) |
| player | Player name (full name, e.g. "John Smith") |
| tries | Total tries scored by the player in the season |
| conversions | Total conversions scored by the player in the season |
| penalties | Total penalties scored by the player in the season |
| points | Total points scored by the player in the season (calculated from tries, conversions, penalties, and drop goals) |

## `players` (Primary key: name)

One summary row per player, with all useful individual-level data that is not specific to a particular game or season. 

| Column name | Description |
| --- | --- |
| name | Player name (full name, e.g. "John Smith") |
| short_name | Player name in short format (e.g. "John S") |
| position | Player most common position (e.g. "Prop", "Centre", etc.) |
| squad | Most common squad ("1st" or "2nd" or "Both" if no clear majority) |
| first_appearance_date | Date of the player's first appearance for EGRFC (YYYY-MM-DD) |
| first_appearance_squad | Squad of the player's first appearance for EGRFC ("1st" or "2nd") |
| first_appearance_opposition | Opposition team for the player's first appearance for EGRFC |
| photo_url | URL of the player's photo (if available) |
| sponsor | Player's sponsor (if available) |