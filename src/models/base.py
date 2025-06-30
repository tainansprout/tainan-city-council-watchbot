from abc import ABC, abstractmethod
from typing import List, Dict, Tuple, Optional, Any
from dataclasses import dataclass
from enum import Enum


class ModelProvider(Enum):
    """支援的模型提供商"""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"
    HUGGINGFACE = "huggingface"
    OLLAMA = "ollama"  # 本地 LLM
    CUSTOM = "custom"


@dataclass
class ChatMessage:
    """統一的聊天訊息格式"""
    role: str  # user, assistant, system
    content: str
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class ChatResponse:
    """統一的聊天回應格式"""
    content: str
    finish_reason: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class ThreadInfo:
    """對話串資訊"""
    thread_id: str
    created_at: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class FileInfo:
    """檔案資訊"""
    file_id: str
    filename: str
    purpose: Optional[str] = None
    size: Optional[int] = None
    status: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class KnowledgeBase:
    """知識庫資訊"""
    kb_id: str
    name: str
    description: Optional[str] = None
    file_count: Optional[int] = None
    status: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class RAGResponse:
    """RAG 查詢回應"""
    answer: str
    sources: List[Dict[str, Any]]  # 來源文件和引用資訊
    confidence: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None


class BaseLLMInterface(ABC):
    """語言模型基礎介面 - 所有模型必須實作這些方法"""
    
    @abstractmethod
    def check_connection(self) -> Tuple[bool, Optional[str]]:
        """檢查模型連線是否正常"""
        pass
    
    @abstractmethod
    def chat_completion(self, messages: List[ChatMessage], **kwargs) -> Tuple[bool, Optional[ChatResponse], Optional[str]]:
        """基本聊天完成 - 所有模型的核心功能"""
        pass
    
    @abstractmethod
    def get_provider(self) -> ModelProvider:
        """取得模型提供商"""
        pass


class RAGInterface(ABC):
    """RAG（檢索增強生成）介面 - 統一的 RAG 功能抽象"""
    
    @abstractmethod
    def upload_knowledge_file(self, file_path: str, **kwargs) -> Tuple[bool, Optional[FileInfo], Optional[str]]:
        """上傳檔案到知識庫（各提供商實作方式不同）"""
        pass
    
    @abstractmethod
    def query_with_rag(self, query: str, thread_id: str = None, **kwargs) -> Tuple[bool, Optional[RAGResponse], Optional[str]]:
        """使用 RAG 查詢並生成回應"""
        pass
    
    @abstractmethod
    def get_knowledge_files(self) -> Tuple[bool, Optional[List[FileInfo]], Optional[str]]:
        """取得知識庫檔案列表"""
        pass
    
    @abstractmethod
    def get_file_references(self) -> Dict[str, str]:
        """取得檔案引用對應表（用於顯示來源）"""
        pass


class AssistantInterface(ABC):
    """助理模式介面 - 支援對話串管理和 RAG 功能"""
    
    @abstractmethod
    def create_thread(self) -> Tuple[bool, Optional[ThreadInfo], Optional[str]]:
        """建立對話串"""
        pass
    
    @abstractmethod
    def delete_thread(self, thread_id: str) -> Tuple[bool, Optional[str]]:
        """刪除對話串"""
        pass
    
    @abstractmethod
    def add_message_to_thread(self, thread_id: str, message: ChatMessage) -> Tuple[bool, Optional[str]]:
        """新增訊息到對話串"""
        pass
    
    @abstractmethod
    def run_assistant(self, thread_id: str, **kwargs) -> Tuple[bool, Optional[RAGResponse], Optional[str]]:
        """執行助理並取得帶 RAG 的回應"""
        pass


class AudioInterface(ABC):
    """音訊處理介面"""
    
    @abstractmethod
    def transcribe_audio(self, audio_file_path: str, **kwargs) -> Tuple[bool, Optional[str], Optional[str]]:
        """音訊轉文字"""
        pass


class ImageInterface(ABC):
    """圖片處理介面"""
    
    @abstractmethod
    def generate_image(self, prompt: str, **kwargs) -> Tuple[bool, Optional[str], Optional[str]]:
        """文字生成圖片"""
        pass


class FullLLMInterface(BaseLLMInterface, RAGInterface, AssistantInterface, AudioInterface, ImageInterface):
    """完整的 LLM 介面 - 包含所有功能（含 RAG）"""
    pass