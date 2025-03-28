import opencc
import re
from datetime import datetime, timedelta

s2t_converter = opencc.OpenCC('s2t')
t2s_converter = opencc.OpenCC('t2s')

def get_response_data(response) -> dict:
    for item in response['data']:
        if item['role'] == 'assistant' and item['content'] and item['content'][0]['type'] == 'text':
            return item
    return None

def get_content_and_reference(response, file_dict) -> str:
    data = get_response_data(response)
    if not data:
        return ''
    text = data['content'][0]['text']['value']
    annotations = data['content'][0]['text']['annotations']
    text = s2t_converter.convert(text)
    # 替換註釋文本
    ref_mapping = {}
    for i, annotation in enumerate(annotations, 1):
        original_text = annotation['text']
        file_id = annotation['file_citation']['file_id']
        replacement_text = f"[{i}]"
        text = text.replace(original_text, replacement_text)
        ref_mapping[replacement_text] = f"{replacement_text}: {file_dict.get(file_id)}"

    # 添加文件識別碼引用
    reference_text = '\n'.join(ref_mapping.values())
    final_text = f"{text}\n\n{reference_text}".strip()

    return final_text

def replace_file_name(content, file_dict) -> str:
    sorted_file_dict = sorted(file_dict.items(), key=lambda x: -len(x[0]))

    # 對每個鍵進行替換
    for key, value in sorted_file_dict:
        # 使用 re.escape 避免鍵中可能包含的任何正則表達式特殊字符影響匹配
        text = re.sub(re.escape(key), value, text) 
    return text

def check_token_valid(model) -> bool:
    is_successful, _, _ = model.check_token_valid()
    if not is_successful:
        raise ValueError('Invalid API token')
    return is_successful

def get_file_dict(model) -> dict:
    is_successful, response, error_message = model.list_files()
    if not is_successful:
        raise Exception(error_message)
    file_dict = { file['id']: file['filename'].replace('.txt', '').replace('.json', '') for file in response['data'] }
    return file_dict

def detect_none_references(text):
    if re.search(r'\[\d+\]: None', text):
        return True
    else:
        return False

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