A list of desired features for the webpage being developed in this repo (index.html)

# Tabular data

- League tables 
  - for each squad each season
  - extracted from englandrugby.com with a web scraper using the squad- and season-specific league IDs
- Season results
  - games played/won/lost/drawn for each squad each season, split by home and away games
  - filterable by game type (league, cup, friendly)
  - extracted from game data extracted from googlesheets and built into a local database
- Squad metrics
  - players per squad each season
  - filterable by position (forwards, backs, etc.)
  - extracted from player data extracted from googlesheets and built into a local database
- Player profiles
  - Individual player selection showing their photo (if available), position, sponsor (if available) and key stats:
    - appearance breakdown by season/squad/position
    - total appearances
    - first (1st team, if applicable) appearance
    - lineout performance (if applicable)

# Graphical data

- League-only data:
  - League position (and league) over time 
    - both squads shown on the same graph for comparison
  - League results grid
    - showing the results of each game in a grid format, with color coding for wins/losses/draws
    - filterable by season/squad
  - League Squad analysis
    - retention/squad size of all clubs in league, with comparison over seasons
    - filterable by season/squad and position (forwards/backs/total)
- Squad-level data:
  - Results over time
    - each game with ranged bar chart showing margin/outcome of the game, with games ordered chronologically
    - filterable by season/squad/game type
  - Player appearances
    - filterable by season/squad/position, showing the number of appearances for each player in a bar chart format  
  - Team sheets
    - showing the team sheets for each game, with player names and positions, filterable by season/squad/game type, in chronological order
    - highlight all of a player's appearances with a click
- Video analysis
  - Set piece performance
    - per game, showing the number of successful/unsuccessful set pieces (lineouts/scrums) for each squad and their opposition, filterable by season/squad/game type
  - Average set piece performance over time
    - showing the average number of successful/unsuccessful set pieces (lineouts/scrums) over a whole season for each squad and their opposition, filterable by season/squad/game type, in a line graph format 
  - Red zone efficiency
    - New statistic recorded in google sheets alongside scrum and lineout for the 1st team (set piece results)
    - Average points scored per red zone entry, and comparison with opposition per game and over a season
  - Lineout analysis:
    - Further breakdown of lineout performance by area, thrower, jumper, call etc.
    - Comparison of individual and team metrics over time
  
# UI features

- Landing page with:
  - links to different sections of the site (league tables, season results, squad metrics, player profiles, graphical data)
  - Navigation bar for easy access to different sections of the site
  - Headline stats for current season - league tables, games played/won/lost/drawn, top players by appearances, etc.
- Data filters/selectors:
  - Unobtrusive (can be hidden when not needed)
  - Bespoke to the data being displayed (e.g. a league table can only apply to a single season, so no "All" option, and it cannot be filtered by player position, so do not include that option)
  - Intuitive URLs to specific data views (e.g. /league-tables/2023-2024, /player-profiles/john-doe)
- Responsive design for mobile and desktop viewing
- Consistent styling and branding across the site