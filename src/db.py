import datetime
from sqlalchemy import create_engine, Column, String, DateTime
from sqlalchemy.orm import sessionmaker, declarative_base
from src.logger import logger

# CREATE TABLE user_thread_table (
#     user_id VARCHAR(255) PRIMARY KEY,
#     thread_id VARCHAR(255),
#     created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
# );

Base = declarative_base()

class UserThread(Base):
    __tablename__ = 'user_thread_table'

    user_id = Column(String(255), primary_key=True)
    thread_id = Column(String(255))
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class Database:
    def __init__(self, config):
        self.config = config
        self.engine = self.create_sqlalchemy_engine()
        self.SessionLocal = sessionmaker(bind=self.engine)
        logger.debug('create SQLAlchemy ORM engine')

    def create_sqlalchemy_engine(self):
        host = self.config['host']
        port = self.config['port']
        db_name = self.config['db_name']
        user = self.config['user']
        password = self.config['password']
        sslmode = self.config['sslmode']
        sslrootcert = self.config['sslrootcert']
        sslcert = self.config['sslcert']
        sslkey = self.config['sslkey']

        # 建立連線字串
        connection_string = f"postgresql://{user}:{password}@{host}:{port}/{db_name}"

        # 設定 SSL 參數
        ssl_args = {
            'sslmode': sslmode,
            'sslrootcert': sslrootcert,
            'sslcert': sslcert,
            'sslkey': sslkey
        }

        # 建立引擎
        engine = create_engine(
            connection_string,
            connect_args=ssl_args,
            pool_size=8,
            max_overflow=0,
            pool_pre_ping=True  # 啟用連線健康檢查
        )
        return engine

    def get_session(self):
        # 獲取一個新的 Session 實例
        return self.SessionLocal()

    def query_thread(self, user_id):
        session = self.get_session()
        try:
            user_thread = session.query(UserThread).filter(UserThread.user_id == user_id).first()
            return user_thread.thread_id if user_thread else None
        finally:
            session.close()

    def save_thread(self, user_id, thread_id):
        session = self.get_session()
        try:
            user_thread = session.query(UserThread).filter(UserThread.user_id == user_id).first()
            if user_thread:
                user_thread.thread_id = thread_id
                user_thread.created_at = datetime.datetime.utcnow()
            else:
                user_thread = UserThread(
                    user_id=user_id,
                    thread_id=thread_id,
                    created_at=datetime.datetime.utcnow()
                )
                session.add(user_thread)
            session.commit()
        finally:
            session.close()

    def delete_thread(self, user_id):
        session = self.get_session()
        try:
            session.query(UserThread).filter(UserThread.user_id == user_id).delete()
            session.commit()
        finally:
            session.close()

    def close_engine(self):
        self.engine.dispose()
        logger.debug('close SQLAlchemy engine.')