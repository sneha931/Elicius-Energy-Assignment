
import logging
import time

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.metrics import (
    cache_hits_total,
    cache_misses_total,
    rate_limit_exceeded_total,
)
from app.core.security import get_current_user
from app.schemas.chat import ChatRequest, ChatResponse, TokenUsage
from app.services.cache import cache_service
from app.services.llm import llm_service
from app.services.rate_limit import rate_limiter


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/chat",
    tags=["Chat"],
)


@router.post("", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    current_user: dict = Depends(get_current_user),
):
    start_time = time.perf_counter()

    # 1. Rate limiting
    try:
        allowed = await rate_limiter.is_allowed(
            user_id=current_user["id"],
            limit=30,
            window_seconds=60,
        )

        if not allowed:
            rate_limit_exceeded_total.inc()

            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Try again later.",
            )

    except HTTPException:
        raise

    except Exception as exc:
        logger.warning(
            "Rate limiter unavailable: %s",
            exc,
        )

    # 2. Check Redis cache
    try:
        cached_result = await cache_service.get(
            request.question
        )

        if cached_result:
            cache_hits_total.inc()

            latency_ms = (
                time.perf_counter() - start_time
            ) * 1000

            logger.info(
                "Cache hit for chat request"
            )

            return ChatResponse(
                answer=cached_result["answer"],
                model=cached_result["model"],
                tokens=TokenUsage(
                    prompt=cached_result["prompt_tokens"],
                    completion=cached_result["completion_tokens"],
                    total=cached_result["total_tokens"],
                ),
                latency_ms=round(latency_ms, 2),
            )

        # No cached response
        cache_misses_total.inc()

    except Exception as exc:
        logger.warning(
            "Redis cache read failed: %s",
            exc,
        )

    # 3. Cache miss → call LLM
    try:
        result = await llm_service.generate(
            request.question
        )

    except TimeoutError:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="LLM request timed out",
        )

    except Exception as exc:
        logger.error(
            "Chat request failed: %s",
            exc,
        )

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LLM service is currently unavailable",
        )

    # 4. Save response to Redis
    try:
        await cache_service.set(
            request.question,
            result,
            ttl=300,
        )

        logger.info(
            "Chat response cached"
        )

    except Exception as exc:
        logger.warning(
            "Redis cache write failed: %s",
            exc,
        )

    # 5. Calculate total API latency
    latency_ms = (
        time.perf_counter() - start_time
    ) * 1000

    # 6. Return response
    return ChatResponse(
        answer=result["answer"],
        model=result["model"],
        tokens=TokenUsage(
            prompt=result["prompt_tokens"],
            completion=result["completion_tokens"],
            total=result["total_tokens"],
        ),
        latency_ms=round(latency_ms, 2),
    )

