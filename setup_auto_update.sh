#!/bin/bash
# Setup automatic updates every 3 hours using cron

echo "🤖 Setting up automatic NHL Lines updates"
echo "=========================================="
echo ""

# Create the cron job entry
CRON_JOB="0 */3 * * * /bin/bash ~/Desktop/nhllines/auto_update_safe.sh"

# Check if cron job already exists
if crontab -l 2>/dev/null | grep -q "nhllines"; then
    echo "⚠️  Cron job already exists. Removing old one..."
    crontab -l 2>/dev/null | grep -v "nhllines" | crontab -
fi

# Add the new cron job
echo "Adding cron job to run every 3 hours..."
(crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -

echo ""
echo "✅ Automatic updates configured!"
echo ""
echo "Schedule: Every 3 hours (at :00 minutes)"
echo "Next runs: 12:00 AM, 3:00 AM, 6:00 AM, 9:00 AM, 12:00 PM, 3:00 PM, 6:00 PM, 9:00 PM"
echo ""
echo "Logs will be saved to: ~/Desktop/nhllines/cron.log"
echo ""
echo "To view your cron jobs:"
echo "  crontab -l"
echo ""
echo "To view the log:"
echo "  tail -f ~/Desktop/nhllines/cron.log"
echo ""
echo "To remove automatic updates:"
echo "  crontab -l | grep -v nhllines | crontab -"
echo ""
