"""
NHL Betting Model
Compares current matchups to similar historical games to estimate
true win probabilities, expected total goals, and spread coverage.
Uses these to find +EV bets.
"""

import math
from typing import Optional


def calculate_similarity(
    home_stats: dict,
    away_stats: dict,
    hist_home_stats: dict,
    hist_away_stats: dict,
    h2h: dict,
    hist_game: dict,
    current_home: str,
    current_away: str,
) -> float:
    """
    Calculate how similar a historical game is to the current matchup.
    Returns a similarity score (higher = more similar, max ~1.0).

    Factors:
    - Team quality differential (points %, win %)
    - Offensive/defensive strength match
    - Home/away context
    - Head-to-head relevance
    """
    score = 0.0
    max_score = 0.0

    # 1. Team quality differential similarity (weight: 3)
    # Compare the gap between teams in current vs historical
    weight = 3.0
    max_score += weight
    current_diff = home_stats.get("win_pct", 0.5) - away_stats.get("win_pct", 0.5)
    hist_diff = hist_home_stats.get("win_pct", 0.5) - hist_away_stats.get("win_pct", 0.5)
    quality_sim = 1.0 - min(abs(current_diff - hist_diff), 1.0)
    score += weight * quality_sim

    # 2. Home team offensive strength similarity (weight: 2)
    weight = 2.0
    max_score += weight
    current_home_gf = home_stats.get("avg_gf", 3.0)
    hist_home_gf = hist_home_stats.get("avg_gf", 3.0)
    off_sim = 1.0 - min(abs(current_home_gf - hist_home_gf) / 3.0, 1.0)
    score += weight * off_sim

    # 3. Away team offensive strength similarity (weight: 2)
    weight = 2.0
    max_score += weight
    current_away_gf = away_stats.get("avg_gf", 3.0)
    hist_away_gf = hist_away_stats.get("avg_gf", 3.0)
    off_sim2 = 1.0 - min(abs(current_away_gf - hist_away_gf) / 3.0, 1.0)
    score += weight * off_sim2

    # 4. Home team defensive strength similarity (weight: 2)
    weight = 2.0
    max_score += weight
    current_home_ga = home_stats.get("avg_ga", 3.0)
    hist_home_ga = hist_home_stats.get("avg_ga", 3.0)
    def_sim = 1.0 - min(abs(current_home_ga - hist_home_ga) / 3.0, 1.0)
    score += weight * def_sim

    # 5. Away team defensive strength similarity (weight: 2)
    weight = 2.0
    max_score += weight
    current_away_ga = away_stats.get("avg_ga", 3.0)
    hist_away_ga = hist_away_stats.get("avg_ga", 3.0)
    def_sim2 = 1.0 - min(abs(current_away_ga - hist_away_ga) / 3.0, 1.0)
    score += weight * def_sim2

    # 6. Same teams bonus (weight: 2)
    weight = 2.0
    max_score += weight
    if (hist_game["home_team"] == current_home and hist_game["away_team"] == current_away):
        score += weight  # Exact same matchup
    elif (hist_game["home_team"] == current_away and hist_game["away_team"] == current_home):
        score += weight * 0.5  # Same teams, reversed home/away
    # else: no bonus

    # 7. Points percentage similarity for both teams (weight: 2)
    weight = 2.0
    max_score += weight
    current_home_ppct = home_stats.get("points_pct", 0.5)
    hist_home_ppct = hist_home_stats.get("points_pct", 0.5)
    current_away_ppct = away_stats.get("points_pct", 0.5)
    hist_away_ppct = hist_away_stats.get("points_pct", 0.5)
    ppct_sim = 1.0 - (
        abs(current_home_ppct - hist_home_ppct) +
        abs(current_away_ppct - hist_away_ppct)
    ) / 2.0
    score += weight * max(ppct_sim, 0)

    return score / max_score if max_score > 0 else 0.0


def find_similar_games(
    home_team: str,
    away_team: str,
    standings: dict,
    all_games: list,
    team_forms: dict,
    n_similar: int = 50,
    min_similarity: float = 0.55,
) -> list:
    """
    Find the N most similar historical games to the current matchup.
    Returns list of (game, similarity_score) tuples.
    """
    home_standing = standings.get(home_team, {})
    away_standing = standings.get(away_team, {})
    home_form = team_forms.get(home_team, {"win_pct": 0.5, "avg_gf": 3.0, "avg_ga": 3.0})
    away_form = team_forms.get(away_team, {"win_pct": 0.5, "avg_gf": 3.0, "avg_ga": 3.0})

    # Blend standings and recent form
    home_stats = {
        "win_pct": 0.4 * home_standing.get("win_pct", 0.5) + 0.6 * home_form.get("win_pct", 0.5),
        "avg_gf": 0.4 * home_standing.get("goals_for_pg", 3.0) + 0.6 * home_form.get("avg_gf", 3.0),
        "avg_ga": 0.4 * home_standing.get("goals_against_pg", 3.0) + 0.6 * home_form.get("avg_ga", 3.0),
        "points_pct": home_standing.get("points_pct", 0.5),
    }
    away_stats = {
        "win_pct": 0.4 * away_standing.get("win_pct", 0.5) + 0.6 * away_form.get("win_pct", 0.5),
        "avg_gf": 0.4 * away_standing.get("goals_for_pg", 3.0) + 0.6 * away_form.get("avg_gf", 3.0),
        "avg_ga": 0.4 * away_standing.get("goals_against_pg", 3.0) + 0.6 * away_form.get("avg_ga", 3.0),
        "points_pct": away_standing.get("points_pct", 0.5),
    }

    scored_games = []

    for game in all_games:
        # Need stats for the historical teams at that time
        # We approximate using current standings (simplification)
        hist_home = game["home_team"]
        hist_away = game["away_team"]

        hist_home_standing = standings.get(hist_home, {})
        hist_away_standing = standings.get(hist_away, {})
        hist_home_form = team_forms.get(hist_home, {"win_pct": 0.5, "avg_gf": 3.0, "avg_ga": 3.0})
        hist_away_form = team_forms.get(hist_away, {"win_pct": 0.5, "avg_gf": 3.0, "avg_ga": 3.0})

        hist_home_stats = {
            "win_pct": 0.4 * hist_home_standing.get("win_pct", 0.5) + 0.6 * hist_home_form.get("win_pct", 0.5),
            "avg_gf": 0.4 * hist_home_standing.get("goals_for_pg", 3.0) + 0.6 * hist_home_form.get("avg_gf", 3.0),
            "avg_ga": 0.4 * hist_home_standing.get("goals_against_pg", 3.0) + 0.6 * hist_home_form.get("avg_ga", 3.0),
            "points_pct": hist_home_standing.get("points_pct", 0.5),
        }
        hist_away_stats = {
            "win_pct": 0.4 * hist_away_standing.get("win_pct", 0.5) + 0.6 * hist_away_form.get("win_pct", 0.5),
            "avg_gf": 0.4 * hist_away_standing.get("goals_for_pg", 3.0) + 0.6 * hist_away_form.get("avg_gf", 3.0),
            "avg_ga": 0.4 * hist_away_standing.get("goals_against_pg", 3.0) + 0.6 * hist_away_form.get("avg_ga", 3.0),
            "points_pct": hist_away_standing.get("points_pct", 0.5),
        }

        h2h = {"games": 0}  # Simplified for speed

        similarity = calculate_similarity(
            home_stats, away_stats,
            hist_home_stats, hist_away_stats,
            h2h, game,
            home_team, away_team,
        )

        if similarity >= min_similarity:
            scored_games.append((game, similarity))

    # Sort by similarity descending
    scored_games.sort(key=lambda x: x[1], reverse=True)
    return scored_games[:n_similar]


def estimate_probabilities(
    similar_games: list,
    home_team: str,
    away_team: str,
    total_line: Optional[float] = None,
    spread_line: Optional[float] = None,
) -> dict:
    """
    From similar historical games, estimate:
    - Home win probability
    - Expected total goals
    - Spread coverage probability
    Uses similarity-weighted averages.
    """
    if not similar_games:
        return {
            "home_win_prob": 0.5,
            "away_win_prob": 0.5,
            "expected_total": 6.0,
            "over_prob": 0.5,
            "under_prob": 0.5,
            "home_cover_prob": 0.5,
            "n_games": 0,
            "confidence": 0.0,
        }

    total_weight = 0
    weighted_home_wins = 0
    weighted_total_goals = 0
    weighted_overs = 0
    weighted_home_covers = 0
    goal_totals = []

    for game, similarity in similar_games:
        weight = similarity ** 2  # Square to emphasize more similar games
        total_weight += weight

        # Home win (in the context of the similar game)
        if game.get("home_win"):
            weighted_home_wins += weight

        # Total goals
        total_goals = game.get("total_goals", 0)
        weighted_total_goals += weight * total_goals
        goal_totals.append(total_goals)

        # Over/under
        if total_line is not None and total_goals > total_line:
            weighted_overs += weight
        elif total_line is not None and total_goals == total_line:
            weighted_overs += weight * 0.5  # Push

        # Spread coverage
        if spread_line is not None:
            goal_diff = game.get("goal_diff", 0)
            if goal_diff + spread_line > 0:
                weighted_home_covers += weight
            elif goal_diff + spread_line == 0:
                weighted_home_covers += weight * 0.5

    if total_weight == 0:
        total_weight = 1

    home_win_prob = weighted_home_wins / total_weight
    expected_total = weighted_total_goals / total_weight

    # If no total line given, use expected total as reference
    if total_line is None:
        total_line = round(expected_total * 2) / 2  # Round to nearest 0.5
        # Recalculate over prob with this line
        over_count = sum(1 for g, _ in similar_games if g.get("total_goals", 0) > total_line)
        push_count = sum(1 for g, _ in similar_games if g.get("total_goals", 0) == total_line)
        over_prob = (over_count + push_count * 0.5) / len(similar_games)
    else:
        over_prob = weighted_overs / total_weight

    home_cover_prob = weighted_home_covers / total_weight if spread_line is not None else 0.5

    # Confidence based on:
    # 1. How many highly-similar games we found (similarity > 0.75)
    # 2. Average similarity of top games
    # 3. Whether we have same-team matchups
    avg_similarity = sum(s for _, s in similar_games) / len(similar_games)
    top5_avg = sum(s for _, s in similar_games[:5]) / min(5, len(similar_games))
    high_sim_count = sum(1 for _, s in similar_games if s > 0.75)
    exact_matchups = sum(1 for g, _ in similar_games
                         if g["home_team"] == home_team and g["away_team"] == away_team)

    # Base confidence from quality of matches (0-0.5)
    quality_conf = min(0.5, top5_avg * 0.55)
    # Bonus from volume of good matches (0-0.3)
    volume_conf = min(0.3, high_sim_count / 25)
    # Bonus from exact matchup history (0-0.2)
    exact_conf = min(0.2, exact_matchups / 5)

    confidence = min(0.95, quality_conf + volume_conf + exact_conf)

    # Apply regression to the mean based on confidence
    # Low confidence -> pull toward 50/50, high confidence -> trust the model
    regressed_home_prob = home_win_prob * confidence + 0.5 * (1 - confidence)
    regressed_over_prob = over_prob * confidence + 0.5 * (1 - confidence)
    # Spreads are harder to predict — extra regression (use confidence * 0.6)
    spread_conf = confidence * 0.6
    regressed_cover_prob = home_cover_prob * spread_conf + 0.5 * (1 - spread_conf)

    return {
        "home_win_prob": regressed_home_prob,
        "away_win_prob": 1 - regressed_home_prob,
        "expected_total": expected_total,
        "over_prob": regressed_over_prob,
        "under_prob": 1 - regressed_over_prob,
        "home_cover_prob": regressed_cover_prob,
        "away_cover_prob": 1 - regressed_cover_prob,
        "total_line": total_line,
        "spread_line": spread_line,
        "n_games": len(similar_games),
        "avg_similarity": avg_similarity,
        "confidence": confidence,
        "raw_home_win_prob": home_win_prob,
        "raw_over_prob": over_prob,
        "goal_distribution": _goal_distribution(goal_totals),
    }


def _goal_distribution(totals: list) -> dict:
    """Simple distribution of total goals in similar games."""
    if not totals:
        return {}
    dist = {}
    for t in totals:
        dist[t] = dist.get(t, 0) + 1
    for k in dist:
        dist[k] = dist[k] / len(totals)
    return dict(sorted(dist.items()))


def blend_model_and_market(
    model_probs: dict,
    market_probs: dict,
    model_weight: float = 0.35,
) -> dict:
    """
    Blend our model's probabilities with market consensus.
    Market is generally efficient, so we only deviate when our model
    has high confidence and disagrees.

    model_weight: how much to trust our model vs market (0-1)
    Higher confidence -> trust model more.
    """
    confidence = model_probs.get("confidence", 0)
    # Scale model weight by confidence
    effective_weight = model_weight * confidence

    blended = {}

    # Moneyline
    blended["home_win_prob"] = (
        effective_weight * model_probs["home_win_prob"] +
        (1 - effective_weight) * market_probs.get("home_win_prob", 0.5)
    )
    blended["away_win_prob"] = 1 - blended["home_win_prob"]

    # Totals
    blended["over_prob"] = (
        effective_weight * model_probs["over_prob"] +
        (1 - effective_weight) * market_probs.get("over_prob", 0.5)
    )
    blended["under_prob"] = 1 - blended["over_prob"]

    # Spread
    blended["home_cover_prob"] = (
        effective_weight * model_probs.get("home_cover_prob", 0.5) +
        (1 - effective_weight) * market_probs.get("spread_home_cover_prob", 0.5)
    )
    blended["away_cover_prob"] = 1 - blended["home_cover_prob"]

    blended["model_confidence"] = confidence
    blended["effective_model_weight"] = effective_weight

    return blended
