import os
import mysql.connector

def get_connection():
    return mysql.connector.connect(
        host=os.getenv("MYSQL_HOST", "physiochamp-physiochamp.b.aivencloud.com"),
        port=int(os.getenv("MYSQL_PORT", "27951")),
        database=os.getenv("MYSQL_DB", "physiochamp"),
        user=os.getenv("MYSQL_USER", "avnadmin"),
        password=os.getenv("MYSQL_PASSWORD", "AVNS_0LnHsd0Wk3utZWoZix1"),
        autocommit=True,
    )
