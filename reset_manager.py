#!/usr/bin/env python3
"""
AshAI Reset Manager
Provides soft reset functionality for backend services without restarting Docker
"""

import os
import sys
import signal
import subprocess
import time
import asyncio
import argparse
from pathlib import Path

# Add app to path for imports
sys.path.insert(0, '/app')


class ServiceManager:
    """Manages service lifecycle within the Docker container"""

    def __init__(self):
        self.pids = {
            'backend': None,
            'cli_controller': None,
            'proxy': None
        }

    def stop_services(self):
        """Stop all running services gracefully"""
        print("🛑 Stopping existing services...")

        # Find and kill processes
        processes = [
            ('python3 -m helperai', 'backend'),
            ('cli-terminal-controller.py', 'cli_controller'),
            ('multi-provider-proxy.py', 'proxy')
        ]

        for pattern, name in processes:
            try:
                result = subprocess.run(
                    f"ps aux | grep '{pattern}' | grep -v grep | awk '{{print $1}}'",
                    shell=True, capture_output=True, text=True
                )
                if result.stdout.strip():
                    pid = result.stdout.strip()
                    os.kill(int(pid), signal.SIGTERM)
                    print(f"  ✅ Stopped {name} (pid: {pid})")
                    time.sleep(0.5)
            except:
                pass

    def start_proxy(self):
        """Start the multi-provider proxy"""
        # Check if any API keys are configured
        has_keys = any([
            os.getenv('ANTHROPIC_API_KEY'),
            os.getenv('OPENAI_API_KEY'),
            os.getenv('GEMINI_API_KEY'),
            os.getenv('OLLAMA_BASE_URL')
        ])

        if has_keys:
            print("🔄 Starting multi-provider proxy...")
            proc = subprocess.Popen(
                ['python3', '/home/claude/multi-provider-proxy.py'],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            self.pids['proxy'] = proc.pid
            print(f"  ✅ Proxy started (pid: {proc.pid})")
        else:
            print("  ⚠️  No API keys configured, skipping proxy")

    def start_backend(self):
        """Start the backend API"""
        print("🚀 Starting backend API...")

        # Set environment variables
        env = os.environ.copy()
        env.update({
            'HELPERAI_DATABASE_URL': 'sqlite+aiosqlite:////app/data/helperai.db',
            'HELPERAI_PLUGINS_DIR': '/app/plugins',
            'HELPERAI_HOST': '0.0.0.0',
            'HELPERAI_PORT': '8000',
            'HELPERAI_ANTHROPIC_BASE_URL': 'http://localhost:8082',
            'HELPERAI_ANTHROPIC_API_KEY': 'proxy',
            'HELPERAI_DEFAULT_PROVIDER': 'cli_agent',
            'HELPERAI_DEFAULT_MODEL': 'sonnet',
            'HELPERAI_EVE_PROVIDER': 'anthropic',
            'HELPERAI_EVE_MODEL': 'claude-opus-4-6'
        })

        proc = subprocess.Popen(
            ['python3', '-m', 'helperai'],
            cwd='/app',
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        self.pids['backend'] = proc.pid
        print(f"  ✅ Backend API started (pid: {proc.pid})")

    def start_cli_controller(self):
        """Start the CLI terminal controller"""
        print("🎮 Starting CLI controller...")
        proc = subprocess.Popen(
            ['python3', '/home/claude/cli-terminal-controller.py'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        self.pids['cli_controller'] = proc.pid
        print(f"  ✅ CLI controller started (pid: {proc.pid})")

    def reset_database(self, backup=True):
        """Reset the database with optional backup"""
        db_path = Path('/app/data/helperai.db')

        if db_path.exists():
            if backup:
                backup_path = f'/app/data/helperai.db.backup.{int(time.time())}'
                print(f"📦 Backing up database to {backup_path}")
                subprocess.run(['cp', str(db_path), backup_path])

            print("🗑️  Removing database...")
            db_path.unlink()
            print("  ✅ Database reset")
        else:
            print("  ℹ️  No database to reset")

    def check_health(self, timeout=10):
        """Check if services are healthy"""
        print("\n🔍 Checking service health...")

        checks = [
            ('Backend API', 'http://localhost:8000/api/health'),
            ('CLI Controller', 'http://localhost:8081/api/status'),
            ('Multi-Provider Proxy', 'http://localhost:8082/health')
        ]

        # Wait a bit for services to start
        time.sleep(3)

        for name, url in checks:
            try:
                result = subprocess.run(
                    f'curl -s -f {url}',
                    shell=True,
                    capture_output=True,
                    timeout=2
                )
                if result.returncode == 0:
                    print(f"  ✅ {name}: Healthy")
                else:
                    print(f"  ❌ {name}: Not responding")
            except:
                print(f"  ❌ {name}: Timeout")

    def show_agents(self):
        """Display current agents"""
        print("\n🤖 Current agents:")
        try:
            result = subprocess.run(
                'curl -s http://localhost:8000/api/agents',
                shell=True,
                capture_output=True,
                text=True,
                timeout=2
            )
            if result.returncode == 0:
                import json
                agents = json.loads(result.stdout)
                if not agents:
                    print("  No agents found")
                else:
                    for agent in agents:
                        status_icon = '✅' if agent['status'] == 'idle' else '❌'
                        print(f"  {status_icon} {agent['name']}: {agent['model_name']} ({agent['status']})")
        except Exception as e:
            print(f"  Could not fetch agents: {e}")


def main():
    parser = argparse.ArgumentParser(description='AshAI Service Reset Manager')
    parser.add_argument('--reset-db', action='store_true', help='Reset the database')
    parser.add_argument('--no-backup', action='store_true', help='Skip database backup')
    parser.add_argument('--health-only', action='store_true', help='Only check service health')
    parser.add_argument('--stop-only', action='store_true', help='Only stop services')

    args = parser.parse_args()

    manager = ServiceManager()

    if args.health_only:
        manager.check_health()
        manager.show_agents()
        return

    if args.stop_only:
        manager.stop_services()
        return

    print("=" * 60)
    print("                 AshAI Service Reset Manager")
    print("=" * 60)

    # Stop existing services
    manager.stop_services()

    # Reset database if requested
    if args.reset_db:
        manager.reset_database(backup=not args.no_backup)

    # Start services
    print("\n🔄 Restarting services...")
    manager.start_proxy()
    manager.start_backend()
    time.sleep(2)  # Give backend time to initialize
    manager.start_cli_controller()

    # Check health
    manager.check_health()
    manager.show_agents()

    print("\n" + "=" * 60)
    print("                    Reset Complete!")
    print("=" * 60)


if __name__ == '__main__':
    main()