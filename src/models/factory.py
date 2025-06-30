from typing import Dict, Any, Optional
from .base import BaseLLMInterface, ModelProvider
from .openai_model import OpenAIModel
from .anthropic_model import AnthropicModel
from .gemini_model import GeminiModel
from .ollama_model import OllamaModel


class ModelFactory:
    """模型工廠 - 用於建立不同的語言模型實例"""
    
    @staticmethod
    def create_model(provider: ModelProvider, config: Dict[str, Any]) -> BaseLLMInterface:
        """根據提供商和配置建立模型實例"""
        
        if provider == ModelProvider.OPENAI:
            return ModelFactory._create_openai_model(config)
        elif provider == ModelProvider.ANTHROPIC:
            return ModelFactory._create_anthropic_model(config)
        elif provider == ModelProvider.GEMINI:
            return ModelFactory._create_gemini_model(config)
        elif provider == ModelProvider.HUGGINGFACE:
            return ModelFactory._create_huggingface_model(config)
        elif provider == ModelProvider.OLLAMA:
            return ModelFactory._create_ollama_model(config)
        else:
            raise ValueError(f"Unsupported model provider: {provider}")
    
    @staticmethod
    def create_from_config(config: Dict[str, Any]) -> BaseLLMInterface:
        """從配置檔案建立模型"""
        provider_name = config.get('provider', 'openai').lower()
        
        try:
            provider = ModelProvider(provider_name)
        except ValueError:
            raise ValueError(f"Unknown provider: {provider_name}")
        
        return ModelFactory.create_model(provider, config)
    
    @staticmethod
    def _create_openai_model(config: Dict[str, Any]) -> OpenAIModel:
        """建立 OpenAI 模型"""
        api_key = config.get('api_key')
        if not api_key:
            raise ValueError("OpenAI API key is required")
        
        return OpenAIModel(
            api_key=api_key,
            assistant_id=config.get('assistant_id'),
            base_url=config.get('base_url')
        )
    
    @staticmethod
    def _create_anthropic_model(config: Dict[str, Any]) -> AnthropicModel:
        """建立 Anthropic 模型"""
        api_key = config.get('api_key')
        if not api_key:
            raise ValueError("Anthropic API key is required")
        
        return AnthropicModel(
            api_key=api_key,
            model_name=config.get('model', 'claude-3-sonnet-20240229'),
            base_url=config.get('base_url')
        )
    
    @staticmethod
    def _create_gemini_model(config: Dict[str, Any]) -> GeminiModel:
        """建立 Gemini 模型"""
        api_key = config.get('api_key')
        if not api_key:
            raise ValueError("Gemini API key is required")
        
        return GeminiModel(
            api_key=api_key,
            model_name=config.get('model', 'gemini-pro'),
            base_url=config.get('base_url')
        )
    
    @staticmethod
    def _create_huggingface_model(config: Dict[str, Any]):
        """建立 HuggingFace 模型（未來實作）"""
        raise NotImplementedError("HuggingFace model not implemented yet")
    
    @staticmethod
    def _create_ollama_model(config: Dict[str, Any]) -> OllamaModel:
        """建立 Ollama 本地模型"""
        return OllamaModel(
            base_url=config.get('base_url', 'http://localhost:11434'),
            model_name=config.get('model', 'llama2')
        )


# 範例：其他模型的基礎框架

class AnthropicModel(BaseLLMInterface):
    """Anthropic Claude 模型框架"""
    
    def __init__(self, api_key: str, model_name: str = "claude-3-sonnet-20240229"):
        self.api_key = api_key
        self.model_name = model_name
        self.base_url = "https://api.anthropic.com/v1"
    
    def get_provider(self) -> ModelProvider:
        return ModelProvider.ANTHROPIC
    
    def check_connection(self):
        # TODO: 實作 Anthropic API 連線檢查
        raise NotImplementedError()
    
    def chat_completion(self, messages, **kwargs):
        # TODO: 實作 Anthropic Chat API
        raise NotImplementedError()


class GeminiModel(BaseLLMInterface):
    """Google Gemini 模型框架"""
    
    def __init__(self, api_key: str, model_name: str = "gemini-pro"):
        self.api_key = api_key
        self.model_name = model_name
        self.base_url = "https://generativelanguage.googleapis.com/v1"
    
    def get_provider(self) -> ModelProvider:
        return ModelProvider.GEMINI
    
    def check_connection(self):
        # TODO: 實作 Gemini API 連線檢查
        raise NotImplementedError()
    
    def chat_completion(self, messages, **kwargs):
        # TODO: 實作 Gemini Chat API
        raise NotImplementedError()


class OllamaModel(BaseLLMInterface):
    """Ollama 本地模型框架"""
    
    def __init__(self, base_url: str = "http://localhost:11434", model_name: str = "llama2"):
        self.base_url = base_url
        self.model_name = model_name
    
    def get_provider(self) -> ModelProvider:
        return ModelProvider.OLLAMA
    
    def check_connection(self):
        # TODO: 實作 Ollama 連線檢查
        raise NotImplementedError()
    
    def chat_completion(self, messages, **kwargs):
        # TODO: 實作 Ollama Chat API
        raise NotImplementedError()