# 向後相容 - 重新匯出新的模型系統
from .models.openai_model import OpenAIModel
from .models.factory import ModelFactory
from .models.base import ModelProvider

# 保持向後相容性
__all__ = ['OpenAIModel', 'ModelFactory', 'ModelProvider']