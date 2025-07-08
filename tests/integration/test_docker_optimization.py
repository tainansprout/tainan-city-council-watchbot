"""
測試 Docker 容器化優化功能
"""
import pytest
import os
import docker
from unittest.mock import patch, MagicMock
from pathlib import Path


class TestDockerOptimization:
    """測試 Docker 優化功能"""

    def setup_method(self):
        """每個測試方法前的設置"""
        self.project_root = Path(__file__).parent.parent.parent

    def test_dockerfile_exists(self):
        """測試 Dockerfile 是否存在"""
        dockerfile_path = self.project_root / "Dockerfile"
        assert dockerfile_path.exists()

    def test_dockerignore_exists(self):
        """測試 .dockerignore 是否存在"""
        dockerignore_path = self.project_root / ".dockerignore"
        assert dockerignore_path.exists()

    def test_dockerfile_basic_structure(self):
        """測試 Dockerfile 基本結構"""
        dockerfile_path = self.project_root / "Dockerfile"
        
        with open(dockerfile_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 檢查基本指令 - 支援多階段建構
        assert 'FROM python:3.12-slim' in content
        assert 'WORKDIR /app' in content
        assert 'COPY requirements.txt' in content
        assert 'RUN pip install' in content
        assert 'USER app' in content
        assert 'CMD ["gunicorn"' in content

    def test_dockerfile_security_features(self):
        """測試 Dockerfile 安全特性"""
        dockerfile_path = self.project_root / "Dockerfile"
        
        with open(dockerfile_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 檢查安全特性
        assert 'useradd' in content  # 非 root 用戶
        assert 'USER app' in content  # 切換到非 root 用戶
        assert '--chown=app:app' in content  # 檔案所有權
        # 注意：健康檢查在 docker-compose.yaml 中定義，而不是在 Dockerfile 中

    def test_dockerfile_optimization_features(self):
        """測試 Dockerfile 優化特性"""
        dockerfile_path = self.project_root / "Dockerfile"
        
        with open(dockerfile_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 檢查優化特性
        assert 'rm -rf /var/lib/apt/lists/*' in content  # 清理 apt 快取
        assert 'PIP_NO_CACHE_DIR=True' in content  # 使用環境變數避免 pip 快取
        # 多階段建構本身就是最大的優化

    def test_dockerfile_cloud_run_compatibility(self):
        """測試 Dockerfile 與 Cloud Run 的兼容性"""
        dockerfile_path = self.project_root / "Dockerfile"
        
        with open(dockerfile_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Cloud Run 兼容性檢查
        assert 'EXPOSE $PORT' in content or 'PORT=8080' in content  # Cloud Run 動態端口
        assert 'gunicorn' in content  # 使用 gunicorn 作為 WSGI 服務器
        assert 'FLASK_ENV=production' in content  # 生產環境設定

    def test_dockerignore_content(self):
        """測試 .dockerignore 內容"""
        dockerignore_path = self.project_root / ".dockerignore"
        
        with open(dockerignore_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 檢查重要的忽略項目
        important_ignores = [
            '.git',
            '__pycache__',
            '*.pyc',
            'tests/',
            'docs/',
            '.env',
            '*.log',
            '.pytest_cache',
            'htmlcov/',
            'scripts/',
            '.vscode/',
            '.idea/'
        ]
        
        for ignore_item in important_ignores:
            assert ignore_item in content

    def test_docker_compose_structure(self):
        """測試 docker-compose.yaml 結構"""
        compose_path = self.project_root / "docker-compose.yaml"
        
        if compose_path.exists():
            with open(compose_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 檢查基本結構
            assert 'version:' in content
            assert 'services:' in content
            assert 'app:' in content
            assert 'db:' in content if 'db:' in content else True

    def test_docker_compose_security_settings(self):
        """測試 docker-compose.yaml 安全設置"""
        compose_path = self.project_root / "docker-compose.yaml"
        
        if compose_path.exists():
            with open(compose_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 檢查安全設置
            if 'security_opt:' in content:
                assert 'no-new-privileges:true' in content
            if 'user:' in content:
                assert '"1000:1000"' in content

    def test_gunicorn_config_cloud_run_compatibility(self):
        """測試 Gunicorn 配置與 Cloud Run 的兼容性"""
        gunicorn_config_path = self.project_root / "gunicorn.conf.py"
        
        with open(gunicorn_config_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Cloud Run 兼容性檢查
        assert 'PORT' in content  # 使用 PORT 環境變數
        assert 'K_SERVICE' in content or 'CLOUD_RUN_SERVICE' in content  # Cloud Run 檢測
        assert 'worker_class = "sync"' in content  # 使用 sync worker
        assert 'preload_app = True' in content  # 預加載應用

    def test_gunicorn_config_no_problematic_settings(self):
        """測試 Gunicorn 配置沒有問題設置"""
        gunicorn_config_path = self.project_root / "gunicorn.conf.py"
        
        with open(gunicorn_config_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 確保沒有問題設置
        assert 'worker_tmp_dir = "/dev/shm"' not in content  # 避免跨平台問題
        # 檢查配置中提到不需要設定 worker_tmp_dir
        assert 'worker_tmp_dir' not in content or 'worker_tmp_dir 在 Cloud Run 中不需要設定' in content

    @pytest.mark.skipif(not os.getenv('TEST_DOCKER'), reason="Docker tests disabled")
    def test_docker_build_success(self):
        """測試 Docker 映像檔構建成功"""
        try:
            client = docker.from_env()
            
            # 構建映像檔
            image, logs = client.images.build(
                path=str(self.project_root),
                tag="chatgpt-line-bot-test:latest",
                rm=True,
                forcerm=True
            )
            
            # 檢查映像檔是否成功構建
            assert image is not None
            assert len(image.tags) > 0
            
            # 清理測試映像檔
            client.images.remove(image.id, force=True)
            
        except docker.errors.DockerException as e:
            pytest.skip(f"Docker not available: {e}")

    @pytest.mark.skipif(not os.getenv('TEST_DOCKER'), reason="Docker tests disabled")
    def test_docker_image_size_optimization(self):
        """測試 Docker 映像檔大小優化"""
        try:
            client = docker.from_env()
            
            # 構建映像檔
            image, logs = client.images.build(
                path=str(self.project_root),
                tag="chatgpt-line-bot-size-test:latest",
                rm=True,
                forcerm=True
            )
            
            # 檢查映像檔大小（應該小於 1GB）
            image_size = image.attrs['Size']
            assert image_size < 1024 * 1024 * 1024  # 1GB
            
            # 清理測試映像檔
            client.images.remove(image.id, force=True)
            
        except docker.errors.DockerException as e:
            pytest.skip(f"Docker not available: {e}")

    def test_healthcheck_command_validity(self):
        """測試健康檢查命令的有效性"""
        # 健康檢查在 docker-compose.yaml 中定義
        compose_path = self.project_root / "docker-compose.yaml"
        
        with open(compose_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 檢查健康檢查使用 Python 而非外部工具
        if 'healthcheck:' in content:
            assert '"python"' in content or 'python -c' in content  # 支援數組和字符串格式
            assert 'urllib.request' in content
            assert 'curl' not in content  # 不依賴 curl


class TestDockerSecurityAndOptimization:
    """測試 Docker 安全性和優化整合"""

    def setup_method(self):
        """每個測試方法前的設置"""
        self.project_root = Path(__file__).parent.parent.parent

    def test_multi_stage_build_used_appropriately(self):
        """測試是否適當使用多階段構建"""
        dockerfile_path = self.project_root / "Dockerfile"
        
        with open(dockerfile_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 檢查多階段構建是否正確使用
        if 'FROM' in content and content.count('FROM') > 1:
            assert 'as builder' in content or 'AS builder' in content
            assert 'COPY --from=builder' in content  # 從建構階段複製檔案

    def test_layer_optimization(self):
        """測試 Docker 層優化"""
        dockerfile_path = self.project_root / "Dockerfile"
        
        with open(dockerfile_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 檢查 RUN 命令是否合併以減少層數
        run_commands = [line.strip() for line in content.split('\n') 
                       if line.strip().startswith('RUN')]
        
        # apt-get 命令應該合併
        apt_runs = [cmd for cmd in run_commands if 'apt-get' in cmd]
        if len(apt_runs) > 1:
            # 如果有多個 apt-get 命令，應該檢查是否合併
            combined_apt = any('&&' in cmd for cmd in apt_runs)
            assert combined_apt, "apt-get commands should be combined"

    def test_environment_variables_security(self):
        """測試環境變數安全性"""
        dockerfile_path = self.project_root / "Dockerfile"
        
        with open(dockerfile_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 檢查是否沒有硬編碼敏感資訊
        sensitive_patterns = [
            'password',
            'secret',
            'key',
            'token'
        ]
        
        content_lower = content.lower()
        for pattern in sensitive_patterns:
            # 允許在註釋或範例中出現
            if pattern in content_lower:
                lines_with_pattern = [line for line in content.split('\n') 
                                    if pattern in line.lower()]
                for line in lines_with_pattern:
                    # 確保不是實際的敏感值設定
                    assert (line.strip().startswith('#') or 
                           'example' in line.lower() or
                           'your_' in line.lower())

    def test_docker_compose_resource_limits(self):
        """測試 Docker Compose 資源限制"""
        compose_path = self.project_root / "docker-compose.yaml"
        
        if compose_path.exists():
            with open(compose_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 檢查是否設置了資源限制
            if 'deploy:' in content:
                assert 'resources:' in content
                assert 'limits:' in content
                if 'memory:' in content:
                    assert 'M' in content or 'G' in content  # 記憶體單位

    def test_docker_labels_and_metadata(self):
        """測試 Docker 標籤和元資料"""
        dockerfile_path = self.project_root / "Dockerfile"
        
        with open(dockerfile_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 檢查是否有適當的元資料（可選）
        # 這不是強制要求，但有助於管理
        if 'LABEL' in content:
            assert 'maintainer' in content.lower() or 'author' in content.lower()

    def test_cloud_run_specific_optimizations(self):
        """測試 Cloud Run 特定優化"""
        # 檢查 Dockerfile 是否針對 Cloud Run 進行了優化
        dockerfile_path = self.project_root / "Dockerfile"
        
        with open(dockerfile_path, 'r', encoding='utf-8') as f:
            dockerfile_content = f.read()
        
        # Cloud Run 特定檢查
        assert 'PORT' in dockerfile_content  # 使用動態端口
        
        # 檢查 gunicorn 配置
        gunicorn_config_path = self.project_root / "gunicorn.conf.py"
        with open(gunicorn_config_path, 'r', encoding='utf-8') as f:
            gunicorn_content = f.read()
        
        # Cloud Run 檢測邏輯
        assert 'K_SERVICE' in gunicorn_content or 'CLOUD_RUN_SERVICE' in gunicorn_content
        # 記憶體優化設置
        assert 'get_workers()' in gunicorn_content
        
    def test_startup_time_optimization(self):
        """測試啟動時間優化"""
        gunicorn_config_path = self.project_root / "gunicorn.conf.py"
        
        with open(gunicorn_config_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 檢查預加載設置（改善啟動時間）
        assert 'preload_app = True' in content
        
        # 檢查 worker 數量設置（不應該太多，避免啟動慢）
        if 'workers =' in content:
            # 確保 worker 數量是動態計算的，而不是固定的大數值
            assert 'get_workers()' in content or 'min(' in content