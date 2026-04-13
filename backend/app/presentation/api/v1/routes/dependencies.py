from functools import lru_cache

from app.application.use_cases.delete_all_sessions import DeleteAllSessionsUseCase
from app.application.use_cases.delete_session import DeleteSessionUseCase
from app.application.use_cases.apply_fix import ApplyFixUseCase
from app.application.use_cases.rollback_fix import RollbackFixUseCase
from app.application.use_cases.explain_finding import ExplainFindingUseCase
from app.application.use_cases.generate_batch_remediation import GenerateBatchRemediationUseCase
from app.application.use_cases.generate_fix import GenerateFixUseCase
from app.application.use_cases.get_scan_job import GetScanJobUseCase
from app.application.use_cases.get_session import GetSessionUseCase
from app.application.use_cases.get_workflow_repo_hotspots import GetWorkflowRepoHotspotsUseCase
from app.application.use_cases.get_workflow_repo_intelligence_summary import GetWorkflowRepoIntelligenceSummaryUseCase
from app.application.use_cases.get_workflow_service_exposure_feed import GetWorkflowServiceExposureFeedUseCase
from app.application.use_cases.get_workflow_service_exposure_summary import GetWorkflowServiceExposureSummaryUseCase
from app.application.use_cases.get_workflow_team_posture_feed import GetWorkflowTeamPostureFeedUseCase
from app.application.use_cases.get_workflow_team_posture_summary import GetWorkflowTeamPostureSummaryUseCase
from app.application.use_cases.list_sessions import ListSessionsUseCase
from app.application.use_cases.reject_fix import RejectFixUseCase
from app.application.use_cases.retry_fix_strategy import RetryFixStrategyUseCase
from app.application.use_cases.start_scan import StartScanUseCase
from app.application.ports.scan_job_dispatcher import ScanJobDispatcher
from app.core.config import get_settings
from app.infrastructure.ai.agents.explain_agent import ExplainAgent
from app.infrastructure.ai.agents.fix_agent import FixAgent
from app.infrastructure.ai.agents.validation_agent import ValidationAgent
from app.domain.repositories.audit_event_repository import AuditEventRepository
from app.domain.repositories.scan_job_repository import ScanJobRepository
from app.domain.repositories.verification_run_repository import VerificationRunRepository
from app.domain.services.ai_client import SecurityAnalysisAIClient
from app.infrastructure.ai.provider_factory import build_ai_client
from app.infrastructure.ai.orchestration.remediation_router import RemediationRouter
from app.infrastructure.queue.scan_job_dispatcher import ArqScanJobDispatcher, InProcessScanJobDispatcher
from app.infrastructure.repositories.mongo_audit_event_repository import MongoAuditEventRepository
from app.infrastructure.repositories.mongo_scan_job_repository import MongoScanJobRepository
from app.infrastructure.repositories.mongo_scan_repository import MongoScanSessionRepository
from app.infrastructure.repositories.mongo_verification_run_repository import MongoVerificationRunRepository
from app.infrastructure.services.runtime_safety_policy import validate_provider_endpoints
from app.infrastructure.services.scan_lock_manager import ScanLockManager
from app.infrastructure.services.scan_execution_service import ScanExecutionService
from app.infrastructure.services.workflow_persistence import WorkflowPersistenceService


@lru_cache
def get_repository() -> MongoScanSessionRepository:
    return MongoScanSessionRepository()


@lru_cache
def get_scan_job_repository() -> ScanJobRepository:
    return MongoScanJobRepository()


@lru_cache
def get_audit_event_repository() -> AuditEventRepository:
    return MongoAuditEventRepository()


@lru_cache
def get_verification_run_repository() -> VerificationRunRepository:
    return MongoVerificationRunRepository()


@lru_cache
def get_workflow_persistence_service() -> WorkflowPersistenceService:
    return WorkflowPersistenceService(
        audit_events=get_audit_event_repository(),
        verification_runs=get_verification_run_repository(),
    )


@lru_cache
def get_scan_lock_manager() -> ScanLockManager:
    return ScanLockManager()


@lru_cache
def get_ai_client() -> SecurityAnalysisAIClient:
    validate_provider_endpoints()
    return build_ai_client()


@lru_cache
def get_scan_execution_service() -> ScanExecutionService:
    return ScanExecutionService(
        get_repository(),
        get_ai_client(),
        get_scan_job_repository(),
        get_workflow_persistence_service(),
        get_scan_lock_manager(),
    )


@lru_cache
def get_scan_job_dispatcher() -> ScanJobDispatcher:
    settings = get_settings()
    if settings.queue_backend == "arq":
        return ArqScanJobDispatcher(settings.scan_queue_name)
    return InProcessScanJobDispatcher(get_scan_execution_service())


@lru_cache
def get_remediation_router() -> RemediationRouter:
    ai_client = get_ai_client()
    return RemediationRouter(
        explain_agent=ExplainAgent(ai_client),
        fix_agent=FixAgent(ai_client),
        validation_agent=ValidationAgent(ai_client),
        model_router=ai_client.model_router,
    )


def get_start_scan_use_case() -> StartScanUseCase:
    return StartScanUseCase(
        get_repository(),
        get_scan_job_repository(),
        get_workflow_persistence_service(),
        get_scan_lock_manager(),
    )


def get_scan_job_use_case() -> GetScanJobUseCase:
    return GetScanJobUseCase(get_scan_job_repository())


def get_list_sessions_use_case() -> ListSessionsUseCase:
    return ListSessionsUseCase(get_repository())


def get_workflow_repo_intelligence_summary_use_case() -> GetWorkflowRepoIntelligenceSummaryUseCase:
    return GetWorkflowRepoIntelligenceSummaryUseCase(get_repository())


def get_workflow_repo_hotspots_use_case() -> GetWorkflowRepoHotspotsUseCase:
    return GetWorkflowRepoHotspotsUseCase(get_repository())


def get_workflow_team_posture_summary_use_case() -> GetWorkflowTeamPostureSummaryUseCase:
    return GetWorkflowTeamPostureSummaryUseCase(get_repository())


def get_workflow_team_posture_feed_use_case() -> GetWorkflowTeamPostureFeedUseCase:
    return GetWorkflowTeamPostureFeedUseCase(get_repository())


def get_workflow_service_exposure_summary_use_case() -> GetWorkflowServiceExposureSummaryUseCase:
    return GetWorkflowServiceExposureSummaryUseCase(get_repository())


def get_workflow_service_exposure_feed_use_case() -> GetWorkflowServiceExposureFeedUseCase:
    return GetWorkflowServiceExposureFeedUseCase(get_repository())


def get_session_use_case() -> GetSessionUseCase:
    return GetSessionUseCase(get_repository())


def get_delete_session_use_case() -> DeleteSessionUseCase:
    return DeleteSessionUseCase(get_repository(), get_workflow_persistence_service())


def get_delete_all_sessions_use_case() -> DeleteAllSessionsUseCase:
    return DeleteAllSessionsUseCase(get_repository(), get_workflow_persistence_service())


def get_explain_finding_use_case() -> ExplainFindingUseCase:
    return ExplainFindingUseCase(get_repository(), get_remediation_router(), get_workflow_persistence_service())


def get_generate_fix_use_case() -> GenerateFixUseCase:
    return GenerateFixUseCase(get_repository(), get_remediation_router(), get_workflow_persistence_service())


def get_generate_batch_remediation_use_case() -> GenerateBatchRemediationUseCase:
    return GenerateBatchRemediationUseCase(get_repository(), get_remediation_router(), get_workflow_persistence_service())


def get_apply_fix_use_case() -> ApplyFixUseCase:
    return ApplyFixUseCase(get_repository(), get_workflow_persistence_service())


def get_reject_fix_use_case() -> RejectFixUseCase:
    return RejectFixUseCase(get_repository(), get_workflow_persistence_service())


def get_retry_fix_strategy_use_case() -> RetryFixStrategyUseCase:
    return RetryFixStrategyUseCase(get_repository(), get_remediation_router(), get_workflow_persistence_service())


def get_rollback_fix_use_case() -> RollbackFixUseCase:
    return RollbackFixUseCase(get_repository(), get_workflow_persistence_service())
