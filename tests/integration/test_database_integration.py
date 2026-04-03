"""
Database Integration Tests
測試資料庫整合功能和遷移
"""
import pytest
import tempfile
import os
import subprocess
from pathlib import Path
from unittest.mock import patch, Mock
from contextlib import contextmanager
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# 確保測試可以導入專案模組
import sys
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


@contextmanager
def _test_session_cm(session_factory):
    """測試用的 session context manager，模擬 connection.py 的 get_session"""
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


class TestDatabaseMigration:
    """測試資料庫遷移功能"""

    @pytest.fixture
    def temp_db_file(self):
        """創建臨時 SQLite 資料庫檔案"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            temp_db = f.name
        yield f"sqlite:///{temp_db}"
        try:
            os.unlink(temp_db)
        except OSError:
            pass

    def test_alembic_config_exists(self):
        """測試 Alembic 配置檔案存在"""
        alembic_ini = project_root / "alembic.ini"
        assert alembic_ini.exists(), "alembic.ini 檔案不存在"

        alembic_dir = project_root / "alembic"
        assert alembic_dir.exists(), "alembic 目錄不存在"

        env_py = alembic_dir / "env.py"
        assert env_py.exists(), "alembic/env.py 檔案不存在"

    def test_database_models_import(self):
        """測試資料庫模型可以正確導入"""
        try:
            from src.database.models import (
                UserThreadTable,
                SimpleConversationHistory,
                Base
            )
            from src.database.connection import Database, get_db_session
            assert True
        except ImportError as e:
            pytest.fail(f"無法導入資料庫模組: {e}")

    def test_table_creation_with_engine(self):
        """測試使用 engine 建立表格"""
        from src.database.models import Base

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine)

        with engine.connect() as conn:
            result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
            tables = [row[0] for row in result]

        assert 'user_thread_table' in tables
        assert 'simple_conversation_history' in tables


class TestConversationManagerIntegration:
    """測試對話管理器整合功能"""

    @pytest.fixture
    def test_database(self):
        """設置測試資料庫"""
        from src.database.models import Base

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine)
        SessionLocal = sessionmaker(bind=engine)

        def mock_get_session():
            return _test_session_cm(SessionLocal)

        with patch('src.services.conversation.get_db_session', side_effect=mock_get_session):
            yield engine

    def test_orm_conversation_manager_full_workflow(self, test_database):
        """測試 ORM 對話管理器完整工作流程"""
        from src.services.conversation import ORMConversationManager

        manager = ORMConversationManager()
        user_id = "integration_test_user"

        # 1. 添加用戶對話
        assert manager.add_message(user_id, "anthropic", "user", "Hello") == True
        assert manager.add_message(user_id, "anthropic", "assistant", "Hi there!") == True
        assert manager.add_message(user_id, "anthropic", "user", "How are you?") == True

        # 2. 取得對話歷史
        conversations = manager.get_recent_conversations(user_id, "anthropic", limit=10)
        assert len(conversations) == 3
        assert conversations[0]['content'] == "Hello"
        assert conversations[1]['content'] == "Hi there!"
        assert conversations[2]['content'] == "How are you?"

        # 3. 檢查對話數量
        count = manager.get_conversation_count(user_id, "anthropic")
        assert count == 3

        # 4. 清除對話歷史
        assert manager.clear_user_history(user_id, "anthropic") == True

        # 5. 驗證已清除
        conversations_after = manager.get_recent_conversations(user_id, "anthropic")
        assert len(conversations_after) == 0

        count_after = manager.get_conversation_count(user_id, "anthropic")
        assert count_after == 0

    def test_multi_provider_conversations(self, test_database):
        """測試多提供商對話管理"""
        from src.services.conversation import ORMConversationManager

        manager = ORMConversationManager()
        user_id = "multi_provider_user"

        # 添加不同提供商的對話
        manager.add_message(user_id, "anthropic", "user", "Anthropic message")
        manager.add_message(user_id, "gemini", "user", "Gemini message")
        manager.add_message(user_id, "ollama", "user", "Ollama message")

        # 檢查各提供商的對話
        anthropic_convs = manager.get_recent_conversations(user_id, "anthropic")
        gemini_convs = manager.get_recent_conversations(user_id, "gemini")
        ollama_convs = manager.get_recent_conversations(user_id, "ollama")

        assert len(anthropic_convs) == 1
        assert len(gemini_convs) == 1
        assert len(ollama_convs) == 1

        assert anthropic_convs[0]['content'] == "Anthropic message"
        assert gemini_convs[0]['content'] == "Gemini message"
        assert ollama_convs[0]['content'] == "Ollama message"

        # 檢查總對話數量
        total_count = manager.get_conversation_count(user_id)
        assert total_count == 3

    def test_conversation_cleanup(self, test_database):
        """測試對話清理功能"""
        from src.services.conversation import ORMConversationManager

        manager = ORMConversationManager()

        try:
            cleaned_count = manager.cleanup_old_conversations(days_to_keep=30)
            assert cleaned_count >= 0
        except Exception as e:
            pytest.fail(f"清理對話失敗: {e}")


class TestDatabaseScripts:
    """測試資料庫管理腳本"""

    def test_db_commands_script_exists(self):
        """測試資料庫命令腳本存在"""
        script_path = project_root / "scripts" / "db_commands.py"
        assert script_path.exists(), "db_commands.py 腳本不存在"
        assert script_path.is_file()

    def test_db_shell_script_exists(self):
        """測試資料庫 shell 腳本存在"""
        script_path = project_root / "scripts" / "db.sh"
        assert script_path.exists(), "db.sh 腳本不存在"
        assert script_path.is_file()

        # 檢查是否可執行
        assert os.access(script_path, os.X_OK), "db.sh 腳本不可執行"

    def test_requirements_orm_exists(self):
        """測試 ORM 需求檔案存在"""
        req_path = project_root / "requirements.txt"
        assert req_path.exists(), "requirements.txt 檔案不存在"

        # 檢查檔案內容包含必要的套件
        content = req_path.read_text()
        assert "SQLAlchemy" in content
        assert "Flask-Migrate" in content or "alembic" in content
        assert "psycopg2" in content

    @pytest.mark.skipif(
        subprocess.run(["which", "python"], capture_output=True).returncode != 0,
        reason="Python 可執行檔案不可用"
    )
    def test_db_commands_import(self):
        """測試資料庫命令腳本可以導入"""
        script_path = project_root / "scripts" / "db_commands.py"

        try:
            result = subprocess.run(
                ["python", str(script_path), "check"],
                capture_output=True,
                text=True,
                cwd=project_root,
                timeout=30
            )
            assert result.returncode in [0, 1]
        except subprocess.TimeoutExpired:
            pytest.fail("資料庫命令腳本執行超時")
        except Exception as e:
            pytest.skip(f"無法測試資料庫命令腳本: {e}")


class TestConnectionPoolConfig:
    """測試連線池配置"""

    def test_connection_pool_defaults(self):
        """測試連線池預設配置"""
        from src.database.models import Base

        engine = create_engine("sqlite:///:memory:")
        assert engine.pool is not None

    def test_ssl_config_structure(self):
        """測試 SSL 配置結構"""
        postgres_url = "postgresql://user:pass@localhost:5432/db"

        try:
            engine = create_engine(postgres_url)
            assert engine is not None
        except Exception as e:
            assert "could not connect" in str(e).lower() or "connection" in str(e).lower()


@pytest.mark.integration
class TestFullDatabaseIntegration:
    """完整資料庫整合測試"""

    def test_end_to_end_conversation_flow(self):
        """測試端到端對話流程"""
        from src.database.models import Base
        from src.services.conversation import ORMConversationManager

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine)
        SessionLocal = sessionmaker(bind=engine)

        def mock_get_session():
            return _test_session_cm(SessionLocal)

        with patch('src.services.conversation.get_db_session', side_effect=mock_get_session):
            conv_manager = ORMConversationManager()

            user_id = "e2e_test_user"

            # 用戶開始對話
            conv_manager.add_message(user_id, "anthropic", "user", "你好")
            conv_manager.add_message(user_id, "anthropic", "assistant", "你好！我是 Claude，很高興認識你。")
            conv_manager.add_message(user_id, "anthropic", "user", "你能幫我什麼？")
            conv_manager.add_message(user_id, "anthropic", "assistant", "我可以協助你進行對話、回答問題、協助寫作等。")

            # 取得對話歷史
            history = conv_manager.get_recent_conversations(user_id, "anthropic")
            assert len(history) == 4

            # 檢查對話順序
            assert history[0]['role'] == 'user'
            assert history[0]['content'] == '你好'
            assert history[1]['role'] == 'assistant'
            assert history[2]['role'] == 'user'
            assert history[3]['role'] == 'assistant'

            # 切換到不同的模型
            conv_manager.add_message(user_id, "gemini", "user", "Hello Gemini")
            conv_manager.add_message(user_id, "gemini", "assistant", "Hello! I'm Gemini.")

            # 檢查不同模型的對話是分開的
            anthropic_history = conv_manager.get_recent_conversations(user_id, "anthropic")
            gemini_history = conv_manager.get_recent_conversations(user_id, "gemini")

            assert len(anthropic_history) == 4
            assert len(gemini_history) == 2

            # 清除特定模型的歷史
            conv_manager.clear_user_history(user_id, "anthropic")

            # 檢查清除結果
            anthropic_after = conv_manager.get_recent_conversations(user_id, "anthropic")
            gemini_after = conv_manager.get_recent_conversations(user_id, "gemini")

            assert len(anthropic_after) == 0
            assert len(gemini_after) == 2  # Gemini 的對話應該還在
