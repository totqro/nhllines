# Goalie Adjustment System Review

## Current System Overview

The goalie adjustment system uses three main factors:

1. **Hot/Cold Streaks**: ±3% adjustment per goalie
   - Hot: Recent save % > 0.920
   - Cold: Recent save % < 0.890

2. **Quality Advantage**: +2% per 10 points of quality score difference
   - Quality score ranges from 0-100 (50 = league average)
   - Based on save %, GAA, games played, win %

3. **Combined Effect**: Multiple adjustments can stack

## Examples from Today's Games

### SEA @ VAN
```
Goalie advantage: SEA +20 points
Model prediction: VAN 26.5% / SEA 73.5%
Context: [VAN G cold] [Goalie ?: SEA +20]
```

**Analysis**:
- 20-point goalie advantage = 4% adjustment (20 / 10 * 0.02)
- VAN goalie cold = additional -3% for VAN
- Combined: ~7% swing toward SEA
- This seems reasonable given VAN's goalie is struggling

### COL @ WPG
```
Goalie advantage: COL +16 points
Model prediction: WPG 30.5% / COL 69.5%
Context: [Goalie ?: COL +16]
```

**Analysis**:
- 16-point advantage = 3.2% adjustment
- Reasonable adjustment for a significant goalie mismatch

### CGY @ NYI
```
Goalie advantage: NYI +14 points
Model prediction: NYI 73.2% / CGY 26.8%
Context: [CGY G cold] [Goalie ?: NYI +14]
```

**Analysis**:
- 14-point advantage = 2.8% adjustment
- CGY goalie cold = additional -3% for CGY
- Combined: ~6% swing toward NYI

## Current Weights (from optimize_adjustments.py)

```python
'home_goalie_hot': +0.03,      # +3% if home goalie is hot
'home_goalie_cold': -0.03,     # -3% if home goalie is cold
'away_goalie_hot': -0.03,      # -3% if away goalie is hot
'away_goalie_cold': +0.03,     # +3% if away goalie is cold
'goalie_quality_advantage': +0.02,  # +2% per 10 points of quality difference
```

## Assessment

### Strengths

1. **More Conservative than Injuries**: 
   - Max goalie adjustment ~10% (50-point difference + hot/cold)
   - Injury adjustments can reach 20%
   - Goalie adjustments are more reasonable

2. **Based on Measurable Stats**:
   - Save % and GAA are objective metrics
   - Recent form (last 10 starts) is relevant
   - Quality score methodology is sound

3. **Reasonable Thresholds**:
   - Hot: >0.920 save % (top ~25% of league)
   - Cold: <0.890 save % (bottom ~25% of league)
   - These are meaningful performance differences

### Potential Issues

1. **Stacking Can Be Aggressive**:
   - Quality advantage (20 points) = 4%
   - Hot/cold streak = 3%
   - Combined = 7% adjustment
   - With both goalies having streaks: up to 10% swing

2. **Quality Score Calculation**:
   - Need to verify the 0-100 scale is well-calibrated
   - 60% weight on save % might overweight recent performance
   - Experience bonus (games played) might favor veterans too much

3. **No Consensus Check**:
   - Unlike injuries, no safeguard against contradicting model+market
   - A 10% goalie adjustment could override strong signals

4. **Sample Size for "Recent Form"**:
   - Last 10 starts might be too small
   - One bad game can significantly impact recent save %
   - Variance in small samples

## Comparison: Goalie vs Injury Adjustments

| Factor | Goalie System | Injury System | Assessment |
|--------|---------------|---------------|------------|
| Max adjustment | ~10% | 20% | Goalie more reasonable |
| Based on | Objective stats | Subjective impact scores | Goalie more reliable |
| Consensus check | No | No | Both need improvement |
| Historical validation | Unknown | Unknown | Both need testing |
| Typical adjustment | 3-7% | 10-20% | Goalie more conservative |

## Recommendations

### Priority 1: Add Consensus Check (Same as Injuries)

```python
def apply_goalie_adjustment(base_prob, goalie_adj, model_prob, market_prob):
    """Apply goalie adjustment with consensus check."""
    
    # If adjustment contradicts both model and market, reduce it
    if model_prob and market_prob:
        model_favors_home = model_prob > 0.5
        market_favors_home = market_prob > 0.5
        adjustment_favors_home = goalie_adj > 0
        
        # If adjustment contradicts BOTH, reduce to 50%
        if (model_favors_home == market_favors_home and 
            adjustment_favors_home != model_favors_home):
            goalie_adj *= 0.5
    
    return base_prob + goalie_adj
```

### Priority 2: Cap Total Goalie Adjustment at ±8%

```python
# After calculating all goalie adjustments
total_goalie_adj = quality_adj + hot_cold_adj
total_goalie_adj = max(-0.08, min(0.08, total_goalie_adj))
```

### Priority 3: Increase Sample Size for "Recent Form"

- Change from last 10 starts to last 15 starts
- Reduces variance from single outlier games
- Still captures recent trends

### Priority 4: Review Quality Score Weights

Current weights in `get_goalie_quality_score()`:
```python
save_pct_score * 0.60 +  # 60% weight
gaa_score * 0.30 +       # 30% weight
experience_score * 0.05 + # 5% weight
win_score * 0.05         # 5% weight
```

Recommendations:
- Reduce save % weight to 50%
- Increase GAA weight to 35%
- Keep experience and win % at 5% each
- Add recent form weight at 10%

### Priority 5: Historical Validation

Create `analyze_goalie_impact.py` to:
1. Compare predictions with vs without goalie adjustments
2. Measure if adjustments improve accuracy
3. Determine optimal weights empirically
4. Validate hot/cold thresholds

## Testing Plan

```python
# Test cases to validate
test_cases = [
    {
        'scenario': 'Elite vs backup',
        'home_quality': 70,
        'away_quality': 40,
        'expected_adj': '~6%',
        'reasonable': True
    },
    {
        'scenario': 'Both average',
        'home_quality': 50,
        'away_quality': 50,
        'expected_adj': '0%',
        'reasonable': True
    },
    {
        'scenario': 'Hot vs cold',
        'home_sv_pct': 0.930,
        'away_sv_pct': 0.880,
        'expected_adj': '~6%',
        'reasonable': True
    },
    {
        'scenario': 'Extreme difference',
        'home_quality': 80,
        'away_quality': 30,
        'home_hot': True,
        'away_cold': True,
        'expected_adj': '~13%',
        'reasonable': False,  # Too high, should cap at 8%
    }
]
```

## Immediate Actions

1. **For Today's Bets**: Goalie adjustments appear reasonable
   - SEA +20 advantage is legitimate (elite vs struggling goalie)
   - No extreme adjustments like we saw with injuries

2. **Code Changes Needed**:
   - Add consensus check (Priority 1)
   - Cap at ±8% (Priority 2)
   - Increase sample size to 15 games (Priority 3)

3. **Analysis Needed**:
   - Create `analyze_goalie_impact.py`
   - Backtest goalie adjustments on historical games
   - Validate current weights

## Conclusion

The goalie adjustment system is **more reasonable than the injury system** but still needs:
1. Consensus checks to prevent contradicting strong signals
2. Tighter caps (8% instead of 10%)
3. Historical validation to confirm weights are optimal

Unlike injuries (which need a 75% reduction in coefficient), goalie adjustments are in the right ballpark but need safeguards and validation.

The current goalie adjustments in today's games (3-7% range) appear reasonable and are not causing the extreme swings we saw with the CHI injury adjustment (-20%).
