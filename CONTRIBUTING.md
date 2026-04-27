# 🤝 Contributing to PhantomStrike

Thank you for your interest in contributing to PhantomStrike! This document provides guidelines for contributing to this project.

## 📋 Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [How to Contribute](#how-to-contribute)
- [Development Setup](#development-setup)
- [Pull Request Process](#pull-request-process)
- [Coding Standards](#coding-standards)
- [Security Issues](#security-issues)

## 📜 Code of Conduct

This project adheres to a code of conduct. By participating, you are expected to uphold this code:

- Be respectful and inclusive
- Welcome newcomers
- Focus on constructive feedback
- Respect different viewpoints and experiences

## 🚀 Getting Started

1. **Fork the repository** on GitHub
2. **Clone your fork** locally
3. **Set up development environment**
4. **Create a branch** for your changes

```bash
# Fork on GitHub, then:
git clone https://github.com/YOUR_USERNAME/phantom-strike.git
cd phantom-strike
git checkout -b feature/your-feature-name
```

## 💡 How to Contribute

### Reporting Bugs

Before creating a bug report:

1. Check if the issue already exists
2. Collect information about the bug:
   - Version being used
   - Steps to reproduce
   - Expected vs actual behavior
   - Error messages/logs

Use the [Bug Report Template](.github/ISSUE_TEMPLATE/bug_report.md)

### Suggesting Enhancements

Enhancement suggestions are tracked as GitHub issues. Provide:

- Clear use case
- Detailed description
- Possible implementation approach
- Why this would be useful

Use the [Feature Request Template](.github/ISSUE_TEMPLATE/feature_request.md)

### Adding New Modules

PhantomStrike is modular! To add a new module:

1. Create module in `phantom/modules/<module_name>/`
2. Implement `engine.py` with `BaseModule` interface
3. Add tests in `tests/test_<module_name>.py`
4. Update documentation

Example structure:
```
phantom/modules/
└── your_module/
    ├── __init__.py
    ├── engine.py
    ├── payloads/
    │   └── __init__.py
    └── config.yaml
```

## 🔧 Development Setup

```bash
# Clone and setup
git clone https://github.com/thecnical/phantom-strike.git
cd phantom-strike
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dev dependencies
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install

# Run tests
pytest tests/ -v

# Run linting
black phantom/
ruff check phantom/
```

## 📝 Pull Request Process

1. **Update documentation** for any changed functionality
2. **Add tests** for new code
3. **Ensure all tests pass**
4. **Update CHANGELOG.md** if applicable
5. **Reference issues** your PR addresses

### PR Checklist

- [ ] Code follows style guidelines
- [ ] Tests added/updated
- [ ] Documentation updated
- [ ] CHANGELOG updated
- [ ] No security vulnerabilities introduced
- [ ] Commit messages are clear

### Commit Message Format

```
type(scope): subject

body (optional)

footer (optional)
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting)
- `refactor`: Code refactoring
- `test`: Adding/updating tests
- `chore`: Build process, dependencies

Examples:
```
feat(ai): add Cerebras provider support
fix(web): resolve blind SQLi false positives
docs(readme): update installation instructions
```

## 📐 Coding Standards

### Python Style Guide

- Follow [PEP 8](https://pep8.org/)
- Use `black` for formatting
- Maximum line length: 100 characters
- Use type hints where possible
- Docstrings for all public functions/classes

### Example:

```python
from typing import Optional, Dict, Any

async def scan_target(
    target: str,
    scan_type: str = "full",
    options: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Scan a target with specified options.
    
    Args:
        target: URL or IP to scan
        scan_type: Type of scan (full, web, network, cloud)
        options: Optional scan configuration
        
    Returns:
        Dictionary containing scan results
        
    Raises:
        ValueError: If target is invalid
        ConnectionError: If target unreachable
    """
    # Implementation
    pass
```

### Testing Standards

- Use `pytest` for all tests
- Minimum 80% code coverage
- Test both success and error cases
- Use fixtures for common setup
- Mock external API calls

### Example Test:

```python
import pytest
from phantom.modules.web.engine import WebEngine

@pytest.fixture
def web_engine():
    return WebEngine({})

@pytest.mark.asyncio
async def test_sql_detection(web_engine):
    result = await web_engine._test_sql_injection("http://test.com/search?q=test")
    assert isinstance(result, list)
```

## 🔒 Security Issues

**DO NOT** create public issues for security vulnerabilities.

Instead:
1. Email: security@phantomstrike.dev
2. Include detailed description
3. Provide steps to reproduce
4. Allow time for fix before disclosure

We follow responsible disclosure practices.

## 🏆 Recognition

Contributors will be:
- Listed in CONTRIBUTORS.md
- Mentioned in release notes
- Added to project README (significant contributions)

## 📞 Questions?

- [GitHub Discussions](https://github.com/thecnical/phantom-strike/discussions)
- [Discord Community](https://discord.gg/phantomstrike) (coming soon)
- Email: chandanabhay4456@gmail.com

---

Thank you for making PhantomStrike better! 🚀
