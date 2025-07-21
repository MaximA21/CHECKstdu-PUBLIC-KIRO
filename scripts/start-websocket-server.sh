#!/bin/bash

# Start WebSocket server for container deployment

set -e

# Default values
CONFIG_DIR=${CONFIG_DIR:-"config"}
WS_HOST=${WS_HOST:-"0.0.0.0"}
WS_PORT=${WS_PORT:-8081}
APP_ENVIRONMENT=${APP_ENVIRONMENT:-"development"}

echo "Starting WebWunder WebSocket Server..."
echo "Environment: $APP_ENVIRONMENT"
echo "Host: $WS_HOST"
echo "Port: $WS_PORT"
echo "Config Directory: $CONFIG_DIR"

# Set Python path
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# Start the server
python -m src.presentation.websocket_server