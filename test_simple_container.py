#!/usr/bin/env python3
"""Simple test for container deployment configuration."""

import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

try:
    from infrastructure.config.loader import ConfigLoader
    from infrastructure.config.models import Environment, ContainerConfig

    def test_configuration():
        """Test configuration loading."""
        print("Testing container configuration...")

        # Test with development config
        config_loader = ConfigLoader("config")
        config = config_loader.load_config()

        print(f"✓ Configuration loaded successfully")
        print(f"  Environment: {config.environment.value}")
        print(f"  HTTP Port: {config.container.http_port}")
        print(f"  WebSocket Port: {config.container.websocket_port}")
        print(f"  CORS Enabled: {config.container.cors_enabled}")
        print(f"  Max Connections: {config.container.max_connections}")
        print(f"  Database Provider: {config.database.provider.value}")
        print(f"  Messaging Provider: {config.messaging.provider.value}")
        print(f"  Logging Provider: {config.logging.provider.value}")

        # Test provider configs
        print(f"  Enabled Providers: {[name for name, cfg in config.provider_configs.items() if cfg.enabled]}")

        return True

    def test_config_files():
        """Test different configuration files."""
        print("\nTesting configuration files...")

        config_files = ["config/development.json", "config/container.json", "config/production.json"]

        for config_file in config_files:
            if Path(config_file).exists():
                try:
                    with open(config_file, "r") as f:
                        data = json.load(f)
                    print(f"✓ {config_file} - Valid JSON")

                    # Check for required sections
                    required_sections = ["database", "messaging", "logging"]
                    for section in required_sections:
                        if section in data:
                            print(f"  ✓ {section} section present")
                        else:
                            print(f"  ⚠ {section} section missing")

                    # Check container section
                    if "container" in data:
                        container = data["container"]
                        print(
                            f"  ✓ Container config: HTTP={container.get('http_port', 8080)}, WS={container.get('websocket_port', 8081)}"
                        )

                except json.JSONDecodeError as e:
                    print(f"✗ {config_file} - Invalid JSON: {e}")
                    return False
            else:
                print(f"⚠ {config_file} - File not found")

        return True

    def main():
        """Run tests."""
        print("Container Configuration Test")
        print("=" * 40)

        tests = [test_configuration, test_config_files]
        results = []

        for test in tests:
            try:
                result = test()
                results.append(result)
            except Exception as e:
                print(f"✗ Test failed: {e}")
                results.append(False)

        print("\n" + "=" * 40)
        print(f"Results: {sum(results)}/{len(results)} tests passed")

        if all(results):
            print("✓ Container configuration is ready!")
            return 0
        else:
            print("✗ Some configuration issues found.")
            return 1

    if __name__ == "__main__":
        sys.exit(main())

except ImportError as e:
    print(f"Import error: {e}")
    print("Make sure you're running from the project root directory.")
    sys.exit(1)
