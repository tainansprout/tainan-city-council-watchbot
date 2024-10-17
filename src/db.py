import os
import psycopg2
import datetime
from psycopg2 import pool
from src.logger import logger

# CREATE TABLE user_thread_table (
#     user_id VARCHAR(255) PRIMARY KEY,
#     thread_id VARCHAR(255),
#     created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
# );

class Database:

    def __init__(self, config):
        self.config = config
        self.pool = None
        self.connect_to_database()

    def connect_to_database(self):
        host = self.config['host']
        port = self.config['port']
        db_name = self.config['db_name']
        user = self.config['user']
        password = self.config['password']
        sslmode = self.config['sslmode']
        sslrootcert = self.config['sslrootcert']
        sslcert = self.config['sslcert']
        sslkey = self.config['sslkey']

        # 建立連線池
        if sslmode in ['verify-full', 'verify-ca']:
            self.pool = psycopg2.pool.SimpleConnectionPool(
                1, 5,  # minconn, maxconn
                dbname=db_name,
                user=user,
                password=password,
                host=host,
                port=port,
                sslmode=sslmode,
                sslrootcert=sslrootcert,
                sslcert=sslcert,
                sslkey=sslkey
            )
        else:
            self.pool = psycopg2.pool.SimpleConnectionPool(
                1, 10,  # minconn, maxconn
                dbname=db_name,
                user=user,
                password=password,
                host=host,
                port=port
            )
        logger.debug('Database connection pool created')

    def query_thread(self, user_id):
        conn = self.pool.getconn()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT thread_id
                    FROM user_thread_table
                    WHERE user_id = %s;
                    """,
                    (user_id,)
                )
                result = cursor.fetchone()
                return result[0] if result else None
        finally:
            self.pool.putconn(conn)

    def save_thread(self, user_id, thread_id):
        conn = self.pool.getconn()
        try:
            with conn.cursor() as cursor:
                now = datetime.datetime.utcnow()
                cursor.execute(
                    """
                    INSERT INTO user_thread_table (user_id, thread_id, created_at)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (user_id) DO UPDATE SET
                    thread_id = EXCLUDED.thread_id,
                    created_at = EXCLUDED.created_at;
                    """,
                    (user_id, thread_id, now)
                )
                conn.commit()
        finally:
            self.pool.putconn(conn)

    def delete_thread(self, user_id):
        conn = self.pool.getconn()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    DELETE FROM user_thread_table
                    WHERE user_id = %s;
                    """,
                    (user_id,)
                )
                conn.commit()
        finally:
            self.pool.putconn(conn)

    def close_all_connections(self):
        if self.pool:
            self.pool.closeall()
            logger.debug('All database connections closed')