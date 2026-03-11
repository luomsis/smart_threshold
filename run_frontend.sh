#!/bin/bash
# SmartThreshold Frontend Server Management Script

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_DIR="$SCRIPT_DIR/frontend"
PID_FILE="$SCRIPT_DIR/.frontend.pid"
LOG_FILE="$SCRIPT_DIR/frontend.log"
PORT="3000"

cd "$FRONTEND_DIR"

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

start() {
    if is_running; then
        log_warn "Frontend server is already running (PID: $(get_pid))"
        return 1
    fi

    log_info "Starting SmartThreshold Frontend server..."
    log_info "Open http://localhost:$PORT in your browser"

    # Start server in background
    nohup python3 -m http.server $PORT > "$LOG_FILE" 2>&1 &
    local pid=$!
    echo $pid > "$PID_FILE"

    sleep 1
    if is_running; then
        log_info "Frontend server started (PID: $pid)"
        return 0
    else
        log_error "Failed to start frontend server"
        log_error "Check $LOG_FILE for details"
        rm -f "$PID_FILE"
        return 1
    fi
}

stop() {
    if ! is_running; then
        log_warn "Frontend server is not running"
        rm -f "$PID_FILE"
        return 1
    fi

    local pid=$(get_pid)
    log_info "Stopping frontend server (PID: $pid)..."

    kill "$pid" 2>/dev/null

    # Wait for process to stop
    local count=0
    while ps -p "$pid" > /dev/null 2>&1 && [ $count -lt 10 ]; do
        sleep 1
        count=$((count + 1))
    done

    if ps -p "$pid" > /dev/null 2>&1; then
        log_warn "Force killing frontend server..."
        kill -9 "$pid" 2>/dev/null
    fi

    rm -f "$PID_FILE"
    log_info "Frontend server stopped"
    return 0
}

restart() {
    log_info "Restarting frontend server..."
    stop
    sleep 1
    start
}

status() {
    if is_running; then
        local pid=$(get_pid)
        log_info "Frontend server is running (PID: $pid)"
        log_info "Port: $PORT"
        log_info "URL: http://localhost:$PORT"
        log_info "Log file: $LOG_FILE"
        return 0
    else
        log_info "Frontend server is not running"
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
        log_warn "Frontend server is already running (PID: $(get_pid)). Stop it first."
        return 1
    fi

    log_info "Starting SmartThreshold Frontend server in development mode..."
    log_info "Open http://localhost:$PORT in your browser"

    python3 -m http.server $PORT
}

usage() {
    echo "Usage: $0 {start|stop|restart|status|logs|dev}"
    echo ""
    echo "Commands:"
    echo "  start   - Start frontend server in background"
    echo "  stop    - Stop frontend server"
    echo "  restart - Restart frontend server"
    echo "  status  - Check if frontend server is running"
    echo "  logs    - Follow frontend server logs"
    echo "  dev     - Start frontend server in foreground"
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