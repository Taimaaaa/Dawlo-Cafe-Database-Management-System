import mysql.connector

DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "12toto345",
    "database": "dawlo_phase3",
}

def get_db_connection():
    return mysql.connector.connect(**DB_CONFIG)
