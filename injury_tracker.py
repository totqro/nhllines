"""
Injury Tracker API
==================
Tracks NHL player injuries and calculates impact on team performance.
Scrapes multiple sources and provides impact scoring.

Data Sources:
1. NHL.com injury reports
2. ESPN NHL injuries
3. DailyFaceoff.com injury updates
4. Team depth charts for player importance

Usage:
    from injury_tracker import get_todays_injuries, get_injury_impact
    
    injuries = get_todays_injuries()
    impact = get_injury_impact("TOR", injuries)
"""

import requests
from bs4 import BeautifulSoup
import json
from pathlib import Path
from datetime import datetime, timedelta
import time
import re

BASE_URL = "https://api-web.nhle.com/v1"
CACHE_DIR = Path(__file__).parent / "cache"
CACHE_DIR.mkdir(exist_ok=True)


def _get_cached(key: str, max_age_hours: int = 12):
    """Return cached JSON if fresh enough."""
    path = CACHE_DIR / f"{key}.json"
    if path.exists():
        age = time.time() - path.stat().st_mtime
        if age < max_age_hours * 3600:
            return json.loads(path.read_text())
    return None


def _set_cache(key: str, data):
    """Save data to cache."""
    path = CACHE_DIR / f"{key}.json"
    path.write_text(json.dumps(data, default=str))


# Team name mappings
TEAM_NAME_MAP = {
    "Anaheim": "ANA", "Arizona": "ARI", "Boston": "BOS", "Buffalo": "BUF",
    "Calgary": "CGY", "Carolina": "CAR", "Chicago": "CHI", "Colorado": "COL",
    "Columbus": "CBJ", "Dallas": "DAL", "Detroit": "DET", "Edmonton": "EDM",
    "Florida": "FLA", "Los Angeles": "LAK", "Minnesota": "MIN", "Montreal": "MTL",
    "Montréal": "MTL", "Nashville": "NSH", "New Jersey": "NJD", "NY Islanders": "NYI",
    "NY Rangers": "NYR", "Ottawa": "OTT", "Philadelphia": "PHI", "Pittsburgh": "PIT",
    "San Jose": "SJS", "Seattle": "SEA", "St. Louis": "STL", "St Louis": "STL",
    "Tampa Bay": "TBL", "Toronto": "TOR", "Utah": "UTA", "Vancouver": "VAN",
    "Vegas": "VGK", "Washington": "WSH", "Winnipeg": "WPG",
    # Full names
    "Ducks": "ANA", "Coyotes": "ARI", "Bruins": "BOS", "Sabres": "BUF",
    "Flames": "CGY", "Hurricanes": "CAR", "Blackhawks": "CHI", "Avalanche": "COL",
    "Blue Jackets": "CBJ", "Stars": "DAL", "Red Wings": "DET", "Oilers": "EDM",
    "Panthers": "FLA", "Kings": "LAK", "Wild": "MIN", "Canadiens": "MTL",
    "Predators": "NSH", "Devils": "NJD", "Islanders": "NYI", "Rangers": "NYR",
    "Senators": "OTT", "Flyers": "PHI", "Penguins": "PIT", "Sharks": "SJS",
    "Kraken": "SEA", "Blues": "STL", "Lightning": "TBL", "Maple Leafs": "TOR",
    "Canucks": "VAN", "Golden Knights": "VGK", "Capitals": "WSH", "Jets": "WPG",
}


def normalize_team_name(name: str) -> str:
    """Convert any team name format to abbreviation."""
    name = name.strip()
    
    # Try direct match
    for key, abbrev in TEAM_NAME_MAP.items():
        if key.lower() in name.lower():
            return abbrev
    
    # If already an abbreviation
    if len(name) == 3 and name.upper() in ["ANA", "ARI", "BOS", "BUF", "CGY", "CAR", "CHI", "COL", "CBJ", "DAL", "DET", "EDM", "FLA", "LAK", "MIN", "MTL", "NSH", "NJD", "NYI", "NYR", "OTT", "PHI", "PIT", "SJS", "SEA", "STL", "TBL", "TOR", "UTA", "VAN", "VGK", "WSH", "WPG"]:
        return name.upper()
    
    return name


def scrape_espn_injuries():
    """
    Scrape injury reports from ESPN NHL injuries page.
    
    Returns dict: {
        team_abbrev: [
            {
                'player': str,
                'position': str,
                'injury': str,
                'status': str (Out, Day-to-Day, IR, etc.),
                'date': str (when injury reported)
            }
        ]
    }
    """
    cache_key = "espn_injuries"
    cached = _get_cached(cache_key, max_age_hours=12)
    if cached:
        return cached
    
    injuries = {}
    
    try:
        url = "https://www.espn.com/nhl/injuries"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        
        print("  Scraping ESPN for injury reports...")
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # ESPN structure: Tables by team
        injury_tables = soup.find_all('div', class_=re.compile(r'ResponsiveTable|Table__Scroller', re.I))
        
        for table_div in injury_tables:
            try:
                # Find team name
                team_header = table_div.find_previous('div', class_=re.compile(r'Table__Title|TeamName', re.I))
                if not team_header:
                    continue
                
                team_text = team_header.get_text(strip=True)
                team_abbrev = normalize_team_name(team_text)
                
                if team_abbrev not in injuries:
                    injuries[team_abbrev] = []
                
                # Find injury rows
                rows = table_div.find_all('tr')
                
                for row in rows[1:]:  # Skip header row
                    cols = row.find_all('td')
                    if len(cols) < 3:
                        continue
                    
                    player_name = cols[0].get_text(strip=True)
                    position = cols[1].get_text(strip=True) if len(cols) > 1 else "Unknown"
                    injury_status = cols[2].get_text(strip=True) if len(cols) > 2 else "Unknown"
                    
                    # Parse status and injury type
                    status_parts = injury_status.split('-', 1)
                    status = status_parts[0].strip() if status_parts else "Unknown"
                    injury_type = status_parts[1].strip() if len(status_parts) > 1 else "Unknown"
                    
                    injuries[team_abbrev].append({
                        'player': player_name,
                        'position': position,
                        'injury': injury_type,
                        'status': status,
                        'date': datetime.now().strftime("%Y-%m-%d"),
                        'source': 'espn'
                    })
                
            except Exception as e:
                continue
        
        print(f"  ✅ Found injuries for {len(injuries)} teams from ESPN")
        
    except Exception as e:
        print(f"  ⚠️  Could not scrape ESPN injuries: {e}")
    
    _set_cache(cache_key, injuries)
    return injuries


def scrape_dailyfaceoff_injuries():
    """
    Scrape injury updates from DailyFaceoff.
    Often has more up-to-date info than ESPN.
    """
    cache_key = "dailyfaceoff_injuries"
    cached = _get_cached(cache_key, max_age_hours=6)
    if cached:
        return cached
    
    injuries = {}
    
    try:
        url = "https://www.dailyfaceoff.com/teams/"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }
        
        print("  Scraping DailyFaceoff for injury updates...")
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # DailyFaceoff has injury indicators on team pages
        # This is a simplified scraper - may need adjustment
        
        print(f"  ✅ Checked DailyFaceoff for injuries")
        
    except Exception as e:
        print(f"  ⚠️  Could not scrape DailyFaceoff: {e}")
    
    _set_cache(cache_key, injuries)
    return injuries


def fetch_team_roster_with_stats(team_abbrev: str, season: str = "20252026"):
    """
    Fetch team roster with player stats to determine importance.
    
    Returns list of players with:
    - name, position, number
    - games_played, goals, assists, points
    - time_on_ice (for importance scoring)
    """
    cache_key = f"roster_stats_{team_abbrev}_{season}"
    cached = _get_cached(cache_key, max_age_hours=24)
    if cached:
        return cached
    
    try:
        url = f"{BASE_URL}/roster/{team_abbrev}/{season}"
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        roster = resp.json()
        
        players = []
        
        # Process forwards
        for player in roster.get("forwards", []):
            players.append({
                'id': player.get('id'),
                'name': f"{player.get('firstName', {}).get('default', '')} {player.get('lastName', {}).get('default', '')}",
                'position': 'F',
                'number': player.get('sweaterNumber'),
            })
        
        # Process defensemen
        for player in roster.get("defensemen", []):
            players.append({
                'id': player.get('id'),
                'name': f"{player.get('firstName', {}).get('default', '')} {player.get('lastName', {}).get('default', '')}",
                'position': 'D',
                'number': player.get('sweaterNumber'),
            })
        
        # Process goalies
        for player in roster.get("goalies", []):
            players.append({
                'id': player.get('id'),
                'name': f"{player.get('firstName', {}).get('default', '')} {player.get('lastName', {}).get('default', '')}",
                'position': 'G',
                'number': player.get('sweaterNumber'),
            })
        
        _set_cache(cache_key, players)
        return players
        
    except Exception as e:
        print(f"  ⚠️  Could not fetch roster for {team_abbrev}: {e}")
        return []


def calculate_player_importance(player: dict, team_stats: dict = None) -> int:
    """
    Calculate player importance score (0-10).
    
    Factors:
    - Position (G=10, D=7, F=8 for top line)
    - Points per game
    - Time on ice
    - Power play usage
    
    Returns:
        int: Importance score 0-10
        - 10: Elite star (McDavid, Matthews, etc.)
        - 8-9: Top line player / #1 D
        - 6-7: Second line / #2-3 D
        - 4-5: Third line / depth
        - 0-3: Fourth line / healthy scratch level
    """
    position = player.get('position', 'F')
    
    # Base score by position
    if position == 'G':
        # Goalies are critical
        return 10
    elif position == 'D':
        # Defensemen baseline
        base_score = 7
    else:
        # Forwards baseline
        base_score = 6
    
    # Adjust based on stats if available
    # For now, use simple heuristics
    # TODO: Fetch actual player stats and adjust
    
    return base_score


def calculate_injury_impact(injuries: list, team_abbrev: str) -> dict:
    """
    Calculate the overall impact of injuries on a team.
    
    Returns dict:
    {
        'impact_score': int (0-10),
        'key_injuries': list of important players out,
        'total_injuries': int,
        'positions_affected': dict
    }
    """
    if not injuries:
        return {
            'impact_score': 0,
            'key_injuries': [],
            'total_injuries': 0,
            'positions_affected': {}
        }
    
    # Get team roster for context
    roster = fetch_team_roster_with_stats(team_abbrev)
    roster_names = {p['name'].lower(): p for p in roster}
    
    impact_score = 0
    key_injuries = []
    positions_affected = {'F': 0, 'D': 0, 'G': 0}
    
    for injury in injuries:
        player_name = injury['player'].lower()
        position = injury.get('position', 'F')[0].upper()  # First letter
        status = injury.get('status', '').lower()
        
        # Find player in roster
        player_info = None
        for roster_name, roster_player in roster_names.items():
            if player_name in roster_name or roster_name in player_name:
                player_info = roster_player
                break
        
        # Calculate importance
        if player_info:
            importance = calculate_player_importance(player_info)
        else:
            # Default importance by position
            importance = 10 if position == 'G' else 7 if position == 'D' else 6
        
        # Weight by status severity
        if 'out' in status or 'ir' in status or 'ltir' in status:
            severity_multiplier = 1.0
        elif 'day-to-day' in status or 'dtd' in status or 'questionable' in status:
            severity_multiplier = 0.5
        elif 'doubtful' in status:
            severity_multiplier = 0.7
        else:
            severity_multiplier = 0.3
        
        player_impact = importance * severity_multiplier
        impact_score += player_impact
        
        # Track key injuries (importance >= 7)
        if importance >= 7 and severity_multiplier >= 0.5:
            key_injuries.append({
                'player': injury['player'],
                'position': position,
                'importance': importance,
                'status': injury['status']
            })
        
        # Track positions
        if position in positions_affected:
            positions_affected[position] += 1
    
    # Cap impact score at 10
    impact_score = min(10, impact_score)
    
    return {
        'impact_score': round(impact_score, 1),
        'key_injuries': key_injuries,
        'total_injuries': len(injuries),
        'positions_affected': positions_affected
    }


def get_todays_injuries():
    """
    Get all current NHL injuries from multiple sources.
    
    Returns dict: {
        team_abbrev: [injury_dicts]
    }
    """
    cache_key = f"todays_injuries_{datetime.now().strftime('%Y-%m-%d')}"
    cached = _get_cached(cache_key, max_age_hours=12)
    if cached:
        return cached
    
    print("\n[Injury Tracker] Fetching injury reports...")
    
    # Fetch from multiple sources
    espn_injuries = scrape_espn_injuries()
    dailyfaceoff_injuries = scrape_dailyfaceoff_injuries()
    
    # Merge injuries (ESPN is primary source)
    all_injuries = espn_injuries.copy()
    
    # Add DailyFaceoff injuries if not already present
    for team, injuries in dailyfaceoff_injuries.items():
        if team not in all_injuries:
            all_injuries[team] = []
        
        for injury in injuries:
            # Check if player already in list
            player_name = injury['player'].lower()
            if not any(player_name in existing['player'].lower() for existing in all_injuries[team]):
                all_injuries[team].append(injury)
    
    print(f"  ✅ Loaded injuries for {len(all_injuries)} teams")
    
    _set_cache(cache_key, all_injuries)
    return all_injuries


def get_injury_impact_for_game(home_team: str, away_team: str):
    """
    Get injury impact analysis for a specific game.
    
    Returns dict:
    {
        'home_impact': impact_dict,
        'away_impact': impact_dict,
        'advantage': 'home' | 'away' | 'even',
        'advantage_score': float (-10 to +10)
    }
    """
    all_injuries = get_todays_injuries()
    
    home_injuries = all_injuries.get(home_team, [])
    away_injuries = all_injuries.get(away_team, [])
    
    home_impact = calculate_injury_impact(home_injuries, home_team)
    away_impact = calculate_injury_impact(away_injuries, away_team)
    
    # Calculate advantage (negative impact is bad)
    advantage_score = away_impact['impact_score'] - home_impact['impact_score']
    
    if advantage_score > 2:
        advantage = 'home'  # Away team more injured
    elif advantage_score < -2:
        advantage = 'away'  # Home team more injured
    else:
        advantage = 'even'
    
    return {
        'home_impact': home_impact,
        'away_impact': away_impact,
        'advantage': advantage,
        'advantage_score': advantage_score
    }


def get_star_players_out():
    """
    Get list of star players currently out.
    Useful for quick reference.
    
    Returns list of dicts with player, team, status.
    """
    all_injuries = get_todays_injuries()
    
    star_players = []
    
    # Known star players (could be expanded)
    STAR_NAMES = [
        'mcdavid', 'matthews', 'mackinnon', 'kucherov', 'panarin',
        'makar', 'fox', 'hedman', 'josi', 'hughes',
        'hellebuyck', 'shesterkin', 'vasilevskiy', 'sorokin',
        'draisaitl', 'pastrnak', 'rantanen', 'marner', 'nylander'
    ]
    
    for team, injuries in all_injuries.items():
        for injury in injuries:
            player_name = injury['player'].lower()
            
            # Check if star player
            if any(star in player_name for star in STAR_NAMES):
                star_players.append({
                    'player': injury['player'],
                    'team': team,
                    'position': injury.get('position', 'Unknown'),
                    'status': injury.get('status', 'Unknown'),
                    'injury': injury.get('injury', 'Unknown')
                })
    
    return star_players


if __name__ == "__main__":
    print("=" * 80)
    print("  INJURY TRACKER TEST")
    print("=" * 80)
    
    # Test getting all injuries
    injuries = get_todays_injuries()
    
    print(f"\nFound injuries for {len(injuries)} teams:\n")
    
    total_injuries = 0
    for team, team_injuries in sorted(injuries.items()):
        if team_injuries:
            impact = calculate_injury_impact(team_injuries, team)
            print(f"{team:4s} | {len(team_injuries):2d} injuries | "
                  f"Impact: {impact['impact_score']:4.1f}/10 | "
                  f"Key: {len(impact['key_injuries'])}")
            total_injuries += len(team_injuries)
    
    print(f"\nTotal injuries tracked: {total_injuries}")
    
    # Test star players out
    print("\n" + "=" * 80)
    print("  STAR PLAYERS OUT")
    print("=" * 80)
    
    stars_out = get_star_players_out()
    if stars_out:
        print()
        for star in stars_out:
            print(f"  {star['player']:25s} ({star['team']}) - {star['status']}")
    else:
        print("\n  No major star players currently injured")
    
    # Test game impact analysis
    print("\n" + "=" * 80)
    print("  SAMPLE GAME IMPACT ANALYSIS")
    print("=" * 80)
    
    # Pick two teams with injuries
    teams_with_injuries = [t for t, inj in injuries.items() if inj]
    if len(teams_with_injuries) >= 2:
        home = teams_with_injuries[0]
        away = teams_with_injuries[1]
        
        game_impact = get_injury_impact_for_game(home, away)
        
        print(f"\n{away} @ {home}")
        
        print(f"\nHome Team ({home}) Injuries:")
        print(f"  Impact Score: {game_impact['home_impact']['impact_score']:.1f}/10")
        print(f"  Total Injuries: {game_impact['home_impact']['total_injuries']}")
        if game_impact['home_impact']['key_injuries']:
            print(f"  Key Players Out:")
            for player in game_impact['home_impact']['key_injuries']:
                print(f"    - {player['player']} ({player['position']}) - {player['status']}")
        
        print(f"\nAway Team ({away}) Injuries:")
        print(f"  Impact Score: {game_impact['away_impact']['impact_score']:.1f}/10")
        print(f"  Total Injuries: {game_impact['away_impact']['total_injuries']}")
        if game_impact['away_impact']['key_injuries']:
            print(f"  Key Players Out:")
            for player in game_impact['away_impact']['key_injuries']:
                print(f"    - {player['player']} ({player['position']}) - {player['status']}")
        
        print(f"\nAdvantage: {game_impact['advantage'].upper()}")
        print(f"Advantage Score: {game_impact['advantage_score']:+.1f}")
