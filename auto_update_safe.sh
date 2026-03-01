#!/bin/bash
# Safe auto-update script with rate limit protection
# This version checks if enough time has passed since last run

LOG_FILE=~/Desktop/nhllines/cron.log
LAST_RUN_FILE=~/Desktop/nhllines/.last_run
MIN_INTERVAL=10800  # 3 hours in seconds

echo "=== NHL Lines Auto-Update ===" >> "$LOG_FILE"
echo "Started at: $(date)" >> "$LOG_FILE"

# Check if we should run (respect rate limits)
if [ -f "$LAST_RUN_FILE" ]; then
    LAST_RUN=$(cat "$LAST_RUN_FILE")
    CURRENT_TIME=$(date +%s)
    TIME_DIFF=$((CURRENT_TIME - LAST_RUN))
    
    if [ $TIME_DIFF -lt $MIN_INTERVAL ]; then
        echo "Skipping: Only $TIME_DIFF seconds since last run (need $MIN_INTERVAL)" >> "$LOG_FILE"
        echo "" >> "$LOG_FILE"
        exit 0
    fi
fi

# Run the update
cd ~/Desktop/nhllines

# Activate venv and run analysis
source venv/bin/activate
python3 main.py --stake 0.50 --conservative >> "$LOG_FILE" 2>&1

if [ $? -ne 0 ]; then
    echo "❌ Analysis failed - check log for details" >> "$LOG_FILE"
    echo "" >> "$LOG_FILE"
    exit 1
fi

# Copy files
cp latest_analysis.json ~/Desktop/projects/public/nhllines/

# Build and deploy
cd ~/Desktop/projects
npm run build >> "$LOG_FILE" 2>&1
cp -r public/nhllines build/
firebase deploy --only hosting >> "$LOG_FILE" 2>&1

if [ $? -eq 0 ]; then
    echo "✅ Deployment successful at $(date)" >> "$LOG_FILE"
    # Save timestamp of successful run
    date +%s > "$LAST_RUN_FILE"
else
    echo "❌ Deployment failed" >> "$LOG_FILE"
fi

echo "" >> "$LOG_FILE"
