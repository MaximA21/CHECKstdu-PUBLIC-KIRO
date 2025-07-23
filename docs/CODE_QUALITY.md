# Code Quality and Security

This document outlines the code quality and security measures implemented in the project.

## Overview

The project uses automated code quality and security checks through GitHub Actions, pre-commit hooks, and local development tools.

## Code Quality Tools

### Linting and Formatting
- **Black**: Code formatter with 127 character line length
- **isort**: Import statement organizer
- **flake8**: Style guide enforcement and error detection

### Type Checking
- **mypy**: Static type checking (configured to be permissive for gradual adoption)

### Security Scanning
- **Bandit**: Security vulnerability scanner for Python code
- **Safety**: Dependency vulnerability checker
- **pip-audit**: Modern dependency auditing tool

### Test Coverage
- **pytest-cov**: Code coverage reporting with 80% minimum threshold
- **Coverage reports**: Generated in XML and HTML formats

## GitHub Actions Workflow

The `code-quality-security.yml` workflow runs on:
- Push to `kiro-rewrite` branch
- Pull requests to `kiro-rewrite` branch

### Workflow Jobs

1. **Code Quality** (Matrix: Python 3.9, 3.10, 3.11)
   - Code formatting check (Black)
   - Import sorting check (isort)
   - Linting (flake8)
   - Type checking (mypy)

2. **Security Scan**
   - Security scanning (Bandit)
   - Dependency vulnerability check (Safety)
   - Dependency audit (pip-audit)
   - Uploads security reports as artifacts

3. **Test Coverage**
   - Runs tests with coverage reporting
   - Enforces 80% minimum coverage
   - Uploads coverage reports to Codecov
   - Generates HTML coverage reports

4. **Quality Gate**
   - Validates all previous jobs passed
   - Provides consolidated status

## Local Development

### Pre-commit Hooks

Install pre-commit hooks to run checks locally:

```bash
pip install pre-commit
pre-commit install
```

This will run the same checks locally before each commit.

### Manual Commands

Run individual tools manually:

```bash
# Code formatting
black src/ tests/ lambda_functions/ examples/

# Import sorting
isort src/ tests/ lambda_functions/ examples/

# Linting
flake8 src/ tests/ lambda_functions/ examples/

# Type checking
mypy src/

# Security scanning
bandit -r src/ lambda_functions/

# Dependency checking
safety check
pip-audit

# Test coverage
pytest tests/ --cov=src --cov-report=html
```

## Configuration Files

- `.flake8`: Flake8 configuration
- `pyproject.toml`: Black, isort, mypy, bandit, and coverage configuration
- `.pre-commit-config.yaml`: Pre-commit hook configuration
- `requirements-dev.txt`: Development dependencies

## Quality Standards

### Code Coverage
- Minimum 80% test coverage required
- Coverage reports exclude test files and virtual environments
- HTML reports generated for detailed analysis

### Security
- All security scans must pass without high-severity issues
- Dependency vulnerabilities are tracked and reported
- Security reports are archived as workflow artifacts

### Code Style
- Black formatting enforced (127 character line length)
- Import statements organized with isort
- Flake8 linting with complexity limit of 10
- Type hints encouraged but not strictly enforced

## Troubleshooting

### Common Issues

1. **Black formatting conflicts**: Run `black .` to auto-format
2. **Import order issues**: Run `isort .` to fix import ordering
3. **Type checking errors**: Add `# type: ignore` comments for gradual adoption
4. **Security false positives**: Update `.bandit` configuration to skip specific checks

### Workflow Failures

- Check the Actions tab in GitHub for detailed error logs
- Download artifacts for security and coverage reports
- Review the quality gate job for consolidated status

## Integration

The code quality workflow integrates with:
- **GitHub branch protection**: Can be required for PR merges
- **Codecov**: Automatic coverage reporting and PR comments
- **Pre-commit**: Local development workflow
- **IDE integration**: Most tools support editor plugins