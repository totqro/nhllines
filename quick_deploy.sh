#!/bin/bash
# Quick deploy script - run this from nhllines folder

echo "🏒 NHL Lines - Quick Deploy"
echo "============================"
echo ""

# Copy latest analysis
echo "Copying latest_analysis.json..."
cp latest_analysis.json ~/Desktop/projects/public/nhllines/

echo "✅ Files updated"
echo ""
echo "Now run these commands:"
echo ""
echo "  cd ~/Desktop/projects"
echo "  npm run build"
echo "  firebase deploy"
echo ""
