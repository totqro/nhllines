# Injury Adjustment System Review

## Issue Identified

The CHI @ VGK game showed a -20% injury adjustment that completely flipped the prediction:
- Model: VGK 67.5% / CHI 32.5%
- Market: VGK 66.8% / CHI 33.2%
- After injury adjustment: VGK 47.1% / CHI 52.9%

This resulted in CHI ML being flagged as a 19% edge bet at +195 odds.

## Root Cause

The injury adjustment coefficient is set to `-0.02` per point of injury impact difference.

Current calculation:
```python
net_impact = home_score - away_score  # VGK: 0, CHI: 10 → net_impact = -10
win_prob_adjustment = -net_impact * coef  # -(-10) * (-0.02) = -0.20 = -20%
```

With CHI having 10 injury points and VGK having 0, this creates a 20% swing, which is extreme.

## Problems with Current System

1. **Too Aggressive**: A 2% swing per injury point means:
   - 5-point difference = 10% adjustment
   - 10-point difference = 20% adjustment (capped at max)
   - This can completely override model and market consensus

2. **No Historical Validation**: The coefficient of -0.02 appears to be arbitrary, not derived from historical data showing actual impact of injuries on game outcomes.

3. **Injury Impact Scoring May Be Inflated**: If the injury impact calculation itself is too generous (giving 10 points for relatively minor injuries), the problem compounds.

4. **Overrides Strong Signals**: When both model (67.5%) and market (66.8%) agree VGK is heavily favored, a 20% injury adjustment that flips the prediction is suspicious.

## Recommendations

### Option 1: Reduce Coefficient (Conservative)
Change coefficient from `-0.02` to `-0.005` or `-0.01`:
- 5-point difference = 2.5-5% adjustment (reasonable)
- 10-point difference = 5-10% adjustment (significant but not overwhelming)

### Option 2: Cap Adjustments More Aggressively
Keep coefficient but cap at ±10% instead of ±20%:
```python
win_prob_adjustment = max(-0.10, min(0.10, win_prob_adjustment))
```

### Option 3: Scale Non-Linearly
Use diminishing returns for large injury differences:
```python
# Square root scaling reduces impact of large differences
scaled_impact = math.copysign(math.sqrt(abs(net_impact)), net_impact)
win_prob_adjustment = -scaled_impact * 0.03
```

### Option 4: Require Consensus (Recommended)
Only apply injury adjustments when they align with model OR market direction:
```python
# If model and market both favor VGK, don't flip to CHI
if (model_favors_home and adjustment < 0) or (model_favors_away and adjustment > 0):
    # Adjustment goes against consensus, reduce it
    win_prob_adjustment *= 0.3  # Only apply 30% of adjustment
```

## Immediate Action

For today's CHI @ VGK bet:
- The 19% edge is likely inflated due to over-aggressive injury adjustment
- CHI may still have value, but probably closer to 5-10% edge, not 19%
- Consider this a B-grade bet rather than A-grade

## Testing Plan

1. **Historical Backtest**: Analyze past games where injury adjustments were applied
   - Compare prediction accuracy with vs without adjustments
   - Measure if adjustments improve or hurt performance
   - Determine optimal coefficient empirically

2. **Injury Impact Validation**: Review how injury impact scores are calculated
   - Are 10-point impacts truly representing significant roster degradation?
   - Should day-to-day injuries count less?
   - Should depth players count less than stars?

3. **Consensus Check**: Implement safeguards
   - Flag bets where injury adjustment contradicts both model and market
   - Require manual review for adjustments > 10%
   - Log all large adjustments for post-game analysis

## Proposed Changes

### File: `src/analysis/injury_impact_enhanced.py`

```python
# Line 28: Reduce coefficient
'injury_win_prob_coefficient': -0.005,  # Changed from -0.02

# Line 77: Add consensus check
def calculate_injury_win_prob_adjustment(home_injuries, away_injuries, 
                                         home_team, away_team,
                                         model_home_prob=None,  # NEW
                                         market_home_prob=None):  # NEW
    # ... existing code ...
    
    # Win probability adjustment
    win_prob_adjustment = -net_impact * coef
    
    # NEW: Reduce adjustment if it contradicts consensus
    if model_home_prob and market_home_prob:
        model_favors_home = model_home_prob > 0.5
        market_favors_home = market_home_prob > 0.5
        adjustment_favors_home = win_prob_adjustment > 0
        
        # If adjustment contradicts BOTH model and market, reduce it
        if (model_favors_home == market_favors_home and 
            adjustment_favors_home != model_favors_home):
            win_prob_adjustment *= 0.3  # Only apply 30%
    
    # Cap adjustment at ±10% (changed from ±20%)
    win_prob_adjustment = max(-0.10, min(0.10, win_prob_adjustment))
    
    return {
        'home_win_prob_adjustment': win_prob_adjustment,
        # ... rest of return dict ...
    }
```

## Conclusion

The injury adjustment system needs calibration. The current -0.02 coefficient is too aggressive and can override strong consensus signals. Recommend reducing to -0.005 and adding consensus checks to prevent extreme adjustments that contradict both model and market.

The CHI @ VGK bet should be approached cautiously - it may have value, but the 19% edge is likely overstated.
