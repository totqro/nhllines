"""
Expected Value Calculator
Compares model probabilities to bookmaker odds to find +EV bets.
Outputs ranked recommendations.
"""

from src.data.odds_fetcher import american_to_decimal, american_to_implied_prob
from scipy import stats


def _calculate_total_probability(expected_total: float, line: float, is_over: bool) -> float:
    """
    Calculate probability of over/under for a given total line.
    Uses Poisson distribution based on expected total goals.
    
    Args:
        expected_total: Model's predicted total goals
        line: The total line (e.g., 5.5, 6.0, 6.5)
        is_over: True for Over, False for Under
    
    Returns:
        Probability of the bet winning
    """
    # Use Poisson distribution for goal scoring
    # For NHL, goals follow roughly a Poisson distribution
    lambda_param = expected_total
    
    if is_over:
        # P(X > line) = 1 - P(X <= line)
        # For line 5.5, we need P(X >= 6)
        prob = 1 - stats.poisson.cdf(int(line), lambda_param)
    else:
        # P(X < line) = P(X <= floor(line))
        # For line 5.5, we need P(X <= 5)
        prob = stats.poisson.cdf(int(line), lambda_param)
    
    return prob


def _evaluate_all_total_lines(
    game_label: str,
    blended_probs: dict,
    best_odds: dict,
    stake: float,
    min_edge: float,
    max_edge: float,
    confidence: float,
) -> list:
    """
    Evaluate all available total lines across all books.
    Uses blended probabilities for the main line, Poisson for others.
    Returns list of +EV total bets.
    """
    total_bets = []
    expected_total = blended_probs.get("expected_total", 6.0)
    main_line = blended_probs.get("total_line")  # The line the model was trained on
    
    # Collect all unique total lines with their best odds
    lines_data = {}  # {line: {"over": {book, odds}, "under": {book, odds}}}
    
    for book, book_odds in best_odds.get("all_books", {}).items():
        # Check for over
        if "total_over" in book_odds:
            line = book_odds["total_over"]["point"]
            odds = book_odds["total_over"]["price"]
            
            if line not in lines_data:
                lines_data[line] = {"over": None, "under": None}
            
            # Keep best odds for this line
            if lines_data[line]["over"] is None or odds > lines_data[line]["over"]["odds"]:
                lines_data[line]["over"] = {"book": book, "odds": odds}
        
        # Check for under
        if "total_under" in book_odds:
            line = book_odds["total_under"]["point"]
            odds = book_odds["total_under"]["price"]
            
            if line not in lines_data:
                lines_data[line] = {"over": None, "under": None}
            
            # Keep best odds for this line
            if lines_data[line]["under"] is None or odds > lines_data[line]["under"]["odds"]:
                lines_data[line]["under"] = {"book": book, "odds": odds}
    
    # Evaluate each line
    for line, sides in lines_data.items():
        # Use blended probs if this is the main line, otherwise use Poisson
        if main_line and abs(line - main_line) < 0.1:
            # This is the main line - use blended probabilities
            over_prob = blended_probs.get("over_prob", 0.5)
            under_prob = blended_probs.get("under_prob", 0.5)
        else:
            # Different line - calculate using Poisson
            over_prob = _calculate_total_probability(expected_total, line, is_over=True)
            under_prob = _calculate_total_probability(expected_total, line, is_over=False)
        
        # Evaluate Over
        if sides["over"]:
            ev_data = calculate_ev(
                true_prob=over_prob,
                american_odds=sides["over"]["odds"],
                stake=stake,
            )
            
            if ev_data["edge"] >= min_edge and ev_data["edge"] <= max_edge:
                total_bets.append({
                    "game": game_label,
                    "bet_type": "Total",
                    "pick": f"Over {line}",
                    "book": sides["over"]["book"],
                    "odds": sides["over"]["odds"],
                    **ev_data,
                    "confidence": confidence,
                    "line": line,
                    "expected_total": expected_total,
                })
        
        # Evaluate Under
        if sides["under"]:
            ev_data = calculate_ev(
                true_prob=under_prob,
                american_odds=sides["under"]["odds"],
                stake=stake,
            )
            
            if ev_data["edge"] >= min_edge and ev_data["edge"] <= max_edge:
                total_bets.append({
                    "game": game_label,
                    "bet_type": "Total",
                    "pick": f"Under {line}",
                    "book": sides["under"]["book"],
                    "odds": sides["under"]["odds"],
                    **ev_data,
                    "confidence": confidence,
                    "line": line,
                    "expected_total": expected_total,
                })
    
    return total_bets


def calculate_ev(
    true_prob: float,
    american_odds: int,
    stake: float = 1.00,
) -> dict:
    """
    Calculate expected value of a bet.

    EV = (P_win * profit) - (P_lose * stake)
    Where profit = stake * (decimal_odds - 1)

    Returns dict with EV, ROI, and breakdown.
    """
    decimal_odds = american_to_decimal(american_odds)
    implied_prob = american_to_implied_prob(american_odds)

    profit_if_win = stake * (decimal_odds - 1)
    loss_if_lose = stake

    ev = (true_prob * profit_if_win) - ((1 - true_prob) * loss_if_lose)
    roi = ev / stake  # As a fraction

    # Edge = our probability minus the implied probability
    edge = true_prob - implied_prob

    return {
        "ev": ev,
        "roi": roi,
        "edge": edge,
        "true_prob": true_prob,
        "implied_prob": implied_prob,
        "american_odds": american_odds,
        "decimal_odds": decimal_odds,
        "stake": stake,
        "profit_if_win": profit_if_win,
        "loss_if_lose": loss_if_lose,
        "is_positive_ev": ev > 0,
    }


def evaluate_all_bets(
    game_label: str,
    home_team: str,
    away_team: str,
    blended_probs: dict,
    best_odds: dict,
    stake: float = 1.00,
    min_edge: float = 0.02,  # Minimum 2% edge to recommend
    min_confidence: float = 0.3,
    conservative: bool = False,
    max_edge: float = 1.0,  # No practical cap - show all edges
) -> list:
    """
    Evaluate all possible bets for a single game.
    Returns list of bet recommendations sorted by EV.

    conservative mode: only totals and moneylines, higher min edge
    """
    bets = []
    confidence = blended_probs.get("model_confidence", 0)

    # Skip if confidence is too low
    if confidence < min_confidence:
        return bets

    # In conservative mode, raise the bar
    if conservative:
        min_edge = max(min_edge, 0.03)  # At least 3% edge
        min_confidence = max(min_confidence, 0.5)

    # --- MONEYLINE BETS ---
    # Evaluate both but only keep the one with higher edge (if any)
    home_ml_bet = None
    away_ml_bet = None
    
    if best_odds["moneyline"]["home"]:
        ev_data = calculate_ev(
            true_prob=blended_probs["home_win_prob"],
            american_odds=best_odds["moneyline"]["home"]["price"],
            stake=stake,
        )
        if ev_data["edge"] >= min_edge and ev_data["edge"] <= max_edge:
            home_ml_bet = {
                "game": game_label,
                "bet_type": "Moneyline",
                "pick": f"{home_team} ML",
                "book": best_odds["moneyline"]["home"]["book"],
                "odds": best_odds["moneyline"]["home"]["price"],
                **ev_data,
                "confidence": confidence,
            }

    if best_odds["moneyline"]["away"]:
        ev_data = calculate_ev(
            true_prob=blended_probs["away_win_prob"],
            american_odds=best_odds["moneyline"]["away"]["price"],
            stake=stake,
        )
        if ev_data["edge"] >= min_edge and ev_data["edge"] <= max_edge:
            away_ml_bet = {
                "game": game_label,
                "bet_type": "Moneyline",
                "pick": f"{away_team} ML",
                "book": best_odds["moneyline"]["away"]["book"],
                "odds": best_odds["moneyline"]["away"]["price"],
                **ev_data,
                "confidence": confidence,
            }
    
    # Only add the ML bet with higher edge (don't recommend both sides)
    if home_ml_bet and away_ml_bet:
        if home_ml_bet["edge"] > away_ml_bet["edge"]:
            bets.append(home_ml_bet)
        else:
            bets.append(away_ml_bet)
    elif home_ml_bet:
        bets.append(home_ml_bet)
    elif away_ml_bet:
        bets.append(away_ml_bet)

    # --- SPREAD BETS ---
    # Skip spreads entirely in conservative mode (model isn't reliable enough)
    if not conservative:
        # Evaluate both but only keep the one with higher edge (if any)
        home_spread_bet = None
        away_spread_bet = None
        
        if best_odds["spread"]["home"]:
            point = best_odds["spread"]["home"]["point"]
            ev_data = calculate_ev(
                true_prob=blended_probs["home_cover_prob"],
                american_odds=best_odds["spread"]["home"]["price"],
                stake=stake,
            )
            if ev_data["edge"] >= min_edge and ev_data["edge"] <= max_edge:
                home_spread_bet = {
                    "game": game_label,
                    "bet_type": "Spread",
                    "pick": f"{home_team} {point:+.1f}",
                    "book": best_odds["spread"]["home"]["book"],
                    "odds": best_odds["spread"]["home"]["price"],
                    **ev_data,
                    "confidence": confidence,
                }

        if best_odds["spread"]["away"]:
            point = best_odds["spread"]["away"]["point"]
            ev_data = calculate_ev(
                true_prob=blended_probs["away_cover_prob"],
                american_odds=best_odds["spread"]["away"]["price"],
                stake=stake,
            )
            if ev_data["edge"] >= min_edge and ev_data["edge"] <= max_edge:
                away_spread_bet = {
                    "game": game_label,
                    "bet_type": "Spread",
                    "pick": f"{away_team} {point:+.1f}",
                    "book": best_odds["spread"]["away"]["book"],
                    "odds": best_odds["spread"]["away"]["price"],
                    **ev_data,
                    "confidence": confidence,
                }
        
        # Only add the spread bet with higher edge (don't recommend both sides)
        if home_spread_bet and away_spread_bet:
            if home_spread_bet["edge"] > away_spread_bet["edge"]:
                bets.append(home_spread_bet)
            else:
                bets.append(away_spread_bet)
        elif home_spread_bet:
            bets.append(home_spread_bet)
        elif away_spread_bet:
            bets.append(away_spread_bet)

    # --- TOTAL BETS ---
    # Evaluate ALL available total lines across all books
    # Find the line that maximizes EV based on model's expected total
    total_bets_by_line = _evaluate_all_total_lines(
        game_label, blended_probs, best_odds, stake, min_edge, max_edge, confidence
    )
    
    # Only keep the best total bet (highest EV)
    if total_bets_by_line:
        best_total = max(total_bets_by_line, key=lambda b: b["ev"])
        bets.append(best_total)

    # Also evaluate theScore specifically if available
    bets.extend(_evaluate_thescore_odds(
        game_label, home_team, away_team,
        blended_probs, best_odds, stake, min_edge
    ))

    # Sort by EV descending
    bets.sort(key=lambda b: b["ev"], reverse=True)
    return bets


def _evaluate_thescore_odds(
    game_label, home_team, away_team,
    blended_probs, best_odds, stake, min_edge
) -> list:
    """Evaluate bets specifically at theScore Bet odds."""
    bets = []
    thescore = best_odds.get("thescore", {})
    if not thescore:
        return bets

    # theScore moneyline - only keep the side with higher edge
    home_ts_bet = None
    away_ts_bet = None

    if "ml_home" in thescore:
        ev_data = calculate_ev(blended_probs["home_win_prob"], thescore["ml_home"], stake)
        if ev_data["edge"] >= min_edge:
            home_ts_bet = {
                "game": game_label,
                "bet_type": "Moneyline",
                "pick": f"{home_team} ML (theScore)",
                "book": "thescore",
                "odds": thescore["ml_home"],
                **ev_data,
                "confidence": blended_probs.get("model_confidence", 0),
            }

    if "ml_away" in thescore:
        ev_data = calculate_ev(blended_probs["away_win_prob"], thescore["ml_away"], stake)
        if ev_data["edge"] >= min_edge:
            away_ts_bet = {
                "game": game_label,
                "bet_type": "Moneyline",
                "pick": f"{away_team} ML (theScore)",
                "book": "thescore",
                "odds": thescore["ml_away"],
                **ev_data,
                "confidence": blended_probs.get("model_confidence", 0),
            }

    if home_ts_bet and away_ts_bet:
        if home_ts_bet["edge"] > away_ts_bet["edge"]:
            bets.append(home_ts_bet)
        else:
            bets.append(away_ts_bet)
    elif home_ts_bet:
        bets.append(home_ts_bet)
    elif away_ts_bet:
        bets.append(away_ts_bet)

    return bets


def format_recommendations(all_bets: list, top_n: int = 15, quota_info: dict = None) -> str:
    """
    Format the top bet recommendations into a readable report.
    """
    if not all_bets:
        return "No +EV bets found for today's games."

    # Sort all bets across all games by EV
    all_bets.sort(key=lambda b: b["ev"], reverse=True)
    top = all_bets[:top_n]

    lines = []
    lines.append("=" * 75)
    lines.append("  NHL +EV BET RECOMMENDATIONS")
    lines.append("=" * 75)
    lines.append("")
    lines.append(f"  Found {len(all_bets)} total +EV bets, showing top {min(top_n, len(all_bets))}:")
    lines.append("")

    for i, bet in enumerate(top, 1):
        edge_pct = bet["edge"]
        if edge_pct >= 0.07:
            grade = "A  "  # 7%+  exceptional, rare
        elif edge_pct >= 0.04:
            grade = "B+ "  # 4-7% very good
        elif edge_pct >= 0.03:
            grade = "B  "  # 3-4% solid sharp-level edge
        else:
            grade = "C+ "  # 2-3% thin but playable
        lines.append(f"  {i}. [{grade}] {bet['pick']}")
        lines.append(f"     Game: {bet['game']}")
        lines.append(f"     Type: {bet['bet_type']} | Book: {bet['book']}")
        lines.append(f"     Odds: {bet['odds']:+d} (decimal: {bet['decimal_odds']:.3f})")
        lines.append(f"     Model prob: {bet['true_prob']:.1%} vs Implied: {bet['implied_prob']:.1%}")
        lines.append(f"     Edge: {bet['edge']:.1%} | EV per $1: ${bet['ev']:.4f} | ROI: {bet['roi']:.2%}")
        lines.append(f"     Confidence: {bet['confidence']:.0%}")
        lines.append("")

    # Summary stats
    total_ev = sum(b["ev"] for b in top)
    avg_edge = sum(b["edge"] for b in top) / len(top)
    total_stake = sum(b["stake"] for b in top)

    lines.append("-" * 75)
    lines.append(f"  SUMMARY (top {len(top)} bets)")
    lines.append(f"  Total stake: ${total_stake:.2f} CAD")
    lines.append(f"  Total expected profit: ${total_ev:.4f} CAD")
    lines.append(f"  Average edge: {avg_edge:.2%}")
    lines.append(f"  Expected ROI: {total_ev/total_stake:.2%}")
    lines.append("=" * 75)
    lines.append("")
    lines.append("  EDGE GRADES:")
    lines.append("    A  = 7%+  exceptional (rare, verify before betting)")
    lines.append("    B+ = 4-7% very good")
    lines.append("    B  = 3-4% solid (sharp bettor territory)")
    lines.append("    C+ = 2-3% thin but playable at volume")
    lines.append("")
    lines.append("  Bet $0.50-$1.00 CAD per pick for optimal bankroll management.")
    lines.append("")
    
    # Add API quota info if available
    if quota_info:
        lines.append("-" * 75)
        lines.append("  ODDS API QUOTA")
        
        # Check if it's the new multi-key format
        if isinstance(quota_info, dict) and "total_keys" in quota_info:
            # Multi-key format
            lines.append(f"  Total API keys: {quota_info['total_keys']}")
            lines.append(f"  Combined quota: {quota_info['total_used']} used, {quota_info['total_remaining']} remaining")
            
            if len(quota_info.get('keys', [])) > 1:
                lines.append("")
                lines.append("  Per-key breakdown:")
                for key_info in quota_info['keys']:
                    lines.append(f"    Key #{key_info['index'] + 1}: {key_info['used']} used, {key_info['remaining']} remaining")
        else:
            # Old single-key format
            lines.append(f"  Requests used this month: {quota_info.get('used', '?')}")
            lines.append(f"  Requests remaining: {quota_info.get('remaining', '?')}")
            if 'last_cost' in quota_info:
                lines.append(f"  Last request cost: {quota_info['last_cost']} credit(s)")
        
        lines.append("=" * 75)
        lines.append("")

    return "\n".join(lines)


def kelly_criterion(true_prob: float, decimal_odds: float, fraction: float = 0.25) -> float:
    """
    Kelly criterion for optimal bet sizing.
    Returns fraction of bankroll to bet.
    Uses fractional Kelly (default 1/4) for safety.

    f* = (bp - q) / b
    where b = decimal_odds - 1, p = true_prob, q = 1 - p
    """
    b = decimal_odds - 1
    p = true_prob
    q = 1 - p

    full_kelly = (b * p - q) / b
    if full_kelly <= 0:
        return 0.0

    return full_kelly * fraction
