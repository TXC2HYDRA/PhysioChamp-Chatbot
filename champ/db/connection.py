import os
import mysql.connector

def get_connection():
    return mysql.connector.connect(
        host=os.getenv("MYSQL_HOST", "10.171.28.60"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        database=os.getenv("MYSQL_DB", "Physiochamp"),
        user=os.getenv("MYSQL_USER", "rag_user"),
        password=os.getenv("MYSQL_PASSWORD", "root"),
        autocommit=True,
    )
