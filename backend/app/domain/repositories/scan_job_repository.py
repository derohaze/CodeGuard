from abc import ABC, abstractmethod

from app.domain.entities.scan_job import ScanJobEntity


class ScanJobRepository(ABC):
    @abstractmethod
    async def create(self, job: ScanJobEntity) -> ScanJobEntity:
        raise NotImplementedError

    @abstractmethod
    async def update(self, job_id: str, updates: dict) -> ScanJobEntity | None:
        raise NotImplementedError

    @abstractmethod
    async def get_by_id(self, job_id: str) -> ScanJobEntity | None:
        raise NotImplementedError

    @abstractmethod
    async def list_by_session(self, session_id: str, limit: int = 25) -> list[ScanJobEntity]:
        raise NotImplementedError

    @abstractmethod
    async def list_active(self, limit: int = 200) -> list[ScanJobEntity]:
        raise NotImplementedError

    @abstractmethod
    async def count_active(self) -> int:
        raise NotImplementedError

    @abstractmethod
    async def find_active_by_source(self, source_fingerprint: str) -> ScanJobEntity | None:
        raise NotImplementedError
