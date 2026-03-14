# Adjustment System Improvements - March 14, 2026

## Summary

Implemented improvements to both injury and goalie adjustment systems to prevent extreme adjustments that override model and market consensus.

## Changes Made

### 1. Injury Adjustments

**Problem**: CHI @ VGK showed -20% injury adjustment that flipped strong consensus
- Model: VGK 67.5%, Market: VGK 66.8%
- After adjustment: CHI 52.9% (complete reversal)

**Fixes**:
- Reduced coefficient from -0.02 to -0.005 (75% reduction)
- Cap reduced from ±20% to ±10%
- Added consensus check: reduces adjustment to 30% if contradicting both model and market
- Now 10-point injury difference = 5% adjustment (was 20%)

**Files Modified**:
- `src/analysis/injury_impact_enhanced.py`
- `main.py` (passes model/market probs to injury function)

### 2. Goalie Adjustments

**Improvements**:
- Increased sample size from 10 to 15 games for recent form
- Created new `goalie_adjustment.py` module with consensus checks
- Cap total adjustment at ±8% (was ~10%)
- Added consensus check similar to injuries

**Files Modified**:
- `src/analysis/goalie_tracker.py` (15 games instead of 10)
- `src/analysis/goalie_adjustment.py` (new module)
- `src/analysis/__init__.py` (exports new functions)

### 3. Documentation

**New Documents**:
- `docs/INJURY_ADJUSTMENT_REVIEW.md` - Detailed injury system analysis
- `docs/GOALIE_ADJUSTMENT_REVIEW.md` - Detailed goalie system analysis
- `docs/ADJUSTMENT_SYSTEM_IMPROVEMENTS.md` - This summary

**Analysis Scripts**:
- `analyze_injury_impact.py` - Historical validation tool (needs historical injury data)

## Expected Impact

### Injury Adjustments
- Before: 10-point difference = 20% swing
- After: 10-point difference = 5% swing (or 1.5% if contradicts consensus)
- More conservative, less likely to override strong signals

### Goalie Adjustments
- Before: Max ~10% adjustment
- After: Max 8% adjustment (4% if contradicts consensus)
- Larger sample size (15 games) reduces variance

## Testing Recommendations

1. Run analysis on today's games to see new adjustment values
2. Compare CHI @ VGK prediction with new injury coefficient
3. Monitor adjustment sizes over next week
4. Backtest when historical injury data becomes available

## Next Steps

1. Deploy and test with today's games
2. Monitor for any extreme adjustments
3. Collect data for historical validation
4. Consider further reductions if adjustments still too aggressive
