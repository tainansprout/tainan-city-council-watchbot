#!/usr/bin/env python3
"""
現代化資料庫遷移管理工具 - 遵循 2024 年最佳實踐
使用 Flask-Migrate (基於 Alembic) 而非純 Alembic

特色:
- 使用 Flask-Migrate 而非純 Alembic (Flask 專案最佳實踐)
- 將遷移與應用啟動解耦 (Docker 最佳實踐)
- 自動檢查和驗證機制
- 生產環境安全操作
- 統一的 CLI 介面
"""

import os
import sys
import click
from pathlib import Path

# 添加專案根目錄到 Python 路徑
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

def create_flask_app():
    """創建 Flask 應用程式實例用於遷移"""
    try:
        from src.app import create_app
        
        # 設定為遷移模式，避免初始化所有服務
        os.environ['MIGRATION_MODE'] = 'true'
        
        app = create_app()
        return app
    except Exception as e:
        click.echo(f"❌ 無法創建 Flask 應用: {e}", err=True)
        sys.exit(1)

def get_flask_migrate():
    """取得 Flask-Migrate 實例"""
    try:
        app = create_flask_app()
        
        # 初始化 Flask-Migrate
        from flask_migrate import Migrate
        from src.database.models import db
        
        migrate = Migrate(app, db)
        return app, migrate
    except Exception as e:
        click.echo(f"❌ 無法初始化 Flask-Migrate: {e}", err=True)
        sys.exit(1)

@click.group()
@click.option('--verbose', '-v', is_flag=True, help='顯示詳細輸出')
@click.pass_context
def cli(ctx, verbose):
    """現代化資料庫遷移管理工具"""
    ctx.ensure_object(dict)
    ctx.obj['verbose'] = verbose
    
    if verbose:
        click.echo("🔧 使用 Flask-Migrate 進行資料庫遷移管理")

@cli.command()
@click.pass_context
def init(ctx):
    """初始化遷移環境（僅首次使用）"""
    click.echo("🚀 初始化 Flask-Migrate 遷移環境...")
    
    try:
        from flask.cli import with_appcontext
        from flask_migrate import init as migrate_init
        
        app, migrate = get_flask_migrate()
        
        with app.app_context():
            # 檢查是否已經初始化
            migrations_dir = PROJECT_ROOT / "migrations"
            if migrations_dir.exists():
                click.echo("⚠️  遷移環境已存在，跳過初始化")
                return
            
            # 初始化遷移環境
            migrate_init()
            click.echo("✅ 遷移環境初始化完成")
            
    except Exception as e:
        click.echo(f"❌ 初始化失敗: {e}", err=True)
        sys.exit(1)

@cli.command()
@click.option('--message', '-m', required=True, help='遷移描述訊息')
@click.option('--autogenerate', is_flag=True, default=True, help='自動檢測模型變更')
@click.pass_context
def create(ctx, message, autogenerate):
    """創建新的遷移檔案"""
    click.echo(f"📝 創建遷移: {message}")
    
    try:
        from flask_migrate import migrate as migrate_create
        
        app, migrate = get_flask_migrate()
        
        with app.app_context():
            if autogenerate:
                # 自動檢測變更
                migrate_create(message=message)
                click.echo("✅ 自動檢測並創建遷移檔案")
                click.echo("⚠️  請檢查生成的遷移檔案，Alembic 無法檢測所有變更")
            else:
                # 創建空白遷移
                migrate_create(message=message, empty=True)
                click.echo("✅ 創建空白遷移檔案")
                
    except Exception as e:
        click.echo(f"❌ 創建遷移失敗: {e}", err=True)
        sys.exit(1)

@cli.command()
@click.option('--revision', '-r', default='head', help='目標版本 (預設: head)')
@click.option('--sql', is_flag=True, help='僅顯示 SQL，不執行')
@click.pass_context
def upgrade(ctx, revision, sql):
    """升級資料庫到指定版本"""
    if sql:
        click.echo(f"📋 顯示升級到 {revision} 的 SQL:")
    else:
        click.echo(f"⬆️  升級資料庫到版本: {revision}")
    
    try:
        from flask_migrate import upgrade as migrate_upgrade
        
        app, migrate = get_flask_migrate()
        
        with app.app_context():
            migrate_upgrade(revision=revision, sql=sql)
            
            if not sql:
                click.echo("✅ 資料庫升級完成")
                
    except Exception as e:
        click.echo(f"❌ 升級失敗: {e}", err=True)
        sys.exit(1)

@cli.command()
@click.option('--revision', '-r', required=True, help='目標版本')
@click.option('--sql', is_flag=True, help='僅顯示 SQL，不執行')
@click.pass_context
def downgrade(ctx, revision, sql):
    """降級資料庫到指定版本"""
    if sql:
        click.echo(f"📋 顯示降級到 {revision} 的 SQL:")
    else:
        click.echo(f"⬇️  降級資料庫到版本: {revision}")
        click.confirm("確定要降級資料庫嗎？此操作可能造成資料遺失！", abort=True)
    
    try:
        from flask_migrate import downgrade as migrate_downgrade
        
        app, migrate = get_flask_migrate()
        
        with app.app_context():
            migrate_downgrade(revision=revision, sql=sql)
            
            if not sql:
                click.echo("✅ 資料庫降級完成")
                
    except Exception as e:
        click.echo(f"❌ 降級失敗: {e}", err=True)
        sys.exit(1)

@cli.command()
@click.pass_context
def current(ctx):
    """顯示目前的資料庫版本"""
    click.echo("📍 查詢目前資料庫版本...")
    
    try:
        from flask_migrate import current as migrate_current
        
        app, migrate = get_flask_migrate()
        
        with app.app_context():
            migrate_current()
            
    except Exception as e:
        click.echo(f"❌ 查詢版本失敗: {e}", err=True)
        sys.exit(1)

@cli.command()
@click.option('--verbose', '-v', is_flag=True, help='顯示詳細歷史')
@click.pass_context
def history(ctx, verbose):
    """顯示遷移歷史"""
    click.echo("📚 遷移歷史:")
    
    try:
        from flask_migrate import history as migrate_history
        
        app, migrate = get_flask_migrate()
        
        with app.app_context():
            migrate_history(verbose=verbose)
            
    except Exception as e:
        click.echo(f"❌ 查詢歷史失敗: {e}", err=True)
        sys.exit(1)

@cli.command()
@click.pass_context
def check(ctx):
    """檢查是否有待創建的遷移"""
    click.echo("🔍 檢查模型變更...")
    
    try:
        # 使用 Flask-Migrate 的檢查功能
        app, migrate = get_flask_migrate()
        
        with app.app_context():
            from alembic.script import ScriptDirectory
            from alembic.runtime.migration import MigrationContext
            from alembic.autogenerate import compare_metadata
            from src.database.models import db
            
            # 取得當前遷移環境
            config = migrate.get_config()
            script = ScriptDirectory.from_config(config)
            
            # 取得當前資料庫狀態
            with db.engine.connect() as connection:
                context = MigrationContext.configure(connection)
                
                # 比較模型和資料庫
                diff = compare_metadata(context, db.metadata)
                
                if diff:
                    click.echo("⚠️  檢測到未遷移的變更:")
                    for change in diff:
                        click.echo(f"  - {change}")
                    click.echo("\n💡 建議運行: python scripts/migrate.py create -m '描述變更'")
                else:
                    click.echo("✅ 資料庫與模型同步，無需遷移")
                    
    except Exception as e:
        click.echo(f"❌ 檢查失敗: {e}", err=True)
        sys.exit(1)

@cli.command()
@click.option('--revision', '-r', help='標記為特定版本')
@click.pass_context
def stamp(ctx, revision):
    """標記資料庫版本（不執行 SQL）"""
    if not revision:
        revision = 'head'
    
    click.echo(f"🏷️  標記資料庫版本為: {revision}")
    click.confirm("確定要標記版本嗎？", abort=True)
    
    try:
        from flask_migrate import stamp as migrate_stamp
        
        app, migrate = get_flask_migrate()
        
        with app.app_context():
            migrate_stamp(revision=revision)
            click.echo("✅ 版本標記完成")
            
    except Exception as e:
        click.echo(f"❌ 標記失敗: {e}", err=True)
        sys.exit(1)

@cli.command()
@click.pass_context
def status(ctx):
    """顯示完整的遷移狀態"""
    click.echo("📊 遷移狀態報告:")
    
    try:
        app, migrate = get_flask_migrate()
        
        with app.app_context():
            # 顯示當前版本
            click.echo("\n📍 當前版本:")
            from flask_migrate import current as migrate_current
            migrate_current()
            
            # 檢查待遷移變更
            click.echo("\n🔍 變更檢查:")
            ctx.invoke(check)
            
            # 顯示資料庫連線狀態
            from src.database.models import db
            try:
                with db.engine.connect() as conn:
                    result = conn.execute(db.text("SELECT 1"))
                    click.echo("\n💾 資料庫連線: ✅ 正常")
            except Exception as e:
                click.echo(f"\n💾 資料庫連線: ❌ 失敗 ({e})")
            
    except Exception as e:
        click.echo(f"❌ 狀態檢查失敗: {e}", err=True)
        sys.exit(1)

@cli.command()
@click.pass_context
def setup(ctx):
    """一鍵設置並初始化資料庫（生產環境使用）"""
    click.echo("🚀 一鍵資料庫設置...")
    
    try:
        # 1. 檢查或初始化遷移環境
        migrations_dir = PROJECT_ROOT / "migrations"
        if not migrations_dir.exists():
            click.echo("📁 初始化遷移環境...")
            ctx.invoke(init)
        
        # 2. 升級到最新版本
        click.echo("⬆️  升級資料庫到最新版本...")
        ctx.invoke(upgrade)
        
        # 3. 顯示最終狀態
        click.echo("📊 顯示最終狀態...")
        ctx.invoke(status)
        
        click.echo("\n🎉 資料庫設置完成！")
        
    except Exception as e:
        click.echo(f"❌ 設置失敗: {e}", err=True)
        sys.exit(1)

if __name__ == '__main__':
    cli()