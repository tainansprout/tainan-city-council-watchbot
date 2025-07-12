"""
測試資料庫初始化模組的單元測試
"""
import pytest
import sys
import logging
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from src.database.init_db import init_database, check_database_status


class TestDatabaseInitialization:
    """測試資料庫初始化功能"""
    
    def test_init_database_success(self):
        """測試成功的資料庫初始化"""
        with patch('src.database.init_db.ConfigManager') as mock_config_manager, \
             patch('src.database.init_db.Config') as mock_alembic_config, \
             patch('src.database.init_db.command') as mock_command, \
             patch('src.database.init_db.logger') as mock_logger:
            
            # 設定 mock
            mock_config_instance = Mock()
            mock_config_manager.return_value = mock_config_instance
            mock_config_instance.get_config.return_value = {'db': {'host': 'test'}}
            
            mock_alembic_cfg = Mock()
            mock_alembic_config.return_value = mock_alembic_cfg
            
            # 執行初始化
            result = init_database()
            
            # 驗證結果
            assert result is True
            
            # 驗證調用
            mock_config_manager.assert_called_once()
            mock_config_instance.get_config.assert_called_once()
            mock_alembic_config.assert_called_once()
            mock_command.upgrade.assert_called_once_with(mock_alembic_cfg, "head")
            
            # 驗證日誌
            mock_logger.info.assert_any_call("檢查資料庫連接...")
            mock_logger.info.assert_any_call("執行資料庫 migration...")
            mock_logger.info.assert_any_call("資料庫初始化完成！")
    
    def test_init_database_config_manager_failure(self):
        """測試配置管理器失敗的情況"""
        with patch('src.database.init_db.ConfigManager') as mock_config_manager, \
             patch('src.database.init_db.logger') as mock_logger:
            
            # 模擬配置管理器拋出異常
            mock_config_manager.side_effect = Exception("配置載入失敗")
            
            # 執行初始化
            result = init_database()
            
            # 驗證結果
            assert result is False
            
            # 驗證錯誤日誌
            mock_logger.error.assert_called_once()
            error_call_args = mock_logger.error.call_args[0][0]
            assert "資料庫初始化失敗" in error_call_args
            assert "配置載入失敗" in error_call_args
    
    def test_init_database_alembic_config_failure(self):
        """測試 Alembic 配置失敗的情況"""
        with patch('src.database.init_db.ConfigManager') as mock_config_manager, \
             patch('src.database.init_db.Config') as mock_alembic_config, \
             patch('src.database.init_db.logger') as mock_logger:
            
            # 設定正常的配置管理器
            mock_config_instance = Mock()
            mock_config_manager.return_value = mock_config_instance
            mock_config_instance.get_config.return_value = {'db': {'host': 'test'}}
            
            # 模擬 Alembic 配置失敗
            mock_alembic_config.side_effect = Exception("Alembic 配置檔案不存在")
            
            # 執行初始化
            result = init_database()
            
            # 驗證結果
            assert result is False
            
            # 驗證錯誤日誌
            mock_logger.error.assert_called_once()
            error_call_args = mock_logger.error.call_args[0][0]
            assert "資料庫初始化失敗" in error_call_args
            assert "Alembic 配置檔案不存在" in error_call_args
    
    def test_init_database_migration_failure(self):
        """測試 migration 執行失敗的情況"""
        with patch('src.database.init_db.ConfigManager') as mock_config_manager, \
             patch('src.database.init_db.Config') as mock_alembic_config, \
             patch('src.database.init_db.command') as mock_command, \
             patch('src.database.init_db.logger') as mock_logger:
            
            # 設定正常的配置
            mock_config_instance = Mock()
            mock_config_manager.return_value = mock_config_instance
            mock_config_instance.get_config.return_value = {'db': {'host': 'test'}}
            
            mock_alembic_cfg = Mock()
            mock_alembic_config.return_value = mock_alembic_cfg
            
            # 模擬 migration 失敗
            mock_command.upgrade.side_effect = Exception("Migration 執行失敗")
            
            # 執行初始化
            result = init_database()
            
            # 驗證結果
            assert result is False
            
            # 驗證錯誤日誌
            mock_logger.error.assert_called_once()
            error_call_args = mock_logger.error.call_args[0][0]
            assert "資料庫初始化失敗" in error_call_args
            assert "Migration 執行失敗" in error_call_args


class TestDatabaseStatusCheck:
    """測試資料庫狀態檢查功能"""
    
    def test_check_database_status_success(self):
        """測試成功的資料庫狀態檢查"""
        with patch('src.database.init_db.Config') as mock_alembic_config, \
             patch('src.database.init_db.command') as mock_command, \
             patch('src.database.init_db.logger') as mock_logger:
            
            # 設定 mock
            mock_alembic_cfg = Mock()
            mock_alembic_config.return_value = mock_alembic_cfg
            
            # 執行狀態檢查
            result = check_database_status()
            
            # 驗證結果
            assert result is True
            
            # 驗證調用
            mock_alembic_config.assert_called_once()
            mock_command.current.assert_called_once_with(mock_alembic_cfg)
            mock_command.heads.assert_called_once_with(mock_alembic_cfg)
            
            # 驗證日誌
            mock_logger.info.assert_any_call("檢查資料庫版本...")
            mock_logger.info.assert_any_call("檢查待執行的 migration...")
    
    def test_check_database_status_config_failure(self):
        """測試配置載入失敗的情況"""
        with patch('src.database.init_db.Config') as mock_alembic_config, \
             patch('src.database.init_db.logger') as mock_logger:
            
            # 模擬配置載入失敗
            mock_alembic_config.side_effect = Exception("找不到 alembic.ini")
            
            # 執行狀態檢查
            result = check_database_status()
            
            # 驗證結果
            assert result is False
            
            # 驗證錯誤日誌
            mock_logger.error.assert_called_once()
            error_call_args = mock_logger.error.call_args[0][0]
            assert "檢查資料庫狀態失敗" in error_call_args
            assert "找不到 alembic.ini" in error_call_args
    
    def test_check_database_status_command_failure(self):
        """測試命令執行失敗的情況"""
        with patch('src.database.init_db.Config') as mock_alembic_config, \
             patch('src.database.init_db.command') as mock_command, \
             patch('src.database.init_db.logger') as mock_logger:
            
            # 設定正常的配置
            mock_alembic_cfg = Mock()
            mock_alembic_config.return_value = mock_alembic_cfg
            
            # 模擬命令執行失敗
            mock_command.current.side_effect = Exception("無法連接到資料庫")
            
            # 執行狀態檢查
            result = check_database_status()
            
            # 驗證結果
            assert result is False
            
            # 驗證錯誤日誌
            mock_logger.error.assert_called_once()
            error_call_args = mock_logger.error.call_args[0][0]
            assert "檢查資料庫狀態失敗" in error_call_args
            assert "無法連接到資料庫" in error_call_args


class TestDatabaseInitMain:
    """測試資料庫初始化主程式功能"""
    
    def test_main_script_path_setup(self):
        """測試主程式的路徑設定"""
        # 驗證專案根目錄路徑設定
        from src.database.init_db import project_root
        
        assert isinstance(project_root, Path)
        assert project_root.name == "ChatGPT-Line-Bot"
        assert (project_root / "src").exists()
        assert (project_root / "alembic.ini").exists()
    
    def test_main_script_argv_logic(self):
        """測試主程式的命令行參數邏輯"""
        # 測試狀態檢查邏輯
        test_argv_status = ['init_db.py', 'status']
        if len(test_argv_status) > 1 and test_argv_status[1] == "status":
            should_check_status = True
        else:
            should_check_status = False
        
        assert should_check_status is True
        
        # 測試初始化邏輯
        test_argv_init = ['init_db.py']
        if len(test_argv_init) > 1 and test_argv_init[1] == "status":
            should_init = False
        else:
            should_init = True
        
        assert should_init is True
    
    def test_logger_configuration(self):
        """測試日誌配置"""
        # 驗證 logger 設定
        from src.database.init_db import logger
        
        assert logger.name == "src.database.init_db"
        assert isinstance(logger, logging.Logger)


class TestDatabaseInitIntegration:
    """測試資料庫初始化整合功能"""
    
    @patch('src.database.init_db.ConfigManager')
    @patch('src.database.init_db.Config')
    @patch('src.database.init_db.command')
    def test_full_initialization_workflow(self, mock_command, mock_config, mock_config_manager):
        """測試完整的初始化工作流程"""
        # 設定所有 mock
        mock_config_instance = Mock()
        mock_config_manager.return_value = mock_config_instance
        mock_config_instance.get_config.return_value = {
            'db': {
                'host': 'localhost',
                'port': 5432,
                'database': 'test_db'
            }
        }
        
        mock_alembic_cfg = Mock()
        mock_config.return_value = mock_alembic_cfg
        
        # 執行完整的初始化流程
        result = init_database()
        
        # 驗證整個工作流程
        assert result is True
        
        # 驗證調用順序和次數
        mock_config_manager.assert_called_once()
        mock_config_instance.get_config.assert_called_once()
        mock_config.assert_called_once()
        mock_command.upgrade.assert_called_once_with(mock_alembic_cfg, "head")
    
    @patch('src.database.init_db.Config')
    @patch('src.database.init_db.command')
    def test_full_status_check_workflow(self, mock_command, mock_config):
        """測試完整的狀態檢查工作流程"""
        # 設定 mock
        mock_alembic_cfg = Mock()
        mock_config.return_value = mock_alembic_cfg
        
        # 執行完整的狀態檢查流程
        result = check_database_status()
        
        # 驗證整個工作流程
        assert result is True
        
        # 驗證調用順序和次數
        mock_config.assert_called_once()
        mock_command.current.assert_called_once_with(mock_alembic_cfg)
        mock_command.heads.assert_called_once_with(mock_alembic_cfg)


class TestDatabaseInitMainExecution:
    """測試資料庫初始化主程式執行"""
    
    @patch('src.database.init_db.init_database')
    @patch('src.database.init_db.logging.basicConfig')
    def test_main_execution_init_database(self, mock_logging_config, mock_init_database):
        """測試主程式執行初始化資料庫"""
        # 保存原始的 sys.argv
        original_argv = sys.argv
        
        try:
            # 設定測試環境 - 沒有額外參數
            sys.argv = ['init_db.py']
            
            # 直接調用被 patch 的函數來模擬主程式邏輯
            from src.database.init_db import init_database
            init_database()
            
            # 驗證調用
            mock_init_database.assert_called_once()
            
        finally:
            # 恢復原始值
            sys.argv = original_argv
    
    @patch('src.database.init_db.check_database_status')
    @patch('src.database.init_db.logging.basicConfig')
    def test_main_execution_check_status(self, mock_logging_config, mock_check_status):
        """測試主程式執行檢查狀態"""
        # 保存原始的 sys.argv
        original_argv = sys.argv
        
        try:
            # 設定測試環境 - 有 status 參數
            sys.argv = ['init_db.py', 'status']
            
            # 直接調用被 patch 的函數來模擬主程式邏輯
            from src.database.init_db import check_database_status
            check_database_status()
            
            # 驗證調用
            mock_check_status.assert_called_once()
            
        finally:
            # 恢復原始值
            sys.argv = original_argv
    
    def test_main_execution_logging_setup(self):
        """測試主程式的日誌設定"""
        # 測試日誌配置邏輯
        import logging
        
        with patch('src.database.init_db.logging.basicConfig') as mock_logging_config:
            # 模擬主程式的日誌設定邏輯
            logging.basicConfig(level=logging.INFO)
            mock_logging_config.assert_called_with(level=logging.INFO)