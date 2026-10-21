import os
import time
import socket
import logging
from datetime import datetime, timezone

import psutil
from dotenv import load_dotenv

import sql
import mongo

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("cpu_monitor.log"),
    ],
)

# Configuration settings
HOSTNAME = socket.gethostname()
INTERVAL = int(os.getenv("CPU_INTERVAL", "5"))
THRESHOLD = float(os.getenv("CPU_THRESHOLD", "60"))


def main():
    # Initialize database connections
    mysql_conn = sql.connect_mysql()
    mongo_client, mongo_col = mongo.connect_mongo()

    if mysql_conn is None and mongo_col is None:
        logging.error("Neither MySQL nor MongoDB is available. Exiting.")
        return

    logging.info(
        "CPU monitoring started (Threshold: %.1f%%, Interval: %ds). Press Ctrl+C to stop.",
        THRESHOLD,
        INTERVAL,
    )

    try:
        while True:
            # Measure CPU utilization over a 1-second window
            cpu_percent = psutil.cpu_percent(interval=1)
            timestamp = datetime.now(timezone.utc)
            is_anomaly = cpu_percent >= THRESHOLD

            # Save to MySQL if available
            if mysql_conn is not None:
                sql.insert_reading(mysql_conn, HOSTNAME, cpu_percent, is_anomaly, timestamp)

            # Save to MongoDB if available
            if mongo_col is not None:
                mongo.insert_reading(mongo_col, HOSTNAME, cpu_percent, is_anomaly, timestamp)

            logging.info(
                "CPU: %.2f%% | Anomaly: %s",
                cpu_percent,
                is_anomaly,
            )

            # Sleep for the remaining interval
            time.sleep(max(0, INTERVAL - 1))

    except KeyboardInterrupt:
        logging.info("Monitoring stopped by user")

    except Exception:
        logging.exception("Unexpected error occurred during monitoring")

    finally:
        # Clean up database connections
        sql.close_mysql(mysql_conn)
        mongo.close_mongo(mongo_client)
        logging.info("Cleaned up resources successfully.")


if __name__ == "__main__":
    main()
