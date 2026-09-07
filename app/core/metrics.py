from prometheus_client import Counter, Histogram


llm_requests_total = Counter(
    "llm_requests_total",
    "Total number of LLM requests",
    ["model", "status"],
)

llm_request_duration_seconds = Histogram(
    "llm_request_duration_seconds",
    "LLM request duration in seconds",
    ["model"],
)

llm_tokens_total = Counter(
    "llm_tokens_total",
    "Total number of LLM tokens",
    ["model", "token_type"],
)

cache_hits_total = Counter(
    "cache_hits_total",
    "Total number of Redis cache hits",
)

cache_misses_total = Counter(
    "cache_misses_total",
    "Total number of Redis cache misses",
)

rate_limit_exceeded_total = Counter(
    "rate_limit_exceeded_total",
    "Total number of rate limit violations",
)