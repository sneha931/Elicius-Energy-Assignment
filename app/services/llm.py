import asyncio
import logging

from openai import AsyncOpenAI

from app.core.config import settings
from app.core.metrics import (
    llm_requests_total,
    llm_request_duration_seconds,
    llm_tokens_total,
)

logger = logging.getLogger(__name__)


class LLMService:
    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=settings.llm_api_key,
            base_url="https://openrouter.ai/api/v1",
            default_headers={
                "HTTP-Referer": "http://localhost:8000",
                "X-OpenRouter-Title": "AI Q&A Platform",
            },
        )

        self.timeout_seconds = 30

    async def _call_llm(self, question: str, model: str):
        start_time = asyncio.get_running_loop().time()

        try:
            logger.info("Calling LLM model: %s", model)

            response = await asyncio.wait_for(
                self.client.chat.completions.create(
                    model=model,
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are a helpful AI assistant. "
                                "Answer the user's question clearly "
                                "and accurately."
                            ),
                        },
                        {
                            "role": "user",
                            "content": question,
                        },
                    ],
                ),
                timeout=self.timeout_seconds,
            )

            duration = (
                asyncio.get_running_loop().time()
                - start_time
            )

            llm_requests_total.labels(
                model=model,
                status="success",
            ).inc()

            llm_request_duration_seconds.labels(
                model=model,
            ).observe(duration)

            answer = response.choices[0].message.content or ""
            usage = response.usage

            prompt_tokens = (
                usage.prompt_tokens
                if usage
                else 0
            )

            completion_tokens = (
                usage.completion_tokens
                if usage
                else 0
            )

            total_tokens = (
                usage.total_tokens
                if usage
                else 0
            )

            llm_tokens_total.labels(
                model=model,
                token_type="prompt",
            ).inc(prompt_tokens)

            llm_tokens_total.labels(
                model=model,
                token_type="completion",
            ).inc(completion_tokens)

            return {
                "answer": answer,
                "model": response.model,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
            }

        except asyncio.TimeoutError:
            duration = (
                asyncio.get_running_loop().time()
                - start_time
            )

            llm_requests_total.labels(
                model=model,
                status="timeout",
            ).inc()

            llm_request_duration_seconds.labels(
                model=model,
            ).observe(duration)

            logger.warning(
                "LLM timeout after %s seconds: %s",
                self.timeout_seconds,
                model,
            )

            raise

        except Exception as exc:
            duration = (
                asyncio.get_running_loop().time()
                - start_time
            )

            llm_requests_total.labels(
                model=model,
                status="error",
            ).inc()

            llm_request_duration_seconds.labels(
                model=model,
            ).observe(duration)

            logger.warning(
                "LLM error for %s: %s",
                model,
                exc,
            )

            raise

    async def generate(self, question: str):
        primary_model = settings.llm_model
        fallback_model = settings.llm_fallback_model

        # Primary attempt
        try:
            return await self._call_llm(
                question,
                primary_model,
            )

        except asyncio.TimeoutError:
            logger.warning(
                "Primary LLM timed out: %s",
                primary_model,
            )

        except Exception as exc:
            logger.warning(
                "Primary LLM failed: %s",
                exc,
            )

        # Fallback attempt
        try:
            logger.info(
                "Trying fallback LLM: %s",
                fallback_model,
            )

            return await self._call_llm(
                question,
                fallback_model,
            )

        except asyncio.TimeoutError:
            logger.error(
                "Fallback LLM timed out: %s",
                fallback_model,
            )

        except Exception as exc:
            logger.error(
                "Fallback LLM failed: %s",
                exc,
            )

        raise RuntimeError(
            "All configured LLM providers/models failed"
        )


llm_service = LLMService()