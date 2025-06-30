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