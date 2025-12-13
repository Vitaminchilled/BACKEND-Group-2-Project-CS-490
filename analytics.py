from flask import Blueprint, jsonify, request, current_app
from datetime import datetime, timezone, timedelta
from MySQLdb.cursors import DictCursor
import time
import os
import json
from collections import defaultdict, deque

analytics_bp = Blueprint('analytics', __name__)

# ============================================================================
# IN-MEMORY MONITORING STORAGE (No database changes needed!)
# ============================================================================

# Store errors in memory (last 1000 errors)
error_log = deque(maxlen=1000)

# Store uptime checks in memory (last 500 checks)
uptime_checks = deque(maxlen=500)

# Error statistics by endpoint
error_stats = defaultdict(lambda: {'count': 0, 'last_error': None})

# Response time tracking
response_times = deque(maxlen=100)

def log_error_memory(error_type, endpoint, error_message, stack_trace=None):
    """Log errors to in-memory storage"""
    error_entry = {
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'error_type': error_type,
        'endpoint': endpoint,
        'error_message': error_message,
        'stack_trace': stack_trace
    }
    error_log.append(error_entry)
    error_stats[endpoint]['count'] += 1
    error_stats[endpoint]['last_error'] = datetime.now(timezone.utc)

    # Also log to file for persistence
    try:
        log_dir = 'logs'
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, f'errors_{datetime.now().strftime("%Y%m%d")}.log')

        with open(log_file, 'a') as f:
            f.write(f"{json.dumps(error_entry)}\n")
    except Exception as e:
        print(f"Failed to write error log: {e}")

def log_uptime_check(status, response_time_ms):
    """Log uptime checks to in-memory storage"""
    check_entry = {
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'status': status,
        'response_time_ms': response_time_ms
    }
    uptime_checks.append(check_entry)
    response_times.append(response_time_ms)

# ============================================================================
# MONITORING ENDPOINTS (No database required!)
# ============================================================================

@analytics_bp.route('/admin/system-health', methods=['GET'])
def admin_system_health():
    mysql = current_app.config['MYSQL']
    cursor = mysql.connection.cursor(DictCursor)

    def table_exists(name):
        cursor.execute(
            "SELECT COUNT(*) AS cnt "
            "FROM information_schema.tables "
            "WHERE table_schema = DATABASE() AND table_name = %s",
            (name,)
        )
        row = cursor.fetchone()
        cnt = row.get('cnt') if isinstance(row, dict) else row[0]
        return int(cnt or 0) > 0

    def column_exists(table, column):
        cursor.execute(
            "SELECT COUNT(*) AS cnt "
            "FROM information_schema.columns "
            "WHERE table_schema = DATABASE() AND table_name = %s AND column_name = %s",
            (table, column)
        )
        row = cursor.fetchone()
        cnt = row.get('cnt') if isinstance(row, dict) else row[0]
        return int(cnt or 0) > 0

    try:
        # DB ping
        cursor.execute("SELECT 1 AS ok")
        cursor.fetchone()

        # Uptime (if you set this in app.py on startup)
        uptime_seconds = None
        uptime_human = None
        start_time = current_app.config.get('SERVER_START_TIME')
        if start_time:
            uptime_seconds = int((datetime.now(timezone.utc) - start_time).total_seconds())
            hours, rem = divmod(uptime_seconds, 3600)
            minutes, seconds = divmod(rem, 60)
            uptime_human = f"{hours}h {minutes}m {seconds}s"

        # Errors (ONLY from error_logs if it exists)
        errors_total = 0
        errors_24h = None
        last_error = None

        if table_exists('error_logs'):
            cursor.execute("SELECT COUNT(*) AS errors_total FROM error_logs")
            row = cursor.fetchone()
            errors_total = row.get('errors_total', 0) if isinstance(row, dict) else row[0]

            ts_col = None
            for c in ('created_at', 'timestamp', 'error_time', 'logged_at', 'created_on', 'createdAt'):
                if column_exists('error_logs', c):
                    ts_col = c
                    break

            if ts_col:
                cursor.execute(f"SELECT COUNT(*) AS errors_24h FROM error_logs WHERE {ts_col} >= (NOW() - INTERVAL 1 DAY)")
                row = cursor.fetchone()
                errors_24h = row.get('errors_24h', 0) if isinstance(row, dict) else row[0]

                cursor.execute(f"SELECT MAX({ts_col}) AS last_error FROM error_logs")
                row = cursor.fetchone()
                last_error = row.get('last_error') if isinstance(row, dict) else row[0]

        # Active users 24h (if columns exist)
        active_users_24h = None
        if table_exists('users') and column_exists('users', 'last_login'):
            cursor.execute(
                "SELECT COUNT(DISTINCT user_id) AS active_users_24h "
                "FROM users WHERE last_login >= (NOW() - INTERVAL 1 DAY)"
            )
            row = cursor.fetchone()
            active_users_24h = row.get('active_users_24h', 0) if isinstance(row, dict) else row[0]
        elif table_exists('user_history') and column_exists('user_history', 'last_visit_date'):
            cursor.execute(
                "SELECT COUNT(DISTINCT user_id) AS active_users_24h "
                "FROM user_history WHERE last_visit_date >= (CURDATE() - INTERVAL 1 DAY)"
            )
            row = cursor.fetchone()
            active_users_24h = row.get('active_users_24h', 0) if isinstance(row, dict) else row[0]

        return jsonify({
            "database_status": "ok",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "uptime_seconds": uptime_seconds,
            "uptime_human": uptime_human,
            "active_users_24h": active_users_24h,
            "errors_total": errors_total,
            "errors_24h": errors_24h,
            "last_error": last_error
        }), 200

    except Exception as e:
        return jsonify({"database_status": "error", "error": str(e)}), 500
    finally:
        try:
            cursor.close()
        except Exception:
            pass

print("SYSTEM HEALTH FILE:", __file__)



@analytics_bp.route('/admin/error-logs', methods=['GET'])
def admin_error_logs():
    """Get recent error logs from memory"""
    limit = request.args.get('limit', 50, type=int)
    hours = request.args.get('hours', 24, type=int)
    error_type = request.args.get('error_type', None)

    try:
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=hours)

        # Filter errors
        filtered_errors = []
        for error in reversed(error_log):  # Most recent first
            error_time = datetime.fromisoformat(error['timestamp'])
            if error_time < cutoff:
                continue
            if error_type and error['error_type'] != error_type:
                continue

            filtered_errors.append(error)
            if len(filtered_errors) >= limit:
                break

        return jsonify({
            'errors': filtered_errors,
            'total': len(filtered_errors),
            'filters': {
                'hours': hours,
                'error_type': error_type,
                'limit': limit
            }
        })

    except Exception as e:
        log_error_memory('error_logs_fetch', '/admin/error-logs', str(e))
        return jsonify({'error': str(e)}), 500


@analytics_bp.route('/admin/error-statistics', methods=['GET'])
def admin_error_statistics():
    """Get error statistics from in-memory data"""
    try:
        days = 7
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=days)

        # Error count by type
        by_type = defaultdict(int)
        trend_by_day = defaultdict(int)

        for error in error_log:
            error_time = datetime.fromisoformat(error['timestamp'])
            if error_time >= cutoff:
                by_type[error['error_type']] += 1
                day_key = error_time.strftime('%Y-%m-%d')
                trend_by_day[day_key] += 1

        by_type_list = [
            {'error_type': k, 'count': v}
            for k, v in sorted(by_type.items(), key=lambda x: x[1], reverse=True)
        ]

        trend_list = [
            {'date': k, 'error_count': v}
            for k, v in sorted(trend_by_day.items())
        ]

        # Most problematic endpoints
        endpoints_list = [
            {
                'endpoint': k,
                'error_count': v['count'],
                'last_error': v['last_error'].isoformat() if v['last_error'] else None
            }
            for k, v in sorted(error_stats.items(), key=lambda x: x[1]['count'], reverse=True)[:10]
        ]

        return jsonify({
            'errors_by_type': by_type_list,
            'error_trend': trend_list,
            'problematic_endpoints': endpoints_list,
            'period': f'last_{days}_days',
            'total_errors': len(error_log)
        })

    except Exception as e:
        log_error_memory('error_stats_fetch', '/admin/error-statistics', str(e))
        return jsonify({'error': str(e)}), 500


@analytics_bp.route('/admin/performance-metrics', methods=['GET'])
def admin_performance_metrics():
    """Get performance metrics from in-memory data"""
    try:
        if not response_times:
            return jsonify({
                'response_time_stats': {
                    'avg_response': 0,
                    'min_response': 0,
                    'max_response': 0,
                    'median_response': 0
                },
                'slow_responses_count': 0,
                'total_checks': 0
            })

        sorted_times = sorted(response_times)
        median_idx = len(sorted_times) // 2

        stats = {
            'avg_response': sum(response_times) / len(response_times),
            'min_response': min(response_times),
            'max_response': max(response_times),
            'median_response': sorted_times[median_idx]
        }

        slow_count = sum(1 for t in response_times if t > 1000)

        return jsonify({
            'response_time_stats': {
                k: round(v, 2) for k, v in stats.items()
            },
            'slow_responses_count': slow_count,
            'total_checks': len(response_times),
            'timestamp': datetime.now(timezone.utc).isoformat()
        })

    except Exception as e:
        log_error_memory('performance_metrics_error', '/admin/performance-metrics', str(e))
        return jsonify({'error': str(e)}), 500


@analytics_bp.route('/health', methods=['GET'])
def health_check():
    """Simple health check endpoint"""
    start_time = time.time()

    try:
        mysql = current_app.config['MYSQL']
        cursor = mysql.connection.cursor()

        # Test database connection
        cursor.execute("SELECT 1")
        cursor.fetchone()
        cursor.close()

        response_time = (time.time() - start_time) * 1000

        # Log this check
        log_uptime_check('up', response_time)

        return jsonify({
            'status': 'healthy',
            'database': 'connected',
            'response_time_ms': round(response_time, 2),
            'timestamp': datetime.now(timezone.utc).isoformat()
        }), 200

    except Exception as e:
        response_time = (time.time() - start_time) * 1000
        log_uptime_check('down', response_time)
        log_error_memory('database_connection', '/health', str(e))

        return jsonify({
            'status': 'unhealthy',
            'database': 'disconnected',
            'error': str(e),
            'response_time_ms': round(response_time, 2),
            'timestamp': datetime.now(timezone.utc).isoformat()
        }), 503


# ============================================================================
# YOUR EXISTING ANALYTICS ENDPOINTS (Keep all of these!)
# ============================================================================

# top 5 highest earning services
@analytics_bp.route('/admin/top-earning-services', methods=['GET'])
def admin_top_earning_services():
    mysql = current_app.config['MYSQL']
    cursor = mysql.connection.cursor(DictCursor)

    query = """
        select salons.salon_id, salons.name as salon_name, services.service_id, services.name,
               sum(invoices.total_amount) as revenue
        from invoices
        join appointments on appointments.appointment_id = invoices.appointment_id
        join salons on salons.salon_id = appointments.salon_id
        join services on appointments.service_id = services.service_id
        group by services.service_id, salons.salon_id
        order by revenue desc
        limit 5
    """

    cursor.execute(query)
    result = cursor.fetchall()
    cursor.close()
    return jsonify(result)

# top 5 highest earning products
@analytics_bp.route('/admin/top-earning-products', methods=['GET'])
def admin_top_earning_products():
    mysql = current_app.config['MYSQL']
    cursor = mysql.connection.cursor(DictCursor)

    query = """
        select salons.salon_id, salons.name as salon_name, products.product_id, products.name,
               sum(invoice_line_items.line_total) as revenue
        from invoice_line_items
        join products on invoice_line_items.product_id = products.product_id
        join salons on salons.salon_id = products.salon_id
        group by products.product_id, salons.salon_id
        order by revenue desc
        limit 5
    """

    cursor.execute(query)
    result = cursor.fetchall()
    cursor.close()
    return jsonify(result)

# Add all your other existing analytics endpoints here...
# (I'm keeping the monitoring ones separate at the top)
