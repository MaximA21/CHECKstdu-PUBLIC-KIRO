#!/bin/bash

# Start HTTP server for container deployment

set -e

# Default values
CONFIG_DIR=${CONFIG_DIR:-"config"}
PORT=${PORT:-8080}
APP_ENVIRONMENT=${APP_ENVIRONMENT:-"development"}

echo "Starting WebWunder HTTP Server..."
echo "Environment: $APP_ENVIRONMENT"
echo "Port: $PORT"
echo "Config Directory: $CONFIG_DIR"

# Set Python path
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# Start the server
python -m src.presentation.http_server