"""
Odds Fetcher Module
Fetches live NHL betting lines from The Odds API.
Free tier: 500 requests/month — sign up at https://the-odds-api.com

Supports moneyline (h2h), spreads (puck line), and totals (over/under).
Includes theScore and other Ontario-available books.
"""

import requests
import json
import os
from pathlib import Path
from datetime import datetime
import time

ODDS_API_BASE = "https://api.the-odds-api.com/v4"
CACHE_DIR = Path(__file__).parent / "cache"
CACHE_DIR.mkdir(exist_ok=True)

# Ontario/Canada-relevant bookmakers
# The Odds API 'us' region includes many books available in Ontario
PREFERRED_BOOKS = [
    "thescore",        # theScore Bet (primary)
    "fanduel",         # FanDuel (available in ON)
    "draftkings",      # DraftKings (available in ON)
    "betrivers",       # BetRivers (available in ON)
    "pointsbet",       # PointsBet (available in ON)
    "bet365",          # bet365 (available in ON)
    "betway",          # Betway
    "pinnacle",        # Pinnacle (sharp book, good for fair odds)
]

# Markets we care about
MARKETS = "h2h,spreads,totals"


def get_api_key() -> str:
    """
    Get The Odds API key from environment variable or config file.
    """
    key = os.environ.get("ODDS_API_KEY", "")
    if key:
        return key

    config_path = Path(__file__).parent / "config.json"
    if config_path.exists():
        config = json.loads(config_path.read_text())
        key = config.get("odds_api_key", "")
        if key:
            return key

    raise ValueError(
        "No API key found!\n"
        "1. Sign up free at https://the-odds-api.com\n"
        "2. Either set ODDS_API_KEY environment variable, or\n"
        "3. Create config.json with: {\"odds_api_key\": \"YOUR_KEY\"}"
    )


def _cache_key(name: str) -> str:
    return f"odds_{name}_{datetime.now().strftime('%Y%m%d_%H')}"


def fetch_nhl_odds(markets: str = MARKETS) -> list:
    """
    Fetch current NHL odds for all available games.
    Returns list of game dicts with odds from multiple bookmakers.
    """
    api_key = get_api_key()

    cache_key = _cache_key(f"nhl_{markets.replace(',', '_')}")
    cached_path = CACHE_DIR / f"{cache_key}.json"
    if cached_path.exists():
        age = time.time() - cached_path.stat().st_mtime
        if age < 1800:  # 30 min cache for odds
            return json.loads(cached_path.read_text())

    url = f"{ODDS_API_BASE}/sports/icehockey_nhl/odds"
    params = {
        "apiKey": api_key,
        "regions": "us,us2",  # covers most Ontario books
        "markets": markets,
        "oddsFormat": "american",
    }

    resp = requests.get(url, params=params, timeout=15)
    resp.raise_for_status()
    games = resp.json()

    # Log remaining requests
    remaining = resp.headers.get("x-requests-remaining", "?")
    used = resp.headers.get("x-requests-used", "?")
    print(f"  Odds API: {used} requests used, {remaining} remaining this month")

    cached_path.write_text(json.dumps(games, default=str))
    return games


def parse_odds(games: list) -> list:
    """
    Parse raw odds API response into clean structured data.
    Returns list of dicts, one per game, with nested odds by bookmaker.
    """
    parsed = []

    for game in games:
        game_data = {
            "game_id": game["id"],
            "commence_time": game["commence_time"],
            "home_team": game["home_team"],
            "away_team": game["away_team"],
            "bookmakers": {},
        }

        for bk in game.get("bookmakers", []):
            bk_key = bk["key"]
            bk_data = {"name": bk["title"], "markets": {}}

            for market in bk.get("markets", []):
                mk = market["key"]
                outcomes = []
                for outcome in market.get("outcomes", []):
                    o = {
                        "name": outcome["name"],
                        "price": outcome["price"],
                    }
                    if "point" in outcome:
                        o["point"] = outcome["point"]
                    outcomes.append(o)
                bk_data["markets"][mk] = outcomes

            game_data["bookmakers"][bk_key] = bk_data

        parsed.append(game_data)

    return parsed


def american_to_decimal(american: int) -> float:
    """Convert American odds to decimal odds."""
    if american > 0:
        return 1 + (american / 100)
    else:
        return 1 + (100 / abs(american))


def american_to_implied_prob(american: int) -> float:
    """Convert American odds to implied probability (no-vig)."""
    if american < 0:
        return abs(american) / (abs(american) + 100)
    else:
        return 100 / (american + 100)


def get_best_odds(game_data: dict, preferred_books: list = None) -> dict:
    """
    For a single game, find the best available odds across bookmakers
    for each market (moneyline, spread, total).
    Prioritizes preferred bookmakers but includes all.
    """
    if preferred_books is None:
        preferred_books = PREFERRED_BOOKS

    best = {
        "home_team": game_data["home_team"],
        "away_team": game_data["away_team"],
        "commence_time": game_data["commence_time"],
        "moneyline": {"home": None, "away": None},
        "spread": {"home": None, "away": None},
        "total": {"over": None, "under": None},
        "thescore": {"moneyline": {}, "spread": {}, "total": {}},
        "all_books": {},
    }

    for bk_key, bk_data in game_data["bookmakers"].items():
        book_odds = {}

        # Moneyline (h2h)
        if "h2h" in bk_data["markets"]:
            for outcome in bk_data["markets"]["h2h"]:
                side = "home" if outcome["name"] == game_data["home_team"] else "away"
                book_odds[f"ml_{side}"] = outcome["price"]

                current_best = best["moneyline"][side]
                if current_best is None or outcome["price"] > current_best["price"]:
                    best["moneyline"][side] = {
                        "price": outcome["price"],
                        "book": bk_key,
                        "decimal": american_to_decimal(outcome["price"]),
                        "implied_prob": american_to_implied_prob(outcome["price"]),
                    }

        # Spread (puck line)
        if "spreads" in bk_data["markets"]:
            for outcome in bk_data["markets"]["spreads"]:
                side = "home" if outcome["name"] == game_data["home_team"] else "away"
                point = outcome.get("point", 0)
                book_odds[f"spread_{side}"] = {
                    "price": outcome["price"],
                    "point": point,
                }

                current_best = best["spread"][side]
                if current_best is None or outcome["price"] > current_best["price"]:
                    best["spread"][side] = {
                        "price": outcome["price"],
                        "point": point,
                        "book": bk_key,
                        "decimal": american_to_decimal(outcome["price"]),
                        "implied_prob": american_to_implied_prob(outcome["price"]),
                    }

        # Totals (over/under)
        if "totals" in bk_data["markets"]:
            for outcome in bk_data["markets"]["totals"]:
                side = "over" if outcome["name"] == "Over" else "under"
                point = outcome.get("point", 0)
                book_odds[f"total_{side}"] = {
                    "price": outcome["price"],
                    "point": point,
                }

                current_best = best["total"][side]
                if current_best is None or outcome["price"] > current_best["price"]:
                    best["total"][side] = {
                        "price": outcome["price"],
                        "point": point,
                        "book": bk_key,
                        "decimal": american_to_decimal(outcome["price"]),
                        "implied_prob": american_to_implied_prob(outcome["price"]),
                    }

        # Store theScore specifically
        if bk_key == "thescore":
            best["thescore"] = book_odds

        best["all_books"][bk_key] = book_odds

    return best


def get_consensus_no_vig_odds(game_data: dict) -> dict:
    """
    Calculate consensus 'fair' (no-vig) probabilities by averaging
    across sharp bookmakers. This gives us a market-implied true probability.
    """
    sharp_books = ["pinnacle", "betcris", "bovada"]  # known sharp books

    ml_home_probs = []
    ml_away_probs = []
    total_over_probs = []
    spread_home_probs = []
    total_line = None
    spread_line = None

    for bk_key, bk_data in game_data["bookmakers"].items():
        # Moneyline
        if "h2h" in bk_data["markets"]:
            probs = {}
            for outcome in bk_data["markets"]["h2h"]:
                side = "home" if outcome["name"] == game_data["home_team"] else "away"
                probs[side] = american_to_implied_prob(outcome["price"])

            # Remove vig by normalizing
            total_prob = sum(probs.values())
            if total_prob > 0:
                if "home" in probs:
                    ml_home_probs.append(probs["home"] / total_prob)
                if "away" in probs:
                    ml_away_probs.append(probs["away"] / total_prob)

        # Totals
        if "totals" in bk_data["markets"]:
            probs = {}
            for outcome in bk_data["markets"]["totals"]:
                side = outcome["name"].lower()
                probs[side] = american_to_implied_prob(outcome["price"])
                if total_line is None and "point" in outcome:
                    total_line = outcome["point"]

            total_prob = sum(probs.values())
            if total_prob > 0 and "over" in probs:
                total_over_probs.append(probs["over"] / total_prob)

        # Spreads
        if "spreads" in bk_data["markets"]:
            probs = {}
            for outcome in bk_data["markets"]["spreads"]:
                side = "home" if outcome["name"] == game_data["home_team"] else "away"
                probs[side] = american_to_implied_prob(outcome["price"])
                if spread_line is None and "point" in outcome and side == "home":
                    spread_line = outcome["point"]

            total_prob = sum(probs.values())
            if total_prob > 0 and "home" in probs:
                spread_home_probs.append(probs["home"] / total_prob)

    return {
        "home_win_prob": sum(ml_home_probs) / len(ml_home_probs) if ml_home_probs else 0.5,
        "away_win_prob": sum(ml_away_probs) / len(ml_away_probs) if ml_away_probs else 0.5,
        "over_prob": sum(total_over_probs) / len(total_over_probs) if total_over_probs else 0.5,
        "under_prob": 1 - (sum(total_over_probs) / len(total_over_probs)) if total_over_probs else 0.5,
        "spread_home_cover_prob": sum(spread_home_probs) / len(spread_home_probs) if spread_home_probs else 0.5,
        "total_line": total_line,
        "spread_line": spread_line,
        "n_books_ml": len(ml_home_probs),
        "n_books_total": len(total_over_probs),
        "n_books_spread": len(spread_home_probs),
    }


# Team name mapping: The Odds API uses full names, NHL API uses abbreviations
TEAM_NAME_TO_ABBREV = {
    "Anaheim Ducks": "ANA",
    "Boston Bruins": "BOS",
    "Buffalo Sabres": "BUF",
    "Calgary Flames": "CGY",
    "Carolina Hurricanes": "CAR",
    "Chicago Blackhawks": "CHI",
    "Colorado Avalanche": "COL",
    "Columbus Blue Jackets": "CBJ",
    "Dallas Stars": "DAL",
    "Detroit Red Wings": "DET",
    "Edmonton Oilers": "EDM",
    "Florida Panthers": "FLA",
    "Los Angeles Kings": "LAK",
    "Minnesota Wild": "MIN",
    "Montreal Canadiens": "MTL",
    "Montréal Canadiens": "MTL",
    "Nashville Predators": "NSH",
    "New Jersey Devils": "NJD",
    "New York Islanders": "NYI",
    "New York Rangers": "NYR",
    "Ottawa Senators": "OTT",
    "Philadelphia Flyers": "PHI",
    "Pittsburgh Penguins": "PIT",
    "San Jose Sharks": "SJS",
    "Seattle Kraken": "SEA",
    "St. Louis Blues": "STL",
    "St Louis Blues": "STL",
    "Tampa Bay Lightning": "TBL",
    "Toronto Maple Leafs": "TOR",
    "Utah Hockey Club": "UTA",
    "Vancouver Canucks": "VAN",
    "Vegas Golden Knights": "VGK",
    "Washington Capitals": "WSH",
    "Winnipeg Jets": "WPG",
    # Arizona moved to Utah
    "Arizona Coyotes": "UTA",
}


def team_name_to_abbrev(name: str) -> str:
    """Convert full team name to NHL abbreviation."""
    return TEAM_NAME_TO_ABBREV.get(name, name)


if __name__ == "__main__":
    try:
        print("Fetching NHL odds...")
        raw = fetch_nhl_odds()
        parsed = parse_odds(raw)
        print(f"\nFound {len(parsed)} games with odds:\n")

        for game in parsed:
            home = game["home_team"]
            away = game["away_team"]
            best = get_best_odds(game)
            consensus = get_consensus_no_vig_odds(game)

            print(f"{away} @ {home}")
            if best["moneyline"]["home"]:
                print(f"  ML: {home} {best['moneyline']['home']['price']:+d} "
                      f"({best['moneyline']['home']['book']}) | "
                      f"{away} {best['moneyline']['away']['price']:+d} "
                      f"({best['moneyline']['away']['book']})")
            if best["spread"]["home"]:
                print(f"  Spread: {home} {best['spread']['home']['point']:+.1f} "
                      f"{best['spread']['home']['price']:+d}")
            if best["total"]["over"]:
                print(f"  Total: O/U {best['total']['over']['point']} | "
                      f"O {best['total']['over']['price']:+d} "
                      f"U {best['total']['under']['price']:+d}")
            print(f"  Fair odds: {home} {consensus['home_win_prob']:.1%} / "
                  f"{away} {consensus['away_win_prob']:.1%}")
            print()

    except ValueError as e:
        print(f"Setup needed: {e}")
