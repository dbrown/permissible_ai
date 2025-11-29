# Testing Guide for Permissible

This document describes how to run and write tests for the Permissible application.

## Quick Start

### Install Test Dependencies

```bash
pip install -r requirements-test.txt
```

### Run All Tests

```bash
pytest
```

Or use the test runner script:

```bash
./run_tests.sh
```

## Test Organization

```
tests/
├── __init__.py
├── conftest.py                    # Pytest fixtures and configuration
├── test_api_key_model.py         # API Key model tests
├── test_api_key_routes.py        # API Key CRUD route tests
└── test_api_authentication.py    # API authentication tests
```

## Running Tests

### Run All Tests

```bash
pytest
```

### Run Tests with Coverage

```bash
pytest --cov=app --cov-report=html --cov-report=term
```

Or use the script:

```bash
./run_tests.sh coverage
```

Then open `htmlcov/index.html` in your browser to see the coverage report.

### Run Specific Test File

```bash
pytest tests/test_api_key_model.py
```

Or:

```bash
./run_tests.sh specific tests/test_api_key_model.py
```

### Run Specific Test Class

```bash
pytest tests/test_api_key_model.py::TestAPIKeyModel
```

### Run Specific Test Method

```bash
pytest tests/test_api_key_model.py::TestAPIKeyModel::test_generate_key
```

### Run Tests Matching a Pattern

```bash
pytest -k "test_create"
```

### Run Tests with Verbose Output

```bash
pytest -v
```

Or:

```bash
./run_tests.sh verbose
```

## Test Fixtures

The `conftest.py` file provides several useful fixtures:

### `app`
Creates a test Flask application instance with in-memory SQLite database.

```python
def test_something(app):
    with app.app_context():
        # Your test code here
```

### `client`
Creates a test client for making HTTP requests.

```python
def test_endpoint(client):
    response = client.get('/api/health')
    assert response.status_code == 200
```

### `regular_user`
Creates a regular (non-admin) user.

```python
def test_user_feature(regular_user):
    assert regular_user['email'] == 'user@example.com'
    assert regular_user['is_admin'] is False
```

### `admin_user`
Creates an admin user.

```python
def test_admin_feature(admin_user):
    assert admin_user['is_admin'] is True
```

### `api_key_for_user`
Creates an API key for the regular user.

```python
def test_api_key_feature(api_key_for_user):
    assert len(api_key_for_user['key']) > 40
```

### `authenticated_client`
Creates a test client with an authenticated regular user session.

```python
def test_protected_route(authenticated_client):
    response = authenticated_client.get('/dashboard')
    assert response.status_code == 200
```

### `admin_authenticated_client`
Creates a test client with an authenticated admin user session.

```python
def test_admin_route(admin_authenticated_client):
    response = admin_authenticated_client.get('/admin/users')
    assert response.status_code == 200
```

## Writing New Tests

### Model Tests

Place in `tests/test_<model_name>_model.py`:

```python
class TestYourModel:
    def test_create(self, app):
        with app.app_context():
            # Create model instance
            # Test assertions
```

### Route Tests

Place in `tests/test_<feature>_routes.py`:

```python
class TestYourRoutes:
    def test_endpoint(self, client):
        response = client.get('/your/endpoint')
        assert response.status_code == 200
```

### API Tests

Place in `tests/test_<feature>_api.py`:

```python
class TestYourAPI:
    def test_api_endpoint(self, client, api_key_for_user):
        response = client.get(
            '/api/your-endpoint',
            headers={'Authorization': f'Bearer {api_key_for_user["key"]}'}
        )
        assert response.status_code == 200
```

## Test Coverage

Current test coverage includes:

### API Key Model (`test_api_key_model.py`)
- ✅ Key generation and uniqueness
- ✅ Creating API keys
- ✅ User relationships
- ✅ Key retrieval by value
- ✅ Active/inactive key handling
- ✅ Last used tracking
- ✅ Key deactivation
- ✅ User lookup by API key
- ✅ Cascade deletion

### API Key Routes (`test_api_key_routes.py`)
- ✅ List keys (authenticated/unauthenticated)
- ✅ Create keys with validation
- ✅ Maximum key limit enforcement
- ✅ Key display and security
- ✅ Delete keys with ownership verification
- ✅ Rename keys with validation
- ✅ Permission checks
- ✅ Active/inactive filtering

### API Authentication (`test_api_authentication.py`)
- ✅ Public endpoints (no auth required)
- ✅ Protected endpoints (auth required)
- ✅ Bearer token authentication
- ✅ X-API-Key header authentication
- ✅ Query parameter authentication
- ✅ Invalid key rejection
- ✅ Inactive key rejection
- ✅ Last used timestamp updates
- ✅ User info endpoint
- ✅ Admin-only endpoints
- ✅ Security features

## Continuous Integration

To integrate with CI/CD pipelines:

### GitHub Actions Example

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v2
    
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: '3.8'
    
    - name: Install dependencies
      run: |
        cd web_api
        pip install -r requirements-test.txt
    
    - name: Run tests
      run: |
        cd web_api
        pytest --cov=app --cov-report=xml
    
    - name: Upload coverage
      uses: codecov/codecov-action@v2
```

## Best Practices

1. **Use fixtures**: Leverage pytest fixtures for common setup
2. **Test isolation**: Each test should be independent
3. **Clear assertions**: Use descriptive assertion messages
4. **Test edge cases**: Include boundary conditions and error cases
5. **Mock external services**: Don't make real API calls in tests
6. **Fast tests**: Use in-memory database (SQLite) for speed
7. **Descriptive names**: Test names should describe what they test

## Troubleshooting

### Import Errors

If you get import errors, make sure you're in the web_api directory:

```bash
cd web_api
pytest
```

### Database Errors

Tests use an in-memory SQLite database that's created and destroyed for each test. If you see database errors, check that the testing configuration in `config.py` is correct.

### Fixture Not Found

Make sure `conftest.py` is in the tests directory and pytest can find it.

## Further Reading

- [Pytest Documentation](https://docs.pytest.org/)
- [Flask Testing Documentation](https://flask.palletsprojects.com/en/3.0.x/testing/)
- [pytest-flask Documentation](https://pytest-flask.readthedocs.io/)
