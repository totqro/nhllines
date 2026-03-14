"""
Goalie Adjustment Module
========================
Calculates win probability adjustments based on goalie matchups.
Includes consensus checks and caps to prevent extreme adjustments.
"""


def calculate_goalie_adjustment(home_goalie_info: dict, away_goalie_info: dict,
                                model_home_prob: float = None,
                                market_home_prob: float = None) -> dict:
    """
    Calculate win probability adjustment based on goalie matchup.
    
    Args:
        home_goalie_info: Home goalie stats and quality score
        away_goalie_info: Away goalie stats and quality score
        model_home_prob: Model's home win probability (for consensus check)
        market_home_prob: Market's home win probability (for consensus check)
    
    Returns:
        dict with:
        - adjustment: float (-0.08 to +0.08)
        - quality_adjustment: float
        - hot_cold_adjustment: float
        - explanation: str
    """
    if not home_goalie_info or not away_goalie_info:
        return {
            'adjustment': 0.0,
            'quality_adjustment': 0.0,
            'hot_cold_adjustment': 0.0,
            'explanation': 'Goalie data unavailable'
        }
    
    # Quality score adjustment (±2% per 10 points)
    home_quality = home_goalie_info.get('quality_score', 50)
    away_quality = away_goalie_info.get('quality_score', 50)
    quality_diff = home_quality - away_quality
    quality_adjustment = (quality_diff / 10) * 0.02
    
    # Hot/cold streak adjustment (±3%)
    hot_cold_adjustment = 0.0
    
    home_recent_sv = home_goalie_info.get('stats', {}).get('recent_save_pct', 0.900)
    away_recent_sv = away_goalie_info.get('stats', {}).get('recent_save_pct', 0.900)
    
    # Hot threshold: >0.920 (top ~25%)
    # Cold threshold: <0.890 (bottom ~25%)
    if home_recent_sv > 0.920:
        hot_cold_adjustment += 0.03
    elif home_recent_sv < 0.890:
        hot_cold_adjustment -= 0.03
    
    if away_recent_sv > 0.920:
        hot_cold_adjustment -= 0.03
    elif away_recent_sv < 0.890:
        hot_cold_adjustment += 0.03
    
    # Total adjustment before caps
    total_adjustment = quality_adjustment + hot_cold_adjustment
    
    # Consensus check: reduce adjustment if it contradicts both model and market
    if model_home_prob is not None and market_home_prob is not None:
        model_favors_home = model_home_prob > 0.5
        market_favors_home = market_home_prob > 0.5
        adjustment_favors_home = total_adjustment > 0
        
        # If adjustment contradicts BOTH model and market, reduce to 50%
        if (model_favors_home == market_favors_home and 
            adjustment_favors_home != model_favors_home and
            abs(total_adjustment) > 0.03):  # Only apply if adjustment is significant
            total_adjustment *= 0.5
    
    # Cap total adjustment at ±8%
    total_adjustment = max(-0.08, min(0.08, total_adjustment))
    
    # Generate explanation
    explanation_parts = []
    
    if abs(quality_diff) > 10:
        advantage_team = 'home' if quality_diff > 0 else 'away'
        explanation_parts.append(f"{advantage_team} goalie +{abs(quality_diff):.0f} quality")
    
    if home_recent_sv > 0.920:
        explanation_parts.append("home goalie hot")
    elif home_recent_sv < 0.890:
        explanation_parts.append("home goalie cold")
    
    if away_recent_sv > 0.920:
        explanation_parts.append("away goalie hot")
    elif away_recent_sv < 0.890:
        explanation_parts.append("away goalie cold")
    
    explanation = ", ".join(explanation_parts) if explanation_parts else "goalies even"
    
    return {
        'adjustment': total_adjustment,
        'quality_adjustment': quality_adjustment,
        'hot_cold_adjustment': hot_cold_adjustment,
        'explanation': explanation,
        'home_quality': home_quality,
        'away_quality': away_quality,
        'home_recent_sv': home_recent_sv,
        'away_recent_sv': away_recent_sv
    }


def apply_goalie_adjustment(base_home_prob: float, home_goalie_info: dict,
                           away_goalie_info: dict, model_home_prob: float = None,
                           market_home_prob: float = None) -> dict:
    """
    Apply goalie adjustment to base probability.
    
    Args:
        base_home_prob: Base home win probability
        home_goalie_info: Home goalie stats
        away_goalie_info: Away goalie stats
        model_home_prob: Model probability (for consensus check)
        market_home_prob: Market probability (for consensus check)
    
    Returns:
        dict with adjusted probabilities and details
    """
    adjustment_data = calculate_goalie_adjustment(
        home_goalie_info, away_goalie_info,
        model_home_prob, market_home_prob
    )
    
    # Apply adjustment
    adjusted_home_prob = base_home_prob + adjustment_data['adjustment']
    
    # Ensure probabilities stay in valid range
    adjusted_home_prob = max(0.05, min(0.95, adjusted_home_prob))
    adjusted_away_prob = 1 - adjusted_home_prob
    
    return {
        'adjusted_home_prob': adjusted_home_prob,
        'adjusted_away_prob': adjusted_away_prob,
        'adjustment': adjustment_data['adjustment'],
        'quality_adjustment': adjustment_data['quality_adjustment'],
        'hot_cold_adjustment': adjustment_data['hot_cold_adjustment'],
        'explanation': adjustment_data['explanation'],
        'home_quality': adjustment_data['home_quality'],
        'away_quality': adjustment_data['away_quality']
    }


if __name__ == "__main__":
    # Test the goalie adjustment calculator
    print("=" * 80)
    print("  GOALIE ADJUSTMENT CALCULATOR TEST")
    print("=" * 80)
    print()
    
    # Test case 1: Elite vs backup
    print("Test 1: Elite goalie vs backup")
    result = calculate_goalie_adjustment(
        home_goalie_info={'quality_score': 70, 'stats': {'recent_save_pct': 0.925}},
        away_goalie_info={'quality_score': 40, 'stats': {'recent_save_pct': 0.885}},
        model_home_prob=0.55,
        market_home_prob=0.53
    )
    print(f"  Quality diff: 30 points")
    print(f"  Home hot (0.925), Away cold (0.885)")
    print(f"  Quality adjustment: {result['quality_adjustment']:+.1%}")
    print(f"  Hot/cold adjustment: {result['hot_cold_adjustment']:+.1%}")
    print(f"  Total adjustment: {result['adjustment']:+.1%}")
    print(f"  Explanation: {result['explanation']}")
    print()
    
    # Test case 2: Adjustment contradicts consensus
    print("Test 2: Adjustment contradicts model+market consensus")
    result = calculate_goalie_adjustment(
        home_goalie_info={'quality_score': 65, 'stats': {'recent_save_pct': 0.920}},
        away_goalie_info={'quality_score': 45, 'stats': {'recent_save_pct': 0.890}},
        model_home_prob=0.35,  # Model favors away
        market_home_prob=0.33  # Market favors away
    )
    print(f"  Quality diff: 20 points (favors home)")
    print(f"  But model (35%) and market (33%) both favor away")
    print(f"  Raw adjustment: {(result['quality_adjustment'] + result['hot_cold_adjustment']):+.1%}")
    print(f"  After consensus check: {result['adjustment']:+.1%}")
    print(f"  Explanation: {result['explanation']}")
    print()
    
    # Test case 3: Both average
    print("Test 3: Both goalies average")
    result = calculate_goalie_adjustment(
        home_goalie_info={'quality_score': 50, 'stats': {'recent_save_pct': 0.905}},
        away_goalie_info={'quality_score': 50, 'stats': {'recent_save_pct': 0.905}},
        model_home_prob=0.55,
        market_home_prob=0.53
    )
    print(f"  Quality diff: 0 points")
    print(f"  Both average form")
    print(f"  Total adjustment: {result['adjustment']:+.1%}")
    print(f"  Explanation: {result['explanation']}")
    print()
