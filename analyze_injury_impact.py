#!/usr/bin/env python3
"""
Injury Impact Analysis
======================
Analyzes historical games to see how injury adjustments affected predictions
and actual outcomes.

This helps calibrate the injury adjustment system to ensure it's not over/under-weighting
injury impacts.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict

from src.data import fetch_season_games, fetch_standings
from src.analysis import get_todays_injuries, get_injury_impact_for_game
from src.models import StreamlinedNHLMLModel, find_similar_games, estimate_probabilities


def analyze_injury_adjustments(days_back=90, min_injury_impact=5):
    """
    Analyze how injury adjustments affected predictions vs actual results.
    
    Args:
        days_back: How many days of historical games to analyze
        min_injury_impact: Minimum injury impact score to include in analysis
    """
    print("=" * 80)
    print("  INJURY ADJUSTMENT IMPACT ANALYSIS")
    print("=" * 80)
    print()
    
    # Fetch historical games
    print(f"Fetching last {days_back} days of completed games...")
    all_games = fetch_season_games(days_back=days_back)
    print(f"  Loaded {len(all_games)} games")
    
    # Get current standings for context
    standings = fetch_standings()
    
    # Initialize ML model
    print("\nInitializing ML model...")
    ml_model = StreamlinedNHLMLModel()
    
    # Track results
    results = {
        'with_injuries': [],  # Games where injury adjustment was applied
        'without_injuries': [],  # Games with no significant injuries
    }
    
    injury_adjustments = []  # Track all injury adjustments
    
    print(f"\nAnalyzing games with injury impact >= {min_injury_impact}...")
    print()
    
    analyzed = 0
    skipped = 0
    
    for game in all_games:
        home = game['home_team']
        away = game['away_team']
        home_score = game['home_score']
        away_score = game['away_score']
        game_date = game['date']
        
        # Skip if we don't have both teams in standings
        if home not in standings or away not in standings:
            skipped += 1
            continue
        
        try:
            # Get injury data for this game's date
            # Note: We're using current injury data as proxy since historical injury data
            # isn't available. This is a limitation but still useful for pattern analysis.
            injuries = get_todays_injuries()
            
            home_injuries = injuries.get(home, {})
            away_injuries = injuries.get(away, {})
            
            home_impact = home_injuries.get('impact_score', 0)
            away_impact = away_injuries.get('impact_score', 0)
            
            # Calculate injury adjustment
            injury_adj = get_injury_impact_for_game(home, away, injuries)
            
            # Only analyze games with significant injury impact
            if abs(injury_adj) >= min_injury_impact / 100.0:
                # Find similar games for prediction
                similar = find_similar_games(
                    home_team=home,
                    away_team=away,
                    all_games=all_games,
                    standings=standings,
                    n=50
                )
                
                if not similar:
                    continue
                
                # Get base prediction (without injury adjustment)
                base_probs = estimate_probabilities(similar, home, away)
                
                # Apply injury adjustment
                adjusted_home_prob = base_probs['home_win_prob'] + injury_adj
                adjusted_away_prob = 1 - adjusted_home_prob
                
                # Determine actual winner
                home_won = home_score > away_score
                
                # Record results
                result = {
                    'game': f"{away} @ {home}",
                    'date': game_date,
                    'home_score': home_score,
                    'away_score': away_score,
                    'home_won': home_won,
                    'base_home_prob': base_probs['home_win_prob'],
                    'adjusted_home_prob': adjusted_home_prob,
                    'injury_adjustment': injury_adj,
                    'home_injury_impact': home_impact,
                    'away_injury_impact': away_impact,
                    'base_correct': (base_probs['home_win_prob'] > 0.5) == home_won,
                    'adjusted_correct': (adjusted_home_prob > 0.5) == home_won,
                }
                
                results['with_injuries'].append(result)
                injury_adjustments.append(injury_adj)
                
                analyzed += 1
                
                if analyzed <= 10:  # Show first 10 examples
                    print(f"  {result['game']} ({result['date']})")
                    print(f"    Score: {home} {home_score} - {away_score} {away}")
                    print(f"    Injuries: {home} impact={home_impact}, {away} impact={away_impact}")
                    print(f"    Base prediction: {home} {base_probs['home_win_prob']:.1%}")
                    print(f"    Injury adjustment: {injury_adj:+.1%}")
                    print(f"    Adjusted prediction: {home} {adjusted_home_prob:.1%}")
                    print(f"    Result: {'✓ Correct' if result['adjusted_correct'] else '✗ Wrong'}")
                    print()
            
        except Exception as e:
            skipped += 1
            continue
    
    print(f"\nAnalyzed {analyzed} games with significant injuries")
    print(f"Skipped {skipped} games (missing data or no injuries)")
    print()
    
    # Calculate statistics
    if results['with_injuries']:
        print("=" * 80)
        print("  RESULTS SUMMARY")
        print("=" * 80)
        print()
        
        games_with_injuries = results['with_injuries']
        
        # Accuracy
        base_correct = sum(1 for r in games_with_injuries if r['base_correct'])
        adjusted_correct = sum(1 for r in games_with_injuries if r['adjusted_correct'])
        
        base_accuracy = base_correct / len(games_with_injuries)
        adjusted_accuracy = adjusted_correct / len(games_with_injuries)
        
        print(f"Prediction Accuracy:")
        print(f"  Without injury adjustment: {base_correct}/{len(games_with_injuries)} = {base_accuracy:.1%}")
        print(f"  With injury adjustment:    {adjusted_correct}/{len(games_with_injuries)} = {adjusted_accuracy:.1%}")
        print(f"  Improvement: {adjusted_accuracy - base_accuracy:+.1%}")
        print()
        
        # Adjustment statistics
        avg_adjustment = sum(abs(r['injury_adjustment']) for r in games_with_injuries) / len(games_with_injuries)
        max_adjustment = max(abs(r['injury_adjustment']) for r in games_with_injuries)
        
        print(f"Injury Adjustment Statistics:")
        print(f"  Average absolute adjustment: {avg_adjustment:.1%}")
        print(f"  Maximum absolute adjustment: {max_adjustment:.1%}")
        print()
        
        # Break down by adjustment size
        print("Accuracy by Adjustment Size:")
        
        buckets = [
            (0.00, 0.05, "0-5%"),
            (0.05, 0.10, "5-10%"),
            (0.10, 0.15, "10-15%"),
            (0.15, 0.20, "15-20%"),
            (0.20, 1.00, "20%+"),
        ]
        
        for min_adj, max_adj, label in buckets:
            bucket_games = [r for r in games_with_injuries 
                          if min_adj <= abs(r['injury_adjustment']) < max_adj]
            
            if bucket_games:
                bucket_correct = sum(1 for r in bucket_games if r['adjusted_correct'])
                bucket_accuracy = bucket_correct / len(bucket_games)
                print(f"  {label:8s}: {bucket_correct:2d}/{len(bucket_games):2d} = {bucket_accuracy:.1%}")
        
        print()
        
        # Games where adjustment helped vs hurt
        helped = sum(1 for r in games_with_injuries 
                    if r['adjusted_correct'] and not r['base_correct'])
        hurt = sum(1 for r in games_with_injuries 
                  if not r['adjusted_correct'] and r['base_correct'])
        no_change = sum(1 for r in games_with_injuries 
                       if r['adjusted_correct'] == r['base_correct'])
        
        print(f"Impact of Injury Adjustments:")
        print(f"  Helped (wrong → right): {helped} games")
        print(f"  Hurt (right → wrong):   {hurt} games")
        print(f"  No change:              {no_change} games")
        print(f"  Net benefit:            {helped - hurt:+d} games")
        print()
        
        # Show most impactful adjustments
        print("=" * 80)
        print("  LARGEST INJURY ADJUSTMENTS")
        print("=" * 80)
        print()
        
        sorted_by_adjustment = sorted(games_with_injuries, 
                                     key=lambda r: abs(r['injury_adjustment']), 
                                     reverse=True)
        
        for i, result in enumerate(sorted_by_adjustment[:10], 1):
            status = "✓" if result['adjusted_correct'] else "✗"
            print(f"{i:2d}. {status} {result['game']}")
            print(f"    Adjustment: {result['injury_adjustment']:+.1%} "
                  f"({result['base_home_prob']:.1%} → {result['adjusted_home_prob']:.1%})")
            print(f"    Result: {result['home_score']}-{result['away_score']} "
                  f"({'Home' if result['home_won'] else 'Away'} won)")
            print()
        
        # Recommendations
        print("=" * 80)
        print("  RECOMMENDATIONS")
        print("=" * 80)
        print()
        
        if adjusted_accuracy > base_accuracy + 0.02:
            print("✓ Injury adjustments are IMPROVING predictions")
            print(f"  Current system adds {(adjusted_accuracy - base_accuracy):.1%} accuracy")
        elif adjusted_accuracy < base_accuracy - 0.02:
            print("⚠ Injury adjustments are HURTING predictions")
            print(f"  Current system reduces accuracy by {(base_accuracy - adjusted_accuracy):.1%}")
            print("\n  Recommendations:")
            print("  1. Reduce injury adjustment weights")
            print("  2. Cap maximum adjustment at 10-15%")
            print("  3. Review injury impact scoring methodology")
        else:
            print("→ Injury adjustments have NEUTRAL impact")
            print("  System is neither helping nor hurting significantly")
        
        print()
        
        if max_adjustment > 0.15:
            print(f"⚠ Maximum adjustment of {max_adjustment:.1%} seems very high")
            print("  Consider capping adjustments at 10-15% to avoid over-correction")
            print()
        
        if avg_adjustment > 0.10:
            print(f"⚠ Average adjustment of {avg_adjustment:.1%} is quite large")
            print("  Consider reducing injury impact weights by 30-50%")
            print()
    
    else:
        print("No games with significant injury impacts found in the dataset.")
        print("This could mean:")
        print("  1. Injury data is not available for historical games")
        print("  2. The time period analyzed had few significant injuries")
        print("  3. The min_injury_impact threshold is too high")
    
    print()
    print("=" * 80)
    print("  ANALYSIS COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Analyze injury adjustment impact")
    parser.add_argument("--days", type=int, default=90, 
                       help="Days of history to analyze (default: 90)")
    parser.add_argument("--min-impact", type=int, default=5,
                       help="Minimum injury impact score to analyze (default: 5)")
    
    args = parser.parse_args()
    
    analyze_injury_adjustments(
        days_back=args.days,
        min_injury_impact=args.min_impact
    )
