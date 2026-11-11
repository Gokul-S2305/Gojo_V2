#!/usr/bin/env bash
# exit on error
set -o errexit

# Install Python dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Run database migrations
python -m alembic upgrade head

# Create fallback directories
mkdir -p uploads/docs
mkdir -p app/static
mkdir -p app/templates

echo "Build completed successfully!"
