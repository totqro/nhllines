"""
Expected Value Calculator
Compares model probabilities to bookmaker odds to find +EV bets.
Outputs ranked recommendations.
"""

from odds_fetcher import american_to_decimal, american_to_implied_prob


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
    max_edge: float = 0.15,  # Cap: edges above 15% are likely model errors
) -> list:
    """
    Evaluate all possible bets for a single game.
    Returns list of bet recommendations sorted by EV.

    conservative mode: only totals and moneylines, higher min edge, cap unrealistic edges
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
    # Home ML
    if best_odds["moneyline"]["home"]:
        ev_data = calculate_ev(
            true_prob=blended_probs["home_win_prob"],
            american_odds=best_odds["moneyline"]["home"]["price"],
            stake=stake,
        )
        if ev_data["edge"] >= min_edge and ev_data["edge"] <= max_edge:
            bets.append({
                "game": game_label,
                "bet_type": "Moneyline",
                "pick": f"{home_team} ML",
                "book": best_odds["moneyline"]["home"]["book"],
                "odds": best_odds["moneyline"]["home"]["price"],
                **ev_data,
                "confidence": confidence,
            })

    # Away ML
    if best_odds["moneyline"]["away"]:
        ev_data = calculate_ev(
            true_prob=blended_probs["away_win_prob"],
            american_odds=best_odds["moneyline"]["away"]["price"],
            stake=stake,
        )
        if ev_data["edge"] >= min_edge and ev_data["edge"] <= max_edge:
            bets.append({
                "game": game_label,
                "bet_type": "Moneyline",
                "pick": f"{away_team} ML",
                "book": best_odds["moneyline"]["away"]["book"],
                "odds": best_odds["moneyline"]["away"]["price"],
                **ev_data,
                "confidence": confidence,
            })

    # --- SPREAD BETS ---
    # Skip spreads entirely in conservative mode (model isn't reliable enough)
    if not conservative:
        # Home spread (puck line)
        if best_odds["spread"]["home"]:
            point = best_odds["spread"]["home"]["point"]
            ev_data = calculate_ev(
                true_prob=blended_probs["home_cover_prob"],
                american_odds=best_odds["spread"]["home"]["price"],
                stake=stake,
            )
            if ev_data["edge"] >= min_edge and ev_data["edge"] <= max_edge:
                bets.append({
                    "game": game_label,
                    "bet_type": "Spread",
                    "pick": f"{home_team} {point:+.1f}",
                    "book": best_odds["spread"]["home"]["book"],
                    "odds": best_odds["spread"]["home"]["price"],
                    **ev_data,
                    "confidence": confidence,
                })

        # Away spread
        if best_odds["spread"]["away"]:
            point = best_odds["spread"]["away"]["point"]
            ev_data = calculate_ev(
                true_prob=blended_probs["away_cover_prob"],
                american_odds=best_odds["spread"]["away"]["price"],
                stake=stake,
            )
            if ev_data["edge"] >= min_edge and ev_data["edge"] <= max_edge:
                bets.append({
                    "game": game_label,
                    "bet_type": "Spread",
                    "pick": f"{away_team} {point:+.1f}",
                    "book": best_odds["spread"]["away"]["book"],
                    "odds": best_odds["spread"]["away"]["price"],
                    **ev_data,
                    "confidence": confidence,
                })

    # --- TOTAL BETS ---
    # Over
    if best_odds["total"]["over"]:
        point = best_odds["total"]["over"]["point"]
        ev_data = calculate_ev(
            true_prob=blended_probs["over_prob"],
            american_odds=best_odds["total"]["over"]["price"],
            stake=stake,
        )
        if ev_data["edge"] >= min_edge and ev_data["edge"] <= max_edge:
            bets.append({
                "game": game_label,
                "bet_type": "Total",
                "pick": f"Over {point}",
                "book": best_odds["total"]["over"]["book"],
                "odds": best_odds["total"]["over"]["price"],
                **ev_data,
                "confidence": confidence,
            })

    # Under
    if best_odds["total"]["under"]:
        point = best_odds["total"]["under"]["point"]
        ev_data = calculate_ev(
            true_prob=blended_probs["under_prob"],
            american_odds=best_odds["total"]["under"]["price"],
            stake=stake,
        )
        if ev_data["edge"] >= min_edge and ev_data["edge"] <= max_edge:
            bets.append({
                "game": game_label,
                "bet_type": "Total",
                "pick": f"Under {point}",
                "book": best_odds["total"]["under"]["book"],
                "odds": best_odds["total"]["under"]["price"],
                **ev_data,
                "confidence": confidence,
            })

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

    # theScore moneyline
    if "ml_home" in thescore:
        ev_data = calculate_ev(blended_probs["home_win_prob"], thescore["ml_home"], stake)
        if ev_data["edge"] >= min_edge:
            bets.append({
                "game": game_label,
                "bet_type": "Moneyline",
                "pick": f"{home_team} ML (theScore)",
                "book": "thescore",
                "odds": thescore["ml_home"],
                **ev_data,
                "confidence": blended_probs.get("model_confidence", 0),
            })

    if "ml_away" in thescore:
        ev_data = calculate_ev(blended_probs["away_win_prob"], thescore["ml_away"], stake)
        if ev_data["edge"] >= min_edge:
            bets.append({
                "game": game_label,
                "bet_type": "Moneyline",
                "pick": f"{away_team} ML (theScore)",
                "book": "thescore",
                "odds": thescore["ml_away"],
                **ev_data,
                "confidence": blended_probs.get("model_confidence", 0),
            })

    return bets


def format_recommendations(all_bets: list, top_n: int = 15) -> str:
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
