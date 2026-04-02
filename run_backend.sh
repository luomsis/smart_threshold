#!/bin/bash
# SmartThreshold Backend Server & Celery Worker Management Script

# Set proxy if needed (uncomment and modify as needed)
# export http_proxy=http://127.0.0.1:1087
# export https_proxy=http://127.0.0.1:1087

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_DIR="$SCRIPT_DIR/.pids"
LOG_DIR="$SCRIPT_DIR/logs"

# PID files
API_PID_FILE="$PID_DIR/api.pid"
WORKER_PID_FILE="$PID_DIR/worker.pid"

# Log files
API_LOG_FILE="$LOG_DIR/api.log"
WORKER_LOG_FILE="$LOG_DIR/worker.log"

# Server config
HOST="0.0.0.0"
PORT="8010"

cd "$SCRIPT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
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

log_debug() {
    echo -e "${BLUE}[DEBUG]${NC} $1"
}

# Create required directories
ensure_dirs() {
    mkdir -p "$PID_DIR" "$LOG_DIR"
}

get_pid() {
    local pid_file=$1
    if [ -f "$pid_file" ]; then
        cat "$pid_file"
    fi
}

is_running() {
    local pid_file=$1
    local pid=$(get_pid "$pid_file")
    if [ -n "$pid" ]; then
        if ps -p "$pid" > /dev/null 2>&1; then
            return 0
        fi
    fi
    return 1
}

wait_for_stop() {
    local pid_file=$1
    local name=$2
    local pid=$(get_pid "$pid_file")

    if [ -z "$pid" ]; then
        return 0
    fi

    local count=0
    while ps -p "$pid" > /dev/null 2>&1 && [ $count -lt 10 ]; do
        sleep 1
        count=$((count + 1))
    done

    if ps -p "$pid" > /dev/null 2>&1; then
        return 1
    fi
    return 0
}

setup_env() {
    if [ ! -d ".venv" ]; then
        log_info "Creating virtual environment..."
        uv venv
    fi

    log_info "Installing dependencies..."
    uv pip install -e . > /dev/null 2>&1
}

# ==================== API Server ====================

api_start() {
    ensure_dirs

    if is_running "$API_PID_FILE"; then
        log_warn "API server is already running (PID: $(get_pid $API_PID_FILE))"
        return 1
    fi

    setup_env

    log_info "Starting API server on $HOST:$PORT..."
    log_info "API Documentation: http://$HOST:$PORT/api/docs"

    nohup uvicorn backend.app.main:app --host $HOST --port $PORT > "$API_LOG_FILE" 2>&1 &
    local pid=$!
    echo $pid > "$API_PID_FILE"

    sleep 1
    if is_running "$API_PID_FILE"; then
        log_info "API server started (PID: $pid)"
        return 0
    else
        log_error "Failed to start API server"
        log_error "Check $API_LOG_FILE for details"
        rm -f "$API_PID_FILE"
        return 1
    fi
}

api_stop() {
    if ! is_running "$API_PID_FILE"; then
        log_warn "API server is not running"
        rm -f "$API_PID_FILE"
        return 1
    fi

    local pid=$(get_pid "$API_PID_FILE")
    log_info "Stopping API server (PID: $pid)..."

    kill "$pid" 2>/dev/null

    if wait_for_stop "$API_PID_FILE" "API"; then
        rm -f "$API_PID_FILE"
        log_info "API server stopped"
        return 0
    else
        log_warn "Force killing API server..."
        kill -9 "$pid" 2>/dev/null
        rm -f "$API_PID_FILE"
        log_info "API server killed"
        return 0
    fi
}

api_status() {
    if is_running "$API_PID_FILE"; then
        local pid=$(get_pid "$API_PID_FILE")
        log_info "API server: ${GREEN}running${NC} (PID: $pid)"
        log_info "  Listen: http://$HOST:$PORT"
        log_info "  Docs: http://$HOST:$PORT/api/docs"
        log_info "  Log: $API_LOG_FILE"
        return 0
    else
        log_info "API server: ${RED}stopped${NC}"
        return 1
    fi
}

api_logs() {
    if [ -f "$API_LOG_FILE" ]; then
        tail -f "$API_LOG_FILE"
    else
        log_warn "No log file found at $API_LOG_FILE"
    fi
}

# ==================== Celery Worker ====================

worker_start() {
    ensure_dirs

    if is_running "$WORKER_PID_FILE"; then
        log_warn "Celery worker is already running (PID: $(get_pid $WORKER_PID_FILE))"
        return 1
    fi

    setup_env

    log_info "Starting Celery worker..."

    nohup uv run celery -A backend.tasks.celery_app worker --loglevel=info > "$WORKER_LOG_FILE" 2>&1 &
    local pid=$!
    echo $pid > "$WORKER_PID_FILE"

    sleep 2
    if is_running "$WORKER_PID_FILE"; then
        log_info "Celery worker started (PID: $pid)"
        return 0
    else
        log_error "Failed to start Celery worker"
        log_error "Check $WORKER_LOG_FILE for details"
        rm -f "$WORKER_PID_FILE"
        return 1
    fi
}

worker_stop() {
    if ! is_running "$WORKER_PID_FILE"; then
        log_warn "Celery worker is not running"
        rm -f "$WORKER_PID_FILE"
        return 1
    fi

    local pid=$(get_pid "$WORKER_PID_FILE")
    log_info "Stopping Celery worker (PID: $pid)..."

    # Send SIGTERM for graceful shutdown
    kill "$pid" 2>/dev/null

    if wait_for_stop "$WORKER_PID_FILE" "Worker"; then
        rm -f "$WORKER_PID_FILE"
        log_info "Celery worker stopped"
        return 0
    else
        log_warn "Force killing Celery worker..."
        kill -9 "$pid" 2>/dev/null
        rm -f "$WORKER_PID_FILE"
        log_info "Celery worker killed"
        return 0
    fi
}

worker_status() {
    if is_running "$WORKER_PID_FILE"; then
        local pid=$(get_pid "$WORKER_PID_FILE")
        log_info "Celery worker: ${GREEN}running${NC} (PID: $pid)"
        log_info "  Log: $WORKER_LOG_FILE"

        # Try to get worker info
        local worker_info=$(uv run celery -A backend.tasks.celery_app inspect stats 2>/dev/null | head -5)
        if [ -n "$worker_info" ]; then
            log_info "  Status: Active"
        fi
        return 0
    else
        log_info "Celery worker: ${RED}stopped${NC}"
        return 1
    fi
}

worker_logs() {
    if [ -f "$WORKER_LOG_FILE" ]; then
        tail -f "$WORKER_LOG_FILE"
    else
        log_warn "No log file found at $WORKER_LOG_FILE"
    fi
}

# ==================== Combined Commands ====================

start_all() {
    log_info "Starting all services..."
    api_start
    worker_start
    log_info "All services started"
}

stop_all() {
    log_info "Stopping all services..."
    worker_stop
    api_stop
    log_info "All services stopped"
}

restart_all() {
    log_info "Restarting all services..."
    stop_all
    sleep 2
    start_all
}

status_all() {
    echo ""
    echo "=========================================="
    echo " SmartThreshold Service Status"
    echo "=========================================="
    api_status
    echo ""
    worker_status
    echo "=========================================="
    echo ""
}

dev() {
    ensure_dirs

    if is_running "$API_PID_FILE"; then
        log_warn "API server is already running (PID: $(get_pid $API_PID_FILE)). Stop it first."
        return 1
    fi

    setup_env

    log_info "Starting API server in development mode on $HOST:$PORT..."
    log_info "API Documentation: http://$HOST:$PORT/api/docs"

    uvicorn backend.app.main:app --reload --host $HOST --port $PORT
}

worker_dev() {
    ensure_dirs

    if is_running "$WORKER_PID_FILE"; then
        log_warn "Celery worker is already running (PID: $(get_pid $WORKER_PID_FILE)). Stop it first."
        return 1
    fi

    setup_env

    log_info "Starting Celery worker in foreground..."
    uv run celery -A backend.tasks.celery_app worker --loglevel=debug
}

usage() {
    echo ""
    echo "SmartThreshold Backend Management Script"
    echo ""
    echo "Usage: $0 <command> [options]"
    echo ""
    echo "Commands:"
    echo ""
    echo "  Service Management (All):"
    echo "    start           Start API server and Celery worker"
    echo "    stop            Stop API server and Celery worker"
    echo "    restart         Restart all services"
    echo "    status          Show status of all services"
    echo ""
    echo "  API Server:"
    echo "    api-start       Start API server in background"
    echo "    api-stop        Stop API server"
    echo "    api-status      Show API server status"
    echo "    api-logs        Follow API server logs"
    echo "    dev             Start API server in foreground (with auto-reload)"
    echo ""
    echo "  Celery Worker:"
    echo "    worker-start    Start Celery worker in background"
    echo "    worker-stop     Stop Celery worker"
    echo "    worker-status   Show Celery worker status"
    echo "    worker-logs     Follow Celery worker logs"
    echo "    worker-dev      Start Celery worker in foreground (debug mode)"
    echo ""
    echo "  Logs:"
    echo "    logs            Follow all logs (API + Worker)"
    echo ""
    echo "Examples:"
    echo "  $0 start              # Start all services"
    echo "  $0 dev                # Start API in dev mode"
    echo "  $0 worker-dev         # Start Worker in foreground"
    echo "  $0 status             # Check all services"
    echo ""
}

logs_all() {
    log_info "Following all logs (Ctrl+C to exit)..."
    if [ -f "$API_LOG_FILE" ] && [ -f "$WORKER_LOG_FILE" ]; then
        tail -f "$API_LOG_FILE" "$WORKER_LOG_FILE"
    elif [ -f "$API_LOG_FILE" ]; then
        tail -f "$API_LOG_FILE"
    elif [ -f "$WORKER_LOG_FILE" ]; then
        tail -f "$WORKER_LOG_FILE"
    else
        log_warn "No log files found"
    fi
}

# Main
case "${1:-}" in
    # Combined commands
    start)
        start_all
        ;;
    stop)
        stop_all
        ;;
    restart)
        restart_all
        ;;
    status)
        status_all
        ;;
    logs)
        logs_all
        ;;

    # API commands
    api-start)
        api_start
        ;;
    api-stop)
        api_stop
        ;;
    api-status)
        api_status
        ;;
    api-logs)
        api_logs
        ;;
    dev)
        dev
        ;;

    # Worker commands
    worker-start)
        worker_start
        ;;
    worker-stop)
        worker_stop
        ;;
    worker-status)
        worker_status
        ;;
    worker-logs)
        worker_logs
        ;;
    worker-dev)
        worker_dev
        ;;

    # Help
    -h|--help|help)
        usage
        ;;
    *)
        usage
        exit 1
        ;;
esac