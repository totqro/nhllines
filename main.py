#!/usr/bin/env python3
"""
NHL +EV Betting Finder
======================
Compares live NHL betting lines to historical similar-game analysis
to find positive expected value bets.

Usage:
    python main.py                   # Full analysis with live odds
    python main.py --no-odds         # Historical analysis only (no API key needed)
    python main.py --stake 0.50      # Set stake per bet (default $1.00 CAD)
    python main.py --days 120        # Historical lookback days (default 90)
    python main.py --min-edge 0.03   # Minimum edge to show (default 0.02)

Setup:
    1. pip install requests
    2. Sign up for free API key at https://the-odds-api.com
    3. Create config.json: {"odds_api_key": "YOUR_KEY_HERE"}
       OR set environment variable: export ODDS_API_KEY=your_key
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from nhl_data import (
    fetch_standings,
    fetch_season_games,
    fetch_todays_games,
    get_team_recent_form,
    get_h2h_record,
)
from odds_fetcher import (
    fetch_nhl_odds,
    parse_odds,
    get_best_odds,
    get_consensus_no_vig_odds,
    team_name_to_abbrev,
)
from model import (
    find_similar_games,
    estimate_probabilities,
    blend_model_and_market,
)
from ev_calculator import (
    evaluate_all_bets,
    format_recommendations,
    kelly_criterion,
    calculate_ev,
)


def run_analysis(
    stake: float = 1.00,
    days_back: int = 90,
    min_edge: float = 0.02,
    use_odds: bool = True,
    n_similar: int = 50,
    conservative: bool = False,
):
    """Main analysis pipeline."""
    print("=" * 60)
    print("  NHL +EV Betting Finder")
    if conservative:
        print("  MODE: Conservative (moneylines + totals only, 3%+ edge, capped at 15%)")
    print(f"  {datetime.now().strftime('%A, %B %d %Y %H:%M')}")
    print("=" * 60)
    print()

    # Step 1: Fetch current standings
    print("[1/5] Fetching current NHL standings...")
    standings = fetch_standings()
    print(f"  Loaded standings for {len(standings)} teams")

    # Step 2: Fetch historical games
    print(f"\n[2/5] Fetching last {days_back} days of game results...")
    all_games = fetch_season_games(days_back=days_back)
    print(f"  Loaded {len(all_games)} completed games")

    # Step 3: Calculate recent form for all teams
    print("\n[3/5] Calculating team form...")
    team_forms = {}
    for team in standings:
        team_forms[team] = get_team_recent_form(team, all_games, n=10)

    # Step 4: Fetch odds (if enabled)
    odds_games = []
    if use_odds:
        print("\n[4/5] Fetching live betting odds...")
        try:
            raw_odds = fetch_nhl_odds()
            odds_games = parse_odds(raw_odds)
            # Filter to today's games only (commence_time is UTC, we're EST/UTC-5)
            # Include today and tomorrow UTC to catch evening EST games
            from datetime import timedelta
            today = datetime.now()
            today_str = today.strftime("%Y-%m-%d")
            tomorrow_str = (today + timedelta(days=1)).strftime("%Y-%m-%d")
            odds_games = [
                g for g in odds_games
                if g["commence_time"][:10] in (today_str, tomorrow_str)
            ]
            # Remove games that are clearly tomorrow EST (UTC afternoon+)
            # Games starting after ~10am UTC tomorrow are tomorrow's games EST
            filtered = []
            for g in odds_games:
                ct = g["commence_time"]
                if ct[:10] == today_str:
                    filtered.append(g)
                elif ct[:10] == tomorrow_str:
                    # Tomorrow UTC but before 10:00 UTC = tonight EST
                    hour = int(ct[11:13]) if len(ct) > 13 else 0
                    if hour < 10:
                        filtered.append(g)
            odds_games = filtered
            print(f"  Found odds for {len(odds_games)} games today")
        except Exception as e:
            print(f"  Warning: Could not fetch odds: {e}")
            print("  Continuing with historical analysis only...")
            use_odds = False

    # Step 5: Run the model
    print("\n[5/5] Running model analysis...\n")
    print("-" * 60)

    all_bets = []
    game_analyses = []

    if use_odds and odds_games:
        # Analyze games with live odds
        for game_data in odds_games:
            home_full = game_data["home_team"]
            away_full = game_data["away_team"]
            home = team_name_to_abbrev(home_full)
            away = team_name_to_abbrev(away_full)

            if home not in standings or away not in standings:
                print(f"  Skipping {away_full} @ {home_full} (team not found in standings)")
                continue

            game_label = f"{away} @ {home}"
            print(f"\n  Analyzing: {game_label}")

            # Get best odds and market consensus
            best_odds = get_best_odds(game_data)
            market_probs = get_consensus_no_vig_odds(game_data)

            # Find similar historical games
            similar = find_similar_games(
                home, away, standings, all_games, team_forms,
                n_similar=n_similar,
            )
            print(f"    Found {len(similar)} similar historical games")

            # Get total and spread lines from odds
            total_line = None
            spread_line = None
            if best_odds["total"]["over"]:
                total_line = best_odds["total"]["over"]["point"]
            if best_odds["spread"]["home"]:
                spread_line = best_odds["spread"]["home"]["point"]

            # Estimate true probabilities from similar games
            model_probs = estimate_probabilities(
                similar, home, away,
                total_line=total_line,
                spread_line=spread_line,
            )

            # Blend model with market
            blended = blend_model_and_market(model_probs, market_probs)

            # Print analysis
            print(f"    Model: {home} {model_probs['home_win_prob']:.1%} / "
                  f"{away} {model_probs['away_win_prob']:.1%} "
                  f"(confidence: {model_probs['confidence']:.0%})")
            print(f"    Market: {home} {market_probs['home_win_prob']:.1%} / "
                  f"{away} {market_probs['away_win_prob']:.1%}")
            print(f"    Blended: {home} {blended['home_win_prob']:.1%} / "
                  f"{away} {blended['away_win_prob']:.1%}")
            if total_line:
                print(f"    Total: line {total_line}, model expects "
                      f"{model_probs['expected_total']:.1f} goals "
                      f"(O {blended['over_prob']:.1%} / U {blended['under_prob']:.1%})")

            # Find +EV bets
            game_bets = evaluate_all_bets(
                game_label, home, away,
                blended, best_odds,
                stake=stake, min_edge=min_edge,
                conservative=conservative,
            )
            if game_bets:
                print(f"    >>> Found {len(game_bets)} +EV bets!")
            else:
                print(f"    No +EV bets at current lines")

            all_bets.extend(game_bets)
            game_analyses.append({
                "game": game_label,
                "home": home,
                "away": away,
                "model_probs": model_probs,
                "market_probs": market_probs,
                "blended_probs": blended,
                "n_similar": len(similar),
                "n_bets": len(game_bets),
            })

    else:
        # No odds - just show model analysis for today's games
        print("  Running in historical-only mode (no live odds)")
        todays_games = fetch_todays_games()
        if not todays_games:
            print("  No games scheduled today.")

        for game in todays_games:
            home = game["home_team"]
            away = game["away_team"]
            game_label = f"{away} @ {home}"

            if home not in standings or away not in standings:
                continue

            print(f"\n  Analyzing: {game_label}")

            similar = find_similar_games(
                home, away, standings, all_games, team_forms,
                n_similar=n_similar,
            )

            model_probs = estimate_probabilities(similar, home, away)

            print(f"    Model: {home} {model_probs['home_win_prob']:.1%} / "
                  f"{away} {model_probs['away_win_prob']:.1%}")
            print(f"    Expected total: {model_probs['expected_total']:.1f} goals")
            print(f"    Confidence: {model_probs['confidence']:.0%}")
            print(f"    Based on {len(similar)} similar games")

            game_analyses.append({
                "game": game_label,
                "home": home,
                "away": away,
                "model_probs": model_probs,
            })

    # Print recommendations
    print("\n")
    report = format_recommendations(all_bets, top_n=15)
    print(report)

    # Save results
    output = {
        "timestamp": datetime.now().isoformat(),
        "stake": stake,
        "days_back": days_back,
        "min_edge": min_edge,
        "n_historical_games": len(all_games),
        "games_analyzed": game_analyses,
        "recommendations": [
            {k: v for k, v in bet.items() if not callable(v)}
            for bet in all_bets
        ],
    }

    output_path = Path(__file__).parent / "latest_analysis.json"
    output_path.write_text(json.dumps(output, indent=2, default=str))
    print(f"Full analysis saved to: {output_path}")

    return all_bets, game_analyses


def main():
    parser = argparse.ArgumentParser(description="NHL +EV Betting Finder")
    parser.add_argument("--stake", type=float, default=1.00,
                        help="Stake per bet in CAD (default: 1.00)")
    parser.add_argument("--days", type=int, default=90,
                        help="Historical lookback in days (default: 90)")
    parser.add_argument("--min-edge", type=float, default=0.02,
                        help="Minimum edge to recommend (default: 0.02 = 2%%)")
    parser.add_argument("--no-odds", action="store_true",
                        help="Run without live odds (no API key needed)")
    parser.add_argument("--similar", type=int, default=50,
                        help="Number of similar games to use (default: 50)")
    parser.add_argument("--conservative", action="store_true",
                        help="Conservative mode: totals + ML only, higher min edge, cap unrealistic edges")
    args = parser.parse_args()

    run_analysis(
        stake=args.stake,
        days_back=args.days,
        min_edge=args.min_edge,
        use_odds=not args.no_odds,
        n_similar=args.similar,
        conservative=args.conservative,
    )


if __name__ == "__main__":
    main()
