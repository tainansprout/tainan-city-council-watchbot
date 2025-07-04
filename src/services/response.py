import logging
import json
from typing import Dict, List, Any
from flask import Response
from ..models.base import RAGResponse
from ..utils import s2t_converter

logger = logging.getLogger(__name__)


class ResponseFormatter:
    """統一的回應格式處理器 - 處理不同模型的回應格式"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
    
    def format_rag_response(self, rag_response: RAGResponse) -> str:
        """
        統一格式化所有模型的 RAG 回應
        
        Args:
            rag_response: 包含答案和來源的 RAG 回應物件
            
        Returns:
            格式化後的回應文字
        """
        try:
            # 基本內容處理 - 轉換為繁體中文
            content = s2t_converter.convert(rag_response.answer)
            
            # 如果有來源引用，添加來源資訊
            if rag_response.sources:
                source_text = self._format_sources(rag_response.sources)
                if source_text:
                    content = f"{content}\n\n{source_text}"
            
            logger.debug(f"Formatted response length: {len(content)}, sources: {len(rag_response.sources) if rag_response.sources else 0}")
            return content.strip()
            
        except Exception as e:
            logger.error(f"Error formatting RAG response: {e}")
            # 降級處理 - 至少返回基本內容
            return rag_response.answer if rag_response.answer else "回應處理失敗"
    
    def _format_sources(self, sources: List[Dict[str, Any]]) -> str:
        """
        格式化來源引用
        
        Args:
            sources: 來源資訊列表，支援不同模型的格式
            
        Returns:
            格式化的來源文字
        """
        if not sources:
            return ""
        
        try:
            source_lines = []
            seen_sources = set()  # 避免重複來源
            
            for i, source in enumerate(sources, 1):
                # 跳過 None 值
                if source is None:
                    continue
                    
                # 提取來源資訊
                source_info = self._extract_source_info(source, i)
                
                # 避免重複來源
                source_key = source_info.get('key')
                if source_key and source_key in seen_sources:
                    continue
                
                # 格式化單個來源
                formatted_source = self._format_single_source(source_info, i)
                if formatted_source:
                    source_lines.append(formatted_source)
                    if source_key:
                        seen_sources.add(source_key)
            
            return '\n'.join(source_lines) if source_lines else ""
            
        except Exception as e:
            logger.error(f"Error formatting sources: {e}")
            return ""
    
    def _extract_source_info(self, source: Dict[str, Any], index: int) -> Dict[str, Any]:
        """
        從不同模型的來源格式中提取統一的來源資訊
        
        Args:
            source: 來源資料（不同模型格式不同）
            index: 來源索引
            
        Returns:
            統一格式的來源資訊
        """
        info = {
            'index': index,
            'filename': None,
            'key': None,
            'quote': None,
            'type': source.get('type', 'unknown')
        }
        
        try:
            # OpenAI Assistant API 格式
            if 'file_id' in source:
                info['key'] = source['file_id']
                info['filename'] = source.get('filename')
                info['quote'] = source.get('quote', '')
                info['type'] = 'file_citation'
            
            # Gemini 格式（假設使用 document_id）
            elif 'document_id' in source:
                info['key'] = source['document_id']
                info['filename'] = source.get('title') or source.get('filename')
                info['quote'] = source.get('snippet', '')
                info['type'] = 'document'
            
            # Anthropic 或其他格式
            elif 'reference_id' in source:
                info['key'] = source['reference_id']
                info['filename'] = source.get('title') or source.get('filename')
                info['quote'] = source.get('content', '')
                info['type'] = 'reference'
            
            # 通用格式
            elif 'filename' in source:
                info['filename'] = source['filename']
                info['key'] = source.get('id') or source['filename']
                info['quote'] = source.get('content', '')
            
            # 如果沒有明確的檔案名稱，嘗試從 key 生成
            if not info['filename'] and info['key']:
                if isinstance(info['key'], str) and len(info['key']) > 8:
                    info['filename'] = f"File-{info['key'][:8]}"
                else:
                    info['filename'] = f"Source-{index}"
            
        except Exception as e:
            logger.warning(f"Error extracting source info from {source}: {e}")
            info['filename'] = f"Source-{index}"
        
        return info
    
    def _format_single_source(self, source_info: Dict[str, Any], index: int) -> str:
        """
        格式化單個來源引用
        
        Args:
            source_info: 來源資訊
            index: 來源索引
            
        Returns:
            格式化的來源文字
        """
        try:
            filename = source_info.get('filename') or f"Source-{index}"
            
            # 清理檔案名稱 - 移除常見副檔名
            display_name = filename
            for ext in ['.txt', '.json', '.csv', '.pdf', '.docx', '.md']:
                display_name = display_name.replace(ext, '')
            
            return f"[{index}]: {display_name}"
            
        except Exception as e:
            logger.warning(f"Error formatting single source: {e}")
            return f"[{index}]: Source-{index}"
    
    def format_simple_response(self, content: str) -> str:
        """
        格式化簡單回應（無 RAG）
        
        Args:
            content: 回應內容
            
        Returns:
            格式化後的回應
        """
        try:
            # 轉換為繁體中文
            formatted_content = s2t_converter.convert(content) if content else ""
            return formatted_content.strip()
        except Exception as e:
            logger.error(f"Error formatting simple response: {e}")
            return content if content else "回應處理失敗"
    
    def json_response(self, data: Dict[str, Any], status_code: int = 200) -> Response:
        """
        統一的 JSON 回應處理，確保 UTF-8 編碼
        
        Args:
            data: 要回應的資料字典
            status_code: HTTP 狀態碼
            
        Returns:
            正確編碼的 Flask Response 物件
        """
        try:
            json_str = json.dumps(data, ensure_ascii=False, indent=2)
            return Response(
                json_str, 
                status=status_code, 
                mimetype='application/json; charset=utf-8'
            )
        except Exception as e:
            logger.error(f"Error creating JSON response: {e}")
            # 備用回應
            error_data = {'error': '回應處理失敗'}
            json_str = json.dumps(error_data, ensure_ascii=False)
            return Response(
                json_str,
                status=500,
                mimetype='application/json; charset=utf-8'
            )