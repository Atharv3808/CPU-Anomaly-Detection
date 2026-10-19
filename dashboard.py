import os
import atexit
import logging
import threading
from flask import Flask, render_template, jsonify
from dotenv import load_dotenv

import sql

# Load environment configuration
load_dotenv()

app = Flask(__name__)

# Prevent browsers from caching dynamic API telemetry responses
@app.after_request
def add_no_cache_headers(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

# Maintain a persistent MySQL connection and thread lock for safe concurrent queries
_db_conn = None
_db_lock = threading.Lock()


def get_db_connection():
    """Retrieve an active MySQL connection or re-establish if disconnected."""
    global _db_conn
    try:
        if _db_conn is None or not _db_conn.is_connected():
            _db_conn = sql.connect_mysql()
    except Exception as e:
        logging.error("Failed to connect to MySQL from dashboard: %s", e)
        _db_conn = None
    return _db_conn


@atexit.register
def cleanup_db():
    """Close the database connection when the Flask process exits."""
    global _db_conn
    with _db_lock:
        if _db_conn is not None:
            sql.close_mysql(_db_conn)
            _db_conn = None


@app.route("/")
def index():
    """Render the dashboard page."""
    return render_template("index.html")


@app.route("/api/metrics")
def api_metrics():
    """Return the latest CPU reading and its anomaly status."""
    global _db_conn
    with _db_lock:
        conn = get_db_connection()
        if conn is None:
            return jsonify({"error": "Database connection unavailable"}), 503

        try:
            reading = sql.get_latest_reading(conn)
        except Exception:
            _db_conn = None
            reading = None

    if reading is None:
        return jsonify({
            "hostname": "N/A",
            "cpu_percent": 0.0,
            "is_anomaly": False,
            "recorded_at": "No records found",
        }), 200

    return jsonify(reading), 200


@app.route("/api/summary")
def api_summary():
    """Return total readings, total anomalies, and normal readings."""
    global _db_conn
    with _db_lock:
        conn = get_db_connection()
        if conn is None:
            return jsonify({"error": "Database connection unavailable"}), 503

        try:
            summary = sql.get_summary(conn)
        except Exception:
            _db_conn = None
            summary = {"total": 0, "anomalies": 0, "normal": 0}

    return jsonify(summary), 200


@app.route("/api/history")
def api_history():
    """Return recent CPU readings for the chart and history table."""
    global _db_conn
    with _db_lock:
        conn = get_db_connection()
        if conn is None:
            return jsonify({"error": "Database connection unavailable"}), 503

        try:
            history = sql.get_history(conn, limit=30)
        except Exception:
            _db_conn = None
            history = []

    return jsonify(history), 200


if __name__ == "__main__":
    port = int(os.getenv("FLASK_PORT", "5000"))
    app.run(host="127.0.0.1", port=port, debug=True)
