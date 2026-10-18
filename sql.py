import os
import logging
import mysql.connector
from dotenv import load_dotenv

load_dotenv()


def connect_mysql():
    """Establish connection to MySQL and ensure the table exists."""
    try:
        conn = mysql.connector.connect(
            host=os.getenv("MYSQL_HOST", "127.0.0.1"),
            port=int(os.getenv("MYSQL_PORT", "3306")),
            user=os.getenv("MYSQL_USER", "root"),
            password=os.getenv("MYSQL_PASSWORD", ""),
            database=os.getenv("MYSQL_DATABASE", "cpu_monitor"),
            connection_timeout=5,
        )
        init_mysql_table(conn)
        logging.info("Connected to MySQL successfully")
        return conn
    except Exception as e:
        logging.error("Could not connect to MySQL: %s", e)
        return None


def init_mysql_table(conn):
    """Create the cpu_metrics table if it does not already exist."""
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

    except mysql.connector.Error:
        logging.exception("Failed to save reading to MySQL")
        return False
    except Exception:
        logging.exception("Unexpected error saving reading to MySQL")
        return False


def close_mysql(conn):
    """Safely close the MySQL connection."""
    if conn is not None and conn.is_connected():
        conn.close()
        logging.info("MySQL connection closed.")


# Aliases for flexible imports
insert_mysql = insert_reading
close_connection = close_mysql
