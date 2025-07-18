import opencc
import re
from typing import Match
from ..core.logger import get_logger
from datetime import datetime, timedelta

logger = get_logger(__name__)

s2t_converter = opencc.OpenCC('s2t')
t2s_converter = opencc.OpenCC('t2s')

def get_response_data(response) -> dict:
    for item in response['data']:
        if item['role'] == 'assistant' and item['content'] and item['content'][0]['type'] == 'text':
            return item
    return None

def get_role_and_content(response):
    """
    從聊天回應中提取角色和內容
    支援不同格式的回應結構
    """
    if isinstance(response, dict):
        # 處理 OpenAI Assistant API 格式
        if 'data' in response:
            data = get_response_data(response)
            if data:
                return data['role'], data['content'][0]['text']['value']
        
        # 處理標準聊天格式
        if 'choices' in response:
            choice = response['choices'][0]
            if 'message' in choice:
                message = choice['message']
                return message.get('role', 'assistant'), message.get('content', '')
        
        # 處理簡單的訊息格式
        if 'role' in response and 'content' in response:
            return response['role'], response['content']
    
    # 如果是 ChatResponse 物件
    if hasattr(response, 'content'):
        return 'assistant', response.content
    
    # 預設回傳
    return 'assistant', str(response)

def dedup_citation_blocks(text: str) -> str:
    """
    將正文中的連續引用標籤去重後回傳新字串。
    
    例：
        '[1][1][1]'         -> '[1]'
        '[1][2][1][3][2]'   -> '[1][2][3]'
        其他文字不受影響
    """
    
    def _dedup(match: Match[str]) -> str:
        # 取出該連續區塊，例如 '[1][2][1]'
        block = match.group(0)
        # 抓出所有數字去重後轉 int
        nums = {int(n) for n in re.findall(r'\d+', match.group(0))}
        return ' ' + ''.join(f'[{n}]' for n in sorted(nums)) + ' '

    # 至少兩個連在一起的 [數字] 才視為一個「去重區塊」
    citation_block_pattern = r'(?:\[\d+\]){2,}'
    
    # 取代後回傳
    return re.sub(citation_block_pattern, _dedup, text)

def check_token_valid(model) -> bool:
    is_successful, _, _ = model.check_token_valid()
    if not is_successful:
        raise ValueError('Invalid API token')
    return is_successful

def get_date_string(day="today"):
    """
    返回指定天數的日期字串：'今天', '明天', '昨天'
    預設為'今天'。
    """
    today = datetime.now()
    
    if day == "today":
        target_date = today
    elif day == "tomorrow":
        target_date = today + timedelta(days=1)
    elif day == "yesterday":
        target_date = today - timedelta(days=1)
    else:
        raise ValueError("day 參數必須是 'today', 'tomorrow' 或 'yesterday'")
    
    # 格式化日期為 YYYY/MM/DD
    return target_date.strftime("%Y/%m/%d")

def load_text_processing_config(config):
    return config.get('text_processing', {})

def preprocess_text(text, config):
    text_processing_config = load_text_processing_config(config)
    for preprocessor in text_processing_config.get('preprocessors', []):
        if preprocessor['type'] == 'replace_date_string':
            text = re.sub(r'(今天|today)', get_date_string('today'), text, flags=re.IGNORECASE)
            text = re.sub(r'(明天|tomorrow)', get_date_string('tomorrow'), text, flags=re.IGNORECASE)
            text = re.sub(r'(昨天|yesterday)', get_date_string('yesterday'), text, flags=re.IGNORECASE)
    return text

def replace_text(text, replacements):
    if replacements:
        for replacement in replacements:
            text = re.sub(replacement['pattern'], replacement['replacement'], text)
    return text

def postprocess_text(text, config):
    text_processing_config = load_text_processing_config(config)
    text = replace_text(text, text_processing_config.get('post-replacements', []))
    return text

def add_disclaimer(text, config):
    """
    在文字後面加上免責聲明
    
    Args:
        text: 原始文字
        config: 配置字典，包含 disclaimer 內容
        
    Returns:
        加上免責聲明的文字
    """
    # 使用既有的 text_processing 配置載入方式
    text_processing_config = load_text_processing_config(config)
    disclaimer = text_processing_config.get('disclaimer', '')
    
    # 如果有免責聲明且不為空，則添加
    if disclaimer and disclaimer.strip():
        return text + "\n\n" + disclaimer.strip()
    
    # 沒有免責聲明就直接返回原文
    return text