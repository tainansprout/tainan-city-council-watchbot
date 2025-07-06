"""
智慧超時配置模組
根據不同操作類型設定合理的超時時間，平衡性能與成功率
"""

from typing import Dict, Union


class SmartTimeoutConfig:
    """智慧超時配置 - 根據 API 類型和操作調整"""
    
    TIMEOUT_MAPPING: Dict[str, int] = {
        # 系統操作 - 可以快速失敗
        'health_check': 3,         # 健康檢查：3秒
        'model_list': 5,           # 模型列表：5秒
        'thread_create': 10,       # 建立 thread：10秒
        
        # 用戶核心功能 - 優先成功而非速度
        'chat_completion': 45,     # 聊天回應：45秒 (保持較長，確保成功)
        'rag_query': 60,           # RAG 查詢：60秒 (複雜查詢需要時間)
        'audio_transcription': 60, # 音訊轉錄：60秒 (檔案處理需要時間)
        
        # 檔案操作 - 保持原有設定
        'file_upload': 60,         # 檔案上傳：60秒 (維持原設定)
        'assistant_run': 120,      # Assistant 執行：120秒 (維持原設定)
        'bulk_operation': 120,     # 批次操作：120秒
    }
    
    @classmethod
    def get_timeout(cls, operation_type: str, default: int = 45) -> int:
        """
        取得操作類型對應的超時時間
        
        Args:
            operation_type: 操作類型
            default: 預設超時時間
            
        Returns:
            超時時間（秒）
        """
        return cls.TIMEOUT_MAPPING.get(operation_type, default)
    
    @classmethod
    def get_timeout_for_model(cls, operation_type: str, model_provider: str) -> int:
        """
        根據模型提供商調整超時時間
        
        Args:
            operation_type: 操作類型
            model_provider: 模型提供商 (openai, anthropic, gemini, ollama)
            
        Returns:
            調整後的超時時間（秒）
        """
        base_timeout = cls.get_timeout(operation_type)
        
        # 根據不同模型提供商的特性調整
        adjustments = {
            'openai': 1.0,      # OpenAI 速度適中
            'anthropic': 1.1,   # Claude 稍慢
            'gemini': 0.9,      # Gemini 相對較快
            'ollama': 2.0,      # 本地模型可能較慢
        }
        
        adjustment_factor = adjustments.get(model_provider, 1.0)
        adjusted_timeout = int(base_timeout * adjustment_factor)
        
        return max(adjusted_timeout, 5)  # 最少5秒
    
    @classmethod
    def get_operation_info(cls, operation_type: str) -> Dict[str, Union[int, str]]:
        """
        取得操作類型的詳細資訊
        
        Args:
            operation_type: 操作類型
            
        Returns:
            包含超時時間和描述的字典
        """
        timeout = cls.get_timeout(operation_type)
        
        descriptions = {
            'health_check': '系統健康檢查',
            'model_list': '取得模型列表',
            'thread_create': '建立對話執行緒',
            'chat_completion': '聊天回應生成',
            'rag_query': 'RAG 知識庫查詢',
            'audio_transcription': '音訊轉錄處理',
            'file_upload': '檔案上傳',
            'assistant_run': 'Assistant 執行',
            'bulk_operation': '批次操作處理',
        }
        
        return {
            'timeout': timeout,
            'description': descriptions.get(operation_type, '未知操作'),
            'category': cls._get_operation_category(operation_type)
        }
    
    @classmethod
    def _get_operation_category(cls, operation_type: str) -> str:
        """取得操作類型的分類"""
        system_ops = {'health_check', 'model_list', 'thread_create'}
        user_ops = {'chat_completion', 'rag_query', 'audio_transcription'}
        file_ops = {'file_upload', 'assistant_run', 'bulk_operation'}
        
        if operation_type in system_ops:
            return 'system'
        elif operation_type in user_ops:
            return 'user_core'
        elif operation_type in file_ops:
            return 'file_operation'
        else:
            return 'unknown'


class TimeoutContext:
    """超時上下文管理器 - 用於監控和記錄超時事件"""
    
    def __init__(self, operation_type: str, model_provider: str = None):
        self.operation_type = operation_type
        self.model_provider = model_provider
        self.timeout = SmartTimeoutConfig.get_timeout_for_model(
            operation_type, model_provider or 'openai'
        )
        self.start_time = None
        
    def __enter__(self):
        import time
        self.start_time = time.time()
        return self.timeout
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        import time
        elapsed = time.time() - self.start_time
        
        # 記錄超時事件
        if exc_type and 'timeout' in str(exc_val).lower():
            from ..core.logger import get_logger
            logger = get_logger(__name__)
            logger.warning(
                f"操作超時: {self.operation_type}, "
                f"提供商: {self.model_provider}, "
                f"設定超時: {self.timeout}秒, "
                f"實際耗時: {elapsed:.1f}秒"
            )