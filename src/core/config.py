import yaml
import os
from typing import Dict, Any, Optional
import threading


def _get_env_value(key: str, default: Any = None) -> Any:
    """獲取環境變數值，支持類型轉換"""
    value = os.getenv(key)
    if value is None:
        return default
    
    # 嘗試類型轉換
    if isinstance(default, bool):
        return value.lower() in ('true', '1', 'yes', 'on')
    elif isinstance(default, int):
        try:
            return int(value)
        except ValueError:
            return default
    elif isinstance(default, float):
        try:
            return float(value)
        except ValueError:
            return default
    
    return value


def _merge_env_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """將環境變數覆蓋配置文件設定"""
    
    # 確保必要的配置節點存在
    if 'platforms' not in config:
        config['platforms'] = {}
    if 'line' not in config['platforms']:
        config['platforms']['line'] = {}
    if 'openai' not in config:
        config['openai'] = {}
    if 'db' not in config:
        config['db'] = {}
    if 'auth' not in config:
        config['auth'] = {}
    
    # Line 平台配置 (新結構)
    config['platforms']['line']['channel_access_token'] = _get_env_value(
        'LINE_CHANNEL_ACCESS_TOKEN', 
        config['platforms']['line'].get('channel_access_token')
    )
    config['platforms']['line']['channel_secret'] = _get_env_value(
        'LINE_CHANNEL_SECRET', 
        config['platforms']['line'].get('channel_secret')
    )
    config['platforms']['line']['enabled'] = _get_env_value(
        'LINE_ENABLED', 
        config['platforms']['line'].get('enabled', True)
    )
    
    # OpenAI 配置
    config['openai']['api_key'] = _get_env_value(
        'OPENAI_API_KEY', 
        config['openai'].get('api_key')
    )
    config['openai']['base_url'] = _get_env_value(
        'OPENAI_BASE_URL', 
        config['openai'].get('base_url')
    )
    
    # 資料庫配置
    config['db']['host'] = _get_env_value('DB_HOST', config['db'].get('host'))
    config['db']['port'] = _get_env_value('DB_PORT', config['db'].get('port'))
    config['db']['db_name'] = _get_env_value('DB_NAME', config['db'].get('db_name'))
    config['db']['user'] = _get_env_value('DB_USER', config['db'].get('user'))
    config['db']['password'] = _get_env_value('DB_PASSWORD', config['db'].get('password'))
    config['db']['sslmode'] = _get_env_value('DB_SSLMODE', config['db'].get('sslmode'))
    config['db']['sslrootcert'] = _get_env_value('DB_SSLROOTCERT', config['db'].get('sslrootcert'))
    config['db']['sslcert'] = _get_env_value('DB_SSLCERT', config['db'].get('sslcert'))
    config['db']['sslkey'] = _get_env_value('DB_SSLKEY', config['db'].get('sslkey'))
    
    # 認證配置
    config['auth']['method'] = _get_env_value('TEST_AUTH_METHOD', config['auth'].get('method'))
    config['auth']['password'] = _get_env_value('TEST_PASSWORD', config['auth'].get('password'))
    config['auth']['username'] = _get_env_value('TEST_USERNAME', config['auth'].get('username'))
    config['auth']['api_token'] = _get_env_value('TEST_API_TOKEN', config['auth'].get('api_token'))
    config['auth']['secret_key'] = _get_env_value('TEST_SECRET_KEY', config['auth'].get('secret_key'))
    config['auth']['token_expiry'] = _get_env_value('TEST_TOKEN_EXPIRY', config['auth'].get('token_expiry'))
    
    # 日誌配置
    config['log_level'] = _get_env_value('LOG_LEVEL', config.get('log_level'))
    config['logfile'] = _get_env_value('LOG_FILE', config.get('logfile'))
    
    # Flask 環境配置
    flask_env = _get_env_value('FLASK_ENV', 'development')
    if flask_env not in config:
        config['flask_env'] = flask_env
    
    return config


class ConfigManager:
    """
    配置管理器 - 使用 Singleton 模式確保配置只載入一次
    線程安全的配置管理
    """
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(ConfigManager, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._config = {}
        self._file_path = None
        self._load_count = 0
        self._initialized = True
    
    def get_config(self, file_path: str = "config/config.yml", force_reload: bool = False) -> Dict[str, Any]:
        """
        獲取配置，只在第一次或強制重載時載入文件
        
        Args:
            file_path: 配置文件路徑
            force_reload: 是否強制重新載入
        """
        with self._lock:
            # 如果是第一次載入或強制重載或文件路徑改變
            if not self._config or force_reload or self._file_path != file_path:
                self._load_config(file_path)
                self._file_path = file_path
            
            return self._config.copy()  # 返回副本，避免外部修改
    
    def _load_config(self, file_path: str):
        """內部載入配置的方法"""
        self._load_count += 1
        config = {}
        
        # 1. 嘗試加載 YAML 配置文件
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                config = yaml.safe_load(file) or {}
                if self._load_count == 1:
                    print(f"✅ 成功載入配置文件: {file_path}")
                else:
                    print(f"🔄 重新載入配置文件 (第 {self._load_count} 次): {file_path}")
                    
        except FileNotFoundError:
            if self._load_count == 1:
                print(f"⚠️  配置文件不存在: {file_path}，使用環境變數配置")
        except yaml.YAMLError as exc:
            print(f"❌ 配置文件格式錯誤: {exc}")
            return
        
        # 2. 使用環境變數覆蓋配置
        config = _merge_env_config(config)
        
        # 3. 驗證必要配置
        self._validate_config(config)
        
        self._config = config
    
    def _validate_config(self, config: Dict[str, Any]):
        """驗證配置的完整性"""
        required_configs = [
            ('openai', 'api_key'),
            ('db', 'host'),
            ('db', 'user'),
            ('db', 'password')
        ]
        
        missing_configs = []
        for section, key in required_configs:
            if section not in config or not config[section].get(key):
                missing_configs.append(f"{section}.{key}")
        
        if missing_configs and self._load_count == 1:
            print(f"⚠️  缺少必要配置: {', '.join(missing_configs)}")
            print("請檢查 config.yml 或設定對應的環境變數")
    
    def reload_config(self, file_path: str = None):
        """重新載入配置"""
        if file_path is None:
            file_path = self._file_path or "config/config.yml"
        return self.get_config(file_path, force_reload=True)
    
    def get_value(self, path: str, default: Any = None) -> Any:
        """
        使用點分隔符獲取嵌套配置值
        例如: get_value('db.host', 'localhost')
        """
        config = self.get_config()
        keys = path.split('.')
        value = config
        
        try:
            for key in keys:
                value = value[key]
            return value if value is not None else default
        except (KeyError, TypeError):
            return default


# 全域配置管理器實例
_config_manager = ConfigManager()


# 全域配置緩存 (向後兼容)
_config_cache = {}
_config_loaded = False
_config_load_count = 0

def load_config(file_path: str = "config/config.yml", force_reload: bool = False) -> Dict[str, Any]:
    """
    加載配置文件 - 使用 ConfigManager 單例模式
    
    Args:
        file_path: 配置文件路徑
        force_reload: 是否強制重新載入
    
    Returns:
        配置字典
    """
    return _config_manager.get_config(file_path, force_reload)


def get_cached_config(file_path: str = "config/config.yml") -> Dict[str, Any]:
    """獲取緩存的配置，如果不存在則載入"""
    return _config_manager.get_config(file_path)


def clear_config_cache():
    """清除配置緩存，強制重新載入"""
    _config_manager.reload_config()


def get_config_value(config: Dict[str, Any], path: str, default: Any = None) -> Any:
    """
    使用點分隔符獲取嵌套配置值
    例如: get_config_value(config, 'db.host', 'localhost')
    """
    keys = path.split('.')
    value = config
    
    try:
        for key in keys:
            value = value[key]
        return value if value is not None else default
    except (KeyError, TypeError):
        return default


# 便利函數 - 直接使用 ConfigManager
def get_config(file_path: str = "config/config.yml") -> Dict[str, Any]:
    """獲取配置 - 便利函數"""
    return _config_manager.get_config(file_path)


def get_value(path: str, default: Any = None) -> Any:
    """獲取配置值 - 便利函數"""
    return _config_manager.get_value(path, default)


def reload_config(file_path: str = None) -> Dict[str, Any]:
    """重新載入配置 - 便利函數"""
    return _config_manager.reload_config(file_path)


# 例如使用
if __name__ == "__main__":
    config = load_config()
    print("=== 配置載入結果 ===")
    print(f"LINE Token: {'✅ 已設定' if config.get('platforms', {}).get('line', {}).get('channel_access_token') else '❌ 未設定'}")
    print(f"OpenAI Key: {'✅ 已設定' if config.get('openai', {}).get('api_key') else '❌ 未設定'}")
    print(f"Database: {'✅ 已設定' if config.get('db', {}).get('host') else '❌ 未設定'}")
    print(f"Auth Method: {config.get('auth', {}).get('method', '未設定')}")
    print(f"Log Level: {config.get('log_level', '未設定')}")
    
    # 測試 ConfigManager
    print("\n=== ConfigManager 測試 ===")
    print(f"使用 get_value: OpenAI API Key: {'✅ 已設定' if get_value('openai.api_key') else '❌ 未設定'}")
    print(f"使用 get_value: LINE Token: {'✅ 已設定' if get_value('platforms.line.channel_access_token') else '❌ 未設定'}")
    print(f"使用 get_value: DB Host: {get_value('db.host', '未設定')}")
    print(f"使用 get_value: Auth Method: {get_value('auth.method', '未設定')}")