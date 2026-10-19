import os
import logging
# pyrefly: ignore[missing-import]
import mysql.connector
from dotenv import load_dotenv

load_dotenv()


def connect_mysql():
    """connection to MySQL and the table exist."""
    try:
        conn = mysql.connector.connect(
            host=os.getenv("MYSQL_HOST", "127.0.0.1"),
            port=int(os.getenv("MYSQL_PORT", "3306")),
            user=os.getenv("MYSQL_USER", "root"),
            password=os.getenv("MYSQL_PASSWORD", ""),
            database=os.getenv("MYSQL_DATABASE", "cpu_monitor"),
            connection_timeout=5,
            autocommit=True,
        )
        init_mysql_table(conn)
        logging.info("Connected to MySQL successfully")
        return conn
    except Exception as e:
        logging.error("Could not connect to MySQL: %s", e)
        return None


def init_mysql_table(conn):
    """cpu_metrics table creation."""
    if conn is None:
        return
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS cpu_metrics (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                hostname VARCHAR(255) NOT NULL,
                cpu_percent DECIMAL(5,2) NOT NULL,
                is_anomaly TINYINT(1) DEFAULT 0,
                recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()
    finally:
        cursor.close()


def insert_reading(conn, hostname, cpu_percent, is_anomaly, recorded_at):
    """Insert a single CPU reading into MySQL using a parameterized query."""
    if conn is None:
        return False
    try:
        if not conn.is_connected():
            conn.reconnect(attempts=3, delay=2)

        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO cpu_metrics
                (hostname, cpu_percent, is_anomaly, recorded_at)
                VALUES (%s, %s, %s, %s)
                """,
                (
                    hostname,
                    cpu_percent,
                    is_anomaly,
                    recorded_at.replace(tzinfo=None) if hasattr(recorded_at, "replace") else recorded_at,
                ),
            )
            conn.commit()
            return True
        finally:
            cursor.close()

    except Exception:
        logging.exception("Failed to save reading to MySQL")
        return False


def close_mysql(conn):
    """close connection."""
    if conn is not None and conn.is_connected():
        conn.close()
        logging.info("MySQL connection closed.")


def get_latest_reading(conn):
    """Retrieve the most recent CPU reading."""
    if conn is None:
        return None
    try:
        if not conn.is_connected():
            conn.reconnect(attempts=3, delay=1)
        else:
            conn.commit()  # Flush read view to ensure latest committed records are visible

        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                """
                SELECT id, hostname, cpu_percent, is_anomaly, recorded_at
                FROM cpu_metrics
                ORDER BY id DESC
                LIMIT 1
                """
            )
            row = cursor.fetchone()
            if row:
                return {
                    "id": row["id"],
                    "hostname": row["hostname"],
                    "cpu_percent": float(row["cpu_percent"]),
                    "is_anomaly": bool(row["is_anomaly"]),
                    "recorded_at": row["recorded_at"].strftime("%Y-%m-%d %H:%M:%S") if row["recorded_at"] else "",
                }
            return None
        finally:
            cursor.close()
    except Exception:
        logging.exception("Error fetching latest CPU reading")
        return None


def get_summary(conn):
    """Retrieve total readings, anomaly count, and normal count."""
    if conn is None:
        return {"total": 0, "anomalies": 0, "normal": 0}
    try:
        if not conn.is_connected():
            conn.reconnect(attempts=3, delay=1)
        else:
            conn.commit()  # Flush read view to ensure latest committed records are visible

        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                """
                SELECT 
                    COUNT(*) AS total,
                    SUM(CASE WHEN is_anomaly = 1 THEN 1 ELSE 0 END) AS anomalies
                FROM cpu_metrics
                """
            )
            row = cursor.fetchone()
            total = int(row["total"]) if row and row["total"] is not None else 0
            anomalies = int(row["anomalies"]) if row and row["anomalies"] is not None else 0
            normal = max(0, total - anomalies)
            return {
                "total": total,
                "anomalies": anomalies,
                "normal": normal,
            }
        finally:
            cursor.close()
    except Exception:
        logging.exception("Error fetching summary metrics")
        return {"total": 0, "anomalies": 0, "normal": 0}


def get_history(conn, limit=30):
    """Retrieve recent CPU readings for dashboard tables and charts."""
    if conn is None:
        return []
    try:
        if not conn.is_connected():
            conn.reconnect(attempts=3, delay=1)
        else:
            conn.commit()  # Flush read view to ensure latest committed records are visible

        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                """
                SELECT id, hostname, cpu_percent, is_anomaly, recorded_at
                FROM cpu_metrics
                ORDER BY id DESC
                LIMIT %s
                """,
                (limit,),
            )
            rows = cursor.fetchall()
            results = []
            for row in rows:
                results.append({
                    "id": row["id"],
                    "hostname": row["hostname"],
                    "cpu_percent": float(row["cpu_percent"]),
                    "is_anomaly": bool(row["is_anomaly"]),
                    "recorded_at": row["recorded_at"].strftime("%Y-%m-%d %H:%M:%S") if row["recorded_at"] else "",
                })
            return results
        finally:
            cursor.close()
    except Exception:
        logging.exception("Error fetching history readings")
        return []
