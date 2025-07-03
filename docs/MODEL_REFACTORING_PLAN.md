# 多模型重構計畫

> **更新時間**: 2024-07-02  
> **狀態**: 規劃階段  
> **目標**: 將現有的多個語言模型重構為統一接口，同時保持各模型的特色功能

## 📊 目錄

- [重構背景](#重構背景)
- [現狀分析](#現狀分析)
- [API Best Practices 研究](#api-best-practices-研究)
- [重構策略](#重構策略)
- [實作計畫](#實作計畫)
- [技術規格](#技術規格)
- [測試策略](#測試策略)
- [風險評估](#風險評估)

---

## 重構背景

### 🎯 重構目標

1. **統一接口**: 所有模型提供相同的功能接口
2. **保持特色**: 每個模型發揮自己的優勢和特性  
3. **完整功能**: 音訊轉錄、RAG、對話管理等完整支援
4. **可擴展性**: 易於添加新的語言模型
5. **向後相容**: 不破壞現有的 OpenAI Assistant API 實作

### 📋 成功標準

- [ ] 三個模型 (Claude, Gemini, Ollama) 都實作統一接口
- [ ] 所有模型都支援 RAG 功能
- [ ] 所有模型都支援音訊轉錄
- [ ] 測試覆蓋率維持在 80% 以上
- [ ] 現有 OpenAI Assistant API 功能正常運作

---

## 現狀分析

### 🔍 模型現狀對比

| 功能模組 | OpenAI | Anthropic Claude | Google Gemini | Ollama |
|---------|--------|------------------|---------------|--------|
| **基礎聊天** | ✅ 完整 | ✅ 基本實作 | ✅ 基本實作 | ✅ 基本實作 |
| **RAG 功能** | ✅ Assistant API | ❌ 簡單記憶體庫 | ❌ 未完整實作 | ❌ 未完整實作 |
| **音訊轉錄** | ✅ Whisper API | ❌ 缺失 | ❌ 缺失 | ❌ 缺失 |
| **檔案管理** | ✅ Files API | ❌ 基本實作 | ❌ 基本實作 | ❌ 基本實作 |
| **對話串管理** | ✅ Threads API | ❌ 缺失 | ❌ 缺失 | ❌ 缺失 |
| **錯誤處理** | ✅ 完整 | ⚠️ 基本 | ⚠️ 基本 | ⚠️ 基本 |

### 🏗️ 現有架構評估

**優勢**:
- 已有完整的統一接口定義 (`base.py`)
- OpenAI 實作成熟，可作為參考
- 模型工廠模式已建立

**問題**:
- 其他模型實作不完整
- 缺乏統一的錯誤處理
- RAG 實作各自為政
- 音訊功能只有 OpenAI 支援

---

## API Best Practices 研究

### 🤖 Anthropic Claude (2024)

**核心能力**:
- **Files API**: 持久化文件管理，支援跨對話引用
- **Extended Prompt Caching**: 最長1小時的提示快取，降低成本
- **MCP 連接器**: 模型上下文協議，整合外部工具
- **代碼執行工具**: 內建資料分析和程式碼執行能力
- **Agent 模式**: 增強的代理人能力

**RAG 最佳實踐**:
```python
# Claude RAG 實作重點
- 使用 Files API 作為知識庫
- 利用 Extended Prompt Caching 維持對話上下文
- MCP 連接器整合外部資料源
- 系統提示詞優化指導 RAG 行為
```

**系統設計原則**:
- 結構化系統提示詞定義角色和能力
- 使用 "As mentioned earlier" 等語句建立對話連貫性
- 批量處理相關任務以減少 API 調用
- 讀取超時設定至少60分鐘

### 🔍 Google Gemini (2024)

**核心能力**:
- **Semantic Retrieval API**: Google 的語義檢索服務
- **Multimodal RAG**: 支援文字、圖片、影片的混合檢索
- **Long Context Window**: Gemini Pro 1.5 支援百萬 token 上下文
- **Vertex AI 整合**: 企業級 AI 平台整合
- **Ranking API**: 智能重排序提升檢索品質

**RAG 最佳實踐**:
```python
# Gemini RAG 實作重點
- 使用 Vertex AI Embeddings API 生成向量
- 整合 Vector Search 和 Ranking API
- 支援混合搜尋 (語義 + 關鍵字)
- Multimodal embeddings 處理多媒體內容
- 重排序 API 提升相關性
```

**技術特色**:
- 1408維多模態向量空間
- 語義和關鍵字混合搜尋
- 會話記憶和上下文保持
- 效能評估指標 (RAGAS, Tonic Validate)

### 🏠 Ollama 本地模型 (2024)

**核心能力**:
- **完全本地化**: 資料不出本地環境，隱私保護
- **多模型支援**: llama3.1, mistral, codellama 等
- **本地向量資料庫**: ChromaDB, Weaviate, PostgreSQL+pgvector
- **本地 Embedding**: nomic-embed-text, mxbai-embed-large
- **硬體優化**: GPU 加速，高效能運算

**RAG 最佳實踐**:
```python
# Ollama RAG 實作重點
- 本地向量資料庫 (ChromaDB/Weaviate)
- 本地 embedding 模型
- 文件分塊和語義搜尋
- 本地 Whisper 語音轉錄
- Docker 容器化部署
```

**架構優勢**:
- 零網路依賴，完全離線運行
- 敏感資料保護
- 自定義模型訓練
- 成本控制 (無 API 費用)

---

## 重構策略

### 🎯 新架構設計理念

**核心原則**：讓每個模型使用自己最適合的對話管理方式，避免強制統一不存在的功能。

#### 📋 模型對話管理 + RAG 能力分析

| 模型 | Thread 支援 | 對話策略 | RAG 特色 | 實作重點 |
|------|-------------|----------|----------|----------|
| **OpenAI** | ✅ Assistant API | 原生 Thread | Files API + 引用 | Thread + RAG 整合 |
| **Claude** | ❌ 簡單歷史 | 最近 N 輪對話 | Files API + 快取 | Extended Caching + RAG |
| **Gemini** | ❌ 簡單歷史 | 長上下文 (1M tokens) | Semantic Retrieval | 多模態 RAG |
| **Ollama** | ❌ 簡單歷史 | 本地快取 | 本地向量庫 | 本地 RAG + 隱私保護 |

### 🔄 簡化統一接口設計

**核心思路**：各模型專注於自己的 RAG 特色，簡單的對話歷史管理 + 強大的 RAG 功能

```python
class FullLLMInterface:
    # 基礎功能
    def check_connection(self) -> Tuple[bool, Optional[str]]
    def chat_completion(self, messages: List[ChatMessage], **kwargs) -> Tuple[bool, Optional[ChatResponse], Optional[str]]
    
    # 🆕 用戶級對話 + RAG（主要接口）
    def chat_with_user(self, user_id: str, message: str, **kwargs) -> Tuple[bool, Optional[RAGResponse], Optional[str]]
    def clear_user_history(self, user_id: str) -> Tuple[bool, Optional[str]]
    
    # RAG 知識管理
    def upload_knowledge_file(self, file_path: str, **kwargs) -> Tuple[bool, Optional[FileInfo], Optional[str]]
    def get_knowledge_files(self) -> Tuple[bool, Optional[List[FileInfo]], Optional[str]]
    def get_file_references(self) -> Dict[str, str]
    
    # 音訊處理
    def transcribe_audio(self, audio_file_path: str, **kwargs) -> Tuple[bool, Optional[str], Optional[str]]
```

### 🗄️ 簡化資料庫設計

```sql
-- 簡單對話歷史表（僅用於非 OpenAI 模型）
CREATE TABLE simple_conversation_history (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    model_provider VARCHAR(50) NOT NULL,  -- 'anthropic', 'gemini', 'ollama'
    role VARCHAR(20) NOT NULL,             -- 'user', 'assistant'
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_user_model_recent (user_id, model_provider, created_at DESC)
);

-- 保留原有的 OpenAI thread 表
-- user_thread_table 繼續用於 OpenAI Assistant API
```

### 🎯 各模型對話歷史策略

#### OpenAI 模型
- **策略**：繼續使用 Assistant API 的原生 Thread 功能
- **實作**：`user_id` → `thread_id` 映射，完整的對話串管理

#### 非 OpenAI 模型 (Claude, Gemini, Ollama)
- **策略**：簡單的「最近 N 輪對話」記憶
- **實作**：每次對話時帶入最近 3-5 輪的對話歷史作為上下文
- **清理**：定期清理超過 30 天的對話記錄

### 🔧 各模型特化實作重點

#### Anthropic Claude - Extended Caching + Files API

```python
class AnthropicModel(FullLLMInterface):
    """
    Claude 2024 特化實作：Extended Prompt Caching + Files API RAG
    """
    
    def chat_with_user(self, user_id: str, message: str, **kwargs):
        """主要接口：簡單對話歷史 + Files API RAG"""
        # 1. 取得最近 3-5 輪對話歷史
        recent_history = self._get_recent_conversations(user_id, limit=5)
        
        # 2. 結合對話歷史 + RAG 知識 + Extended Caching
        system_prompt = self._build_cached_system_prompt()
        
        # 3. 使用 Files API 進行 RAG 查詢
        # 4. 儲存對話結果
        # 5. 回傳 RAG 結果
    
    def upload_knowledge_file(self, file_path: str, **kwargs):
        """Files API 檔案上傳 + 快取管理"""
    
    def _build_cached_system_prompt(self):
        """利用 Extended Prompt Caching 優化成本"""
```

#### Google Gemini - Semantic Retrieval + 長上下文

```python
class GeminiModel(FullLLMInterface):
    """
    Gemini 2024 特化實作：Semantic Retrieval + 1M Token 長上下文
    """
    
    def chat_with_user(self, user_id: str, message: str, **kwargs):
        """主要接口：長上下文對話歷史 + Semantic Retrieval RAG"""
        # 1. 利用 1M token 上下文，取得較多對話歷史
        long_history = self._get_recent_conversations(user_id, limit=20)
        
        # 2. 使用 Semantic Retrieval API 進行語義檢索
        # 3. 結合 Ranking API 重排序結果
        # 4. 多模態內容處理
    
    def upload_knowledge_file(self, file_path: str, **kwargs):
        """Semantic Retrieval 語料庫管理 + 多模態支援"""
    
    def _create_corpus(self, corpus_name: str):
        """建立語料庫"""
    
    def _multimodal_rag_query(self, query: str):
        """多模態 RAG 查詢"""
```

#### Ollama - 本地 RAG + 隱私保護

```python
class OllamaModel(FullLLMInterface):
    """
    Ollama 2024 特化實作：本地向量 RAG + 完全隱私保護
    """
    
    def chat_with_user(self, user_id: str, message: str, **kwargs):
        """主要接口：本地對話歷史 + 本地向量 RAG"""
        # 1. 本地快取對話歷史
        # 2. 本地向量資料庫檢索
        # 3. 本地 LLM 生成，完全不出網路
    
    def upload_knowledge_file(self, file_path: str, **kwargs):
        """本地檔案向量化 + ChromaDB 儲存"""
    
    def _local_vector_search(self, query: str):
        """本地向量相似度搜尋"""
    
    def _local_embedding(self, text: str):
        """本地 Embedding 模型"""
```

---

## 實作計畫

### 📅 Phase 0: 基礎架構重構 (預計1天)

**優先順序**: 最高 (基礎設施)

**實作清單**:
1. **資料庫設計**
   - [ ] 創建 `simple_conversation_history` 表
   - [ ] 資料庫遷移腳本
   - [ ] 索引優化

2. **基礎接口更新**
   - [ ] 更新 `base.py` 統一接口
   - [ ] 新增 `chat_with_user` 方法
   - [ ] 移除不必要的 thread 相關方法

3. **ChatService 簡化**
   - [ ] 調整為使用 `chat_with_user` 接口
   - [ ] 移除複雜的 thread 管理邏輯

### 📅 Phase 1: Anthropic Claude 重構 (預計1-2天)

**優先順序**: 最高 (已有基礎)

**實作清單**:
1. **簡單對話歷史管理**
   - [ ] 實作 `_get_recent_conversations` 方法
   - [ ] 對話歷史的存儲和檢索
   - [ ] 定期清理機制

2. **Enhanced Files API RAG**
   - [ ] 改進現有 Files API 實作
   - [ ] Extended Prompt Caching 優化
   - [ ] 成本控制邏輯

3. **主要接口實作**
   - [ ] `chat_with_user` 方法實作
   - [ ] 對話歷史 + RAG 整合
   - [ ] 第三方語音轉錄 (Deepgram/AssemblyAI)

4. **測試更新**
   - [ ] 更新現有測試
   - [ ] 新增對話歷史管理測試
   - [ ] 整合測試驗證

### 📅 Phase 2: Google Gemini 重構 (預計2-3天)

**優先順序**: 中高 (Semantic Retrieval 特色)

**實作清單**:
1. **長上下文對話管理**
   - [ ] 利用 1M token 上下文優勢
   - [ ] 較長的對話歷史管理
   - [ ] 記憶體和性能優化

2. **Semantic Retrieval API 強化**
   - [ ] 語料庫管理優化
   - [ ] 多模態檔案支援
   - [ ] Ranking API 整合

3. **主要接口實作**
   - [ ] `chat_with_user` 方法實作
   - [ ] 長上下文 + Semantic RAG
   - [ ] Google Speech-to-Text 整合

4. **多模態 RAG**
   - [ ] 圖片、影片檔案處理
   - [ ] 跨模態檢索優化
   - [ ] 多模態回應生成

### 📅 Phase 3: Ollama 本地模型重構 (預計2-3天)

**優先順序**: 中 (隱私保護特色)

**實作清單**:
1. **本地對話歷史管理**
   - [ ] 本地快取實作
   - [ ] 隱私保護的對話存儲
   - [ ] 本地資料清理

2. **本地 RAG 系統**
   - [ ] ChromaDB 本地向量庫
   - [ ] 本地 Embedding 模型
   - [ ] 向量相似度搜尋

3. **主要接口實作**
   - [ ] `chat_with_user` 方法實作
   - [ ] 本地對話 + 本地 RAG
   - [ ] 本地 Whisper 轉錄

4. **隱私和性能優化**
   - [ ] 完全本地化驗證
   - [ ] 資源使用優化
   - [ ] Docker 部署支援

---

## 技術規格

### 🔧 依賴套件更新

```python
# requirements.txt 新增依賴
anthropic>=0.8.0          # Claude API
google-cloud-aiplatform    # Vertex AI
chromadb>=0.4.0           # 本地向量資料庫
sentence-transformers     # 本地 embedding
openai-whisper           # 本地語音轉錄
deepgram-sdk             # 語音轉錄服務
assemblyai               # 語音轉錄服務備選
```

### 📁 檔案結構規劃

```
src/models/
├── base.py                    # 統一接口定義
├── openai_model.py           # OpenAI 實作 (已完成)
├── anthropic_model.py        # Claude 重構版本
├── gemini_model.py           # Gemini 重構版本
├── ollama_model.py           # Ollama 重構版本
└── factory.py               # 模型工廠

src/services/
├── response_formatter.py     # 統一回應格式化 (已完成)
├── audio_service.py          # 統一音訊服務 (已完成)
├── chat_service.py           # 統一聊天服務 (已完成)
└── rag_service.py            # RAG 服務抽象層 (新增)

src/integrations/             # 新增：第三方整合
├── vector_databases/         # 向量資料庫整合
│   ├── chromadb_client.py
│   └── weaviate_client.py
├── speech_services/          # 語音服務整合
│   ├── deepgram_client.py
│   └── google_speech_client.py
└── embeddings/              # Embedding 服務
    ├── local_embeddings.py
    └── vertex_embeddings.py

tests/unit/
├── test_anthropic_model.py   # Claude 測試
├── test_gemini_model.py      # Gemini 測試
├── test_ollama_model.py      # Ollama 測試
└── test_integrations/        # 整合測試

docs/
├── MODEL_REFACTORING_PLAN.md # 本文檔
├── API_USAGE_EXAMPLES.md     # API 使用範例
└── DEPLOYMENT_GUIDE.md       # 部署指南
```

### ⚙️ 配置檔案更新

```yaml
# config/config.yml 範例
models:
  default_provider: "openai"  # openai, anthropic, gemini, ollama
  
  openai:
    api_key: "${OPENAI_API_KEY}"
    assistant_id: "${OPENAI_ASSISTANT_ID}"
    
  anthropic:
    api_key: "${ANTHROPIC_API_KEY}"
    model: "claude-3-5-sonnet-20241022"
    max_tokens: 4000
    enable_caching: true
    cache_ttl: 3600  # 1 hour
    
  gemini:
    api_key: "${GEMINI_API_KEY}"
    model: "gemini-pro-1.5"
    project_id: "${GOOGLE_CLOUD_PROJECT}"
    corpus_name: "chatbot-knowledge"
    
  ollama:
    base_url: "http://localhost:11434"
    model: "llama3.1:8b"
    embedding_model: "nomic-embed-text"
    whisper_model: "whisper"
    vector_db:
      type: "chromadb"  # chromadb, weaviate
      path: "./data/vectordb"

# 語音轉錄配置
audio:
  default_provider: "model_specific"  # model_specific, deepgram, google
  deepgram:
    api_key: "${DEEPGRAM_API_KEY}"
  google_speech:
    credentials_path: "${GOOGLE_CREDENTIALS_PATH}"
```

---

## 測試策略

### 🧪 測試層級

1. **單元測試** (各模型獨立測試)
   - API 連線測試
   - 功能接口測試
   - 錯誤處理測試
   - Mock 外部服務

2. **整合測試** (跨模組測試)
   - 模型切換測試
   - RAG 端到端測試
   - 音訊轉錄測試
   - 檔案上傳測試

3. **效能測試** (負載和延遲)
   - 並發請求測試
   - 大檔案處理測試
   - 記憶體使用測試
   - 回應時間測試

### 📊 測試覆蓋率目標

- **最低要求**: 80% 程式碼覆蓋率
- **核心功能**: 95% 覆蓋率 (chat_completion, query_with_rag, transcribe_audio)
- **邊界情況**: 完整的錯誤處理測試
- **整合測試**: 所有模型的相同行為驗證

### 🔍 測試檢查清單

- [ ] 所有模型都通過相同的接口測試套件
- [ ] RAG 功能在所有模型上正常運作
- [ ] 音訊轉錄在所有模型上正常運作
- [ ] 檔案上傳和管理功能正常
- [ ] 錯誤處理一致且健全
- [ ] 效能滿足預期指標
- [ ] 記憶體洩漏檢查
- [ ] 並發安全性驗證

---

## 風險評估

### ⚠️ 技術風險

| 風險項目 | 機率 | 影響 | 緩解策略 |
|---------|------|------|----------|
| **第三方 API 變更** | 中 | 高 | 版本鎖定、向後相容設計 |
| **向量資料庫效能** | 中 | 中 | 效能測試、索引優化 |
| **本地模型資源消耗** | 高 | 中 | 資源監控、配置優化 |
| **語音轉錄精度** | 中 | 中 | 多服務備選、品質測試 |
| **快取一致性** | 低 | 高 | 快取策略設計、測試驗證 |

### 💰 成本風險

| 項目 | Claude | Gemini | Ollama |
|------|--------|--------|--------|
| **API 費用** | 中高 | 中 | 無 |
| **存儲費用** | 低 | 中 | 本地 |
| **計算資源** | 無 | 低 | 高 |
| **維護成本** | 低 | 中 | 高 |

### 🛡️ 安全風險

- **資料隱私**: Ollama 最安全 > Claude > Gemini
- **API 金鑰管理**: 統一加密存儲
- **資料傳輸**: HTTPS + API 金鑰驗證
- **本地存儲**: 檔案系統權限控制

---

## 成功指標

### 📈 量化指標

1. **功能完整性**
   - [ ] 3個模型 × 8個核心功能 = 24個功能點全部實作
   - [ ] 統一接口 100% 相容
   - [ ] 測試覆蓋率 ≥ 80%

2. **效能指標**
   - [ ] 回應時間 < 5秒 (95th percentile)
   - [ ] 音訊轉錄準確率 > 95%
   - [ ] RAG 檢索相關性 > 90%

3. **可靠性指標**
   - [ ] API 可用性 > 99.9%
   - [ ] 錯誤率 < 1%
   - [ ] 記憶體洩漏 = 0

### 🎯 質化指標

- [ ] 開發者體驗：模型切換只需修改配置
- [ ] 用戶體驗：功能一致性，無感知切換
- [ ] 維護性：程式碼結構清晰，易於擴展
- [ ] 文檔完整：API 使用指南和範例齊全

---

## 下一步行動

### 🚀 立即行動

1. **確認重構順序**：確認從 Claude 開始的優先順序
2. **環境準備**：申請 Claude, Gemini API 金鑰
3. **依賴安裝**：更新 requirements.txt
4. **分支策略**：建立 feature/model-refactoring 分支

### 📋 檢查清單

- [ ] 專案負責人確認重構計畫
- [ ] 申請必要的 API 金鑰和配額
- [ ] 準備測試資料和環境
- [ ] 建立專用分支開始開發
- [ ] 設定 CI/CD 管道適配新架構

---

**文檔版本**: v1.0  
**最後更新**: 2024-07-02  
**維護人員**: Claude Code Assistant

> 此文檔將隨著重構進度持續更新，記錄實作細節和遇到的問題解決方案。