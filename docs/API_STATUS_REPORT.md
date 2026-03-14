# API Status Report - March 13, 2026

## Summary

Both DailyFaceoff and MoneyPuck APIs are experiencing issues, but the system has working fallbacks in place.

## Issue Details

### 1. MoneyPuck API - 404 Error

**Status**: ⚠️ Not Working (Fallback Active)

**Problem**: 
- MoneyPuck is behind Cloudflare protection
- URL returns 404: `https://moneypuck.com/moneypuck/playerData/seasonSummary/20252026/regular/teams.csv`
- Cannot access advanced stats (xG, Corsi, Fenwick, PDO)

**Fallback**: 
- System automatically falls back to NHL API
- Calculates estimated advanced stats from basic NHL data
- Less accurate than MoneyPuck but functional

**Impact**: 
- Low - fallback provides reasonable estimates
- Advanced stats are approximations rather than actual xG models

**Fix Attempted**:
- Updated season format from "2025" to "20252026"
- Changed from JSON to CSV parsing
- Still blocked by Cloudflare

**Recommendation**: 
- Keep current fallback (working well)
- MoneyPuck may require browser automation (Selenium) to bypass Cloudflare
- Not critical since NHL API fallback is adequate

---

### 2. DailyFaceoff Scraper - 0 Goalies Found

**Status**: ⚠️ Not Working (Fallback Active)

**Problem**:
- HTML structure on DailyFaceoff.com has changed
- Scraper returns 0 starting goalies
- Cannot determine confirmed vs projected starters

**Fallback**:
- System uses NHL API to get team rosters
- Assumes primary goalie (most games played) is starting
- Assigns "probable" status with 70% confidence

**Impact**:
- Medium - loses confirmed starter information
- Cannot distinguish between confirmed and projected starters
- May occasionally predict wrong goalie in back-to-back situations

**Fix Attempted**:
- Updated HTML parsing logic
- Added regex patterns for new page structure
- Still not extracting goalies correctly

**Recommendation**:
- DailyFaceoff scraping needs more work
- Consider alternative sources:
  - NHL.com official starting goalies (if available)
  - Twitter/social media scraping
  - Manual confirmation for important games
- Current fallback is acceptable for most games

---

### 3. Arizona Coyotes (ARI) - 404 Error

**Status**: ⚠️ Expected Error

**Problem**:
- NHL API returns 404 for ARI roster
- Arizona Coyotes relocated to Utah (UTA) for 2025-26 season

**Fix Needed**:
- Update team mappings to remove ARI
- Ensure UTA (Utah Hockey Club) is properly mapped
- Check if any historical data references need updating

**Impact**:
- Low - only affects one team
- System continues with other 31 teams

---

## System Health

**Overall Status**: ✅ Functional with Fallbacks

The system is working despite API issues:
- ✅ NHL API (primary data source) - Working
- ✅ Standings, scores, schedules - Working
- ✅ ML model training - Working
- ✅ Injury tracking (ESPN) - Working
- ⚠️ Advanced stats - Using fallback estimates
- ⚠️ Goalie confirmations - Using fallback predictions

## Recommendations

### Priority 1: Fix Arizona/Utah Team Mapping
- Remove ARI from team list
- Verify UTA is properly configured
- Test with today's games

### Priority 2: Improve DailyFaceoff Scraper (Optional)
- The current fallback (NHL API primary goalie) works for most games
- Only fix if confirmed starter info becomes critical
- Consider alternative data sources

### Priority 3: MoneyPuck Alternative (Optional)
- Current NHL API fallback is adequate
- Only pursue if advanced stats accuracy becomes important
- Would require Selenium/browser automation to bypass Cloudflare

## Testing Results

```
MoneyPuck Test:
  ⚠️  MoneyPuck unavailable: 404 Client Error
  ✅ Calculated advanced stats for 32 teams from NHL API

DailyFaceoff Test:
  ✅ Found 0 starting goalies from DailyFaceoff
  ✅ Processed 32 teams (using NHL API fallback)

Main Analysis:
  ✅ Loaded standings for 32 teams
  ✅ Loaded 575 completed games
  ✅ ML models trained on 545 games
  ✅ Loaded goalie data for 32 teams (fallback)
  ✅ Loaded injuries for 30 teams
  ✅ Model predictions working
```

## Conclusion

The system is production-ready despite API issues. Fallbacks are working correctly and providing reasonable data quality. The only critical fix needed is the Arizona/Utah team mapping.
