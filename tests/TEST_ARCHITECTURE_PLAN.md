# 測試架構重構計劃

## 📋 **當前問題分析**

1. **架構不匹配**: 現有測試基於舊的 main.py 架構，需要適配新的多平台架構
2. **導入路徑過時**: 測試中的導入路徑和 mock 對象需要更新
3. **配置格式變更**: 測試配置需要從舊格式遷移到新的多平台格式
4. **測試覆蓋不足**: 缺少對新平台架構特性的測試

## 🎯 **新測試架構設計**

### **測試組織結構**

```
tests/
├── conftest.py                 # 全域測試配置和 fixtures
├── test_main.py                # 主應用程式測試 (新增)
├── unit/                       # 單元測試
│   ├── __init__.py
│   ├── test_config.py          # 配置系統測試
│   ├── test_models/            # AI 模型測試
│   │   ├── __init__.py
│   │   ├── test_openai_model.py
│   │   ├── test_anthropic_model.py
│   │   ├── test_gemini_model.py
│   │   ├── test_ollama_model.py
│   │   └── test_model_factory.py
│   ├── test_platforms/         # 平台處理器測試
│   │   ├── __init__.py
│   │   ├── test_line_handler.py
│   │   ├── test_platform_factory.py
│   │   └── test_platform_manager.py
│   ├── test_services/          # 服務層測試
│   │   ├── __init__.py
│   │   ├── test_core_chat_service.py
│   │   ├── test_response_formatter.py
│   │   └── test_conversation_manager.py
│   ├── test_database/          # 資料庫相關測試
│   │   ├── __init__.py
│   │   ├── test_database_orm.py
│   │   └── test_migrations.py
│   └── test_utils/             # 工具函數測試
│       ├── __init__.py
│       └── test_text_processing.py
├── integration/                # 整合測試
│   ├── __init__.py
│   ├── test_app_initialization.py  # 應用程式初始化測試
│   ├── test_platform_integration.py
│   ├── test_chat_flow.py
│   └── test_database_integration.py
├── api/                        # API 端點測試
│   ├── __init__.py
│   ├── test_health_endpoints.py   # 健康檢查和指標
│   ├── test_webhook_endpoints.py  # Webhook 處理
│   └── test_legacy_compatibility.py # 向後兼容性測試
└── mocks/                      # Mock 和測試工具
    ├── __init__.py
    ├── mock_config.py          # 標準測試配置
    ├── mock_models.py          # AI 模型 mocks
    ├── mock_platforms.py       # 平台處理器 mocks
    └── test_external_services.py
```

### **測試分類和標記**

```python
@pytest.mark.unit          # 單元測試
@pytest.mark.integration   # 整合測試
@pytest.mark.api          # API 測試
@pytest.mark.slow         # 慢速測試
@pytest.mark.database     # 需要資料庫的測試
@pytest.mark.external     # 需要外部服務的測試
@pytest.mark.legacy       # 舊架構兼容性測試
@pytest.mark.platform     # 平台特定測試
```

## 🔄 **遷移策略**

### **階段 1: 基礎設施更新**
1. ✅ 更新 `conftest.py` - 新的配置格式和 fixtures
2. ✅ 創建 `test_main.py` - 測試新的統一入口點
3. ✅ 更新 mock 配置到新的多平台格式

### **階段 2: 核心組件測試更新** 
1. 🔄 重構平台相關測試 (`test_platforms/`)
2. 🔄 更新 AI 模型測試 (`test_models/`)
3. 🔄 更新服務層測試 (`test_services/`)

### **階段 3: API 和整合測試**
1. 🔄 重寫 API 端點測試
2. 🔄 更新整合測試
3. 🔄 添加向後兼容性測試

### **階段 4: 驗證和清理**
1. ⏳ 運行完整測試套件
2. ⏳ 修復失敗的測試
3. ⏳ 清理過時的測試文件

## 📝 **重要更新項目**

### **配置格式更新**
```python
# 舊格式
config = {
    'line': {'channel_access_token': '...', 'channel_secret': '...'},
    'openai': {'api_key': '...', 'assistant_id': '...'}
}

# 新格式
config = {
    'platforms': {
        'line': {'enabled': True, 'channel_access_token': '...', 'channel_secret': '...'}
    },
    'llm': {'provider': 'openai'},
    'openai': {'api_key': '...', 'assistant_id': '...'}
}
```

### **導入路徑更新**
```python
# 舊導入
from main import app
from src.services.chat_service import ChatService

# 新導入  
from main import create_app, application
from src.services.core_chat_service import ChatService
```

### **測試客戶端更新**
```python
# 舊方式
app.config['TESTING'] = True
client = app.test_client()

# 新方式
app = create_app()
app.config['TESTING'] = True
client = app.test_client()
```

## 🎯 **測試重點**

### **新架構特性測試**
1. **多平台支援**: 測試 LINE、Discord、Telegram 平台處理
2. **環境自動切換**: 測試開發/生產環境自動檢測
3. **統一 webhook 處理**: 測試 `/webhooks/<platform>` 路由
4. **平台工廠模式**: 測試平台處理器的創建和註冊
5. **健康檢查增強**: 測試新的健康檢查格式和平台狀態

### **向後兼容性測試**
1. **舊端點支援**: 測試 `/callback` 端點仍然可用
2. **WSGI 應用**: 測試從 `wsgi.py` 和 `main.py` 導入都正常
3. **配置兼容**: 測試舊配置格式的處理（如果有的話）

### **穩定性測試**
1. **錯誤處理**: 測試各種錯誤情況下的回應
2. **並發處理**: 測試多平台 webhook 的並發處理
3. **資源管理**: 測試資料庫連接池和模型實例管理

## 📋 **實作檢查清單**

- [ ] 更新 `conftest.py` 配置格式
- [ ] 創建 `test_main.py` 主應用程式測試
- [ ] 重構 API 端點測試
- [ ] 更新平台處理器測試
- [ ] 更新 AI 模型測試  
- [ ] 更新服務層測試
- [ ] 添加新架構整合測試
- [ ] 創建向後兼容性測試
- [ ] 驗證所有測試通過
- [ ] 清理過時測試文件