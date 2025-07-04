class ChatBotError(Exception):
    """基礎聊天機器人錯誤"""
    def __init__(self, message: str, error_code: str = None):
        self.message = message
        self.error_code = error_code
        super().__init__(message)


class OpenAIError(ChatBotError):
    """OpenAI API 相關錯誤"""
    pass


class DatabaseError(ChatBotError):
    """資料庫相關錯誤"""
    pass


class ThreadError(ChatBotError):
    """對話串相關錯誤"""
    pass


class ConfigurationError(ChatBotError):
    """配置相關錯誤"""
    pass


class ModelError(ChatBotError):
    """AI 模型相關錯誤"""
    pass


class AnthropicError(ChatBotError):
    """Anthropic API 相關錯誤"""
    pass


class GeminiError(ChatBotError):
    """Gemini API 相關錯誤"""
    pass


class OllamaError(ChatBotError):
    """Ollama API 相關錯誤"""
    pass


class AudioError(ChatBotError):
    """音訊處理相關錯誤"""
    pass


class PlatformError(ChatBotError):
    """平台相關錯誤"""
    pass


class ValidationError(ChatBotError):
    """輸入驗證相關錯誤"""
    pass