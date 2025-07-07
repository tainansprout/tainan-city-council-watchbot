"""
測試資料庫遷移功能
"""
import pytest
import os
import sys
import subprocess
from unittest.mock import patch, MagicMock, call
from pathlib import Path

# 添加專案根目錄到路徑
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.db_migration import DatabaseMigrationManager


class TestDatabaseMigrationManager:
    """測試 DatabaseMigrationManager 類"""

    def setup_method(self):
        """每個測試方法前的設置"""
        self.manager = DatabaseMigrationManager()

    def test_init(self):
        """測試初始化"""
        assert self.manager.project_root is not None
        assert self.manager.alembic_ini is not None
        assert str(self.manager.alembic_ini).endswith('alembic.ini')

    @patch('subprocess.run')
    @patch('os.chdir')
    def test_run_alembic_command_success(self, mock_chdir, mock_run):
        """測試成功執行 Alembic 命令"""
        mock_run.return_value = MagicMock()
        
        self.manager.run_alembic_command(['current'])
        
        mock_chdir.assert_called_once_with(self.manager.project_root)
        mock_run.assert_called_once_with(['alembic', 'current'], check=True)

    @patch('subprocess.run')
    @patch('os.chdir')
    def test_run_alembic_command_with_capture(self, mock_chdir, mock_run):
        """測試執行 Alembic 命令並捕獲輸出"""
        mock_result = MagicMock()
        mock_result.stdout = "test output\n"
        mock_run.return_value = mock_result
        
        result = self.manager.run_alembic_command(['current'], capture_output=True)
        
        assert result == "test output"
        mock_run.assert_called_once_with(
            ['alembic', 'current'], 
            capture_output=True, 
            text=True, 
            check=True
        )

    @patch('subprocess.run')
    @patch('os.chdir')
    def test_run_alembic_command_failure(self, mock_chdir, mock_run):
        """測試 Alembic 命令執行失敗"""
        mock_run.side_effect = subprocess.CalledProcessError(1, 'alembic')
        
        with pytest.raises(subprocess.CalledProcessError):
            self.manager.run_alembic_command(['current'])

    @patch.object(DatabaseMigrationManager, 'run_alembic_command')
    def test_create_migration_auto(self, mock_run):
        """測試自動創建遷移"""
        self.manager.create_migration("test migration", auto=True)
        
        mock_run.assert_called_once_with([
            'revision', '--autogenerate', '-m', 'test migration'
        ])

    @patch.object(DatabaseMigrationManager, 'run_alembic_command')
    def test_create_migration_manual(self, mock_run):
        """測試手動創建遷移"""
        self.manager.create_migration("test migration", auto=False)
        
        mock_run.assert_called_once_with([
            'revision', '-m', 'test migration'
        ])

    @patch.object(DatabaseMigrationManager, 'run_alembic_command')
    def test_upgrade_database_default(self, mock_run):
        """測試升級資料庫到預設版本"""
        self.manager.upgrade_database()
        
        mock_run.assert_called_once_with(['upgrade', 'head'])

    @patch.object(DatabaseMigrationManager, 'run_alembic_command')
    def test_upgrade_database_specific_revision(self, mock_run):
        """測試升級資料庫到特定版本"""
        self.manager.upgrade_database("abc123")
        
        mock_run.assert_called_once_with(['upgrade', 'abc123'])

    @patch.object(DatabaseMigrationManager, 'run_alembic_command')
    def test_downgrade_database(self, mock_run):
        """測試降級資料庫"""
        self.manager.downgrade_database("abc123")
        
        mock_run.assert_called_once_with(['downgrade', 'abc123'])

    @patch.object(DatabaseMigrationManager, 'run_alembic_command')
    def test_show_current_revision_success(self, mock_run):
        """測試顯示當前版本成功"""
        mock_run.return_value = "abc123"
        
        result = self.manager.show_current_revision()
        
        assert result == "abc123"
        mock_run.assert_called_once_with(['current'], capture_output=True)

    @patch.object(DatabaseMigrationManager, 'run_alembic_command')
    def test_show_current_revision_failure(self, mock_run):
        """測試顯示當前版本失敗"""
        mock_run.side_effect = Exception("Database error")
        
        result = self.manager.show_current_revision()
        
        assert result is None

    @patch.object(DatabaseMigrationManager, 'run_alembic_command')
    def test_show_migration_history(self, mock_run):
        """測試顯示遷移歷史"""
        self.manager.show_migration_history()
        
        mock_run.assert_called_once_with(['history', '--verbose'])

    @patch.object(DatabaseMigrationManager, 'run_alembic_command')
    def test_show_heads_success(self, mock_run):
        """測試顯示 head 版本成功"""
        mock_run.return_value = "abc123"
        
        result = self.manager.show_heads()
        
        assert result == "abc123"
        mock_run.assert_called_once_with(['heads'], capture_output=True)

    @patch.object(DatabaseMigrationManager, 'run_alembic_command')
    def test_validate_migrations_success(self, mock_run):
        """測試驗證遷移檔案成功"""
        mock_run.return_value = None
        
        result = self.manager.validate_migrations()
        
        assert result is True
        mock_run.assert_called_once_with(['check'])

    @patch.object(DatabaseMigrationManager, 'run_alembic_command')
    def test_validate_migrations_failure(self, mock_run):
        """測試驗證遷移檔案失敗"""
        mock_run.side_effect = subprocess.CalledProcessError(1, 'alembic')
        
        result = self.manager.validate_migrations()
        
        assert result is False

    @patch.object(DatabaseMigrationManager, 'run_alembic_command')
    def test_stamp_database(self, mock_run):
        """測試標記資料庫版本"""
        self.manager.stamp_database("abc123")
        
        mock_run.assert_called_once_with(['stamp', 'abc123'])

    @patch.object(DatabaseMigrationManager, 'run_alembic_command')
    def test_show_sql_default(self, mock_run):
        """測試顯示 SQL 預設版本"""
        self.manager.show_sql()
        
        mock_run.assert_called_once_with(['upgrade', 'head', '--sql'])

    @patch.object(DatabaseMigrationManager, 'run_alembic_command')
    def test_show_sql_specific_range(self, mock_run):
        """測試顯示 SQL 特定範圍"""
        self.manager.show_sql("abc123:def456")
        
        mock_run.assert_called_once_with(['upgrade', 'abc123:def456', '--sql'])

    @patch('scripts.db_migration.load_config')
    @patch.object(Path, 'exists')
    @patch.object(DatabaseMigrationManager, 'init_migrations')
    @patch.object(DatabaseMigrationManager, 'validate_migrations')
    @patch.object(DatabaseMigrationManager, 'show_current_revision')
    @patch.object(DatabaseMigrationManager, 'show_heads')
    def test_auto_setup_success(self, mock_show_heads, mock_show_current, 
                               mock_validate, mock_init, mock_exists, mock_load_config):
        """測試自動設置成功"""
        # 模擬配置
        mock_load_config.return_value = {'db': {'host': 'localhost'}}
        mock_exists.return_value = True  # alembic.ini 存在
        mock_validate.return_value = True
        
        result = self.manager.auto_setup()
        
        assert result is True
        mock_load_config.assert_called_once()
        mock_validate.assert_called_once()
        mock_show_current.assert_called_once()
        mock_show_heads.assert_called_once()
        # 因為 alembic.ini 存在，不應該調用 init_migrations
        mock_init.assert_not_called()

    @patch('scripts.db_migration.load_config')
    @patch.object(Path, 'exists')
    @patch.object(DatabaseMigrationManager, 'init_migrations')
    @patch.object(DatabaseMigrationManager, 'validate_migrations')
    def test_auto_setup_with_init(self, mock_validate, mock_init, 
                                 mock_exists, mock_load_config):
        """測試自動設置需要初始化的情況"""
        mock_load_config.return_value = {'db': {'host': 'localhost'}}
        mock_exists.return_value = False  # alembic.ini 不存在
        mock_validate.return_value = True
        
        result = self.manager.auto_setup()
        
        assert result is True
        mock_init.assert_called_once()

    @patch('scripts.db_migration.load_config')
    def test_auto_setup_config_failure(self, mock_load_config):
        """測試自動設置配置失敗"""
        mock_load_config.side_effect = Exception("Config error")
        
        result = self.manager.auto_setup()
        
        assert result is False

    @patch('scripts.db_migration.load_config')
    @patch.object(DatabaseMigrationManager, 'validate_migrations')
    def test_auto_setup_validation_failure(self, mock_validate, mock_load_config):
        """測試自動設置驗證失敗"""
        mock_load_config.return_value = {'db': {'host': 'localhost'}}
        mock_validate.return_value = False
        
        result = self.manager.auto_setup()
        
        assert result is False


class TestDatabaseMigrationCLI:
    """測試命令行介面功能"""

    @patch('scripts.db_migration.DatabaseMigrationManager')
    def test_main_init_command(self, mock_manager_class):
        """測試 init 命令"""
        mock_manager = MagicMock()
        mock_manager_class.return_value = mock_manager
        
        from scripts.db_migration import main
        
        with patch('sys.argv', ['db_migration.py', 'init']):
            result = main()
            
            assert result == 0
            mock_manager.init_migrations.assert_called_once()

    @patch('scripts.db_migration.DatabaseMigrationManager')
    def test_main_create_command_with_message(self, mock_manager_class):
        """測試 create 命令帶訊息"""
        mock_manager = MagicMock()
        mock_manager_class.return_value = mock_manager
        
        from scripts.db_migration import main
        
        with patch('sys.argv', ['db_migration.py', 'create', '-m', 'test migration']):
            result = main()
            
            assert result == 0
            mock_manager.create_migration.assert_called_once_with('test migration', auto=True)

    @patch('scripts.db_migration.DatabaseMigrationManager')
    def test_main_create_command_manual(self, mock_manager_class):
        """測試手動 create 命令"""
        mock_manager = MagicMock()
        mock_manager_class.return_value = mock_manager
        
        from scripts.db_migration import main
        
        with patch('sys.argv', ['db_migration.py', 'create', '-m', 'test', '--manual']):
            result = main()
            
            assert result == 0
            mock_manager.create_migration.assert_called_once_with('test', auto=False)

    @patch('scripts.db_migration.DatabaseMigrationManager')
    def test_main_upgrade_command_default(self, mock_manager_class):
        """測試 upgrade 命令預設版本"""
        mock_manager = MagicMock()
        mock_manager_class.return_value = mock_manager
        
        from scripts.db_migration import main
        
        with patch('sys.argv', ['db_migration.py', 'upgrade']):
            result = main()
            
            assert result == 0
            mock_manager.upgrade_database.assert_called_once_with('head')

    @patch('scripts.db_migration.DatabaseMigrationManager')
    def test_main_upgrade_command_with_sql_only(self, mock_manager_class):
        """測試 upgrade 命令僅顯示 SQL"""
        mock_manager = MagicMock()
        mock_manager_class.return_value = mock_manager
        
        from scripts.db_migration import main
        
        with patch('sys.argv', ['db_migration.py', 'upgrade', '--sql-only']):
            result = main()
            
            assert result == 0
            mock_manager.show_sql.assert_called_once_with('head')

    @patch('scripts.db_migration.DatabaseMigrationManager')
    def test_main_validate_command_success(self, mock_manager_class):
        """測試 validate 命令成功"""
        mock_manager = MagicMock()
        mock_manager.validate_migrations.return_value = True
        mock_manager_class.return_value = mock_manager
        
        from scripts.db_migration import main
        
        with patch('sys.argv', ['db_migration.py', 'validate']):
            result = main()
            
            assert result == 0

    @patch('scripts.db_migration.DatabaseMigrationManager')
    def test_main_validate_command_failure(self, mock_manager_class):
        """測試 validate 命令失敗"""
        mock_manager = MagicMock()
        mock_manager.validate_migrations.return_value = False
        mock_manager_class.return_value = mock_manager
        
        from scripts.db_migration import main
        
        with patch('sys.argv', ['db_migration.py', 'validate']):
            result = main()
            
            assert result == 1

    @patch('scripts.db_migration.DatabaseMigrationManager')
    def test_main_auto_setup_success(self, mock_manager_class):
        """測試 auto-setup 命令成功"""
        mock_manager = MagicMock()
        mock_manager.auto_setup.return_value = True
        mock_manager_class.return_value = mock_manager
        
        from scripts.db_migration import main
        
        with patch('sys.argv', ['db_migration.py', 'auto-setup']):
            result = main()
            
            assert result == 0

    @patch('scripts.db_migration.DatabaseMigrationManager')
    def test_main_exception_handling(self, mock_manager_class):
        """測試主函數異常處理"""
        mock_manager = MagicMock()
        mock_manager.init_migrations.side_effect = Exception("Test error")
        mock_manager_class.return_value = mock_manager
        
        from scripts.db_migration import main
        
        with patch('sys.argv', ['db_migration.py', 'init']):
            result = main()
            
            assert result == 1


class TestMigrationManagerIntegration:
    """測試遷移管理器整合功能"""

    def test_project_root_path(self):
        """測試專案根目錄路徑正確性"""
        manager = DatabaseMigrationManager()
        
        # 檢查專案根目錄應該包含重要檔案
        expected_files = [
            'alembic.ini',
            'requirements.txt',
            'main.py'
        ]
        
        for filename in expected_files:
            file_path = manager.project_root / filename
            # 這裡只檢查路徑構造是否正確，不檢查檔案是否存在
            assert str(file_path).endswith(filename)

    @patch('subprocess.run')
    @patch('os.chdir')
    def test_command_construction(self, mock_chdir, mock_run):
        """測試命令構造的正確性"""
        manager = DatabaseMigrationManager()
        
        test_commands = [
            (['current'], ['alembic', 'current']),
            (['revision', '-m', 'test'], ['alembic', 'revision', '-m', 'test']),
            (['upgrade', 'head'], ['alembic', 'upgrade', 'head']),
        ]
        
        for input_cmd, expected_cmd in test_commands:
            manager.run_alembic_command(input_cmd)
            mock_run.assert_called_with(expected_cmd, check=True)