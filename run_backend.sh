#!/bin/bash
# SmartThreshold Backend Server Management Script

# Set proxy if needed (uncomment and modify as needed)
# export http_proxy=http://127.0.0.1:1087
# export https_proxy=http://127.0.0.1:1087

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$SCRIPT_DIR/.backend.pid"
LOG_FILE="$SCRIPT_DIR/backend.log"
HOST="0.0.0.0"
PORT="8010"

cd "$SCRIPT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

get_pid() {
    if [ -f "$PID_FILE" ]; then
        cat "$PID_FILE"
    fi
}

is_running() {
    local pid=$(get_pid)
    if [ -n "$pid" ]; then
        if ps -p "$pid" > /dev/null 2>&1; then
            return 0
        fi
    fi
    return 1
}

setup_env() {
    if [ ! -d ".venv" ]; then
        log_info "Creating virtual environment..."
        uv venv
    fi

    log_info "Installing dependencies..."
    uv pip install -e . > /dev/null 2>&1
}

start() {
    if is_running; then
        log_warn "Backend server is already running (PID: $(get_pid))"
        return 1
    fi

    setup_env

    log_info "Starting SmartThreshold API server..."
    log_info "API Documentation: http://localhost:$PORT/api/docs"

    # Start server in background
    nohup uvicorn backend.app.main:app --host $HOST --port $PORT > "$LOG_FILE" 2>&1 &
    local pid=$!
    echo $pid > "$PID_FILE"

    sleep 1
    if is_running; then
        log_info "Backend server started (PID: $pid)"
        return 0
    else
        log_error "Failed to start backend server"
        log_error "Check $LOG_FILE for details"
        rm -f "$PID_FILE"
        return 1
    fi
}

stop() {
    if ! is_running; then
        log_warn "Backend server is not running"
        rm -f "$PID_FILE"
        return 1
    fi

    local pid=$(get_pid)
    log_info "Stopping backend server (PID: $pid)..."

    kill "$pid" 2>/dev/null

    # Wait for process to stop
    local count=0
    while ps -p "$pid" > /dev/null 2>&1 && [ $count -lt 10 ]; do
        sleep 1
        count=$((count + 1))
    done

    if ps -p "$pid" > /dev/null 2>&1; then
        log_warn "Force killing backend server..."
        kill -9 "$pid" 2>/dev/null
    fi

    rm -f "$PID_FILE"
    log_info "Backend server stopped"
    return 0
}

restart() {
    log_info "Restarting backend server..."
    stop
    sleep 1
    start
}

status() {
    if is_running; then
        local pid=$(get_pid)
        log_info "Backend server is running (PID: $pid)"
        log_info "Host: $HOST, Port: $PORT"
        log_info "API Documentation: http://localhost:$PORT/api/docs"
        log_info "Log file: $LOG_FILE"
        return 0
    else
        log_info "Backend server is not running"
        return 1
    fi
}

logs() {
    if [ -f "$LOG_FILE" ]; then
        tail -f "$LOG_FILE"
    else
        log_warn "No log file found at $LOG_FILE"
    fi
}

dev() {
    if is_running; then
        log_warn "Backend server is already running (PID: $(get_pid)). Stop it first."
        return 1
    fi

    setup_env

    log_info "Starting SmartThreshold API server in development mode..."
    log_info "API Documentation: http://localhost:$PORT/api/docs"

    uvicorn backend.app.main:app --reload --host $HOST --port $PORT
}

usage() {
    echo "Usage: $0 {start|stop|restart|status|logs|dev}"
    echo ""
    echo "Commands:"
    echo "  start   - Start backend server in background"
    echo "  stop    - Stop backend server"
    echo "  restart - Restart backend server"
    echo "  status  - Check if backend server is running"
    echo "  logs    - Follow backend server logs"
    echo "  dev     - Start backend server in foreground with auto-reload"
}

# Main
case "${1:-}" in
    start)
        start
        ;;
    stop)
        stop
        ;;
    restart)
        restart
        ;;
    status)
        status
        ;;
    logs)
        logs
        ;;
    dev)
        dev
        ;;
    *)
        usage
        exit 1
        ;;
esac