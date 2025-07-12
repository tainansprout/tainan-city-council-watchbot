"""
音訊處理服務
"""

import io
import os
import uuid
import threading
import time
import tempfile
import atexit
from typing import Optional, Tuple, BinaryIO, Dict, Any

from ..core.logger import get_logger
from ..core.api_timeouts import SmartTimeoutConfig
from ..models.base import FullLLMInterface
from ..core.exceptions import AudioError
from ..core.error_handler import ErrorHandler
from ..platforms.base import PlatformMessage, PlatformUser, PlatformType

logger = get_logger(__name__)


class AudioHandler:
    """優化的音訊處理器 - 減少磁碟 I/O"""
    
    def __init__(self, model_handler=None):
        self.temp_files_to_cleanup = set()
        self.cleanup_lock = threading.Lock()
        self.processing_stats = {
            'total_processed': 0,
            'memory_processed': 0,
            'file_processed': 0,
            'cleanup_count': 0,
            'average_processing_time': 0,
        }
        self.stats_lock = threading.Lock()
        self.model_handler = model_handler
        
        # 註冊程式結束時的清理
        atexit.register(self._cleanup_all_temp_files)
        
        # 啟動定期清理
        self._start_periodic_cleanup()
    
    def process_audio(self, audio_content: bytes, model_handler) -> Tuple[bool, str, Optional[str]]:
        """
        優化的音訊處理流程
        
        Args:
            audio_content: 音訊檔案內容
            model_handler: 模型處理器（有 transcribe_audio 方法）
            
        Returns:
            (是否成功, 轉錄文字, 錯誤訊息)
        """
        start_time = time.time()
        temp_file_path = None
        
        try:
            # 🔥 方案1：記憶體處理（如果 API 支援）
            if self._can_use_memory_processing(model_handler):
                success, transcription, error = self._process_audio_in_memory(audio_content, model_handler)
                if success:
                    self._update_stats(time.time() - start_time, used_memory=True)
                    return success, transcription, error
            
            # 🔥 方案2：優化的檔案處理
            temp_file_path = self._create_temp_file_optimized(audio_content)
            
            # 轉錄音訊
            success, transcription, error = self._transcribe_audio_file(temp_file_path, model_handler)
            
            if success:
                self._update_stats(time.time() - start_time, used_memory=False)
            
            return success, transcription, error
            
        except Exception as e:
            logger.error(f"音訊處理異常: {e}")
            return False, "", str(e)
        
        finally:
            # 🔥 非阻塞清理
            if temp_file_path:
                self._schedule_cleanup(temp_file_path)
    
    def transcribe_audio(self, audio_content: bytes) -> str:
        """
        便捷的音訊轉錄方法
        
        Args:
            audio_content: 音訊檔案內容（bytes）
            
        Returns:
            轉錄的文字（失敗時返回錯誤訊息）
        """
        if self.model_handler is None:
            # 如果沒有設定模型，使用全域模型
            from ..models.factory import get_model_handler
            try:
                model_handler = get_model_handler()
            except Exception as e:
                logger.error(f"無法獲取模型處理器: {e}")
                return "[Audio Message - Model Not Available]"
        else:
            model_handler = self.model_handler
        
        try:
            success, transcription, error = self.process_audio(audio_content, model_handler)
            if success and transcription:
                return transcription
            else:
                logger.error(f"音訊轉錄失敗: {error}")
                return "[Audio Message - Processing Failed]"
        except Exception as e:
            logger.error(f"音訊轉錄異常: {e}")
            return "[Audio Message - Processing Failed]"
    
    def _can_use_memory_processing(self, model_handler) -> bool:
        """檢查是否可以使用記憶體處理"""
        # 檢查模型是否支援檔案物件輸入
        return hasattr(model_handler, 'supports_memory_audio') and model_handler.supports_memory_audio
    
    def _process_audio_in_memory(self, audio_content: bytes, model_handler) -> Tuple[bool, str, Optional[str]]:
        """
        記憶體中處理音訊（無檔案 I/O）
        
        Args:
            audio_content: 音訊內容
            model_handler: 模型處理器
            
        Returns:
            (是否成功, 轉錄文字, 錯誤訊息)
        """
        try:
            # 🔥 關鍵優化：使用 BytesIO 模擬檔案
            audio_file_obj = io.BytesIO(audio_content)
            audio_file_obj.name = f"audio_{uuid.uuid4().hex}.m4a"  # 某些 API 需要檔名，使用 m4a 格式以符合容器實際內容
            
            # 直接傳遞檔案物件給轉錄 API
            success, transcription, error = self._transcribe_audio_memory(audio_file_obj, model_handler)
            
            logger.debug(f"記憶體音訊處理完成: 成功={success}, 長度={len(transcription) if transcription else 0}")
            return success, transcription, error
            
        except Exception as e:
            logger.error(f"記憶體音訊處理失敗: {e}")
            return False, "", str(e)
    
    def _create_temp_file_optimized(self, audio_content: bytes) -> str:
        """
        優化的暫存檔案創建
        
        Args:
            audio_content: 音訊內容
            
        Returns:
            暫存檔案路徑
        """
        # 🔥 使用系統暫存目錄
        temp_dir = tempfile.gettempdir()
        temp_file_path = os.path.join(temp_dir, f"chatbot_audio_{uuid.uuid4().hex}.m4a")
        
        # 🔥 優化：使用 with 語句確保檔案正確關閉
        try:
            with open(temp_file_path, 'wb') as f:
                f.write(audio_content)
                f.flush()  # 確保寫入磁碟
                os.fsync(f.fileno())  # 強制同步
                
            logger.debug(f"建立暫存音訊檔案: {temp_file_path}, 大小: {len(audio_content)} bytes")
            
        except Exception as e:
            # 如果寫入失敗，立即清理
            if os.path.exists(temp_file_path):
                try:
                    os.remove(temp_file_path)
                except:
                    pass
            raise e
        
        # 記錄需要清理的檔案
        with self.cleanup_lock:
            self.temp_files_to_cleanup.add(temp_file_path)
        
        return temp_file_path
    
    def _transcribe_audio_memory(self, audio_file_obj: BinaryIO, model_handler) -> Tuple[bool, str, Optional[str]]:
        """
        使用記憶體檔案物件進行轉錄
        
        Args:
            audio_file_obj: 音訊檔案物件
            model_handler: 模型處理器
            
        Returns:
            (是否成功, 轉錄文字, 錯誤訊息)
        """
        try:
            # 重置檔案指標到開始位置
            audio_file_obj.seek(0)
            
            # 呼叫模型的轉錄方法
            if hasattr(model_handler, 'transcribe_audio_from_memory'):
                return model_handler.transcribe_audio_from_memory(audio_file_obj)
            else:
                # 備用方案：如果不支援記憶體處理，建立臨時檔案
                return self._fallback_to_file_processing(audio_file_obj, model_handler)
                
        except Exception as e:
            logger.error(f"記憶體轉錄失敗: {e}")
            return False, '', str(e)
    
    def _fallback_to_file_processing(self, audio_file_obj: BinaryIO, model_handler) -> Tuple[bool, str, Optional[str]]:
        """備用檔案處理方案"""
        # 建立臨時檔案
        temp_path = None
        try:
            audio_file_obj.seek(0)
            audio_content = audio_file_obj.read()
            temp_path = self._create_temp_file_optimized(audio_content)
            
            return self._transcribe_audio_file(temp_path, model_handler)
            
        finally:
            if temp_path:
                self._schedule_cleanup(temp_path)
    
    def _transcribe_audio_file(self, file_path: str, model_handler) -> Tuple[bool, str, Optional[str]]:
        """
        使用檔案進行轉錄
        
        Args:
            file_path: 音訊檔案路徑
            model_handler: 模型處理器
            
        Returns:
            (是否成功, 轉錄文字, 錯誤訊息)
        """
        try:
            # 呼叫模型的轉錄方法
            success, transcription, error = model_handler.transcribe_audio(file_path)
            
            logger.debug(f"檔案音訊轉錄完成: 成功={success}, 檔案={file_path}")
            return success, transcription, error
            
        except Exception as e:
            logger.error(f"檔案音訊轉錄失敗: {e}")
            return False, '', str(e)
    
    def _schedule_cleanup(self, file_path: str):
        """
        排程檔案清理（非阻塞）
        
        Args:
            file_path: 要清理的檔案路徑
        """
        def cleanup_worker():
            # 延遲一小段時間確保檔案不再使用
            time.sleep(1)
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    logger.debug(f"已清理暫存音訊檔案: {file_path}")
                
                # 從清理列表移除
                with self.cleanup_lock:
                    self.temp_files_to_cleanup.discard(file_path)
                
                # 更新統計
                with self.stats_lock:
                    self.processing_stats['cleanup_count'] += 1
                    
            except Exception as e:
                logger.warning(f"清理暫存檔案失敗: {file_path}, 錯誤: {e}")
        
        # 背景執行緒清理
        cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True, name=f'AudioCleanup-{uuid.uuid4().hex[:8]}')
        cleanup_thread.start()
    
    def _start_periodic_cleanup(self):
        """啟動定期清理任務"""
        def periodic_cleanup():
            while True:
                time.sleep(300)  # 每5分鐘檢查一次
                try:
                    with self.cleanup_lock:
                        files_to_check = list(self.temp_files_to_cleanup)
                    
                    cleaned_files = 0
                    for file_path in files_to_check:
                        if os.path.exists(file_path):
                            # 檢查檔案年齡
                            file_age = time.time() - os.path.getctime(file_path)
                            if file_age > 300:  # 超過5分鐘的檔案
                                try:
                                    os.remove(file_path)
                                    with self.cleanup_lock:
                                        self.temp_files_to_cleanup.discard(file_path)
                                    cleaned_files += 1
                                except:
                                    pass
                    
                    if cleaned_files > 0:
                        logger.debug(f"定期清理完成: 清理了 {cleaned_files} 個暫存音訊檔案")
                        
                except Exception as e:
                    logger.warning(f"定期清理異常: {e}")
        
        cleanup_thread = threading.Thread(target=periodic_cleanup, daemon=True, name='AudioPeriodicCleanup')
        cleanup_thread.start()
    
    def _cleanup_all_temp_files(self):
        """程式結束時清理所有暫存檔案"""
        with self.cleanup_lock:
            cleaned_count = 0
            for file_path in list(self.temp_files_to_cleanup):
                try:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                        cleaned_count += 1
                except:
                    pass
            self.temp_files_to_cleanup.clear()
            
            if cleaned_count > 0:
                logger.info(f"程式結束清理: 清理了 {cleaned_count} 個暫存音訊檔案")
    
    def _update_stats(self, processing_time: float, used_memory: bool):
        """更新處理統計"""
        with self.stats_lock:
            self.processing_stats['total_processed'] += 1
            if used_memory:
                self.processing_stats['memory_processed'] += 1
            else:
                self.processing_stats['file_processed'] += 1
            
            # 更新平均處理時間
            total = self.processing_stats['total_processed']
            current_avg = self.processing_stats['average_processing_time']
            self.processing_stats['average_processing_time'] = (current_avg * (total - 1) + processing_time) / total
    
    def get_stats(self) -> Dict[str, Any]:
        """取得處理統計資訊"""
        with self.stats_lock:
            stats = dict(self.processing_stats)
        
        with self.cleanup_lock:
            stats['pending_cleanup'] = len(self.temp_files_to_cleanup)
        
        return stats
    
    def get_memory_usage_percent(self) -> float:
        """取得記憶體處理使用比例"""
        with self.stats_lock:
            total = self.processing_stats['total_processed']
            if total == 0:
                return 0.0
            return (self.processing_stats['memory_processed'] / total) * 100


# 全域音訊處理器實例
_audio_handler = None
_audio_handler_lock = threading.Lock()

def get_audio_handler() -> AudioHandler:
    """取得全域音訊處理器實例"""
    global _audio_handler
    if _audio_handler is None:
        with _audio_handler_lock:
            if _audio_handler is None:
                _audio_handler = AudioHandler()
    return _audio_handler


class AudioPerformanceMonitor:
    """音訊處理效能監控器"""
    
    def __init__(self):
        self.start_time = time.time()
        self.handler = get_audio_handler()
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """取得效能摘要"""
        stats = self.handler.get_stats()
        uptime = time.time() - self.start_time
        
        return {
            'uptime_seconds': round(uptime, 1),
            'total_audio_processed': stats['total_processed'],
            'memory_processing_rate': round(self.handler.get_memory_usage_percent(), 1),
            'average_processing_time': round(stats['average_processing_time'], 2),
            'files_processed': stats['file_processed'],
            'memory_processed': stats['memory_processed'],
            'cleanup_efficiency': {
                'total_cleanups': stats['cleanup_count'],
                'pending_cleanups': stats['pending_cleanup']
            }
        }


# 便捷函數
def process_audio(audio_content: bytes, model_handler) -> Tuple[bool, str, Optional[str]]:
    """
    便捷的音訊處理函數
    
    Args:
        audio_content: 音訊檔案內容
        model_handler: 模型處理器
        
    Returns:
        (是否成功, 轉錄文字, 錯誤訊息)
    """
    handler = get_audio_handler()
    return handler.process_audio(audio_content, model_handler)


def get_audio_stats() -> Dict[str, Any]:
    """取得音訊處理統計資訊"""
    handler = get_audio_handler()
    return handler.get_stats()

def get_audio_performance_summary() -> Dict[str, Any]:
    """取得音訊處理效能摘要"""
    monitor = AudioPerformanceMonitor()
    return monitor.get_performance_summary()


class AudioService:
    def __init__(self, model: FullLLMInterface):
        self.model = model
        self.error_handler = ErrorHandler()
    
    def handle_message(self, user_id: str, audio_content: bytes, platform: str = 'line') -> Dict[str, Any]:
        """
        處理音訊訊息：僅負責音訊轉錄
        
        流程：
        1. AudioService: 音訊 -> 轉錄文字
        2. 返回轉錄結果給應用層，由應用層決定後續處理
        
        Returns:
            Dict 包含:
            - success: bool - 轉錄是否成功
            - transcribed_text: str - 轉錄文字（成功時）
            - error_message: str - 錯誤訊息（失敗時）
        """
        try:
            # 音訊轉錄
            logger.debug(f"Starting audio transcription for user {user_id}")
            is_successful, transcribed_text, error_message = process_audio(
                audio_content, self.model
            )
            
            if not is_successful:
                logger.error(f"Audio transcription failed for user {user_id}: {error_message}")
                return {
                    'success': False,
                    'transcribed_text': None,
                    'error_message': f"Audio transcription failed: {error_message}"
                }
            
            # 檢查轉錄文字是否為空
            if not transcribed_text or not transcribed_text.strip():
                logger.warning(f"Empty transcription result for user {user_id}")
                return {
                    'success': False,
                    'transcribed_text': None,
                    'error_message': "無法識別音訊內容，請嘗試說得更清楚"
                }
            
            logger.info(f"Audio transcribed for user {user_id}: {transcribed_text[:50]}{'...' if len(transcribed_text) > 50 else ''}")
            
            # 成功轉錄，返回文字
            return {
                'success': True,
                'transcribed_text': transcribed_text,
                'error_message': None
            }
            
        except Exception as e:
            logger.error(f"Error processing audio for user {user_id}: {e}")
            return {
                'success': False,
                'transcribed_text': None,
                'error_message': str(e)
            }