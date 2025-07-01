import yaml
import os
from typing import Dict, Any, Optional


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
    if 'line' not in config:
        config['line'] = {}
    if 'openai' not in config:
        config['openai'] = {}
    if 'db' not in config:
        config['db'] = {}
    if 'auth' not in config:
        config['auth'] = {}
    
    # Line 配置
    config['line']['channel_access_token'] = _get_env_value(
        'LINE_CHANNEL_ACCESS_TOKEN', 
        config['line'].get('channel_access_token')
    )
    config['line']['channel_secret'] = _get_env_value(
        'LINE_CHANNEL_SECRET', 
        config['line'].get('channel_secret')
    )
    
    # OpenAI 配置
    config['openai']['api_key'] = _get_env_value(
        'OPENAI_API_KEY', 
        config['openai'].get('api_key')
    )
    config['openai']['assistant_id'] = _get_env_value(
        'OPENAI_ASSISTANT_ID', 
        config['openai'].get('assistant_id')
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


def load_config(file_path: str = "config/config.yml") -> Dict[str, Any]:
    """
    加載配置文件，優先級：
    1. config.yml 基本配置
    2. 環境變數覆蓋
    """
    config = {}
    
    # 1. 嘗試加載 YAML 配置文件
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            config = yaml.safe_load(file) or {}
            print(f"✅ 成功載入配置文件: {file_path}")
    except FileNotFoundError:
        print(f"⚠️  配置文件不存在: {file_path}，使用環境變數配置")
    except yaml.YAMLError as exc:
        print(f"❌ 配置文件格式錯誤: {exc}")
        return {}
    
    # 2. 使用環境變數覆蓋配置
    config = _merge_env_config(config)
    
    # 3. 驗證必要配置
    required_configs = [
        ('line', 'channel_access_token'),
        ('line', 'channel_secret'),
        ('openai', 'api_key'),
        ('db', 'host'),
        ('db', 'user'),
        ('db', 'password')
    ]
    
    missing_configs = []
    for section, key in required_configs:
        if section not in config or not config[section].get(key):
            missing_configs.append(f"{section}.{key}")
    
    if missing_configs:
        print(f"⚠️  缺少必要配置: {', '.join(missing_configs)}")
        print("請檢查 config.yml 或設定對應的環境變數")
    
    return config


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


# 例如使用
if __name__ == "__main__":
    config = load_config()
    print("=== 配置載入結果 ===")
    print(f"LINE Token: {'✅ 已設定' if config.get('line', {}).get('channel_access_token') else '❌ 未設定'}")
    print(f"OpenAI Key: {'✅ 已設定' if config.get('openai', {}).get('api_key') else '❌ 未設定'}")
    print(f"Database: {'✅ 已設定' if config.get('db', {}).get('host') else '❌ 未設定'}")
    print(f"Auth Method: {config.get('auth', {}).get('method', '未設定')}")
    print(f"Log Level: {config.get('log_level', '未設定')}")