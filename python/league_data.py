import requests
import os
from bs4 import BeautifulSoup
import json
import pandas as pd

url = 'https://www.englandrugby.com/fixtures-and-results/search-results?competition=261&season=2024-2025&division=56612#results'
response = requests.get(url)

# find all <a> tags with a link containing '/fixtures-and-results/match-centre-community'
soup = BeautifulSoup(response.text, 'html.parser')
links = [a['href'] for a in soup.find_all('a', href=True) if '/fixtures-and-results/match-centre-community' in a['href']]

ids = [link.split("=")[-1] for link in links]

with open('data/match_ids.json', 'w') as f:
    json.dump(ids, f)

def get_players(soup):

    numbers = soup.find_all(class_='c085-lineup-table-player-number')
    numbers = [number.text.strip() for number in numbers]

    players = soup.find_all(class_='c085-lineup-table-player-name-text')
    players = [player.text.strip() for player in players]
    players = list(dict.fromkeys(players))
    
    split_index = len(numbers) - numbers[::-1].index('15') - 1
    
    home_players = {n:" ".join(p.split()) for n,p in zip(numbers[:split_index], players[:split_index])}
    away_players = {n:" ".join(p.split()) for n,p in zip(numbers[split_index:], players[split_index:])}

    return [home_players, away_players]

def get_match_info(id):

    url = f'https://www.englandrugby.com/fixtures-and-results/match-centre-community?matchId={id}#lineup'
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')

    score = soup.find(class_='c042-match-score')
    if score is None:
        return None
    
    score = [int(s) for s in score.text.strip().split(' - ')]

    date = soup.find(id='c042-event-date').text.strip()
    date = date[:date.rfind('202') + 4]
    date = pd.to_datetime(date, format="%A %d %B %Y").strftime("%Y-%m-%d")

    teams = [team.text.strip() for team in soup.find_all(class_='c042-team-name')]

    logos = [img['src'] for img in soup.find_all('img', class_='c042-team-logo')]

    players = get_players(soup)

    match_data = {
        "date": date,
        "score": score,
        "teams": teams,
        "logos": logos,
        "players": players
    }   

    # Save to json
    with open(f'data/match_data/{id}.json', 'w') as f:
        json.dump(match_data, f)

    return {
        "date": date,
        "score": score,
        "teams": teams,
        "logos": logos,
        "players": players
    }

for id in ids:
    if not os.path.exists(f'data/match_data/{id}.json'):
        get_match_info(id)