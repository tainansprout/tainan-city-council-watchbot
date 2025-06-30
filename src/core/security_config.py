"""
安全配置模組
"""

import os
from typing import Dict, Any

class SecurityConfig:
    """安全配置類"""
    
    def __init__(self):
        self.config = self._load_security_config()
    
    def _load_security_config(self) -> Dict[str, Any]:
        """載入安全配置"""
        return {
            # 測試端點配置
            'enable_test_endpoints': os.getenv('ENABLE_TEST_ENDPOINTS', 'true').lower() == 'true',
            'test_endpoint_rate_limit': int(os.getenv('TEST_ENDPOINT_RATE_LIMIT', '10')),  # 每分鐘請求數
            
            # 一般速率限制
            'general_rate_limit': int(os.getenv('GENERAL_RATE_LIMIT', '60')),  # 每分鐘請求數
            'webhook_rate_limit': int(os.getenv('WEBHOOK_RATE_LIMIT', '300')),  # Line webhook 每分鐘請求數
            
            # 內容限制
            'max_message_length': int(os.getenv('MAX_MESSAGE_LENGTH', '5000')),
            'max_test_message_length': int(os.getenv('MAX_TEST_MESSAGE_LENGTH', '1000')),
            
            # 安全標頭
            'enable_security_headers': os.getenv('ENABLE_SECURITY_HEADERS', 'true').lower() == 'true',
            'enable_cors': os.getenv('ENABLE_CORS', 'false').lower() == 'true',
            
            # 監控和日誌
            'log_security_events': os.getenv('LOG_SECURITY_EVENTS', 'true').lower() == 'true',
            'enable_request_logging': os.getenv('ENABLE_REQUEST_LOGGING', 'true').lower() == 'true',
            
            # 環境檢測
            'environment': os.getenv('FLASK_ENV', os.getenv('ENVIRONMENT', 'production')),
            'debug_mode': os.getenv('FLASK_DEBUG', 'false').lower() == 'true',
        }
    
    def is_development(self) -> bool:
        """檢查是否為開發環境"""
        return self.config['environment'] in ['development', 'dev', 'local']
    
    def is_production(self) -> bool:
        """檢查是否為生產環境"""
        return self.config['environment'] in ['production', 'prod']
    
    def should_enable_test_endpoints(self) -> bool:
        """檢查是否應該啟用測試端點"""
        # 在生產環境中，除非明確設定，否則不啟用測試端點
        if self.is_production():
            return self.config['enable_test_endpoints'] and self.config['debug_mode']
        return self.config['enable_test_endpoints']
    
    def get_rate_limit(self, endpoint_type: str = 'general') -> int:
        """獲取特定端點類型的速率限制"""
        rate_limits = {
            'general': self.config['general_rate_limit'],
            'webhook': self.config['webhook_rate_limit'],
            'test': self.config['test_endpoint_rate_limit'],
        }
        return rate_limits.get(endpoint_type, self.config['general_rate_limit'])
    
    def get_max_message_length(self, is_test: bool = False) -> int:
        """獲取訊息長度限制"""
        if is_test:
            return self.config['max_test_message_length']
        return self.config['max_message_length']
    
    def should_log_security_events(self) -> bool:
        """檢查是否應該記錄安全事件"""
        return self.config['log_security_events']
    
    def get_security_headers(self) -> Dict[str, str]:
        """獲取安全標頭"""
        if not self.config['enable_security_headers']:
            return {}
        
        headers = {
            'X-Content-Type-Options': 'nosniff',
            'X-Frame-Options': 'DENY',
            'X-XSS-Protection': '1; mode=block',
            'Referrer-Policy': 'strict-origin-when-cross-origin',
        }
        
        # 在 HTTPS 環境中添加 HSTS
        if not self.is_development():
            headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains; preload'
        
        # CSP 政策
        csp_policy = "default-src 'self'; "
        if self.is_development():
            # 開發環境較寬鬆的 CSP，允許CDN和內聯樣式
            csp_policy += "script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com; font-src 'self' https://cdnjs.cloudflare.com; img-src 'self' data:;"
        else:
            # 生產環境稍微寬鬆的 CSP，允許必要的CDN
            csp_policy += "script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com; font-src 'self' https://cdnjs.cloudflare.com; img-src 'self' data:;"
        
        headers['Content-Security-Policy'] = csp_policy
        
        return headers


# 全域安全配置實例
security_config = SecurityConfig()