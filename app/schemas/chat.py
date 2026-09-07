from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    question: str = Field(
        ...,
        min_length=1,
        max_length=4000,
    )


class TokenUsage(BaseModel):
    prompt: int
    completion: int
    total: int


class ChatResponse(BaseModel):
    answer: str
    model: str
    tokens: TokenUsage
    latency_ms: float