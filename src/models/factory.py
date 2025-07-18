from typing import Dict, Any, Optional
from .base import BaseLLMInterface, ModelProvider
from .openai_model import OpenAIModel
from .anthropic_model import AnthropicModel
from .gemini_model import GeminiModel
from .ollama_model import OllamaModel
from .huggingface_model import HuggingFaceModel


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
    def _create_huggingface_model(config: Dict[str, Any]) -> HuggingFaceModel:
        """建立 HuggingFace 模型"""
        api_key = config.get('api_key')
        if not api_key:
            raise ValueError("HuggingFace API key is required")
        
        return HuggingFaceModel(
            api_key=api_key,
            model_name=config.get('model_name', 'mistralai/Mistral-7B-Instruct-v0.1'),
            api_type=config.get('api_type', 'inference_api'),
            base_url=config.get('base_url', 'https://api-inference.huggingface.co'),
            # 傳遞所有額外配置
            fallback_models=config.get('fallback_models'),
            embedding_model=config.get('embedding_model'),
            speech_model=config.get('speech_model'),
            image_model=config.get('image_model'),
            temperature=config.get('temperature'),
            max_tokens=config.get('max_tokens'),
            timeout=config.get('timeout')
        )
    
    @staticmethod
    def _create_ollama_model(config: Dict[str, Any]) -> OllamaModel:
        """建立 Ollama 本地模型"""
        return OllamaModel(
            base_url=config.get('base_url', 'http://localhost:11434'),
            model_name=config.get('model', 'llama2')
        )

