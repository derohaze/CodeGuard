from bson import ObjectId

from app.domain.entities.scan_job import ScanJobEntity
from app.domain.repositories.scan_job_repository import ScanJobRepository
from app.infrastructure.database.collections import SCAN_JOBS_COLLECTION
from app.infrastructure.database.mongo import get_database


class MongoScanJobRepository(ScanJobRepository):
    def __init__(self) -> None:
        self.collection = get_database()[SCAN_JOBS_COLLECTION]

    async def create(self, job: ScanJobEntity) -> ScanJobEntity:
        await self.collection.insert_one(_entity_to_document(job))
        return job

    async def update(self, job_id: str, updates: dict) -> ScanJobEntity | None:
        await self.collection.update_one({"_id": ObjectId(job_id)}, {"$set": dict(updates)})
        return await self.get_by_id(job_id)

    async def get_by_id(self, job_id: str) -> ScanJobEntity | None:
        document = await self.collection.find_one({"_id": ObjectId(job_id)})
        if document is None:
            return None
        return _document_to_entity(document)

    async def list_by_session(self, session_id: str, limit: int = 25) -> list[ScanJobEntity]:
        cursor = self.collection.find({"session_id": session_id}).sort("created_at", -1).limit(limit)
        return [_document_to_entity(document) async for document in cursor]

    async def count_active(self) -> int:
        return int(await self.collection.count_documents({"status": {"$in": ["queued", "running"]}}))

    async def find_active_by_source(self, source_fingerprint: str) -> ScanJobEntity | None:
        document = await (
            self.collection.find(
                {
                    "source_fingerprint": source_fingerprint,
                    "status": {"$in": ["queued", "running"]},
                }
            )
            .sort("created_at", -1)
            .limit(1)
            .to_list(length=1)
        )
        if not document:
            return None
        return _document_to_entity(document[0])


def _entity_to_document(job: ScanJobEntity) -> dict:
    return {
        "_id": ObjectId(job.id),
        "job_id": job.id,
        "session_id": job.session_id,
        "source_fingerprint": job.source_fingerprint,
        "type": job.job_type,
        "status": job.status,
        "stage": job.stage,
        "progress": job.progress,
        "attempts": job.attempts,
        "queue_name": job.queue_name,
        "submission_key": job.submission_key,
        "lock_owner": job.lock_owner,
        "error_message": job.error_message,
        "created_at": job.created_at,
        "started_at": job.started_at,
        "finished_at": job.finished_at,
    }


def _document_to_entity(document: dict) -> ScanJobEntity:
    return ScanJobEntity(
        id=str(document["_id"]),
        session_id=document["session_id"],
        source_fingerprint=document.get("source_fingerprint", ""),
        job_type=document.get("type", "scan"),
        status=document["status"],
        stage=document["stage"],
        progress=int(document.get("progress", 0)),
        attempts=int(document.get("attempts", 0)),
        queue_name=document.get("queue_name"),
        submission_key=document.get("submission_key"),
        lock_owner=document.get("lock_owner"),
        error_message=document.get("error_message"),
        created_at=document["created_at"],
        started_at=document.get("started_at"),
        finished_at=document.get("finished_at"),
    )
