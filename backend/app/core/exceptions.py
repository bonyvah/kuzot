from fastapi import HTTPException, status


class CompetitorNotFoundError(HTTPException):
    def __init__(self, competitor_id: str) -> None:
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Competitor with id '{competitor_id}' not found"
        )

class MonitoredURLNotFoundError(HTTPException):
    def __init__(self, url_id: str) -> None:
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Monitored URL with id '{url_id}' not found"
        )

class ScrapingError(HTTPException):
    def __init__(self, url: str, reason: str) -> None:
        super().__init__(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to scrape '{url}': {reason}"
        )

class EmbeddingError(HTTPException):
    def __init__(self, reason: str) -> None:
        super().__init__(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Embedding pipeline failed: '{reason}'"
        )
