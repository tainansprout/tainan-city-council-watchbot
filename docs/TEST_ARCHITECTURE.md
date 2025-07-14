# 測試架構說明書

## 📋 **概述**

本文件描述 Multi-Platform Chatbot 項目的測試架構設計和實現。我們採用分層測試策略，確保代碼品質和系統可靠性。

## 🏗️ **測試架構總覽**

### **測試層級**
```
單元測試 (Unit Tests)     → 測試個別組件功能
   ↓
整合測試 (Integration)    → 測試組件間的互動
   ↓  
API 測試 (API Tests)      → 測試 HTTP 端點
   ↓
煙霧測試 (Smoke Tests)    → 測試核心功能完整性
```

### **測試覆蓋範圍**
- **Platform Handlers**: 78-90% 覆蓋率
- **Core Services**: 目標 80%+ 覆蓋率
- **Models**: 目標 75%+ 覆蓋率
- **Utils**: 目標 85%+ 覆蓋率

## 📁 **目錄結構**

```
tests/
├── conftest.py                    # 全域測試配置和 fixtures
├── test_main.py                   # 主應用程式入口測試
├── test_smoke.py                  # 煙霧測試
│
├── unit/                          # 單元測試 (258+ 測試)
│   ├── __init__.py
│   ├── test_app.py                # Flask 應用測試
│   │
│   ├── core/                      # 核心模組測試 (11 files)
│   │   ├── test_config_manager.py
│   │   ├── test_logger.py
│   │   ├── test_security.py
│   │   ├── test_memory_monitor.py
│   │   └── ...
│   │
│   ├── platforms/                 # 平台處理器測試 (8 files, 258 tests)
│   │   ├── test_line_handler.py      # LINE: 90% 覆蓋率
│   │   ├── test_discord_handler.py   # Discord: 78% 覆蓋率
│   │   ├── test_telegram_handler.py  # Telegram: 82% 覆蓋率
│   │   ├── test_slack_handler.py     # Slack: 76% 覆蓋率
│   │   ├── test_whatsapp_handler.py  # WhatsApp: 86% 覆蓋率
│   │   ├── test_instagram_handler.py # Instagram: 77% 覆蓋率
│   │   ├── test_messenger_handler.py # Messenger: 81% 覆蓋率
│   │   └── test_platforms.py         # 平台工廠和管理器
│   │
│   ├── models/                    # AI 模型測試 (6 files)
│   │   ├── test_openai_model.py
│   │   ├── test_anthropic_model.py
│   │   ├── test_gemini_model.py
│   │   ├── test_huggingface_model.py
│   │   ├── test_ollama_model.py
│   │   └── test_models.py            # 模型工廠測試
│   │
│   ├── services/                  # 服務層測試 (4 files)
│   │   ├── test_chat.py
│   │   ├── test_audio.py
│   │   ├── test_conversation.py
│   │   └── test_response.py
│   │
│   ├── databases/                 # 資料庫測試 (5 files)
│   │   ├── test_connection.py
│   │   ├── test_models.py
│   │   ├── test_operations.py
│   │   ├── test_migration.py
│   │   └── test_initdb.py
│   │
│   └── utils/                     # 工具函數測試 (2 files)
│       ├── test_retry.py
│       └── test_utils.py
│
├── integration/                   # 整合測試
│   ├── test_database_integration.py
│   └── test_docker_optimization.py
│
├── api/                          # API 端點測試
│   ├── test_health_endpoints.py
│   └── test_webhook_endpoints.py
│
└── mocks/                        # Mock 和測試工具
    └── test_external_services.py
```

## 🎯 **測試分類和標記**

### **Pytest 標記**
```python
@pytest.mark.unit          # 單元測試 (快速執行)
@pytest.mark.integration   # 整合測試 (需要外部依賴)
@pytest.mark.slow          # 慢速測試 (超過 1 秒)
@pytest.mark.database      # 需要資料庫的測試
@pytest.mark.external      # 需要外部服務的測試
```

### **執行命令**
```bash
# 執行所有測試
python -m pytest

# 只執行單元測試 (快速)
python -m pytest -m unit

# 執行平台測試
python -m pytest tests/unit/platforms/

# 執行特定平台測試
python -m pytest tests/unit/platforms/test_line_handler.py

# 生成覆蓋率報告
python -m pytest --cov=src --cov-report=html
```

## 🔧 **測試配置架構**

### **conftest.py 核心 Fixtures**

```python
@pytest.fixture
def mock_config():
    """新的多平台配置格式"""
    return {
        'platforms': {
            'line': {'enabled': True, 'channel_access_token': '...'},
            'discord': {'enabled': True, 'bot_token': '...'},
            # ... 其他平台
        },
        'llm': {'provider': 'openai'},
        'openai': {'api_key': '...', 'assistant_id': '...'},
        'db': {'host': 'localhost', ...}
    }

@pytest.fixture
def client():
    """Flask 測試客戶端 - 使用 create_app()"""
    app = create_app()
    app.config['TESTING'] = True
    return app.test_client()
```

### **環境變數設定**
```python
# 測試環境自動設定
FLASK_ENV=testing
FLASK_DEBUG=false
ENABLE_SECURITY_HEADERS=false
GENERAL_RATE_LIMIT=1000  # 測試時放寬限制
```

## 🧪 **平台測試架構**

### **測試覆蓋重點**

**✅ 完成的測試 (258 tests passing)**

1. **SDK 相容性測試**
   - 測試當 SDK 不可用時的優雅降級
   - Mock 外部依賴避免實際 API 呼叫

2. **訊息解析測試**
   - 文字訊息、音訊訊息、多媒體訊息
   - 邊界情況和錯誤處理

3. **Webhook 處理測試**
   - 簽名驗證、JSON 解析
   - 多平台 webhook 格式

4. **回應發送測試**
   - 成功發送、失敗重試
   - 長訊息分割、格式化

5. **配置驗證測試**
   - 必要欄位檢查、錯誤處理
   - 平台啟用/停用邏輯

### **測試模式**

```python
# 1. SDK 不可用時的測試
@patch('src.platforms.discord_handler.DISCORD_AVAILABLE', False)
def test_initialization_without_sdk():
    handler = DiscordHandler(config)
    assert handler.bot is None

# 2. Mock 外部依賴
def test_parse_message():
    with patch.object(handler, 'parse_message', return_value=expected_result):
        result = handler.parse_message(mock_message)
        assert result.content == "Expected content"

# 3. 異步操作測試
async def test_async_download():
    result = await handler._download_audio(mock_audio_source)
    assert result == b'fake_audio_data'
```

## 🚀 **測試執行流程**

### **CI/CD 整合**
```bash
# 階段 1: 快速單元測試
pytest tests/unit/ -m "not slow" --maxfail=5

# 階段 2: 平台測試
pytest tests/unit/platforms/ --cov=src/platforms

# 階段 3: 整合測試
pytest tests/integration/ -m integration

# 階段 4: API 測試
pytest tests/api/
```

### **本地開發**
```bash
# 開發時快速測試
pytest tests/unit/platforms/test_line_handler.py -v

# 完整測試套件
python -m pytest --cov=src --cov-report=term-missing

# 特定標記測試
pytest -m "not slow and not external"
```

## 📊 **測試品質指標**

### **當前覆蓋率**
| 模組 | 測試數量 | 覆蓋率 | 狀態 |
|------|----------|--------|------|
| platforms/ | 258 | 78-90% | ✅ 優秀 |
| core/ | 50+ | 60%+ | 🔄 改善中 |
| models/ | 30+ | 目標75% | 🔄 開發中 |
| services/ | 20+ | 目標80% | 🔄 開發中 |

### **品質標準**
- ✅ **單元測試**: 新代碼必須有對應測試
- ✅ **覆蓋率**: 新模組最低 75% 覆蓋率
- ✅ **平台測試**: 所有平台 handler 必須通過測試
- ✅ **回歸測試**: 修改後必須執行完整測試套件

## 🔄 **持續改善**

### **近期完成**
- ✅ 平台處理器測試全面強化 (258 tests passing)
- ✅ Discord 覆蓋率從 69% 提升到 78%
- ✅ Telegram 覆蓋率從 61% 提升到 82%
- ✅ 修復所有 SDK 導入和遞迴錯誤
- ✅ 建立統一的測試目錄結構

### **下一階段目標**
- 🔄 Core 模組測試增強 (security, logger, config)
- 🔄 AI 模型測試完善 (所有提供者)
- 🔄 服務層測試擴展 (chat, audio, conversation)
- 🔄 API 端點測試更新 (新架構適配)

### **長期目標**
- 📋 整體覆蓋率達到 85%+
- 📋 自動化性能測試
- 📋 端到端 (E2E) 測試框架
- 📋 測試數據生成和管理

## 🛠️ **開發指南**

### **編寫新測試**
1. **遵循命名規範**: `test_<功能>_<情況>.py`
2. **使用適當的 fixtures**: 從 `conftest.py` 取得標準配置
3. **Mock 外部依賴**: 避免實際 API 呼叫
4. **測試邊界情況**: 包含錯誤處理和異常情況
5. **添加描述性斷言**: 清楚表達期望結果

### **測試最佳實踐**
```python
class TestPlatformHandler:
    """平台處理器測試類別"""
    
    def setup_method(self):
        """每個測試前的設置"""
        self.config = {...}
    
    def test_functionality_success(self):
        """測試正常功能"""
        # Arrange
        handler = PlatformHandler(self.config)
        
        # Act  
        result = handler.process_message(test_data)
        
        # Assert
        assert result.status == "success"
        assert result.content == "expected_content"
    
    def test_functionality_failure(self):
        """測試錯誤處理"""
        # Test edge cases and error conditions
```

這個測試架構確保了系統的可靠性、可維護性和擴展性，為多平台聊天機器人提供了堅實的品質保證基礎。