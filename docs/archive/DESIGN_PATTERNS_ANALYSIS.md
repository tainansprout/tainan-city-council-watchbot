# Design Patterns 分析與應用

## 🔍 現有架構分析

### 已應用的 Design Patterns

1. **Factory Pattern** ✅
   - `ModelFactory` 用於創建不同的 LLM 模型
   - 位置: `src/models/factory.py`
   - 優點: 統一模型創建邏輯，易於擴展新模型

2. **Strategy Pattern** ✅ (部分)
   - 不同 LLM 模型實作共同的 `FullLLMInterface`
   - 位置: `src/models/base.py` + 各模型實作
   - 優點: 可以動態切換不同的 LLM 模型

3. **Template Method Pattern** ✅ (隱式)
   - `BaseLLMInterface` 定義共同流程
   - 各模型子類實作特定步驟

## 🚀 建議應用的 Design Patterns

### 1. **Observer Pattern** - 事件通知系統
**問題**: 目前缺乏統一的事件通知機制
**解決方案**: 實作 Observer Pattern 處理平台事件

```python
class PlatformEventObserver(ABC):
    @abstractmethod
    def on_message_received(self, message: PlatformMessage): pass
    
    @abstractmethod  
    def on_response_sent(self, response: PlatformResponse): pass

class ChatEventManager:
    def __init__(self):
        self._observers = []
    
    def subscribe(self, observer: PlatformEventObserver):
        self._observers.append(observer)
    
    def notify_message_received(self, message: PlatformMessage):
        for observer in self._observers:
            observer.on_message_received(message)
```

### 2. **Chain of Responsibility Pattern** - 訊息處理鏈
**問題**: 目前 ChatService 處理所有邏輯，職責過重
**解決方案**: 建立處理鏈分離關注點

```python
class MessageHandler(ABC):
    def __init__(self):
        self._next_handler = None
    
    def set_next(self, handler):
        self._next_handler = handler
        return handler
    
    @abstractmethod
    def handle(self, message: PlatformMessage) -> Optional[PlatformResponse]:
        if self._next_handler:
            return self._next_handler.handle(message)
        return None

class CommandHandler(MessageHandler):
    def handle(self, message: PlatformMessage):
        if message.content.startswith('/'):
            return self._process_command(message)
        return super().handle(message)

class ChatHandler(MessageHandler):
    def handle(self, message: PlatformMessage):
        if message.message_type == "text":
            return self._process_chat(message)
        return super().handle(message)
```

### 3. **Adapter Pattern** - 平台適配器
**問題**: 不同平台 API 差異很大
**解決方案**: 使用 Adapter 統一不同平台的介面

```python
class PlatformAdapter(ABC):
    @abstractmethod
    def adapt_incoming_message(self, raw_event) -> PlatformMessage: pass
    
    @abstractmethod
    def adapt_outgoing_response(self, response: PlatformResponse) -> Any: pass

class LineAdapter(PlatformAdapter):
    def adapt_incoming_message(self, line_event) -> PlatformMessage:
        # 轉換 LINE 事件為統一格式
        pass
    
    def adapt_outgoing_response(self, response: PlatformResponse):
        # 轉換統一回應為 LINE 格式
        return LineTextMessage(text=response.content)
```

### 4. **Command Pattern** - 指令封裝
**問題**: 指令處理邏輯分散，難以擴展
**解決方案**: 封裝指令為物件

```python
class Command(ABC):
    @abstractmethod
    def execute(self, user: PlatformUser, args: List[str]) -> PlatformResponse: pass

class ResetCommand(Command):
    def execute(self, user: PlatformUser, args: List[str]):
        # 重置邏輯
        pass

class CommandInvoker:
    def __init__(self):
        self._commands = {}
    
    def register_command(self, name: str, command: Command):
        self._commands[name] = command
    
    def execute_command(self, name: str, user: PlatformUser, args: List[str]):
        if name in self._commands:
            return self._commands[name].execute(user, args)
```

### 5. **Decorator Pattern** - 功能增強
**問題**: 缺乏橫切關注點(如logging、重試、快取)的統一處理
**解決方案**: 使用裝飾器模式

```python
def with_logging(func):
    def wrapper(*args, **kwargs):
        logger.info(f"Calling {func.__name__}")
        result = func(*args, **kwargs)
        logger.info(f"{func.__name__} completed")
        return result
    return wrapper

def with_retry(max_retries=3):
    def decorator(func):
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries - 1:
                        raise e
        return wrapper
    return decorator
```

### 6. **Builder Pattern** - 複雜物件建構
**問題**: 配置物件創建過於複雜
**解決方案**: 使用 Builder 簡化創建過程

```python
class ChatServiceBuilder:
    def __init__(self):
        self._model = None
        self._database = None
        self._config = {}
    
    def with_model(self, model: FullLLMInterface):
        self._model = model
        return self
    
    def with_database(self, database: Database):
        self._database = database
        return self
    
    def with_config(self, config: Dict[str, Any]):
        self._config = config
        return self
    
    def build(self) -> CoreChatService:
        return CoreChatService(self._model, self._database, self._config)
```

## 📊 優先級建議

### 高優先級 (立即實作)
1. **Chain of Responsibility** - 解決 ChatService 職責過重
2. **Adapter Pattern** - 統一平台介面
3. **Command Pattern** - 指令系統重構

### 中優先級 (後續實作)  
4. **Observer Pattern** - 事件系統
5. **Decorator Pattern** - 橫切關注點

### 低優先級 (未來考慮)
6. **Builder Pattern** - 複雜物件建構

## 🎯 實作策略

1. **漸進式重構**: 不破壞現有功能，逐步引入新模式
2. **向後兼容**: 保持現有 API 穩定
3. **測試驅動**: 每個模式都要有對應測試
4. **文檔更新**: 更新架構文檔說明新的設計模式

## 🔧 具體實作計畫

### Phase 1: 核心重構 (本次)
- ✅ Strategy Pattern (已有 - 平台 handlers)
- ✅ Factory Pattern (已有 - ModelFactory)
- 🔄 Chain of Responsibility (訊息處理鏈)
- 🔄 Adapter Pattern (平台適配器)

### Phase 2: 功能增強 (後續)
- Command Pattern (指令系統)
- Observer Pattern (事件系統)

### Phase 3: 品質提升 (後續)  
- Decorator Pattern (logging, retry, cache)
- Builder Pattern (複雜物件建構)

此設計模式分析將指導我們的重構工作，確保系統具有良好的可擴展性和維護性。