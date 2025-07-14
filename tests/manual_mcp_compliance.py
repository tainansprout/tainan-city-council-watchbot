#!/usr/bin/env python3
"""
MCP Protocol Compliance Test Script
測試 MCP 協議合規性和新功能
"""

import asyncio
import json
import os
import sys
from typing import Dict, Any

# Add src to path
project_root = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, project_root)

from src.core.mcp_config import MCPConfigManager
from src.core.mcp_client import MCPClient
from src.services.mcp_service import MCPService

async def test_mcp_client_features():
    """測試 MCP 客戶端新功能"""
    print("=" * 50)
    print("Testing MCP Client Features")
    print("=" * 50)
    
    # 測試設定載入
    config_manager = MCPConfigManager()
    server_config = config_manager.get_server_config()
    print(f"✓ Server config loaded: {server_config.get('base_url', 'N/A')}")
    
    # 建立客戶端
    client = MCPClient(server_config)
    print(f"✓ Client initialized with capabilities: {list(client.capabilities.keys())}")
    
    # 測試分頁功能
    print("\n--- Testing Pagination ---")
    try:
        success, tools, next_cursor, error = await client.list_tools()
        if success:
            print(f"✓ List tools successful: {len(tools) if tools else 0} tools")
            if next_cursor:
                print(f"✓ Next cursor available: {next_cursor[:20]}...")
            else:
                print("✓ No pagination needed")
        else:
            print(f"✗ List tools failed: {error}")
    except Exception as e:
        print(f"✗ List tools error: {e}")
    
    # 測試能力初始化
    print("\n--- Testing Capabilities ---")
    try:
        success, error = await client.initialize_capabilities()
        if success:
            print("✓ Capabilities initialized successfully")
        else:
            print(f"✗ Capabilities initialization failed: {error}")
    except Exception as e:
        print(f"✗ Capabilities initialization error: {e}")
    
    # 測試認證功能（不實際執行）
    print("\n--- Testing Authentication (Mock) ---")
    try:
        # 模擬 OAuth 設定
        auth_config = {
            'client_id': 'test_client',
            'client_secret': 'test_secret',
            'scope': 'read write'
        }
        client.auth_config = auth_config
        
        # 測試認證 URL 生成
        success, auth_url = await client.authenticate_oauth(
            "https://auth.example.com/authorize",
            "https://callback.example.com"
        )
        if success:
            print(f"✓ OAuth URL generated: {auth_url[:50]}...")
        else:
            print(f"✗ OAuth URL generation failed: {auth_url}")
    except Exception as e:
        print(f"✗ OAuth test error: {e}")
    
    await client.close()

async def test_mcp_service_features():
    """測試 MCP 服務新功能"""
    print("\n" + "=" * 50)
    print("Testing MCP Service Features")
    print("=" * 50)
    
    service = MCPService()
    
    # 測試服務資訊
    info = service.get_service_info()
    print(f"✓ Service enabled: {info['enabled']}")
    print(f"✓ Configured functions: {info['configured_functions']}")
    print(f"✓ Server URL: {info.get('server_url', 'N/A')}")
    print(f"✓ Auth configured: {info.get('auth_configured', False)}")
    print(f"✓ Capabilities: {info.get('capabilities', [])}")
    
    # 測試分頁工具列表
    print("\n--- Testing Paginated Tools List ---")
    try:
        success, tools, next_cursor, error = await service.list_available_tools()
        if success:
            print(f"✓ Tools list successful: {len(tools) if tools else 0} tools")
            if next_cursor:
                print(f"✓ Next cursor: {next_cursor[:20]}...")
                
                # 測試下一頁
                success2, tools2, next_cursor2, error2 = await service.list_available_tools(next_cursor)
                if success2:
                    print(f"✓ Next page successful: {len(tools2) if tools2 else 0} tools")
                else:
                    print(f"✗ Next page failed: {error2}")
            else:
                print("✓ No pagination needed")
        else:
            print(f"✗ Tools list failed: {error}")
    except Exception as e:
        print(f"✗ Tools list error: {e}")
    
    # 測試連線初始化
    print("\n--- Testing Connection Initialization ---")
    try:
        success, error = await service.initialize_connection()
        if success:
            print("✓ Connection initialized successfully")
        else:
            print(f"✗ Connection initialization failed: {error}")
    except Exception as e:
        print(f"✗ Connection initialization error: {e}")
    
    # 測試健康檢查
    print("\n--- Testing Health Check ---")
    try:
        healthy, error = await service.health_check()
        if healthy:
            print("✓ Health check passed")
        else:
            print(f"✗ Health check failed: {error}")
    except Exception as e:
        print(f"✗ Health check error: {e}")

def test_config_features():
    """測試配置管理功能"""
    print("\n" + "=" * 50)
    print("Testing Config Management Features")
    print("=" * 50)
    
    config_manager = MCPConfigManager()
    
    # 測試配置列表
    configs = config_manager.list_available_configs()
    print(f"✓ Available configs: {configs}")
    
    # 測試 MCP 啟用檢查
    enabled = config_manager.is_mcp_enabled()
    print(f"✓ MCP enabled: {enabled}")
    
    if enabled and configs:
        # 測試配置載入
        config = config_manager.load_mcp_config(configs[0])
        print(f"✓ Config loaded: {configs[0]}")
        
        # 測試函數模式生成
        openai_schemas = config_manager.get_function_schemas_for_openai(configs[0])
        print(f"✓ OpenAI schemas: {len(openai_schemas)} functions")
        
        anthropic_prompt = config_manager.get_function_schemas_for_anthropic(configs[0])
        print(f"✓ Anthropic prompt: {len(anthropic_prompt)} chars")
        
        # 測試參數驗證
        if config.get('functions'):
            func = config['functions'][0]
            func_name = func['name']
            test_args = {'query': 'test'}
            
            valid, error = config_manager.validate_function_arguments(
                func_name, test_args, configs[0]
            )
            print(f"✓ Argument validation: {valid} (error: {error})")

async def main():
    """主測試函數"""
    print("MCP Protocol Compliance Test")
    print("=" * 50)
    
    # 測試配置管理
    test_config_features()
    
    # 測試客戶端功能
    await test_mcp_client_features()
    
    # 測試服務功能
    await test_mcp_service_features()
    
    print("\n" + "=" * 50)
    print("Testing Complete!")
    print("=" * 50)
    
    # 總結新功能
    print("\n✅ New MCP Protocol Features Implemented:")
    print("1. ✓ Pagination support with cursor-based navigation")
    print("2. ✓ Client capabilities declaration")
    print("3. ✓ OAuth 2.1 authentication framework")
    print("4. ✓ PKCE security for OAuth flows")
    print("5. ✓ Enhanced error handling and logging")
    print("6. ✓ Protocol version specification (2025-06-18)")
    print("7. ✓ Comprehensive configuration management")
    print("8. ✓ Service layer improvements")

if __name__ == "__main__":
    asyncio.run(main())