#!/usr/bin/env bash

# Exit immediately if a command exits with a non-zero status
set -e

echo "🧹 Starting cleanup of unwanted files..."

# Check and remove ngrok archive from parent directory if present
if [ -f "../ngrok-v3-stable-linux-amd64.tgz" ]; then
    echo "🗑️ Removing ngrok archive: ../ngrok-v3-stable-linux-amd64.tgz"
    rm "../ngrok-v3-stable-linux-amd64.tgz"
else
    echo "ℹ️ No ngrok archive found in parent directory."
fi

# Clean Python caches if present in backend app
echo "🧹 Cleaning Python __pycache__ and bytecode files..."
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.pyc" -delete 2>/dev/null || true

echo "📝 Preparing Git commit..."
# Add changes to staging
git add README.md
git add docker-compose.yml
git add apps/frontend/public/.gitkeep

# Commit changes
git commit -m "fix: resolve frontend docker build copy error by adding public directory and build context"


# Push to Github main branch
echo "🚀 Pushing code to GitHub..."
git push origin main

echo "✅ Git push and cleanup completed successfully!"
