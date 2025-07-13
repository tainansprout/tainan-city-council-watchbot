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
    """語言模型基礎介面 - 所有模型必須實作這些方法
    
    這是最核心的接口，定義了所有 LLM 模型都必須具備的基本功能。
    確保不同模型提供商（OpenAI、Anthropic、Gemini等）有統一的調用方式。
    """
    
    @abstractmethod
    def check_connection(self) -> Tuple[bool, Optional[str]]:
        """
        檢查模型 API 連線是否正常
        
        目的:
            在應用啟動或健康檢查時驗證 API 金鑰和網路連線狀態
            避免在用戶互動時才發現連線問題
        
        預期行為:
            - OpenAI: 調用 /models 端點驗證 API 金鑰有效性
            - Anthropic: 發送簡單的 chat completion 請求測試連線
            - Gemini: 嘗試列出可用模型或發送測試請求
            - 應在 10-30 秒內返回結果，不應阻塞應用啟動
        
        Returns:
            Tuple[bool, Optional[str]]: (連線是否成功, 錯誤訊息或None)
            - True, None: 連線正常
            - False, "error message": 連線失敗，附帶具體錯誤原因
        """
        pass
    
    @abstractmethod
    def chat_completion(self, messages: List[ChatMessage], **kwargs) -> Tuple[bool, Optional[ChatResponse], Optional[str]]:
        """
        基本聊天完成功能 - 所有模型的核心功能
        
        目的:
            提供標準的文字生成能力，不涉及 RAG 或對話歷史管理
            這是最純粹的 LLM 交互接口，用於單輪對話或測試
        
        預期行為:
            - 接收標準化的 ChatMessage 列表（role: user/assistant/system）
            - 返回模型生成的文字回應
            - 支援 temperature、max_tokens 等基本參數控制
            - 不應處理文件上傳、RAG 查詢或對話歷史
            - 應處理 API 限流和網路錯誤，提供適當的重試機制
        
        實作參考:
            - OpenAI: 調用 /chat/completions 端點
            - Anthropic: 調用 /messages 端點，處理 system prompt 分離
            - Gemini: 使用 generateContent 方法
        
        Args:
            messages: 標準化的對話訊息列表
            **kwargs: 模型特定參數 (temperature, max_tokens, model名稱等)
        
        Returns:
            Tuple[bool, Optional[ChatResponse], Optional[str]]:
            - (True, ChatResponse, None): 成功生成回應
            - (False, None, error_msg): 生成失敗，附帶錯誤訊息
        """
        pass
    
    @abstractmethod
    def get_provider(self) -> ModelProvider:
        """
        取得模型提供商標識
        
        目的:
            用於日誌記錄、錯誤追蹤、統計分析和配置驗證
            幫助系統識別當前使用的模型提供商，便於除錯和監控
        
        預期行為:
            - 返回對應的 ModelProvider 枚舉值
            - 應該是靜態的，不依賴網路或配置狀態
            - 用於路由不同的處理邏輯或錯誤處理策略
        
        Returns:
            ModelProvider: 模型提供商枚舉 (OPENAI, ANTHROPIC, GEMINI, OLLAMA等)
        """
        pass


class UserConversationInterface(ABC):
    """
    用戶級對話管理介面 - 高級統一對話接口
    
    這是面向最終用戶的主要接口，整合了對話歷史管理和 RAG 功能。
    不同於基礎的 chat_completion，這個接口處理完整的用戶會話流程。
    """
    
    @abstractmethod
    def chat_with_user(self, user_id: str, message: str, platform: str = 'line', **kwargs) -> Tuple[bool, Optional[RAGResponse], Optional[str]]:
        """
        主要對話接口：整合對話歷史管理 + RAG 功能 + 平台識別
        
        目的:
            為聊天機器人提供完整的對話體驗，**基於對話歷史與 RAG 內容提供結果**
            這是面向用戶的核心功能，整合了所有 AI 能力於單一接口
        
        工作流程詳述:
            1. **歷史上下文載入**: 從數據庫載入用戶在指定平台的對話歷史
            2. **RAG 檢索執行**: 如果有上傳知識庫文件，根據用戶問題檢索相關文檔片段
            3. **上下文整合**: 將對話歷史 + RAG 檢索結果 + 當前問題組合成完整上下文
            4. **AI 生成回應**: 基於整合上下文調用模型生成答案
            5. **引用標記處理**: 處理回應中的文件引用，生成 [1], [2] 等標記
            6. **歷史記錄更新**: 將本輪對話（用戶問題+AI回應）保存到歷史
            7. **結構化返回**: 返回包含答案和來源列表的 RAGResponse
        
        **預期回應格式**:
            - **answer**: 包含引用標記的完整回應文字，如"根據 [1] 的說明，產品規格為...參考 [2] 中的技術參數"
            - **sources**: 引用文件列表，每項包含 {file_id, filename, quote}
                例如: [{"file_id": "file-123", "filename": "產品手冊.pdf", "quote": "相關段落"}]
            - **metadata**: 包含用戶資訊、模型供應商、對話 ID 等
        
        實作策略對比:
            - OpenAI: 
                * 使用 Assistant API 的原生 thread 系統自動管理對話歷史
                * thread 與 user_id + platform 綁定，RAG 通過 file attachment 實現
                * 引用格式由 Assistant 自動生成，需要後處理成統一格式
            - Anthropic: 
                * 通過 conversation_manager 手動管理對話歷史，限制最近 N 輪
                * RAG 通過 Files API + Extended Prompt Caching 實現
                * 手動構建包含文件內容的 system prompt
                * 自行解析和標記文件引用
            - Gemini: 
                * 類似 Anthropic，使用對話管理器維護上下文
                * 可能需要自建文件存儲和檢索系統
                * 手動處理引用格式化
            - 共同要求: 所有模型都必須支援 "/reset" 命令清除對話歷史
        
        對話歷史管理:
            - 按 user_id + platform 隔離不同用戶和平台的對話
            - 維護對話的時間順序和上下文連續性
            - 支援對話歷史長度限制（避免 token 超限）
            - 自動處理用戶的 "/reset" 命令
        
        RAG 檢索詳述:
            - 只有在上傳了知識庫文件時才執行 RAG 檢索
            - 基於語義相似度檢索最相關的文檔片段
            - 將檢索結果整合到生成上下文中
            - 確保引用來源的準確性和可追溯性
        
        Args:
            user_id: 用戶唯一識別符 (如 LINE user ID, Discord user ID)
            message: 用戶當前訊息內容
            platform: 平台識別符 ('line', 'discord', 'telegram', 'slack')
            **kwargs: 擴展參數
                - conversation_limit: 對話歷史條數限制 (默認 10)
                - temperature: 生成創造性參數 (0.0-1.0, 預設 0.01)
                - max_tokens: 回應長度限制
                - 其他模型特定參數
        
        Returns:
            Tuple[bool, Optional[RAGResponse], Optional[str]]:
            - (True, RAGResponse, None): 成功生成回應
            - (False, None, error_msg): 生成失敗，附帶詳細錯誤原因
            
            **RAGResponse 詳細結構**:
                - **answer**: 最終回應文字，包含 [1], [2] 等引用標記
                - **sources**: 引用文件來源列表，每項格式為:
                    {"file_id": str, "filename": str, "quote": str, "type": "file_citation"}
                - **metadata**: 元數據，包含:
                    {"user_id": str, "model_provider": str, "conversation_id": str, 
                     "rag_enabled": bool, "sources_count": int}
        """
        pass
    
    @abstractmethod
    def clear_user_history(self, user_id: str, platform: str = 'line') -> Tuple[bool, Optional[str]]:
        """
        清除用戶對話歷史 - 實現 /reset 命令功能
        
        目的:
            允許用戶重置對話上下文，開始全新的對話
            清除可能積累的錯誤上下文或敏感資訊
        
        預期行為:
            - 清除用戶在指定平台上的所有對話歷史
            - 不影響其他用戶或其他平台的對話
            - 不刪除已上傳的知識庫文件（文件是全局共享的）
            - 操作應該是幂等的（重複調用不會產生錯誤）
        
        實作策略對比:
            - OpenAI: 刪除用戶對應的 Assistant thread
            - Anthropic: 調用 conversation_manager.clear_user_history
            - Gemini: 類似 Anthropic，清除對話管理器中的記錄
        
        Args:
            user_id: 要清除歷史的用戶 ID
            platform: 平台識別符，實現平台隔離
        
        Returns:
            Tuple[bool, Optional[str]]:
            - (True, None): 清除成功
            - (False, error_msg): 清除失敗，附帶錯誤原因
        """
        pass


class RAGInterface(ABC):
    """
    RAG（檢索增強生成）介面 - 統一的知識庫和文件檢索功能
    
    RAG 是現代 AI 應用的核心功能，允許模型基於外部知識庫生成更準確的回應。
    不同提供商的實作方式差異很大，這個接口提供統一的抽象層。
    """
    
    @abstractmethod
    def upload_knowledge_file(self, file_path: str, **kwargs) -> Tuple[bool, Optional[FileInfo], Optional[str]]:
        """
        上傳文件到知識庫 - 為 RAG 功能提供知識來源
        
        目的:
            允許用戶上傳 PDF、TXT、JSON 等文件作為知識來源
            這些文件將在後續的對話中被自動檢索和引用
        
        預期行為:
            - 驗證文件格式和大小限制
            - 將文件上傳到提供商的存儲系統
            - 進行文件內容的向量化/索引處理
            - 返回文件元數據，包括唯一 ID
            - 上傳的文件對所有用戶可見（全局知識庫）
        
        實作策略對比:
            - OpenAI: 使用 /files API，purpose='assistants'，與 Assistant 關聯
            - Anthropic: 使用 Files API 上傳，Extended Prompt Caching 優化
            - Gemini: 可能需要自建文件存儲和檢索系統
        
        文件處理要求:
            - 支援 PDF、TXT、JSON、CSV 等常見格式
            - 文件大小限制（通常 100MB 以下）
            - 自動提取和清理文件內容
            - 處理中文編碼問題
        
        Args:
            file_path: 本地文件路徑
            **kwargs: 擴展參數
                - purpose: 文件用途描述
                - metadata: 額外的文件元數據
        
        Returns:
            Tuple[bool, Optional[FileInfo], Optional[str]]:
            - (True, FileInfo, None): 上傳成功，包含文件 ID 和元數據
            - (False, None, error_msg): 上傳失敗，附帶詳細錯誤
            
            FileInfo 包含:
                - file_id: 提供商分配的唯一文件 ID
                - filename: 原始文件名
                - size: 文件大小
                - status: 處理狀態（uploaded, processed, failed）
        """
        pass
    
    @abstractmethod
    def query_with_rag(self, query: str, thread_id: str = None, **kwargs) -> Tuple[bool, Optional[RAGResponse], Optional[str]]:
        """
        使用 RAG 功能進行查詢和生成 - 核心的知識檢索生成功能
        
        目的:
            基於用戶查詢檢索相關的知識庫文件，並生成引用來源的回應
            這是 RAG 功能的核心，結合了檢索和生成兩個步驟
        
        預期行為:
            1. 檢索：根據查詢找出最相關的文件片段
            2. 增強：將檢索到的內容加入到生成上下文
            3. 生成：基於增強上下文生成回應
            4. 引用：標註回應中引用的具體文件來源
        
        實作策略對比:
            - OpenAI: 使用 Assistant API，自動處理文件檢索和引用
            - Anthropic: 手動構建包含文件內容的 system prompt
            - Gemini: 可能需要自建檢索邏輯
        
        引用格式處理:
            - 所有模型都應生成 [1], [2] 格式的引用標記
            - 在回應末尾列出引用來源的文件名
            - 提供文件 ID 到文件名的映射
        
        Args:
            query: 用戶查詢文字
            thread_id: 可選的對話線程 ID（OpenAI 使用）
            **kwargs: 擴展參數
                - context_messages: 對話歷史上下文
                - temperature: 生成參數
        
        Returns:
            Tuple[bool, Optional[RAGResponse], Optional[str]]:
            - (True, RAGResponse, None): 查詢成功
            - (False, None, error_msg): 查詢失敗
            
            RAGResponse 包含:
                - answer: 生成的回應文字（包含引用標記）
                - sources: 引用來源列表，每個包含 file_id, filename, quote
                - metadata: 檢索和生成的元數據
        """
        pass
    
    @abstractmethod
    def get_knowledge_files(self) -> Tuple[bool, Optional[List[FileInfo]], Optional[str]]:
        """
        取得知識庫中所有文件的列表 - 用於管理和顯示
        
        目的:
            允許用戶查看已上傳的知識庫文件
            用於系統管理、除錯和用戶界面顯示
        
        預期行為:
            - 列出所有已上傳且可用的文件
            - 包含文件的基本元數據（名稱、大小、狀態）
            - 支援分頁或限制返回數量（處理大量文件）
            - 過濾掉已刪除或處理失敗的文件
        
        實作策略對比:
            - OpenAI: 調用 /files API，過濾 purpose='assistants'
            - Anthropic: 調用 Files API 獲取文件列表
            - 所有實作都應使用緩存減少 API 調用
        
        Returns:
            Tuple[bool, Optional[List[FileInfo]], Optional[str]]:
            - (True, [FileInfo, ...], None): 成功獲取文件列表
            - (False, None, error_msg): 獲取失敗
            
            每個 FileInfo 包含完整的文件元數據
        """
        pass
    
    @abstractmethod
    def get_file_references(self) -> Dict[str, str]:
        """
        取得文件 ID 到文件名的映射表 - 用於引用解析
        
        目的:
            為回應中的引用標記提供文件名解析
            將 [1], [2] 等數字引用轉換為可讀的文件名
        
        預期行為:
            - 返回 {file_id: clean_filename} 的映射
            - clean_filename 應該移除文件擴展名和特殊字符
            - 用於在用戶界面中顯示友好的文件名
            - 應該與 get_knowledge_files 保持一致
        
        實作注意:
            - 這個方法通常不涉及網路調用，基於緩存數據
            - 文件名清理：移除 .txt, .pdf 等擴展名
            - 處理重複文件名的情況
        
        Returns:
            Dict[str, str]: 文件 ID 到清理後文件名的映射
            例如: {"file-abc123": "產品規格文檔", "file-def456": "用戶手冊"}
        """
        pass


class AssistantInterface(ABC):
    """
    助理模式介面 - 進階對話串管理系統
    
    這個接口主要為 OpenAI Assistant API 設計，但其他模型也需要提供兼容實作。
    提供更精細的對話管理控制，特別適合複雜的多輪對話場景。
    """
    
    @abstractmethod
    def create_thread(self) -> Tuple[bool, Optional[ThreadInfo], Optional[str]]:
        """
        建立新的對話串 - 初始化對話上下文容器
        
        目的:
            為複雜的多輪對話創建獨立的上下文空間
            每個 thread 維護獨立的對話歷史和狀態
        
        預期行為:
            - 在提供商系統中創建新的對話容器
            - 返回唯一的 thread ID 用於後續操作
            - 新 thread 應該是空的，不包含任何歷史訊息
            - 支援併發創建多個 thread
        
        實作策略對比:
            - OpenAI: 調用 /threads API 創建原生 thread
            - Anthropic: 生成 UUID 作為 thread_id，在本地管理
            - Gemini: 類似 Anthropic，模擬 thread 概念
        
        使用場景:
            - 需要並行處理多個對話的場景
            - 需要精確控制對話上下文的應用
            - 集成到 chat_with_user 的底層實作
        
        Returns:
            Tuple[bool, Optional[ThreadInfo], Optional[str]]:
            - (True, ThreadInfo, None): 創建成功
            - (False, None, error_msg): 創建失敗
            
            ThreadInfo 包含:
                - thread_id: 唯一標識符
                - created_at: 創建時間戳
                - metadata: 提供商特定的元數據
        """
        pass
    
    @abstractmethod
    def delete_thread(self, thread_id: str) -> Tuple[bool, Optional[str]]:
        """
        刪除指定的對話串 - 清理對話資源
        
        目的:
            永久刪除對話串及其所有歷史訊息
            釋放提供商系統中的存儲資源
        
        預期行為:
            - 從提供商系統中完全移除 thread 及其數據
            - 刪除後 thread_id 不再有效
            - 操作應該是幂等的（重複刪除不報錯）
            - 不影響其他 thread 或全局資源（如上傳的文件）
        
        實作策略對比:
            - OpenAI: 調用 DELETE /threads/{thread_id}
            - Anthropic: 從本地對話管理器中移除記錄
            - Gemini: 清理本地 thread 緩存
        
        安全注意:
            - 刪除操作不可逆，需要謹慎處理
            - 應該驗證 thread_id 的有效性
            - 記錄刪除操作用於審計
        
        Args:
            thread_id: 要刪除的對話串 ID
        
        Returns:
            Tuple[bool, Optional[str]]:
            - (True, None): 刪除成功
            - (False, error_msg): 刪除失敗或 thread 不存在
        """
        pass
    
    @abstractmethod
    def add_message_to_thread(self, thread_id: str, message: ChatMessage) -> Tuple[bool, Optional[str]]:
        """
        新增訊息到指定對話串 - 構建對話歷史
        
        目的:
            向對話串添加新的訊息（用戶或助理訊息）
            維護對話的時間順序和上下文連續性
        
        預期行為:
            - 將訊息按時間順序添加到 thread 中
            - 保持訊息的 role（user/assistant/system）和內容
            - 支援添加用戶訊息和助理回應
            - 驗證 thread_id 的有效性
        
        實作策略對比:
            - OpenAI: 調用 POST /threads/{thread_id}/messages
            - Anthropic: 將訊息添加到本地對話歷史存儲
            - Gemini: 更新本地 thread 的訊息列表
        
        訊息處理:
            - 自動添加時間戳
            - 處理長訊息的截斷或分割
            - 驗證訊息內容的有效性
        
        Args:
            thread_id: 目標對話串 ID
            message: 要添加的訊息（包含 role 和 content）
        
        Returns:
            Tuple[bool, Optional[str]]:
            - (True, None): 添加成功
            - (False, error_msg): 添加失敗（thread 不存在、訊息無效等）
        """
        pass
    
    @abstractmethod
    def run_assistant(self, thread_id: str, **kwargs) -> Tuple[bool, Optional[RAGResponse], Optional[str]]:
        """
        執行助理生成回應 - 核心的對話生成邏輯
        
        目的:
            基於 thread 中的完整對話歷史生成助理回應
            整合 RAG 功能，提供引用來源的智能回應
        
        預期行為:
            - 讀取 thread 中的所有歷史訊息作為上下文
            - 如果有知識庫文件，進行相關性檢索
            - 生成包含引用標記的回應
            - 自動將生成的回應添加到 thread 中
            - 返回處理後的 RAGResponse 格式
        
        實作策略對比:
            - OpenAI: 調用 /threads/{thread_id}/runs，使用 Assistant API
            - Anthropic: 構建對話上下文，調用 chat completion
            - Gemini: 類似 Anthropic，手動管理對話歷史
        
        執行流程:
            1. 驗證 thread 存在性
            2. 獲取 thread 中的對話歷史
            3. 檢索相關知識庫內容（如果有）
            4. 構建生成請求
            5. 執行生成（可能需要輪詢等待）
            6. 處理回應格式和引用
            7. 將回應添加到 thread
        
        Args:
            thread_id: 對話串 ID
            **kwargs: 生成參數
                - temperature: 創造性控制
                - max_tokens: 回應長度限制
                - 其他模型特定參數
        
        Returns:
            Tuple[bool, Optional[RAGResponse], Optional[str]]:
            - (True, RAGResponse, None): 生成成功
            - (False, None, error_msg): 生成失敗
            
            RAGResponse 應包含完整的回應和引用信息
        """
        pass


class AudioInterface(ABC):
    """
    音訊處理介面 - 語音轉文字功能
    
    為多平台聊天機器人提供語音訊息處理能力。
    不同提供商的語音技術差異很大，需要統一的抽象層。
    """
    
    @abstractmethod
    def transcribe_audio(self, audio_file_path: str, **kwargs) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        音訊轉文字 - 將語音訊息轉換為文字
        
        目的:
            處理來自各平台的語音訊息（LINE、Discord、Telegram 等）
            為聽障用戶提供無障礙支援
            實現語音到文字的多模態交互
        
        預期行為:
            - 接受常見音訊格式（MP3、WAV、OGG、M4A 等）
            - 自動檢測語言（中文、英文等）
            - 返回準確的文字轉錄結果
            - 處理音訊品質問題和噪音
            - 支援較長的音訊文件（通常 10-25MB 限制）
        
        實作策略對比:
            - OpenAI: 使用 Whisper API (/audio/transcriptions)
            - Anthropic: 不提供原生語音服務，需整合第三方（Deepgram、AssemblyAI）
            - Gemini: 可能支援原生語音轉錄
            - 本地模型: 可使用開源 Whisper 模型
        
        音訊處理要求:
            - 自動格式轉換和壓縮
            - 處理不同平台的音訊編碼
            - 控制轉錄品質和速度平衡
            - 支援時間戳標記（可選）
        
        語言支援:
            - 優先支援中文（繁體、簡體）
            - 支援英文和其他主要語言
            - 自動語言檢測
            - 處理多語言混合
        
        Args:
            audio_file_path: 音訊文件的本地路徑
            **kwargs: 擴展參數
                - model: 轉錄模型選擇（如 whisper-1）
                - language: 指定語言代碼
                - response_format: 回應格式（text, json）
                - temperature: 轉錄精確度控制
        
        Returns:
            Tuple[bool, Optional[str], Optional[str]]:
            - (True, transcribed_text, None): 轉錄成功
            - (False, None, error_msg): 轉錄失敗
            
            轉錄失敗的常見原因:
            - 音訊文件損壞或格式不支援
            - 文件過大或過長
            - 音質太差無法識別
            - API 服務不可用
        """
        pass


class ImageInterface(ABC):
    """
    圖片處理介面 - AI 圖片生成功能
    
    為聊天機器人提供文字生成圖片的能力。
    這是一個高級功能，不是所有模型都支援。
    """
    
    @abstractmethod
    def generate_image(self, prompt: str, **kwargs) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        文字生成圖片 - AI 圖片創作功能
        
        目的:
            根據文字描述生成對應的圖片
            為創意工作和視覺化需求提供支援
            增強聊天機器人的多模態交互能力
        
        預期行為:
            - 解析中文和英文的圖片描述
            - 生成高品質的圖片
            - 返回圖片 URL 或 base64 編碼
            - 處理不當內容的過濾
            - 支援不同的圖片尺寸和風格
        
        實作策略對比:
            - OpenAI: 使用 DALL-E API (/images/generations)
            - Anthropic: 不支援圖片生成，應返回錯誤訊息
            - Gemini: 可能支援 Imagen 等圖片生成服務
            - Stable Diffusion: 本地或第三方服務
        
        內容安全:
            - 過濾不當或有害的生成請求
            - 遵守平台的內容政策
            - 處理版權和隱私敏感內容
        
        技術限制:
            - 圖片生成通常較慢（10-60秒）
            - 成本較高，可能需要使用限制
            - 不是所有模型都支援此功能
        
        Args:
            prompt: 圖片描述文字（中文或英文）
            **kwargs: 生成參數
                - size: 圖片尺寸（如 "512x512", "1024x1024"）
                - n: 生成圖片數量（通常限制為 1-4）
                - quality: 圖片品質（standard, hd）
                - style: 藝術風格（natural, vivid）
        
        Returns:
            Tuple[bool, Optional[str], Optional[str]]:
            - (True, image_url, None): 生成成功，返回圖片 URL
            - (False, None, error_msg): 生成失敗或不支援
            
            不支援的模型應返回:
            (False, None, "該模型不支援圖片生成功能")
        """
        pass


class FullLLMInterface(BaseLLMInterface, UserConversationInterface, RAGInterface, AssistantInterface, AudioInterface, ImageInterface):
    """
    完整的 LLM 介面 - 多平台聊天機器人的統一模型接口
    
    這是所有具體模型實作的目標接口，確保不同提供商的模型都能提供
    一致的功能體驗。通過繼承所有子接口，提供完整的 AI 能力矩陣。
    
    功能覆蓋:
        ✅ 基礎聊天生成 (BaseLLMInterface)
        ✅ 用戶對話管理 (UserConversationInterface)  
        ✅ RAG 知識檢索 (RAGInterface)
        ✅ 對話串管理 (AssistantInterface)
        ✅ 語音轉文字 (AudioInterface)
        ⚠️ 圖片生成 (ImageInterface) - 可選功能
    
    實作要求:
        - 所有具體模型類別都應繼承此接口
        - 必須實作所有抽象方法
        - 不支援的功能應返回明確的錯誤訊息
        - 保持接口行為的一致性
    
    使用場景:
        - 多平台聊天機器人的核心模型層
        - 模型切換和 A/B 測試
        - 功能兼容性檢查
        - 統一的錯誤處理和日誌記錄
    
    當前實作狀態:
        - OpenAIModel: ✅ 完整實作所有功能
          ├─ 對話: ✅ Assistant API with thread management
          ├─ 音訊轉錄: ✅ Whisper API (原生支援)
          ├─ 圖片生成: ✅ DALL-E API
          └─ 連線狀態: ✅ 穩定
          
        - AnthropicModel: ✅ 完整實作 (部分功能有限制)
          ├─ 對話: ✅ Messages API (最佳效能)
          ├─ 音訊轉錄: ⚠️ 需配置外部服務 (Deepgram/AssemblyAI)
          ├─ 圖片生成: ❌ 不支援
          └─ 連線狀態: ✅ 穩定
          
        - GeminiModel: ✅ 完整實作 (音訊功能實驗性)
          ├─ 對話: ✅ GenerativeAI API (長文本支援佳)
          ├─ 音訊轉錄: ⚠️ 多模態API (Beta階段，可能不穩定)
          ├─ 圖片生成: ❌ 目前不支援
          └─ 連線狀態: ✅ 穩定
          
        - HuggingFaceModel: ✅ 完整實作 (依賴模型可用性)
          ├─ 對話: ✅ Inference API (支援多種開源模型)
          ├─ 音訊轉錄: ✅ ASR模型 (Whisper/Wav2Vec2，依模型而定)
          ├─ 圖片生成: ✅ Diffusion模型 (Stable Diffusion等)
          └─ 連線狀態: ⚠️ 依賴Hugging Face服務和模型狀態
          
        - OllamaModel: ⚠️ 基本功能正常 (本地部署，功能受限)
          ├─ 對話: ✅ 本地LLM (Llama4, Mistral等)
          ├─ 音訊轉錄: ⚠️ 需本地安裝Whisper (`pip install openai-whisper`)
          ├─ 圖片生成: ❌ 目前不支援
          └─ 連線狀態: ⚠️ 依賴本地Ollama服務狀態
    """
    pass