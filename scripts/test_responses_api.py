#!/usr/bin/env python3
"""
測試 OpenAI Responses API + Conversations API
驗證從 Assistant API 遷移到 Responses API 的可行性

Usage:
    python scripts/test_responses_api.py
"""

import sys
import os
import yaml
import json
import time

# 確保專案根目錄在 path 中
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(project_root)

from openai import OpenAI


def load_configs():
    """讀取 config.yml 和 prompts.yml"""
    with open("config/config.yml", "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    with open("config/prompts.yml", "r", encoding="utf-8") as f:
        prompts = yaml.safe_load(f)

    return config, prompts


def create_client(config):
    """建立 OpenAI client"""
    openai_config = config["openai"]
    kwargs = {
        "api_key": openai_config["api_key"],
    }
    base_url = openai_config.get("base_url")
    if base_url:
        kwargs["base_url"] = base_url
    return OpenAI(**kwargs)


def get_model_params(config):
    """取得模型參數"""
    openai_config = config["openai"]
    params = {
        "model": openai_config.get("model", "gpt-5"),
        "max_output_tokens": openai_config.get("max_output_tokens", 8000),
    }
    # reasoning effort (gpt-5 以上)
    reasoning_effort = openai_config.get("reasoning_effort")
    if reasoning_effort:
        params["reasoning"] = {"effort": reasoning_effort}
    # temperature — gpt-5 + reasoning 時不支援 temperature，跳過
    if not reasoning_effort:
        params["temperature"] = openai_config.get("temperature", 0.1)
    return params


# ============================================================
# 測試函式
# ============================================================

def test_basic_response(client, config, prompts):
    """測試 1: 基本 responses.create() 呼叫"""
    print("\n" + "=" * 60)
    print("TEST 1: Basic Response (responses.create)")
    print("=" * 60)

    model_params = get_model_params(config)
    system_prompt = prompts.get("system_prompt", "You are a helpful assistant.")

    try:
        response = client.responses.create(
            instructions=system_prompt,
            input="請用一句話介紹你自己",
            **model_params,
        )
        print(f"  Response ID: {response.id}")
        print(f"  Status: {response.status}")
        print(f"  Output text: {response.output_text[:200]}...")
        if response.usage:
            print(f"  Usage: input={response.usage.input_tokens}, output={response.usage.output_tokens}")
        print("  [PASS]")
        return True, response
    except Exception as e:
        print(f"  [FAIL] {e}")
        return False, None


def test_file_search(client, config, prompts):
    """測試 2: file_search 工具 + vector_store_id"""
    print("\n" + "=" * 60)
    print("TEST 2: File Search (file_search + vector_store)")
    print("=" * 60)

    vector_store_id = config["openai"].get("vector_store_id")
    if not vector_store_id:
        print("  [SKIP] No vector_store_id configured")
        return False, None

    model_params = get_model_params(config)
    system_prompt = prompts.get("system_prompt", "You are a helpful assistant.")

    try:
        response = client.responses.create(
            instructions=system_prompt,
            input="請問台南市議會第四屆有哪些議員討論過交通議題？",
            tools=[{
                "type": "file_search",
                "vector_store_ids": [vector_store_id],
            }],
            include=["file_search_call.results"],
            **model_params,
        )
        print(f"  Response ID: {response.id}")
        print(f"  Status: {response.status}")
        print(f"  Output text (前200字): {response.output_text[:200]}...")
        print(f"  Output items count: {len(response.output)}")

        # 列出 output 中各 item 的 type
        for i, item in enumerate(response.output):
            print(f"  Output[{i}] type={item.type}", end="")
            if item.type == "file_search_call":
                print(f", queries={getattr(item, 'queries', None)}, status={getattr(item, 'status', None)}")
                # 印出 search_results 摘要
                results = getattr(item, "results", None) or getattr(item, "search_results", None)
                if results:
                    print(f"    search_results count: {len(results)}")
                    for j, r in enumerate(results[:3]):
                        print(f"    result[{j}]: file_id={getattr(r, 'file_id', 'N/A')}, filename={getattr(r, 'filename', 'N/A')}, score={getattr(r, 'score', 'N/A')}")
                else:
                    print("    search_results: None (use include param to get results)")
            else:
                print()

        print("  [PASS]")
        return True, response
    except Exception as e:
        print(f"  [FAIL] {e}")
        import traceback
        traceback.print_exc()
        return False, None


def test_citation_format(client, config, prompts, file_search_response=None):
    """測試 3: 引用 / annotation 格式比較"""
    print("\n" + "=" * 60)
    print("TEST 3: Citation / Annotation Format")
    print("=" * 60)

    if not file_search_response:
        print("  [SKIP] No file_search response to analyze")
        return False

    try:
        # 找出 message 類型的 output
        for item in file_search_response.output:
            if item.type == "message":
                for content_part in item.content:
                    if content_part.type == "output_text":
                        text = content_part.text
                        annotations = content_part.annotations
                        print(f"  Text length: {len(text)}")
                        print(f"  Annotations count: {len(annotations)}")

                        print("\n  --- Responses API Annotation Format ---")
                        for i, ann in enumerate(annotations[:5]):
                            print(f"  annotation[{i}]:")
                            print(f"    type: {ann.type}")
                            print(f"    index: {getattr(ann, 'index', 'N/A')}")
                            print(f"    file_id: {getattr(ann, 'file_id', 'N/A')}")
                            print(f"    filename: {getattr(ann, 'filename', 'N/A')}")

                        print("\n  --- 與 Assistant API 格式對照 ---")
                        print("  Assistant API:  annotation['text'] = '【4:0†source】'")
                        print("                  annotation['file_citation']['file_id'] = 'file-xxx'")
                        print("                  annotation['file_citation']['quote'] = '...'")
                        print("                  (需要另外查詢 filename)")
                        print("  Responses API:  annotation.type = 'file_citation'")
                        print("                  annotation.index = 992  (文字位置)")
                        print("                  annotation.file_id = 'file-xxx'")
                        print("                  annotation.filename = 'xxx.pdf'  (直接提供!)")
                        print("                  (不再有 text 標記，改用 index)")

                        # 檢查文本中的引用標記格式
                        import re
                        old_style = re.findall(r'【[^】]+】', text)
                        new_style = re.findall(r'\[\d+\]', text)
                        print(f"\n  Text citation markers:")
                        print(f"    Old style 【...】: {len(old_style)} found")
                        if old_style[:3]:
                            print(f"      samples: {old_style[:3]}")
                        print(f"    New style [...]: {len(new_style)} found")
                        if new_style[:3]:
                            print(f"      samples: {new_style[:3]}")

                        print("  [PASS]")
                        return True

        print("  [FAIL] No message output found")
        return False
    except Exception as e:
        print(f"  [FAIL] {e}")
        import traceback
        traceback.print_exc()
        return False


def test_conversation_create(client, config):
    """測試 4: conversations.create()"""
    print("\n" + "=" * 60)
    print("TEST 4: Conversation Create")
    print("=" * 60)

    try:
        conversation = client.conversations.create()
        print(f"  Conversation ID: {conversation.id}")
        print(f"  Created at: {getattr(conversation, 'created_at', 'N/A')}")
        print(f"  Object type: {getattr(conversation, 'object', 'N/A')}")
        print(f"  Full object: {conversation}")
        print("  [PASS]")
        return True, conversation
    except Exception as e:
        print(f"  [FAIL] {e}")
        import traceback
        traceback.print_exc()
        return False, None


def test_conversation_multi_turn(client, config, prompts, conversation_id):
    """測試 5: 用 conversation ID 進行多輪對話"""
    print("\n" + "=" * 60)
    print("TEST 5: Conversation Multi-Turn")
    print("=" * 60)

    if not conversation_id:
        print("  [SKIP] No conversation_id")
        return False, None, None

    model_params = get_model_params(config)
    system_prompt = prompts.get("system_prompt", "You are a helpful assistant.")

    try:
        # Turn 1
        print("  --- Turn 1 ---")
        r1 = client.responses.create(
            instructions=system_prompt,
            input="我叫小明，請記住我的名字",
            conversation=conversation_id,
            store=True,
            **model_params,
        )
        print(f"  Response 1 ID: {r1.id}")
        print(f"  Output: {r1.output_text[:200]}")

        # Turn 2 — 驗證上下文保持
        print("\n  --- Turn 2 ---")
        r2 = client.responses.create(
            instructions=system_prompt,
            input="請問我叫什麼名字？",
            conversation=conversation_id,
            store=True,
            **model_params,
        )
        print(f"  Response 2 ID: {r2.id}")
        print(f"  Output: {r2.output_text[:200]}")

        # 驗證是否記住了名字
        if "小明" in r2.output_text:
            print("\n  Context preserved: YES (名字被記住了)")
        else:
            print("\n  Context preserved: UNCERTAIN (回應中未包含「小明」)")

        print("  [PASS]")
        return True, r1, r2
    except Exception as e:
        print(f"  [FAIL] {e}")
        import traceback
        traceback.print_exc()
        return False, None, None


def test_conversation_retrieve(client, conversation_id):
    """測試 6: conversations.retrieve()"""
    print("\n" + "=" * 60)
    print("TEST 6: Conversation Retrieve")
    print("=" * 60)

    if not conversation_id:
        print("  [SKIP] No conversation_id")
        return False

    try:
        conversation = client.conversations.retrieve(conversation_id)
        print(f"  Conversation ID: {conversation.id}")
        print(f"  Object: {conversation}")
        print("  [PASS]")
        return True
    except Exception as e:
        print(f"  [FAIL] {e}")
        import traceback
        traceback.print_exc()
        return False


def test_conversation_delete(client, conversation_id):
    """測試 7: conversations.delete()"""
    print("\n" + "=" * 60)
    print("TEST 7: Conversation Delete")
    print("=" * 60)

    if not conversation_id:
        print("  [SKIP] No conversation_id")
        return False

    try:
        result = client.conversations.delete(conversation_id)
        print(f"  Delete result: {result}")
        print("  [PASS]")
        return True
    except Exception as e:
        print(f"  [FAIL] {e}")
        import traceback
        traceback.print_exc()
        return False


def test_previous_response_id(client, config, prompts):
    """補充測試: previous_response_id 多輪對話 (不需要 conversation)"""
    print("\n" + "=" * 60)
    print("TEST EXTRA: previous_response_id Multi-Turn")
    print("=" * 60)

    model_params = get_model_params(config)
    system_prompt = prompts.get("system_prompt", "You are a helpful assistant.")

    try:
        # Turn 1
        r1 = client.responses.create(
            instructions=system_prompt,
            input="我住在台南，請記住這個資訊",
            store=True,
            **model_params,
        )
        print(f"  Response 1 ID: {r1.id}")
        print(f"  Output: {r1.output_text[:200]}")

        # Turn 2 — 用 previous_response_id 串接
        r2 = client.responses.create(
            instructions=system_prompt,
            input="請問我住在哪裡？",
            previous_response_id=r1.id,
            store=True,
            **model_params,
        )
        print(f"  Response 2 ID: {r2.id}")
        print(f"  Output: {r2.output_text[:200]}")

        if "台南" in r2.output_text:
            print("\n  Context via previous_response_id: YES")
        else:
            print("\n  Context via previous_response_id: UNCERTAIN")

        print("  [PASS]")
        return True
    except Exception as e:
        print(f"  [FAIL] {e}")
        import traceback
        traceback.print_exc()
        return False


# ============================================================
# Main
# ============================================================

def main():
    print("=" * 60)
    print("OpenAI Responses API Migration Test")
    print("=" * 60)

    # 載入設定
    config, prompts = load_configs()
    openai_config = config["openai"]
    print(f"  Model: {openai_config.get('model')}")
    print(f"  Base URL: {openai_config.get('base_url')}")
    print(f"  Reasoning Effort: {openai_config.get('reasoning_effort')}")
    print(f"  Vector Store ID: {openai_config.get('vector_store_id')}")
    print(f"  Max Output Tokens: {openai_config.get('max_output_tokens')}")

    # 建立 client
    client = create_client(config)

    results = {}

    # Test 1: Basic Response
    ok, basic_resp = test_basic_response(client, config, prompts)
    results["basic_response"] = ok

    # Test 2: File Search
    ok, fs_resp = test_file_search(client, config, prompts)
    results["file_search"] = ok

    # Test 3: Citation Format
    ok = test_citation_format(client, config, prompts, fs_resp)
    results["citation_format"] = ok

    # Test 4: Conversation Create
    ok, conversation = test_conversation_create(client, config)
    results["conversation_create"] = ok
    conversation_id = conversation.id if conversation else None

    # Test 5: Conversation Multi-Turn
    ok, _, _ = test_conversation_multi_turn(client, config, prompts, conversation_id)
    results["conversation_multi_turn"] = ok

    # Test 6: Conversation Retrieve
    ok = test_conversation_retrieve(client, conversation_id)
    results["conversation_retrieve"] = ok

    # Test 7: Conversation Delete
    ok = test_conversation_delete(client, conversation_id)
    results["conversation_delete"] = ok

    # Extra: previous_response_id
    ok = test_previous_response_id(client, config, prompts)
    results["previous_response_id"] = ok

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for name, passed in results.items():
        status = "PASS" if passed else "FAIL"
        print(f"  {name:30s} [{status}]")

    total = len(results)
    passed = sum(1 for v in results.values() if v)
    print(f"\n  Total: {passed}/{total} passed")

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
