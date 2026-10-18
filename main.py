import os
import time
import socket
import logging
from datetime import datetime, timezone

import psutil
import mysql.connector
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("cpu_monitor.log")
    ]
)

HOSTNAME = socket.gethostname()
INTERVAL = int(os.getenv("CPU_INTERVAL", "5"))
THRESHOLD = float(os.getenv("CPU_THRESHOLD", "80"))
ENABLE_MONGODB = os.getenv("ENABLE_MONGODB", "false").lower() in ("true", "1", "yes")


def connect_mysql():
    return mysql.connector.connect(
        host=os.getenv("MYSQL_HOST", "127.0.0.1"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.getenv("MYSQL_USER", "root"),
        password=os.getenv("MYSQL_PASSWORD", ""),
        database=os.getenv("MYSQL_DATABASE", "cpu_monitor"),
        connection_timeout=5
    )


def init_mysql_table(conn):
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


def main():
    mysql_conn = None
    mongo_client = None
    mongo_collection = None

    try:
        # Connect to MySQL
        mysql_conn = connect_mysql()
        init_mysql_table(mysql_conn)
        logging.info("Connected to MySQL successfully")

        # Connect to MongoDB (optional / can be enabled later)
        if ENABLE_MONGODB:
            try:
                mongo_client = MongoClient(
                    os.getenv("MONGO_URI", "mongodb://localhost:27017/"),
                    serverSelectionTimeoutMS=5000
                )
                mongo_client.admin.command("ping")
                mongo_db = mongo_client[
                    os.getenv("MONGO_DATABASE", "cpu_monitor")
                ]
                mongo_collection = mongo_db[
                    os.getenv("MONGO_COLLECTION", "cpu_metrics")
                ]
                logging.info("Connected to MongoDB successfully")
            except Exception:
                logging.exception("Could not connect to MongoDB")
                mongo_client = None
                mongo_collection = None
        else:
            logging.info("MongoDB disabled for now. Storing metrics only in MySQL.")

        logging.info("CPU monitoring started. Press Ctrl+C to stop.")

        while True:
            cpu_percent = psutil.cpu_percent(interval=1)
            timestamp = datetime.now(timezone.utc)
            is_anomaly = cpu_percent >= THRESHOLD

            # Save to MySQL
            try:
                if not mysql_conn.is_connected():
                    mysql_conn.reconnect(attempts=3, delay=2)

                cursor = mysql_conn.cursor()
                try:
                    cursor.execute(
                        """
                        INSERT INTO cpu_metrics
                        (hostname, cpu_percent, is_anomaly, recorded_at)
                        VALUES (%s, %s, %s, %s)
                        """,
                        (
                            HOSTNAME,
                            cpu_percent,
                            is_anomaly,
                            timestamp.replace(tzinfo=None)
                        )
                    )
                    mysql_conn.commit()
                finally:
                    cursor.close()

            except mysql.connector.Error:
                logging.exception("Failed to save reading to MySQL")

            # Save to MongoDB if enabled and connected
            if mongo_collection is not None:
                try:
                    mongo_collection.insert_one({
                        "hostname": HOSTNAME,
                        "cpu_percent": cpu_percent,
                        "is_anomaly": is_anomaly,
                        "recorded_at": timestamp
                    })
                except Exception:
                    logging.exception("Failed to save reading to MongoDB")

            logging.info(
                "CPU: %.2f%% | Anomaly: %s (Stored in MySQL)",
                cpu_percent,
                is_anomaly
            )

            time.sleep(max(0, INTERVAL - 1))

    except KeyboardInterrupt:
        logging.info("Monitoring stopped by user")

    except Exception:
        logging.exception("Error in CPU monitoring service")

    finally:
        if mysql_conn is not None and mysql_conn.is_connected():
            mysql_conn.close()
            logging.info("MySQL connection closed.")
        if mongo_client is not None:
            mongo_client.close()
            logging.info("MongoDB connection closed.")


if __name__ == "__main__":
    main()
