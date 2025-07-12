# 統一接口規範

本文件定義了平台層和模型層的統一接口，確保系統的一致性和可維護性。

## Platform 統一接口 (BasePlatformHandler)

所有平台處理器必須實作以下接口：

### 必要方法

```python
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from .base import PlatformMessage, PlatformResponse, PlatformType

class BasePlatformHandler(ABC):
    @abstractmethod
    def get_platform_type(self) -> PlatformType:
        """返回平台類型"""
        pass
    
    @abstractmethod
    def get_required_config_fields(self) -> List[str]:
        """返回必要的配置欄位"""
        pass
    
    @abstractmethod
    def parse_message(self, event: Any) -> Optional[PlatformMessage]:
        """解析平台事件為統一訊息格式"""
        pass
    
    @abstractmethod
    def handle_webhook(self, request_body: str, headers: Dict[str, str]) -> List[PlatformMessage]:
        """處理 webhook 請求，返回訊息列表"""
        pass
    
    @abstractmethod
    def send_response(self, response: PlatformResponse, original_message: PlatformMessage) -> bool:
        """發送回應到平台"""
        pass
```

### 可選方法 (依平台需求)

```python
def verify_webhook(self, verify_token: str, challenge: str) -> Optional[str]:
    """驗證 webhook (適用於 Meta 平台)"""
    pass

def _verify_signature(self, request_body: str, signature: str) -> bool:
    """驗證請求簽名"""
    pass
```

### 平台特色實作範例

#### LINE Platform
- **特色**: reply_token 機制、豐富訊息類型
- **驗證**: HMAC-SHA256 簽名
- **媒體**: 透過 Blob API 下載

#### WhatsApp Business
- **特色**: 手機號碼識別、商業驗證
- **驗證**: Meta webhook 簽名 + verify_token
- **媒體**: Graph API Media ID 下載

#### Telegram  
- **特色**: 群組支援、異步處理
- **驗證**: Bot token (無需簽名)
- **媒體**: Bot API 直接下載

#### Discord
- **特色**: 伺服器/頻道架構、附件支援
- **驗證**: Bot token
- **媒體**: 附件 URL 下載

## Model 統一接口 (FullLLMInterface)

所有 AI 模型必須實作以下接口：

### 核心接口

```python
from abc import ABC, abstractmethod
from typing import Tuple, Optional
from .base import ModelProvider

class FullLLMInterface(ABC):
    @abstractmethod
    def get_provider(self) -> ModelProvider:
        """返回模型提供商"""
        pass
    
    @abstractmethod
    def chat_with_user(self, user_id: str, message: str, platform: str = 'line') -> Tuple[bool, str, Optional[str]]:
        """
        平台無關的對話接口
        
        Args:
            user_id: 用戶 ID
            message: 用戶訊息
            platform: 平台名稱 (僅用於對話歷史區分)
            
        Returns:
            (成功與否, 回應文字, 錯誤訊息)
        """
        pass
    
    @abstractmethod
    def transcribe_audio(self, file_path: str) -> Tuple[bool, str, Optional[str]]:
        """
        音訊轉錄接口
        
        Args:
            file_path: 音訊檔案路徑
            
        Returns:
            (成功與否, 轉錄文字, 錯誤訊息)
        """
        pass
    
    @abstractmethod
    def clear_user_history(self, user_id: str, platform: str) -> Tuple[bool, Optional[str]]:
        """
        清除用戶對話歷史
        
        Args:
            user_id: 用戶 ID
            platform: 平台名稱
            
        Returns:
            (成功與否, 錯誤訊息)
        """
        pass
    
    @abstractmethod
    def check_connection(self) -> Tuple[bool, Optional[str]]:
        """
        檢查模型連線狀態
        
        Returns:
            (連線成功與否, 錯誤訊息)
        """
        pass
```

### 模型特色實作

#### OpenAI Model
- **特色**: Assistant API、Thread 管理、Whisper 轉錄
- **對話**: 使用 Assistant 和 Thread
- **音訊**: 原生 Whisper API 支援
- **歷史**: Thread-based 管理

#### Anthropic Claude Model  
- **特色**: Messages API、長文推理、程式碼生成
- **對話**: 使用 Messages API
- **音訊**: 整合外部轉錄服務
- **歷史**: 資料庫儲存

#### Google Gemini Model
- **特色**: 多模態、快速回應、免費額度
- **對話**: GenerativeAI API
- **音訊**: 整合外部轉錄服務  
- **歷史**: 資料庫儲存

#### Ollama Model
- **特色**: 本地部署、隱私保護、自定義模型
- **對話**: 本地 API
- **音訊**: 整合外部轉錄服務
- **歷史**: 本地資料庫

#### HuggingFace Model
- **特色**: 開源模型、Inference API、彈性配置
- **對話**: Inference API 或 Transformers
- **音訊**: 語音模型整合
- **歷史**: 資料庫儲存

## 資料結構規範

### PlatformMessage
```python
@dataclass
class PlatformMessage:
    message_id: str
    user: PlatformUser
    content: str
    message_type: str  # "text", "audio", "image", etc.
    raw_data: Optional[bytes] = None  # 原始媒體數據
    reply_token: Optional[str] = None  # 平台特定回應 token
    metadata: Optional[Dict[str, Any]] = None  # 平台特定元數據
```

### PlatformResponse
```python
@dataclass
class PlatformResponse:
    content: str
    response_type: str = "text"  # "text", "image", etc.
    metadata: Optional[Dict[str, Any]] = None
```

### PlatformUser
```python
@dataclass
class PlatformUser:
    user_id: str
    platform: PlatformType
    display_name: Optional[str] = None
    username: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
```

## 接口使用原則

### ✅ 正確使用

1. **Platform 層**：只處理平台特定邏輯，返回標準格式
2. **Model 層**：只處理 AI 功能，不知道平台來源
3. **App 層**：協調各層，處理依賴注入

### ❌ 禁止行為

1. **Platform 直接調用 Model**：違反分層架構
2. **Model 了解 Platform 特性**：違反抽象原則
3. **跨層直接通信**：繞過 App 層協調

## 擴展指南

### 新增平台
1. 繼承 `BasePlatformHandler`
2. 實作所有必要方法
3. 添加平台特色說明註解
4. 註冊到 `PlatformFactory`

### 新增模型
1. 繼承 `FullLLMInterface`
2. 實作所有必要方法
3. 添加模型特色說明註解
4. 註冊到 `ModelFactory`

## 測試策略

### Platform 測試
- Mock webhook 數據
- 驗證訊息解析
- 測試回應發送
- **不測試** AI 功能

### Model 測試
- Mock API 回應
- 驗證接口實作
- 測試錯誤處理
- **不測試** 平台特性

### 整合測試
- 端到端訊息流程
- 跨層協調驗證
- 錯誤處理鏈測試