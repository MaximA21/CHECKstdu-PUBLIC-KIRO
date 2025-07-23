# Enterprise Search Platform

[![Code Quality and Security](https://github.com/YOUR_USERNAME/YOUR_REPO/actions/workflows/code-quality-security.yml/badge.svg)](https://github.com/YOUR_USERNAME/YOUR_REPO/actions/workflows/code-quality-security.yml)
[![codecov](https://codecov.io/gh/YOUR_USERNAME/YOUR_REPO/branch/kiro-rewrite/graph/badge.svg)](https://codecov.io/gh/YOUR_USERNAME/YOUR_REPO)

A scalable enterprise search platform built with clean architecture principles, supporting multiple deployment patterns including AWS Lambda and containerized environments.

## Features

- **Multi-Provider Search**: Aggregates results from multiple search providers
- **Real-time WebSocket Communication**: Live search results and connection management
- **Clean Architecture**: Domain-driven design with clear separation of concerns
- **Flexible Deployment**: Supports AWS Lambda, containers, and traditional servers
- **Comprehensive Testing**: Unit, integration, and end-to-end test coverage
- **Security First**: Built-in security scanning and vulnerability management

## Quick Start

### Prerequisites

- Python 3.9+
- pip or poetry for dependency management

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd <repository-name>

# Install dependencies
pip install -r requirements.txt

# Install development dependencies
pip install -r requirements-dev.txt

# Install pre-commit hooks
pre-commit install
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test categories
pytest -m unit
pytest -m integration
pytest -m e2e
```

## Architecture

The project follows clean architecture principles with the following layers:

- **Domain**: Core business logic and entities
- **Application**: Use cases and application services
- **Infrastructure**: External service implementations
- **Presentation**: API handlers and controllers

See [src/README.md](src/README.md) for detailed architecture documentation.

## Code Quality

This project maintains high code quality standards through:

- **Automated Testing**: 80%+ test coverage requirement
- **Code Formatting**: Black and isort for consistent style
- **Linting**: flake8 for code quality checks
- **Type Checking**: mypy for static type analysis
- **Security Scanning**: Bandit, Safety, and pip-audit for vulnerability detection

See [docs/CODE_QUALITY.md](docs/CODE_QUALITY.md) for detailed information.

## Development

### Code Quality Checks

```bash
# Format code
black src/ tests/ lambda_functions/ examples/
isort src/ tests/ lambda_functions/ examples/

# Run linting
flake8 src/ tests/ lambda_functions/ examples/

# Type checking
mypy src/

# Security scanning
bandit -r src/ lambda_functions/
safety check
pip-audit
```

### Pre-commit Hooks

Pre-commit hooks automatically run quality checks before each commit:

```bash
pre-commit install  # One-time setup
pre-commit run --all-files  # Manual run
```

## Deployment

The platform supports multiple deployment patterns:

- **AWS Lambda**: Serverless deployment with API Gateway and WebSocket support
- **Container**: Docker-based deployment with nginx load balancing
- **Traditional Server**: Standard Python web server deployment

See deployment-specific documentation in the `docs/` directory.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Ensure all tests pass and code quality checks succeed
5. Submit a pull request

All contributions must pass the automated code quality and security checks.

## License

[Add your license information here]