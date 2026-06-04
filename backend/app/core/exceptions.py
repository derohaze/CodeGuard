class AegixError(Exception):
    pass


class InvalidSourcePathError(AegixError):
    pass


class ExternalAIServiceError(AegixError):
    def __init__(
        self,
        message: str,
        *,
        provider: str = "ai_provider",
        retryable: bool = True,
        status_code: int | None = None,
        failure_kind: str = "runtime",
        retry_after_seconds: float | None = None,
    ) -> None:
        super().__init__(message)
        self.provider = provider
        self.retryable = retryable
        self.status_code = status_code
        self.failure_kind = failure_kind
        self.retry_after_seconds = retry_after_seconds


class WorkflowConflictError(AegixError):
    pass
