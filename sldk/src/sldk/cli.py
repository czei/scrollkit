"""Command-line interface for SLDK tools.

Provides easy access to development and deployment tools.
"""

from __future__ import annotations

import argparse
import sys
import os
from pathlib import Path

from .exceptions import DeploymentError, NetworkError, OTAError


def main() -> int:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog='sldk',
        description='SLDK (Scrolling LED Dev Kit) command-line tools'
    )

    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    package_parser = subparsers.add_parser('package', help='Package application for deployment')
    package_parser.add_argument('--version', help='Package version')
    package_parser.add_argument('--output', help='Output directory')
    package_parser.add_argument('--no-mpy', action='store_true', help='Disable .mpy compilation')
    package_parser.add_argument('--include-tests', action='store_true', help='Include test files')

    deploy_parser = subparsers.add_parser('deploy', help='Deploy to CircuitPython device')
    deploy_parser.add_argument('--target', help='Target device path')
    deploy_parser.add_argument('--no-backup', action='store_true', help='Skip backup creation')
    deploy_parser.add_argument('--no-verify', action='store_true', help='Skip deployment verification')

    ota_parser = subparsers.add_parser('ota', help='OTA update management')
    ota_subparsers = ota_parser.add_subparsers(dest='ota_action', help='OTA actions')

    ota_create = ota_subparsers.add_parser('create', help='Create OTA package')
    ota_create.add_argument('version', help='Package version')
    ota_create.add_argument('--description', help='Package description')
    ota_create.add_argument('--source', default='./src', help='Source directory')

    ota_serve = ota_subparsers.add_parser('serve', help='Start OTA server')
    ota_serve.add_argument('--port', type=int, default=8080, help='Server port')
    ota_serve.add_argument('--updates-dir', default='./updates', help='Updates directory')

    dev_parser = subparsers.add_parser('dev', help='Start development server')
    dev_parser.add_argument('--port', type=int, default=8000, help='Web interface port')
    dev_parser.add_argument('--no-reload', action='store_true', help='Disable hot-reload')
    dev_parser.add_argument('--app-module', default='main', help='Application module')
    dev_parser.add_argument('--app-function', default='main', help='Application function')

    monitor_parser = subparsers.add_parser('monitor', help='Monitor CircuitPython device')
    monitor_parser.add_argument('--device', help='Device path')
    monitor_parser.add_argument('--no-logs', action='store_true', help='Disable log following')

    list_parser = subparsers.add_parser('list', help='List available devices')

    create_parser = subparsers.add_parser('create', help='Create new SLDK project')
    create_parser.add_argument('name', help='Project name')
    create_parser.add_argument('--template', default='basic', help='Project template')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    try:
        if args.command == 'package':
            return cmd_package(args)
        elif args.command == 'deploy':
            return cmd_deploy(args)
        elif args.command == 'ota':
            return cmd_ota(args)
        elif args.command == 'dev':
            return cmd_dev(args)
        elif args.command == 'monitor':
            return cmd_monitor(args)
        elif args.command == 'list':
            return cmd_list(args)
        elif args.command == 'create':
            return cmd_create(args)
        else:
            print(f"Unknown command: {args.command}")
            return 1

    except KeyboardInterrupt:
        print("\nOperation cancelled.")
        return 1
    except OTAError as e:
        print(f"OTA error: {e}")
        return 1
    except DeploymentError as e:
        print(f"Deployment error: {e}")
        return 1
    except NetworkError as e:
        print(f"Network error: {e}")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        return 1


def cmd_package(args: argparse.Namespace) -> int:
    """Package command implementation."""
    from .tools.packager import SLDKPackager

    print("Packaging SLDK application...")

    packager = SLDKPackager()

    if args.no_mpy:
        packager.set_optimization_options(mpy=False)

    if args.include_tests:
        packager.set_optimization_options(include_tests=True)

    success, result = packager.package(
        output_dir=args.output,
        version=args.version,
    )

    if success:
        print(f"Package created successfully: {result}")
        return 0
    else:
        print(f"Packaging failed: {result}")
        return 1


def cmd_deploy(args: argparse.Namespace) -> int:
    """Deploy command implementation."""
    from .tools.deployer import SLDKDeployer

    print("Deploying to CircuitPython device...")

    deployer = SLDKDeployer()

    if args.target:
        deployer.set_circuitpy_drive(args.target)

    success, error = deployer.deploy_to_device(
        target=args.target,
        backup=not args.no_backup,
        verify=not args.no_verify,
    )

    if success:
        print("Deployment completed successfully!")
        return 0
    else:
        print(f"Deployment failed: {error}")
        return 1


def cmd_ota(args: argparse.Namespace) -> int:
    """OTA command implementation."""
    if not args.ota_action:
        print("OTA action required (create, serve)")
        return 1

    if args.ota_action == 'create':
        return cmd_ota_create(args)
    elif args.ota_action == 'serve':
        return cmd_ota_serve(args)
    else:
        print(f"Unknown OTA action: {args.ota_action}")
        return 1


def cmd_ota_create(args: argparse.Namespace) -> int:
    """OTA create command implementation."""
    from .ota.server import OTAServer

    print(f"Creating OTA package: {args.version}")

    server = OTAServer()
    success, result = server.create_package(
        version=args.version,
        description=args.description or f"SLDK Application {args.version}",
        source_dir=args.source,
    )

    if success:
        print(f"OTA package created: {args.version}")
        return 0
    else:
        print(f"Failed to create OTA package: {result}")
        return 1


def cmd_ota_serve(args: argparse.Namespace) -> int:
    """OTA serve command implementation."""
    from .ota.server import OTAServer
    from .web import SLDKWebServer

    print(f"Starting OTA server on port {args.port}...")

    ota_server = OTAServer(updates_dir=args.updates_dir)

    web_server = SLDKWebServer(host="0.0.0.0", port=args.port)

    ota_server.register_web_routes(web_server)

    print(f"OTA server running at: http://localhost:{args.port}")
    print("Available packages:")

    packages = ota_server.list_packages()
    if packages:
        for pkg in packages:
            current = " (current)" if pkg['is_current'] else ""
            print(f"  {pkg['version']}: {pkg['description']}{current}")
    else:
        print("  No packages available")

    print("Press Ctrl+C to stop")

    try:
        web_server.run_forever()
        return 0
    except KeyboardInterrupt:
        print("\nOTA server stopped.")
        return 0


def cmd_dev(args: argparse.Namespace) -> int:
    """Dev command implementation."""
    try:
        from .tools.dev_server import SLDKDevServer
    except ImportError as e:
        print(f"Development server not available: {e}")
        print("Install with: pip install sldk[dev]")
        return 1

    print("Starting SLDK development server...")

    dev_server = SLDKDevServer(port=args.port)
    dev_server.set_config(hot_reload=not args.no_reload)

    success = dev_server.start(
        app_module=args.app_module,
        app_function=args.app_function,
    )

    return 0 if success else 1


def cmd_monitor(args: argparse.Namespace) -> int:
    """Monitor command implementation."""
    from .tools.deployer import SLDKDeployer

    print("Monitoring CircuitPython device...")

    deployer = SLDKDeployer()

    if args.device:
        deployer.set_circuitpy_drive(args.device)

    success, error = deployer.monitor_device(
        device_path=args.device,
        follow_logs=not args.no_logs,
    )

    if success:
        return 0
    else:
        print(f"Monitoring failed: {error}")
        return 1


def cmd_list(args: argparse.Namespace) -> int:
    """List command implementation."""
    from .tools.deployer import SLDKDeployer

    print("Scanning for CircuitPython devices...")

    deployer = SLDKDeployer()
    drives = deployer.list_available_drives()

    if drives:
        print("Found CircuitPython devices:")
        for drive in drives:
            print(f"  {drive}")
    else:
        print("No CircuitPython devices found.")

        print("\nTip: Make sure your device is connected and mounted.")
        print("Common locations:")
        print("  macOS: /Volumes/CIRCUITPY")
        print("  Linux: /media/*/CIRCUITPY")
        print("  Windows: D:\\, E:\\, F:\\")

    return 0


def cmd_create(args: argparse.Namespace) -> int:
    """Create command implementation."""
    print(f"Creating new SLDK project: {args.name}")

    project_dir = Path(args.name)

    if project_dir.exists():
        print(f"Directory {args.name} already exists!")
        return 1

    try:
        create_project_structure(project_dir, args.template)
        print(f"Project created: {project_dir}")
        print("\nNext steps:")
        print(f"  cd {args.name}")
        print("  sldk dev")
        return 0
    except Exception as e:
        print(f"Failed to create project: {e}")
        return 1


def create_project_structure(project_dir: Path, template: str) -> None:
    """Create SLDK project structure.

    Args:
        project_dir: Project directory path
        template: Project template name
    """
    project_dir.mkdir(parents=True)

    (project_dir / "src").mkdir()
    (project_dir / "tests").mkdir()
    (project_dir / "docs").mkdir()

    main_py_content = '''"""Main SLDK application."""

import asyncio
from sldk.app import SLDKApp
from sldk.display.content import ScrollingText, StaticText


class MyLEDApp(SLDKApp):
    """Example SLDK application."""

    async def setup(self):
        """Initialize application."""
        hello_text = StaticText("Hello SLDK!", duration=3)
        scroll_text = ScrollingText("Welcome to your new SLDK application!", speed=2)

        await self.content_queue.add_content(hello_text)
        await self.content_queue.add_content(scroll_text)

    async def update_data(self):
        """Update application data periodically."""
        pass


def main():
    """Main application entry point."""
    app = MyLEDApp(
        enable_web=True,
        update_interval=300,
    )

    try:
        asyncio.run(app.run())
    except KeyboardInterrupt:
        print("Application stopped.")


if __name__ == "__main__":
    main()
'''

    with open(project_dir / "src" / "main.py", 'w') as f:
        f.write(main_py_content)

    code_py_content = '''"""CircuitPython entry point."""

import src.main
'''

    with open(project_dir / "code.py", 'w') as f:
        f.write(code_py_content)

    boot_py_content = '''"""CircuitPython boot configuration."""

import storage
storage.remount("/", readonly=False)
'''

    with open(project_dir / "boot.py", 'w') as f:
        f.write(boot_py_content)

    requirements_content = '''sldk>=0.5.0
'''

    with open(project_dir / "requirements.txt", 'w') as f:
        f.write(requirements_content)

    readme_content = f'''# {project_dir.name}

SLDK (Scrolling LED Dev Kit) application.

## Development

Start the development server:

```bash
sldk dev
```

## Deployment

Deploy to CircuitPython device:

```bash
sldk deploy
```

## OTA Updates

Create OTA package:

```bash
sldk ota create 1.0.0
```

Start OTA server:

```bash
sldk ota serve
```
'''

    with open(project_dir / "README.md", 'w') as f:
        f.write(readme_content)

    gitignore_content = '''__pycache__/
*.pyc
*.pyo
*.mpy
.pytest_cache/
build/
dist/
*.egg-info/
.vscode/
.DS_Store
'''

    with open(project_dir / ".gitignore", 'w') as f:
        f.write(gitignore_content)


if __name__ == "__main__":
    sys.exit(main())