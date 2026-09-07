import pytest


@pytest.fixture
def auth_token():
    """
    Test JWT token payload.
    The chat endpoint will be overridden in individual tests,
    so no real authentication service is required.
    """
    return "test-token"