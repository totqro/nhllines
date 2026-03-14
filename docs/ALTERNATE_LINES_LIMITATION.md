# Alternate Lines Limitation (Spreads & Totals)

**Date**: March 14, 2026

## Issue Identified

The system is currently showing **only main market lines**, not alternate lines. This affects both spreads and totals:

- **Spreads**: Only standard puck line (-1.5/+1.5), no alternates like -2.5, -3.5, etc.
- **Totals**: Only main O/U line per book (typically 6.5), no alternates like 5.5, 6.0, 7.0 from the same book

This is a limitation of The Odds API, not a bug in our code.

## Current Behavior

### Spreads
When the system recommends a spread bet, it shows:
- **NYI -1.5** @ +180 (DraftKings)
- **MTL -1.5** @ +160 (ESPN BET)

These are the **main/standard puck lines**, not alternate spreads.

### Totals
When the system recommends a total bet, it shows:
- **Under 6.5** @ +115 (Hard Rock Bet)
- **Over 6.5** @ +110 (DraftKings)

These are the **main total lines** from each book. While different books may have different main lines (5.5, 6.0, 6.5), we don't get alternate totals from the same book (e.g., FanDuel offering both 6.5 and 7.0).

## Root Cause

**The Odds API only provides main market lines:**
- Moneyline (h2h)
- Standard spread/puck line (typically -1.5/+1.5 for NHL)
- Standard totals (O/U)

**The API does NOT provide:**
- Alternate spreads (-2.5, -3.5, +2.5, etc.)
- Alternate totals (multiple O/U lines from same book)
- Player props
- Period betting
- Other exotic markets

**Note on Totals:** While you might see different total lines (5.5, 6.0, 6.5) in the recommendations, these are the main lines from different books, not alternate lines from the same book.

## Why This Matters

### Spreads
Alternate spreads can offer better value in certain situations:
- Heavy favorites: -2.5 or -3.5 might have better odds than -1.5
- Underdogs: +2.5 or +3.5 might be safer than +1.5
- Model predictions: If model predicts 3-goal margin, -2.5 might be optimal

### Totals
Alternate totals allow more precise betting:
- Model predicts 7.2 goals but main line is 6.5: O 7.0 might be better value
- Model predicts 5.8 goals but main line is 6.5: U 6.0 might be available at better odds
- Risk management: Can choose lines closer to model prediction

## Potential Solutions

### Option 1: Accept Limitation (Current State)
**Pros:**
- No additional work required
- Standard puck lines are most liquid markets
- Simpler for users

**Cons:**
- Missing potential value in alternate lines
- Less flexibility in bet sizing/risk

### Option 2: Add Alternate Spread API
**Requirements:**
- Find an API that provides alternate lines
- Most premium sports data APIs charge significantly more
- Examples: Pinnacle API, BetConstruct, SportsDataIO

**Pros:**
- Automated alternate line tracking
- Real-time odds updates

**Cons:**
- Additional cost (often $100-500/month)
- More API quota management
- Increased complexity

### Option 3: Web Scraping Specific Books
**Requirements:**
- Scrape FanDuel, DraftKings, etc. for alternate lines
- Handle anti-scraping measures
- Parse dynamic JavaScript content

**Pros:**
- Free (besides development time)
- Can target specific books

**Cons:**
- Fragile (breaks when sites change)
- Slower than API
- May violate terms of service
- Requires maintenance

### Option 4: Manual Entry for Key Games
**Requirements:**
- Add UI for manually entering alternate spreads
- Store in separate data structure
- Display alongside API odds

**Pros:**
- Simple implementation
- Full control over which games get alternates
- No additional API costs

**Cons:**
- Manual work required
- Not scalable
- Can't track all games

### Option 5: Hybrid Approach (Recommended)
**Implementation:**
1. Continue using The Odds API for main lines
2. Add optional manual entry for alternate spreads on key games
3. Display both standard and alternate options in UI
4. Track which performs better over time

**Pros:**
- Best of both worlds
- Scalable to full automation later
- Low initial cost

**Cons:**
- Requires UI changes
- Some manual work for high-value games

## Current Workaround

Users can:
1. Use the system's recommendations as a starting point
2. Manually check their sportsbook for alternate lines
3. Compare the model's predictions to available alternates:
   - **For spreads**: Check model's predicted goal differential
   - **For totals**: Check model's expected total goals vs available lines
4. Make informed decisions based on model confidence

## Example Scenarios

### Spread Example
If the model shows:
- **NYI 62.3%** to win vs CGY
- Model expects 2.1 goal margin
- Standard line: NYI -1.5 @ +180

User can manually check:
- NYI -2.5 might be @ +280 (better value if model is confident)
- NYI -0.5 might be @ -120 (safer but lower payout)

### Total Example
If the model shows:
- **Expected total: 7.3 goals**
- Main line: O/U 6.5
- Over 6.5 @ +110

User can manually check:
- Over 7.0 might be @ +140 (closer to model prediction)
- Over 7.5 might be @ +180 (higher risk, higher reward)
- Under 7.0 might be available if model is wrong

## Recommendation

For now, **accept the limitation** and focus on:
1. Improving moneyline predictions (where we have complete data)
2. Using totals strategically (we get some variety across books)
3. Adding notes in the UI about main lines vs alternates
4. Consider alternate line APIs if/when budget allows

**Key insight:** 
- Moneylines: No limitation, full data ✓
- Totals: Partial limitation (different books have different main lines, so we get some variety)
- Spreads: Full limitation (all books use -1.5/+1.5 as main line)

The main markets represent 80%+ of betting volume, so we're capturing the majority of value.

## UI Update Needed

Add clarification in the web interface:
```
Spread: NYI -1.5 @ +180 (DraftKings)
Note: Main puck line only. Check your book for alternate spreads.

Total: Over 6.5 @ +110 (DraftKings)  
Note: Main total line. Check your book for alternate totals (5.5, 6.0, 7.0, etc.)
```

## Future Enhancement

If we decide to add alternate lines, priority order:
1. Research alternate line APIs (cost/benefit analysis)
2. Prototype web scraping for 1-2 major books (FanDuel, DraftKings)
3. Add manual entry UI for testing high-value games
4. Evaluate performance vs main lines
5. Scale to full automation if ROI justifies cost

**Most valuable additions:**
1. Alternate totals (model predicts specific goal totals)
2. Alternate spreads (for heavy favorites/underdogs)
3. Live betting lines (if model can predict in-game)
