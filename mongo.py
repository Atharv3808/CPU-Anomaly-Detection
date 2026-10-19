import os
import logging
# pyrefly: ignore[missing-import]
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()


def connect_mongo():
    """Establish connection to MongoDB and return (client, collection)."""
    enable_mongodb = os.getenv("ENABLE_MONGODB", "false").lower() in ("true", "1", "yes")
    if not enable_mongodb:
        logging.info("MongoDB disabled via configuration. Storing metrics only in MySQL.")
        return None, None

    try:
        mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
        mongo_client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
        mongo_client.admin.command("ping")

        mongo_db = mongo_client[
            os.getenv("MONGO_DATABASE", "cpu_monitor")
        ]
        collection = mongo_db[
            os.getenv("MONGO_COLLECTION", "cpu_metrics")
        ]
        logging.info("Connected to MongoDB successfully")
        return mongo_client, collection
    except Exception as e:
        logging.warning("Could not connect to MongoDB: %s. Continuing with MySQL only.", e)
        return None, None


def insert_reading(collection, hostname, cpu_percent, is_anomaly, recorded_at):
    """Insert a single CPU reading document into MongoDB."""
    if collection is None:
        return False
    try:
        collection.insert_one({
            "hostname": hostname,
            "cpu_percent": cpu_percent,
            "is_anomaly": is_anomaly,
            "recorded_at": recorded_at,
        })
        return True
    except Exception:
        logging.exception("Failed to save reading to MongoDB")
        return False


def close_mongo(client):
    """Safely close the MongoDB client connection."""
    if client is not None:
        if hasattr(client, "database"):
            client = client.database.client
        client.close()
        logging.info("MongoDB connection closed.")
