# Multi-Platform Chatbot Architecture

## Overview

This document defines the **strict separation of concerns** architecture that ensures maintainability, testability, and extensibility of the multi-platform chatbot system.

## Core Design Principles

⚠️ **CRITICAL**: These principles MUST NEVER be violated:

1. **Platform handlers MUST NOT call AI model APIs directly**
2. **AI models MUST NOT know about platform types or sources**
3. **Audio transcription MUST happen in AudioService, not platform handlers**
4. **App.py is the ONLY coordinator between layers**
5. **Each layer MUST have single responsibility**

## Layer Responsibilities

### 1. Platform Layer (`src/platforms/`)

**Purpose**: Handle platform-specific communication protocols

**Responsibilities**:
- Parse incoming webhooks
- Extract message content and metadata
- Download media files (audio, images, etc.)
- Send responses back to platform APIs
- Verify webhook signatures

**NEVER**:
- Call AI model APIs
- Perform audio transcription
- Process conversation logic
- Store conversation history

**Unified Platform Interface (BasePlatformHandler)**:
All platform handlers MUST implement these standard methods:
- `parse_message(event) -> Optional[PlatformMessage]`
- `handle_webhook(body, headers) -> List[PlatformMessage]`
- `send_response(response, original_message) -> bool`
- `verify_webhook(verify_token, challenge) -> str` (for Meta platforms)
- `get_platform_type() -> PlatformType`

**Meta Platform Handler Inheritance**:
Meta platforms (WhatsApp, Instagram, Messenger) share common functionality through inheritance:
```
BasePlatformHandler (abstract base)
    ↓
MetaBaseHandler (shared Meta functionality)
    ↓ ↓ ↓
WhatsAppHandler  InstagramHandler  MessengerHandler
```

**MetaBaseHandler** (`src/platforms/meta_base_handler.py`) provides shared functionality:
- **Webhook Signature Verification**: Support for both SHA256 (`X-Hub-Signature-256`) and SHA1 (`X-Hub-Signature`) 
- **Media Download**: Two modes - URL-based (Instagram/Messenger) and ID-based (WhatsApp)
- **Graph API Configuration**: Unified base URL and headers setup
- **Common Error Handling**: Centralized logging and exception management
- **Unified Webhook Processing**: Standard flow for all Meta platforms
- **Configuration Management**: Shared Meta-specific config validation

**Platform-specific implementations** handle:
- **Configuration Setup**: Platform-specific tokens (WhatsApp: `access_token`, Others: `page_access_token`)
- **Message Parsing**: Platform-specific webhook structures and message formats
- **Response Sending**: Platform-specific API endpoints and payload formats
- **Unique Features**: WhatsApp media IDs, Instagram story replies, Messenger quick replies

**Benefits of Inheritance Structure**:
- **Code Reuse**: 80%+ shared logic eliminated duplication
- **Consistent Behavior**: All Meta platforms handle webhooks and signatures identically
- **Simplified Maintenance**: Bug fixes in MetaBaseHandler apply to all platforms
- **Easy Extension**: New Meta platforms can inherit common functionality

**Audio Message Handling**:
```python
# ✅ CORRECT: Platform only provides raw data
class PlatformHandler(BasePlatformHandler):
    def parse_message(self, event) -> Optional[PlatformMessage]:
        if message_type == "audio":
            # Platform-specific download logic
            raw_data = self._download_audio(media_url)
            
            return PlatformMessage(
                message_type="audio",
                content="[Audio Message]",  # Placeholder only
                raw_data=raw_data,  # Raw bytes for app layer
                user=user,
                message_id=message_id,
                reply_token=reply_token
            )
    
    def send_response(self, response: PlatformResponse, original_message: PlatformMessage) -> bool:
        """Platform-specific response sending"""
        # Implementation varies by platform (LINE API, Discord API, etc.)
        pass
```

### 2. Application Layer (`src/app.py`)

**Purpose**: Coordinate message routing between layers

**Responsibilities**:
- Receive PlatformMessage from platform handlers
- Route audio messages to AudioService for transcription
- Route text messages to ChatService for processing
- Coordinate response delivery back to platforms
- Handle dependency injection (model → services)

**Message Processing Logic**:
```python
def _handle_webhook(self, platform_name: str):
    messages = self.platform_manager.handle_platform_webhook(...)
    
    for message in messages:
        if message.message_type == "audio":
            # Step 1: AudioService transcribes
            audio_result = self.audio_service.handle_message(
                user_id=message.user.user_id,
                audio_content=message.raw_data,
                platform=message.user.platform.value
            )
            
            if audio_result['success']:
                # Step 2: Create text message for ChatService
                text_message = PlatformMessage(
                    message_id=f"audio_transcribed_{message.user.user_id}",
                    user=message.user,
                    content=audio_result['transcribed_text'],
                    message_type="text",
                    reply_token=message.reply_token
                )
                # Step 3: ChatService processes transcribed text
                response = self.chat_service.handle_message(text_message)
            else:
                # Handle transcription failure
                response = PlatformResponse(
                    content="Sorry, I couldn't process your audio message.",
                    response_type='text'
                )
        else:
            # Direct text processing
            response = self.chat_service.handle_message(message)
        
        # Send response via platform handler
        handler = self.platform_manager.get_handler(platform_type)
        handler.send_response(response, message)
```

### 3. Service Layer (`src/services/`)

**Purpose**: Implement business logic without platform dependencies

#### AudioService (`src/services/audio.py`)
**Responsibilities**:
- Audio-to-text transcription only
- Return transcription results to app layer

**Model Dependency**:
- Receives model instance via dependency injection in app.py
- Uses model's unified `transcribe_audio()` interface

**NEVER**:
- Know about specific platforms
- Process conversation logic
- Send responses directly

```python
class AudioService:
    def __init__(self, model: FullLLMInterface):
        self.model = model  # Injected by app.py
    
    def handle_message(self, user_id: str, audio_content: bytes, platform: str = 'line') -> Dict[str, Any]:
        """
        Process audio message: audio → transcribed text only
        Returns transcription result to app layer for further processing
        """
        is_successful, transcribed_text, error_message = process_audio(
            audio_content, self.model  # Use injected model
        )
        
        return {
            'success': is_successful,
            'transcribed_text': transcribed_text,
            'error_message': error_message
        }
```

#### ChatService (`src/services/chat.py`)
**Responsibilities**:
- Process text messages (including transcribed audio)
- Manage conversation flow and history
- Generate AI responses

**Model Dependency**:
- Receives model instance via dependency injection in app.py
- Uses model's unified `chat_with_user()` interface

**NEVER**:
- Handle audio transcription
- Know about specific platforms
- Route messages

```python
class ChatService:
    def __init__(self, model: FullLLMInterface, database: Database, config: Dict[str, Any]):
        self.model = model  # Injected by app.py
        self.database = database
        self.config = config
    
    def handle_message(self, message: PlatformMessage) -> PlatformResponse:
        """
        Process text messages only - platform agnostic
        """
        if message.message_type == "text":
            return self._handle_text_message(message.user, message.content, platform)
        elif message.message_type == "audio":
            # Audio should be handled by AudioService first
            return PlatformResponse(
                content="System error: Audio messages should be processed by AudioService.",
                response_type="text"
            )
    
    def _process_conversation(self, user: PlatformUser, text: str, platform: str) -> str:
        """Use unified model interface"""
        is_successful, response, error = self.model.chat_with_user(
            user_id=user.user_id,
            message=text,
            platform=platform
        )
        return response if is_successful else error
```

### 4. Model Layer (`src/models/`)

**Purpose**: Provide AI functionality with unified interfaces

**Responsibilities**:
- Text generation and conversation
- Audio transcription  
- Maintain conversation context
- Abstract AI provider differences (OpenAI, Anthropic, Gemini, Ollama, HuggingFace)

**Unified Interface (FullLLMInterface)**:
All models MUST implement these standard methods:
- `chat_with_user(user_id, message, platform) -> (bool, str, str)`
- `transcribe_audio(file_path) -> (bool, str, str)`
- `clear_user_history(user_id, platform) -> (bool, str)`
- `check_connection() -> (bool, str)`

**NEVER**:
- Know about platform sources
- Handle message routing
- Parse platform-specific formats

```python
# Unified Model Interface
class FullLLMInterface(ABC):
    @abstractmethod
    def chat_with_user(self, user_id: str, message: str, platform: str = 'line') -> Tuple[bool, str, Optional[str]]:
        """Platform-agnostic chat interface"""
        pass
    
    @abstractmethod
    def transcribe_audio(self, file_path: str) -> Tuple[bool, str, Optional[str]]:
        """Platform-agnostic audio transcription"""
        pass

# Example Implementation
class OpenAIModel(FullLLMInterface):
    def chat_with_user(self, user_id: str, message: str, platform: str = 'line') -> Tuple[bool, str, Optional[str]]:
        # OpenAI-specific implementation
        # Returns: (success, response_text, error_message)
        pass
    
    def transcribe_audio(self, file_path: str) -> Tuple[bool, str, Optional[str]]:
        # OpenAI Whisper implementation
        # Returns: (success, transcribed_text, error_message)
        pass
```

## Dependency Injection Flow

The model flows through the system via dependency injection:

```python
# 1. App.py creates model instance
class MultiPlatformChatBot:
    def _initialize_model(self):
        model_config = self.config.get('llm', {})
        provider = model_config.get('provider', 'openai')
        self.model = ModelFactory.create_from_config(model_config)
    
    def _initialize_core_service(self):
        # 2. App.py injects model into services
        self.chat_service = ChatService(
            model=self.model,      # ← Dependency injection
            database=self.database,
            config=self.config
        )
        
        self.audio_service = AudioService(
            model=self.model       # ← Dependency injection
        )
```

**Key Benefits**:
- **Single Model Instance**: One model serves all platforms
- **Consistent Interface**: All models work the same way
- **Easy Testing**: Services can be tested with mock models
- **Configuration Flexibility**: Change AI provider without code changes

## Message Flow Diagrams

### Text Message Flow
```
User Input (Text)
    ↓
Platform Handler
    ↓ (parse message)
PlatformMessage(type="text")
    ↓
App.py
    ↓ (route to chat)
ChatService
    ↓ (generate response)
Model (OpenAI/Claude/Gemini)
    ↓ (text response)
PlatformResponse
    ↓
Platform Handler
    ↓ (send response)
User Receives Response
```

### Audio Message Flow
```
User Input (Audio)
    ↓
Platform Handler
    ↓ (download audio)
PlatformMessage(type="audio", raw_data=bytes)
    ↓
App.py
    ↓ (route to audio service)
AudioService
    ↓ (transcribe)
Model (Audio API)
    ↓ (transcribed text)
App.py
    ↓ (create text message)
PlatformMessage(type="text", content=transcribed_text)
    ↓ (route to chat service)
ChatService
    ↓ (generate response)
Model (Chat API)
    ↓ (text response)
PlatformResponse
    ↓
Platform Handler
    ↓ (send response)
User Receives Response
```

## Code Examples

### ✅ CORRECT Platform Implementation

```python
class LineHandler(BasePlatformHandler):
    def parse_message(self, event: Any) -> Optional[PlatformMessage]:
        if isinstance(event.message, AudioMessageContent):
            try:
                # Download audio content
                audio_content = blob_api.get_message_content(message_id=event.message.id)
                
                # Only provide raw data - NO transcription
                content = "[Audio Message]"
                logger.debug(f"Audio message from {user.user_id}, size: {len(audio_content)} bytes")
                
            except Exception:
                logger.error("Failed to download audio content")
                audio_content = None
                content = "[Audio Message - Download Failed]"

            return PlatformMessage(
                message_id=event.message.id,
                user=user,
                content=content,
                message_type="audio",
                raw_data=audio_content,  # Raw data for app layer
                reply_token=event.reply_token
            )
```

### ❌ WRONG Platform Implementation

```python
class WrongHandler(BasePlatformHandler):
    def parse_message(self, event: Any) -> Optional[PlatformMessage]:
        if isinstance(event.message, AudioMessageContent):
            audio_content = blob_api.get_message_content(message_id=event.message.id)
            
            # ❌ WRONG: Platform should NOT transcribe
            transcribed_text = self.audio_handler.transcribe_audio(audio_content)
            
            return PlatformMessage(
                content=transcribed_text,  # ❌ Platform doing AI work
                message_type="text"  # ❌ Hiding that it was audio
            )
```

## File Structure and Dependencies

```
src/
├── core/          # Core infrastructure - no business logic
├── models/        # AI models - no platform knowledge  
├── services/      # Business logic - platform agnostic
├── platforms/     # Platform handlers - no AI calls
└── app.py        # Coordinator - imports all layers
```

**Dependency Rules**:
- `core/` → No dependencies on other src/ modules
- `models/` → Can import `core/` only
- `services/` → Can import `core/` and `models/`
- `platforms/` → Can import `core/` only (NO services, NO models)
- `app.py` → Can import from all layers

## Testing Strategy

### Platform Layer Tests
- Mock webhook data parsing
- Verify message extraction
- Test media download (mock external APIs)
- **NEVER test AI model integration**

### Service Layer Tests  
- Mock model responses
- Test business logic
- Verify platform-agnostic behavior
- **NEVER test platform-specific formats**

### Integration Tests
- Test full message flow through app.py
- Verify proper service coordination
- Test error handling between layers

## Common Mistakes to Avoid

1. **Platform calling AI models directly**
   ```python
   # ❌ WRONG
   transcribed = self.model.transcribe_audio(data)
   ```

2. **Services knowing about platforms**
   ```python
   # ❌ WRONG  
   if platform == "line":
       # Platform-specific logic in service
   ```

3. **Bypassing app.py coordination**
   ```python
   # ❌ WRONG: Platform calling service directly
   response = self.chat_service.handle_message(message)
   ```

4. **Models handling platform formats**
   ```python
   # ❌ WRONG: Model parsing LINE events
   def process_line_event(self, line_event):
   ```

## Migration Notes

Previous versions had platform handlers performing audio transcription. This violated separation of concerns and made the system harder to maintain and test. 

The new architecture ensures:
- **Single Responsibility**: Each layer has one clear purpose
- **Testability**: Layers can be tested independently  
- **Maintainability**: Changes in one layer don't affect others
- **Extensibility**: New platforms or models can be added easily

## Enforcement

To ensure these principles are followed:

1. **Code Reviews**: Check for cross-layer violations
2. **Testing**: Integration tests verify proper flow
3. **Documentation**: This document defines the contract
4. **Monitoring**: Log message flows to verify routing

## Quick Reference

- **詳細接口規範**: [docs/INTERFACES.md](INTERFACES.md)
- **Platform 接口**: `BasePlatformHandler` - 統一的平台處理接口
- **Model 接口**: `FullLLMInterface` - 統一的 AI 模型接口
- **依賴注入**: App.py → Services → Models
- **訊息流向**: Platform → App → Service → Model → Response

Remember: **App.py is the traffic controller, not the workers. Each layer does one job well.**