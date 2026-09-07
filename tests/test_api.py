from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.security import get_current_user


client = TestClient(app)


def override_current_user():
    return {
        "id": 1,
        "username": "admin",
        "role": "admin",
    }


app.dependency_overrides[get_current_user] = override_current_user


def test_root():
    response = client.get("/")

    assert response.status_code == 200
    assert response.json()["message"] == "AI Q&A API is running"


def test_chat_requires_authentication():
    app.dependency_overrides.pop(get_current_user, None)

    response = client.post(
        "/chat",
        json={"question": "What is Python?"},
    )

    assert response.status_code in [401, 403]

    app.dependency_overrides[get_current_user] = override_current_user


@patch(
    "app.api.chat.rate_limiter.is_allowed",
    new_callable=AsyncMock,
)
@patch(
    "app.api.chat.cache_service.get",
    new_callable=AsyncMock,
)
@patch(
    "app.api.chat.cache_service.set",
    new_callable=AsyncMock,
)
@patch(
    "app.api.chat.llm_service.generate",
    new_callable=AsyncMock,
)
def test_chat_success(
    mock_generate,
    mock_cache_set,
    mock_cache_get,
    mock_rate_limit,
):
    mock_rate_limit.return_value = True
    mock_cache_get.return_value = None

    mock_generate.return_value = {
        "answer": "Python is a programming language.",
        "model": "test-model",
        "prompt_tokens": 5,
        "completion_tokens": 8,
        "total_tokens": 13,
    }

    response = client.post(
        "/chat",
        json={
            "question": "What is Python?"
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["answer"] == "Python is a programming language."
    assert data["model"] == "test-model"
    assert data["tokens"]["total"] == 13
    assert "latency_ms" in data

    mock_generate.assert_awaited_once()
    mock_cache_set.assert_awaited_once()


@patch(
    "app.api.chat.rate_limiter.is_allowed",
    new_callable=AsyncMock,
)
@patch(
    "app.api.chat.cache_service.get",
    new_callable=AsyncMock,
)
def test_chat_cache_hit(
    mock_cache_get,
    mock_rate_limit,
):
    mock_rate_limit.return_value = True

    mock_cache_get.return_value = {
        "answer": "Cached answer",
        "model": "cached-model",
        "prompt_tokens": 4,
        "completion_tokens": 6,
        "total_tokens": 10,
    }

    response = client.post(
        "/chat",
        json={
            "question": "Cached question"
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["answer"] == "Cached answer"
    assert data["model"] == "cached-model"
    assert data["tokens"]["total"] == 10


@patch(
    "app.api.chat.rate_limiter.is_allowed",
    new_callable=AsyncMock,
)
def test_rate_limit(
    mock_rate_limit,
):
    mock_rate_limit.return_value = False

    response = client.post(
        "/chat",
        json={
            "question": "Too many requests"
        },
    )

    assert response.status_code == 429
    assert response.json()["detail"] == (
        "Rate limit exceeded. Try again later."
    )


@patch(
    "app.api.chat.rate_limiter.is_allowed",
    new_callable=AsyncMock,
)
@patch(
    "app.api.chat.cache_service.get",
    new_callable=AsyncMock,
)
@patch(
    "app.api.chat.llm_service.generate",
    new_callable=AsyncMock,
)
def test_llm_failure(
    mock_generate,
    mock_cache_get,
    mock_rate_limit,
):
    mock_rate_limit.return_value = True
    mock_cache_get.return_value = None

    mock_generate.side_effect = RuntimeError(
        "All configured LLM models failed"
    )

    response = client.post(
        "/chat",
        json={
            "question": "Will the LLM fail?"
        },
    )

    assert response.status_code == 503

    assert response.json()["detail"] == (
        "LLM service is currently unavailable"
    )


def test_invalid_question():
    response = client.post(
        "/chat",
        json={
            "question": ""
        },
    )

    assert response.status_code == 422


def test_question_too_long():
    response = client.post(
        "/chat",
        json={
            "question": "a" * 4001
        },
    )

    assert response.status_code == 422