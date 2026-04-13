import asyncio
import copy
import logging
from pathlib import Path
import time

from bson import ObjectId

from app.core.exceptions import ExternalAIServiceError, InvalidSourcePathError
from app.domain.entities.scan_job import build_scan_job_snapshot
from app.domain.entities.scan import FindingEntity, ScanSessionEntity, utc_now
from app.domain.repositories.scan_job_repository import ScanJobRepository
from app.domain.repositories.scan_repository import ScanSessionRepository
from app.domain.services.ai_client import SecurityAnalysisAIClient
from app.infrastructure.services.workflow_persistence import WorkflowPersistenceService
from app.infrastructure.services.coverage_calculation import build_progress_state, calculate_progress_metrics
from app.infrastructure.services.duplicate_clustering import cluster_findings
from app.infrastructure.services.evidence_extraction import extract_evidence
from app.infrastructure.services.framework_detection import detect_framework_profile
from app.infrastructure.services.path_tracing import trace_candidate_paths
from app.infrastructure.services.repository_analysis import (
    adaptive_chunk_work_items,
    build_finding_id,
    build_repository_artifacts,
    build_repository_profile,
    collect_files,
    default_fix_suggestions,
    read_text,
    run_precise_heuristics,
    severity_rank,
)
from app.infrastructure.services.repository_graph import build_repository_graph
from app.infrastructure.services.scan_coverage import (
    build_coverage_snapshot,
    build_file_segments,
)
from app.infrastructure.services.scope_planning import build_scan_plan
from app.infrastructure.services.score_calibration import calibrate_security_score
from app.infrastructure.services.scan_identity import (
    build_analysis_cache_key,
    build_repository_snapshot_fingerprint,
    build_source_fingerprint,
)
from app.infrastructure.services.scan_lock_manager import ScanLockLease, ScanLockManager
from app.infrastructure.services.runtime_safety_policy import sanitize_runtime_error
from app.infrastructure.services.scan_modes import ScanModeConfig, get_scan_mode_config
from app.infrastructure.services.segmentation_planning import build_scan_work_units
from app.infrastructure.services.risk_prioritization import prioritize_review_queue
from app.infrastructure.services.source_sink_registry import build_source_sink_registry

logger = logging.getLogger("codeguard.scan")


def create_initial_session(source_path: str, target_type: str, preset: str, scan_mode: str = "deep") -> ScanSessionEntity:
    path = Path(source_path).expanduser().resolve()
    if not path.exists():
        raise InvalidSourcePathError(f"Source path does not exist: {source_path}")
    if target_type == "file" and not path.is_file():
        raise InvalidSourcePathError("Expected a file source but received a folder path.")
    if target_type == "folder" and not path.is_dir():
        raise InvalidSourcePathError("Expected a folder source but received a file path.")

    return ScanSessionEntity(
        id=str(ObjectId()),
        title=f"Scan {path.name}",
        repo=path.name,
        source_path=str(path),
        source_fingerprint=build_source_fingerprint(str(path), target_type),
        target_type=target_type,
        preset=preset,
        scan_mode="fast" if scan_mode == "fast" else "deep",
        status="queued",
        progress=0,
        progress_message="Queued for analysis",
        current_phase="Queued",
        elapsed_seconds=0,
        preview="Scan is queued and will start shortly.",
        progress_logs=["Queued the selected source for security analysis."],
        scan_plan={
            "scan_mode": "fast" if scan_mode == "fast" else "deep",
            "mode_label": "Fast Scan" if scan_mode == "fast" else "Deep Scan",
            "coverage_target_percent": 45 if scan_mode == "fast" else 95,
            "work_unit_strategy": {},
        },
    )


class ScanExecutionService:
    _MAX_ANALYSIS_CACHE_ENTRIES = 8

    def __init__(
        self,
        repository: ScanSessionRepository,
        ai_client: SecurityAnalysisAIClient,
        job_repository: ScanJobRepository | None = None,
        workflow_persistence: WorkflowPersistenceService | None = None,
        scan_lock_manager: ScanLockManager | None = None,
    ) -> None:
        self.repository = repository
        self.ai_client = ai_client
        self.job_repository = job_repository
        self.workflow_persistence = workflow_persistence
        self.scan_lock_manager = scan_lock_manager
        self._analysis_cache: dict[str, dict] = {}

    async def submit(self, session_id: str, job_id: str | None = None) -> None:
        asyncio.create_task(self.run(session_id, job_id=job_id))

    async def run(self, session_id: str, job_id: str | None = None) -> None:
        session = await self.repository.get_by_id(session_id)
        if session is None:
            return

        logs = list(session.progress_logs)
        started_at = time.monotonic()
        lock_lease: ScanLockLease | None = None
        if job_id and self.job_repository is not None and self.scan_lock_manager is not None:
            job = await self.job_repository.get_by_id(job_id)
            if job is not None:
                lock_lease = await self.scan_lock_manager.build_lease_from_job(
                    session_id=session_id,
                    source_fingerprint=job.source_fingerprint or session.source_fingerprint,
                    owner=job.lock_owner,
                )
                await self.scan_lock_manager.refresh_submission_locks(lock_lease)
        try:
            getattr(self.ai_client, "reset_runtime_state", lambda: None)()
            source = Path(session.source_path)
            source_root = source if source.is_dir() else source.parent
            mode_config = get_scan_mode_config(session.scan_mode)

            if job_id and self.job_repository is not None:
                await self._update_job(
                    session_id,
                    job_id,
                    status="running",
                    stage="discovery",
                    progress=1,
                    attempts=1,
                    started_at=utc_now(),
                    error_message=None,
                )
            if self.workflow_persistence is not None:
                await self.workflow_persistence.record_audit(
                    session_id=session_id,
                    entity_type="scan_job",
                    entity_id=job_id or session_id,
                    action="scan.started",
                    payload={
                        "repo": session.repo,
                        "scan_mode": session.scan_mode,
                        "target_type": session.target_type,
                    },
                )

            await self._update_with_logs(
                session_id,
                logs,
                "Collecting repository files",
                "Indexing the selected source and discovering the codebase shape.",
                lock_lease=lock_lease,
                job_id=job_id,
                job_stage="discovery",
                status="scanning",
                scan_mode=session.scan_mode,
                current_phase="Discovery",
                started_at=started_at,
                progress_counters={
                    "files_indexed": 0,
                    "files_total": 1,
                },
            )

            files = collect_files(source, session.target_type)
            profile = build_repository_profile(source_root, files)
            scan_plan = build_scan_plan(
                source_path=source,
                target_type=session.target_type,
                preset=session.preset,
                scan_mode=session.scan_mode,
                repository_profile=profile,
            )
            framework_profile = detect_framework_profile(source_root, files, profile)
            snapshot_fingerprint = build_repository_snapshot_fingerprint(source_root, files)
            source_fingerprint = session.source_fingerprint or build_source_fingerprint(
                session.source_path,
                session.target_type,
            )
            analysis_cache_key = build_analysis_cache_key(
                source_fingerprint=source_fingerprint,
                snapshot_fingerprint=snapshot_fingerprint,
                scan_mode=session.scan_mode,
                target_type=session.target_type,
                preset=session.preset,
            )
            cached_analysis = self._get_cached_analysis(analysis_cache_key)
            if cached_analysis is None:
                repository_artifacts = build_repository_artifacts(source_root, files, profile)
                repository_graph = build_repository_graph(source_root, files, framework_profile)
                security_registry = build_source_sink_registry(source_root, files, framework_profile)
                traced_paths = trace_candidate_paths(source_root, repository_graph, security_registry, files)
                file_segments = build_file_segments(files, source_root, scan_mode=session.scan_mode)
                self._set_cached_analysis(
                    analysis_cache_key,
                    {
                        "repository_artifacts": repository_artifacts,
                        "repository_graph": repository_graph,
                        "security_registry": security_registry,
                        "traced_paths": traced_paths,
                        "file_segments": file_segments,
                    },
                )
                logs.append("Built fresh repository graph and path-tracing artifacts.")
            else:
                repository_artifacts = cached_analysis["repository_artifacts"]
                repository_graph = cached_analysis["repository_graph"]
                security_registry = cached_analysis["security_registry"]
                traced_paths = cached_analysis["traced_paths"]
                file_segments = cached_analysis["file_segments"]
                logs.append("Reused incremental analysis cache for repository graph and path tracing.")
            excluded_review_file_count = sum(1 for item in file_segments if int(item.get("block_count", 0)) == 0)
            heuristic_candidates = collect_heuristic_candidates(files, source_root)
            repository_inventory = build_repository_inventory(profile, files)

            logs.append(f"Indexed {profile['file_count']} code files across {profile['directory_count']} directories.")
            if framework_profile["frameworks"]:
                logs.append(f"Detected stack hints: {', '.join(framework_profile['frameworks'][:4])}.")
            else:
                logs.append(f"Detected primary languages: {', '.join(profile['languages'][:4]) or 'unknown'}.")
            logs.append(
                (
                    "Framework markers: none; language profile: "
                    if framework_profile["primary_framework"] == "unknown"
                    and framework_profile["support_matrix"]["primary"]["stack"] != "unknown"
                    else "Framework confidence: "
                )
                + f"{framework_profile['support_matrix']['primary']['stack']} "
                + f"({framework_profile['support_matrix']['primary']['confidence']})."
            )
            logs.append(
                f"Mapped {repository_artifacts['coverage']['route_files']} route files, "
                f"{repository_artifacts['coverage']['auth_files']} auth files, and "
                f"{repository_artifacts['coverage']['sink_candidates']} sensitive sink markers."
            )
            logs.append(
                f"Built repository graphs with {repository_graph['summary']['import_edges']} import edges, "
                f"{repository_graph['summary']['route_files']} route nodes, and "
                f"{traced_paths['summary']['candidate_path_count']} candidate source-to-sink paths."
            )
            if file_segments:
                logs.append(
                    f"Segmented {len(file_segments)} supported files into "
                    f"{sum(item['block_count'] for item in file_segments)} reviewable code blocks."
                )
            if excluded_review_file_count:
                logs.append(f"{excluded_review_file_count} file(s) contained no reviewable code blocks and will be treated as excluded from block review.")

            await self._update_with_logs(
                session_id,
                logs,
                "Mapping trust boundaries",
                "Building the route map, auth boundaries, imports, sinks, and untrusted-input sources.",
                lock_lease=lock_lease,
                job_id=job_id,
                job_stage="mapping",
                scan_mode=session.scan_mode,
                current_phase="Repository mapping",
                started_at=started_at,
                progress_counters={
                    "mapping_artifacts_ready": 6,
                    "mapping_artifacts_total": 6,
                    "mapping_ai_steps_completed": 0,
                    "mapping_ai_steps_total": 1,
                    "files_indexed": profile["file_count"],
                    "files_total": profile["file_count"],
                },
                scan_plan=scan_plan,
                repository_inventory=repository_inventory,
                framework_profile=framework_profile,
                repository_graph=repository_graph,
                graph_summary=repository_graph["summary"],
                security_registry={"summary": security_registry["summary"]},
                segmentation_summary={
                    "files_with_segments": len(file_segments),
                    "block_units_total": sum(item["block_count"] for item in file_segments),
                },
                path_inventory={"summary": traced_paths["summary"], "paths": traced_paths.get("paths", [])[:12]},
                path_summary=traced_paths["summary"],
                **calculate_progress_metrics(
                    reviewed_files_count=excluded_review_file_count,
                    eligible_files_count=profile["file_count"],
                    blocks_reviewed=0,
                    blocks_total=sum(item["block_count"] for item in file_segments),
                    paths_traced=traced_paths["summary"]["candidate_path_count"],
                    paths_total=traced_paths["summary"]["candidate_path_count"],
                    validated_findings_count=0,
                    candidate_findings_count=0,
                    coverage_percent=0,
                ),
            )

            repository_map = await self.ai_client.map_repository(
                project_name=session.repo,
                source_path=session.source_path,
                repository_profile=profile,
                repository_artifacts={
                    **repository_artifacts,
                    "framework_profile": framework_profile,
                    "repository_graph_summary": repository_graph["summary"],
                    "security_registry_summary": security_registry["summary"],
                    "path_summary": traced_paths["summary"],
                },
                preset=session.preset,
            )
            self._append_runtime_events(logs)
            if repository_map.get("review_note"):
                logs.append(repository_map["review_note"])
            if repository_map.get("coverage_note"):
                logs.append(repository_map["coverage_note"])
            for boundary in repository_map.get("trust_boundaries", [])[:3]:
                logs.append(boundary)

            await self._update_with_logs(
                session_id,
                logs,
                "Mapping trust boundaries",
                "Building the route map, auth boundaries, imports, sinks, and untrusted-input sources.",
                lock_lease=lock_lease,
                job_id=job_id,
                job_stage="mapping",
                scan_mode=session.scan_mode,
                current_phase="Repository mapping",
                started_at=started_at,
                progress_counters={
                    "mapping_artifacts_ready": 6,
                    "mapping_artifacts_total": 6,
                    "mapping_ai_steps_completed": 1,
                    "mapping_ai_steps_total": 1,
                    "files_indexed": profile["file_count"],
                    "files_total": profile["file_count"],
                },
            )

            await self._update_with_logs(
                session_id,
                logs,
                "Prioritizing attack surfaces",
                "Selecting the highest-risk paths for deeper security review.",
                lock_lease=lock_lease,
                job_id=job_id,
                job_stage="segmentation",
                scan_mode=session.scan_mode,
                current_phase="Segmentation",
                started_at=started_at,
                progress_counters={
                    "files_segmented": 0,
                    "files_to_segment": max(1, len(file_segments)),
                },
            )

            work_units = build_scan_work_units(
                scan_mode=session.scan_mode,
                files=files,
                source_root=source_root,
                repository_artifacts=repository_artifacts,
                repository_map=repository_map,
                file_segments=file_segments,
                target_type=session.target_type,
                traced_paths=traced_paths,
            )
            prioritized = prioritize_review_queue(
                work_items=build_path_review_work_items(work_units["review_items"], traced_paths),
                path_units=work_units["path_units"],
                scan_mode=session.scan_mode,
            )
            work_items = prioritized["review_items"]
            path_units = prioritized["path_units"]
            segmentation_summary = work_units["segmentation_summary"]
            review_queue_summary = prioritized["review_queue_summary"]
            logs.append(
                f"Prepared {len(work_items)} prioritized review items from "
                f"{repository_artifacts['coverage']['eligible_files']} eligible code files."
            )
            if session.scan_mode == "deep":
                logs.append(
                    f"Deep Scan scheduled {segmentation_summary['review_block_units']} review blocks and "
                    f"{segmentation_summary['path_units_total']} traced path units."
                )
            else:
                logs.append(
                    f"Fast Scan narrowed review to {segmentation_summary['review_block_units']} blocks and "
                    f"{segmentation_summary['path_units_total']} high-risk paths."
                )

            await self._update_with_logs(
                session_id,
                logs,
                "Tracing source-to-sink paths",
                "Preparing prioritized path units and code blocks for deep review.",
                lock_lease=lock_lease,
                job_id=job_id,
                job_stage="path_tracing",
                scan_mode=session.scan_mode,
                current_phase="Path tracing",
                started_at=started_at,
                progress_counters={
                    "files_segmented": len(file_segments),
                    "files_to_segment": max(1, len(file_segments)),
                    "paths_prepared": len(path_units),
                    "paths_total": max(len(path_units), traced_paths["summary"]["candidate_path_count"], 1),
                    "review_items_prepared": len(work_items),
                    "review_items_total": max(1, len(work_items)),
                },
                segmentation_summary=segmentation_summary,
                review_queue_summary=review_queue_summary,
                path_inventory={"summary": traced_paths["summary"], "paths": path_units[:18]},
                path_summary={
                    **traced_paths["summary"],
                    "review_path_units": len(path_units),
                },
                **calculate_progress_metrics(
                    reviewed_files_count=excluded_review_file_count,
                    eligible_files_count=profile["file_count"],
                    blocks_reviewed=0,
                    blocks_total=segmentation_summary["review_block_units"],
                    paths_traced=len(path_units),
                    paths_total=max(len(path_units), traced_paths["summary"]["candidate_path_count"]),
                    validated_findings_count=0,
                    candidate_findings_count=0,
                    coverage_percent=0,
                ),
            )

            ai_findings: list[dict] = []
            repository_summary = repository_map.get("repository_summary", "")
            support_confidence = framework_profile["support_matrix"]["primary"]["confidence"]
            batches = adaptive_chunk_work_items(
                work_items,
                scan_mode=session.scan_mode,
                support_confidence=support_confidence,
            )
            total_batches = len(batches) or 1

            for index, batch in enumerate(batches, start=1):
                batch_files = ", ".join(item["file"] for item in batch[:3])
                completed_batches = index - 1
                reviewed_blocks = min(len(work_items), sum(len(item) for item in batches[:completed_batches]))
                reviewed_paths = min(
                    len(path_units),
                    round((completed_batches / max(1, total_batches)) * max(1, len(path_units))),
                )
                await self._update_with_logs(
                    session_id,
                    logs,
                    "Reviewing prioritized paths",
                    f"Tracing exploitability across: {batch_files or 'current review batch'}.",
                    lock_lease=lock_lease,
                    job_id=job_id,
                    job_stage="reviewing_paths",
                    scan_mode=session.scan_mode,
                    current_phase="Reviewing paths",
                    started_at=started_at,
                    progress_counters={
                        "blocks_reviewed": reviewed_blocks,
                        "blocks_total": max(1, len(work_items)),
                        "paths_reviewed": reviewed_paths,
                        "paths_total": max(len(path_units), traced_paths["summary"]["candidate_path_count"], 1),
                        "review_batches_completed": completed_batches,
                        "review_batches_total": total_batches,
                    },
                    review_queue_summary={
                        **review_queue_summary,
                        "reviewed_batches": index,
                        "total_batches": total_batches,
                        "current_candidate_findings_count": len(ai_findings),
                        "current_validated_findings_count": 0,
                    },
                    **calculate_progress_metrics(
                        reviewed_files_count=len({item["file"] for item in work_items[:reviewed_blocks]}) + excluded_review_file_count,
                        eligible_files_count=profile["file_count"],
                        blocks_reviewed=reviewed_blocks,
                        blocks_total=max(1, len(work_items)),
                        paths_traced=len(path_units),
                        paths_total=max(len(path_units), traced_paths["summary"]["candidate_path_count"]),
                        validated_findings_count=0,
                        candidate_findings_count=len(ai_findings),
                        coverage_percent=min(92, round((reviewed_blocks / max(1, len(work_items))) * 100)),
                    ),
                )
                try:
                    review = await self.ai_client.review_paths(
                        project_name=session.repo,
                        source_path=session.source_path,
                        repository_profile=profile,
                        repository_map={
                            **repository_map,
                            "framework_profile": framework_profile,
                            "repository_graph_summary": repository_graph["summary"],
                            "path_summary": traced_paths["summary"],
                        },
                        work_items=batch,
                        batch_index=index,
                        total_batches=total_batches,
                        preset=session.preset,
                    )
                    self._append_runtime_events(logs)
                    if review.get("review_note"):
                        logs.append(review["review_note"])
                    if review.get("repository_summary") and not repository_summary:
                        repository_summary = review["repository_summary"]
                    ai_findings.extend(review.get("findings", []))
                    completed_batches = index
                    reviewed_blocks = min(len(work_items), sum(len(item) for item in batches[:completed_batches]))
                    reviewed_paths = min(
                        len(path_units),
                        round((completed_batches / max(1, total_batches)) * max(1, len(path_units))),
                    )
                    await self._update_with_logs(
                        session_id,
                        logs,
                        "Reviewing prioritized paths",
                        f"Reviewed batch {completed_batches}/{total_batches} and queued the next exploit path set.",
                        lock_lease=lock_lease,
                        job_id=job_id,
                        job_stage="reviewing_paths",
                        scan_mode=session.scan_mode,
                        current_phase="Reviewing paths",
                        started_at=started_at,
                        progress_counters={
                            "blocks_reviewed": reviewed_blocks,
                            "blocks_total": max(1, len(work_items)),
                            "paths_reviewed": reviewed_paths,
                            "paths_total": max(len(path_units), traced_paths["summary"]["candidate_path_count"], 1),
                            "review_batches_completed": completed_batches,
                            "review_batches_total": total_batches,
                        },
                        review_queue_summary={
                            **review_queue_summary,
                            "reviewed_batches": completed_batches,
                            "total_batches": total_batches,
                            "current_candidate_findings_count": len(ai_findings),
                            "current_validated_findings_count": 0,
                        },
                        **calculate_progress_metrics(
                            reviewed_files_count=len({item["file"] for item in work_items[:reviewed_blocks]}) + excluded_review_file_count,
                            eligible_files_count=profile["file_count"],
                            blocks_reviewed=reviewed_blocks,
                            blocks_total=max(1, len(work_items)),
                            paths_traced=len(path_units),
                            paths_total=max(len(path_units), traced_paths["summary"]["candidate_path_count"]),
                            validated_findings_count=0,
                            candidate_findings_count=len(ai_findings),
                            coverage_percent=min(92, round((reviewed_blocks / max(1, len(work_items))) * 100)),
                        ),
                    )
                except ExternalAIServiceError as exc:
                    logs.append(
                        "AI review was temporarily unavailable; continuing with heuristic signals only."
                    )
                    logger.warning("AI review failed during path review; continuing without AI batch", exc_info=exc)
                    self._append_runtime_events(logs)
                    break

            heuristic_candidates = attach_path_context(heuristic_candidates, traced_paths)
            ai_findings = attach_path_context(ai_findings, traced_paths)
            candidate_findings = cluster_findings(heuristic_candidates + ai_findings)
            logs.append(f"Collected {len(candidate_findings)} candidate findings before strict validation.")

            await self._update_with_logs(
                session_id,
                logs,
                "Validating concrete findings",
                "Rejecting speculative issues and keeping only defensible exploit paths.",
                lock_lease=lock_lease,
                job_id=job_id,
                job_stage="validation",
                scan_mode=session.scan_mode,
                current_phase="Validation",
                started_at=started_at,
                progress_counters={
                    "candidates_validated": 0,
                    "candidates_total": max(1, len(candidate_findings)),
                    "validation_artifacts_ready": 1,
                    "validation_artifacts_total": 2,
                },
                review_queue_summary={
                    **review_queue_summary,
                    "current_candidate_findings_count": len(candidate_findings),
                    "current_validated_findings_count": 0,
                },
                **calculate_progress_metrics(
                    reviewed_files_count=len({item["file"] for item in work_items}) + excluded_review_file_count,
                    eligible_files_count=profile["file_count"],
                    blocks_reviewed=len(work_items),
                    blocks_total=max(1, len(work_items)),
                    paths_traced=len(path_units),
                    paths_total=max(len(path_units), traced_paths["summary"]["candidate_path_count"]),
                    validated_findings_count=0,
                    candidate_findings_count=len(candidate_findings),
                    coverage_percent=min(95, scan_plan["coverage_target_percent"] if session.scan_mode == "fast" else 96),
                ),
            )

            validated = await self._run_validation_passes(
                session=session,
                profile=profile,
                repository_map=repository_map,
                framework_profile=framework_profile,
                repository_graph=repository_graph,
                traced_paths=traced_paths,
                candidate_findings=candidate_findings,
                mode_config=mode_config,
                logs=logs,
            )
            self._append_runtime_events(logs)
            merged_validated_findings = cluster_findings(merge_validated_findings(
                validated.get("findings", []),
                heuristic_candidates,
            ))
            merged_validated_findings = cluster_findings(filter_validated_findings(
                merged_validated_findings,
                source_root=source_root,
                files=files,
                traced_paths=traced_paths,
            ))
            merged_validated_findings = promote_cross_file_candidates(
                validated_findings=merged_validated_findings,
                candidate_findings=candidate_findings,
                source_root=source_root,
                files=files,
                traced_paths=traced_paths,
            )
            merged_validated_findings = cluster_findings(merged_validated_findings)
            candidate_review_findings = build_candidate_review_findings(
                candidate_findings=candidate_findings,
                validated_findings=merged_validated_findings,
                source_root=source_root,
                files=files,
            )
            if validated.get("review_note"):
                if validated.get("findings"):
                    logs.append(validated["review_note"])
                elif merged_validated_findings:
                    logs.append("The validator rejected speculative candidates, but deterministic high-confidence local findings were retained.")
                else:
                    logs.append(validated["review_note"])

            findings = dict_findings_to_entities(merged_validated_findings)
            candidate_entities = dict_findings_to_entities(candidate_review_findings)
            findings.sort(key=lambda item: (severity_rank(item.severity), -item.confidence, item.file, item.line))
            candidate_entities.sort(key=lambda item: (severity_rank(item.severity), -item.confidence, item.file, item.line))
            annotations = build_annotations(merged_validated_findings)
            coverage_snapshot = build_coverage_snapshot(
                profile=profile,
                repository_artifacts=repository_artifacts,
                file_segments=file_segments,
                work_items=work_items,
                findings=findings,
                scan_mode=session.scan_mode,
                path_units=path_units,
            )
            score_calibration = calibrate_security_score(
                findings,
                candidate_entities,
                coverage_snapshot,
                framework_profile=framework_profile,
                path_summary=traced_paths["summary"],
            )
            security_score = score_calibration["score"]
            is_safe = len(findings) == 0

            await self._update_with_logs(
                session_id,
                logs,
                "Validating concrete findings",
                "Rejecting speculative issues and keeping only defensible exploit paths.",
                lock_lease=lock_lease,
                job_id=job_id,
                job_stage="validation",
                scan_mode=session.scan_mode,
                current_phase="Validation",
                started_at=started_at,
                progress_counters={
                    "candidates_validated": max(1, len(candidate_findings)),
                    "candidates_total": max(1, len(candidate_findings)),
                    "validation_artifacts_ready": 2,
                    "validation_artifacts_total": 2,
                },
            )

            await self._update_with_logs(
                session_id,
                logs,
                "Building final verdict",
                "Summarizing reviewed coverage, severity, and security posture.",
                lock_lease=lock_lease,
                job_id=job_id,
                job_stage="scoring",
                scan_mode=session.scan_mode,
                current_phase="Scoring",
                started_at=started_at,
                progress_counters={
                    "artifacts_finalized": 2,
                    "artifacts_total": 4,
                },
                annotations=annotations,
                annotation_summary={
                    "ready_annotations": len(annotations),
                    "red_annotations": sum(1 for item in annotations if item["tone"] == "red"),
                    "yellow_annotations": sum(1 for item in annotations if item["tone"] == "yellow"),
                },
                coverage_snapshot=coverage_snapshot,
                score_rationale=score_calibration["rationale"],
                review_queue_summary={
                    **review_queue_summary,
                    "current_candidate_findings_count": len(candidate_entities),
                    "current_validated_findings_count": len(findings),
                },
                **calculate_progress_metrics(
                    reviewed_files_count=coverage_snapshot["reviewed_files_count"],
                    eligible_files_count=coverage_snapshot["eligible_files_count"],
                    blocks_reviewed=coverage_snapshot["reviewed_blocks_count"],
                    blocks_total=coverage_snapshot["total_blocks_count"],
                    paths_traced=coverage_snapshot["traced_paths_count"],
                    paths_total=coverage_snapshot["total_paths_count"],
                    validated_findings_count=len(findings),
                    candidate_findings_count=len(candidate_entities),
                    coverage_percent=coverage_snapshot["coverage_percent"],
                ),
            )

            try:
                verdict_summary = await self.ai_client.summarize_verdict(
                    project_name=session.repo,
                    source_path=session.source_path,
                    repository_profile=profile,
                    repository_map={
                        **repository_map,
                        "framework_profile": framework_profile,
                        "repository_graph_summary": repository_graph["summary"],
                        "scan_plan": scan_plan,
                        "security_registry_summary": security_registry["summary"],
                        "coverage_snapshot": coverage_snapshot,
                        "score_rationale": score_calibration["rationale"],
                        "path_summary": traced_paths["summary"],
                    },
                    findings=merged_validated_findings,
                    security_score=security_score,
                    preset=session.preset,
                )
            except ExternalAIServiceError as exc:
                logger.warning("AI verdict summary failed; using deterministic summary", exc_info=exc)
                logs.append("AI verdict summary was unavailable; using deterministic summary.")
                verdict_summary = {
                    "review_note": "",
                    "repository_summary": build_repository_summary(profile, repository_artifacts, findings),
                    "coverage_summary": "Coverage summary unavailable due to AI service interruption.",
                }
            self._append_runtime_events(logs)
            if verdict_summary.get("review_note"):
                logs.append(verdict_summary["review_note"])

            repository_summary = (
                verdict_summary.get("repository_summary")
                or validated.get("safe_summary")
                or repository_summary
                or build_repository_summary(profile, repository_artifacts, findings)
            )
            coverage_summary = verdict_summary.get("coverage_summary") or coverage_snapshot["coverage_summary"]
            if coverage_summary:
                logs.append(coverage_summary)

            if is_safe:
                if coverage_snapshot["coverage_percent"] >= 90:
                    logs.append("No confirmed high-confidence issue remained after validation.")
                else:
                    logs.append("No confirmed high-confidence issue remained, but the reviewed coverage did not span the entire codebase.")
            else:
                logs.append(f"Confirmed {len(findings)} validated findings. Highest severity: {findings[0].severity}.")

            finished_at = utc_now()
            latest_scan_job = (
                await self._update_job(
                    session_id,
                    job_id,
                    status="completed",
                    stage="completed",
                    progress=100,
                    finished_at=finished_at,
                    error_message=None,
                )
                if job_id and self.job_repository is not None
                else None
            )
            await self.repository.update(
                session_id,
                {
                    "status": "completed",
                    "progress": 100,
                    "phase_progress": 100,
                    "progress_message": "Scan completed",
                    "current_phase": "Completed",
                    "elapsed_seconds": int(time.monotonic() - started_at),
                    "preview": build_preview(findings, profile["file_count"], repository_artifacts["coverage"]["reviewed_hotspots"]),
                    "progress_logs": logs[-12:],
                    "runtime_metrics": getattr(self.ai_client, "snapshot_runtime_metrics", lambda **_: None)(),
                    "scan_plan": scan_plan,
                    "repository_summary": repository_summary,
                    "repository_inventory": repository_inventory,
                    "framework_profile": framework_profile,
                    "repository_graph": repository_graph,
                    "graph_summary": repository_graph["summary"],
                    "security_registry": {"summary": security_registry["summary"]},
                    "segmentation_summary": segmentation_summary,
                    "path_inventory": {"summary": traced_paths["summary"], "paths": path_units[:18]},
                    "path_summary": traced_paths["summary"],
                    "review_queue_summary": {
                        **review_queue_summary,
                        "reviewed_batches": total_batches,
                        "total_batches": total_batches,
                    },
                    "progress_counters": {
                        "files_indexed": profile["file_count"],
                        "files_total": profile["file_count"],
                        "mapping_artifacts_ready": 6,
                        "mapping_artifacts_total": 6,
                        "mapping_ai_steps_completed": 1,
                        "mapping_ai_steps_total": 1,
                        "files_segmented": len(file_segments),
                        "files_to_segment": max(1, len(file_segments)),
                        "paths_prepared": len(path_units),
                        "paths_total": max(len(path_units), traced_paths["summary"]["candidate_path_count"], 1),
                        "review_items_prepared": len(work_items),
                        "review_items_total": max(1, len(work_items)),
                        "blocks_reviewed": coverage_snapshot["reviewed_blocks_count"],
                        "blocks_total": max(1, coverage_snapshot["total_blocks_count"]),
                        "paths_reviewed": coverage_snapshot["traced_paths_count"],
                        "review_batches_completed": total_batches,
                        "review_batches_total": total_batches,
                        "candidates_validated": max(1, len(candidate_findings)),
                        "candidates_total": max(1, len(candidate_findings)),
                        "validation_artifacts_ready": 2,
                        "validation_artifacts_total": 2,
                        "artifacts_finalized": 4,
                        "artifacts_total": 4,
                    },
                    "annotations": annotations,
                    "annotation_summary": {
                        "ready_annotations": len(annotations),
                        "red_annotations": sum(1 for item in annotations if item["tone"] == "red"),
                        "yellow_annotations": sum(1 for item in annotations if item["tone"] == "yellow"),
                    },
                    "coverage_snapshot": coverage_snapshot,
                    "coverage_summary": coverage_summary,
                    "coverage_percent": coverage_snapshot["coverage_percent"],
                    "reviewed_files_count": coverage_snapshot["reviewed_files_count"],
                    "eligible_files_count": coverage_snapshot["eligible_files_count"],
                    "reviewed_blocks_count": coverage_snapshot["reviewed_blocks_count"],
                    "total_blocks_count": coverage_snapshot["total_blocks_count"],
                    "reviewed_lines_count": coverage_snapshot["reviewed_lines_count"],
                    "total_lines_count": coverage_snapshot["total_lines_count"],
                    "traced_paths_count": coverage_snapshot["traced_paths_count"],
                    "total_paths_count": coverage_snapshot["total_paths_count"],
                    "skipped_files_count": coverage_snapshot["skipped_files_count"],
                    "high_risk_files_count": coverage_snapshot["high_risk_files_count"],
                    "is_safe": is_safe,
                    "findings": findings,
                    "candidate_findings": candidate_entities,
                    "security_score": security_score,
                    "score_rationale": score_calibration["rationale"],
                    "latest_scan_job": latest_scan_job,
                    "unread": True,
                    "updated_at": finished_at,
                    "completed_at": finished_at,
                },
            )
            if self.workflow_persistence is not None:
                await self.workflow_persistence.record_audit(
                    session_id=session_id,
                    entity_type="scan_job",
                    entity_id=job_id or session_id,
                    action="scan.completed",
                    payload={
                        "findings_count": len(findings),
                        "candidate_findings_count": len(candidate_entities),
                        "security_score": security_score,
                        "status": "completed",
                    },
                )
        except Exception as exc:
            failed_at = utc_now()
            logger.exception("Scan execution failed", extra={"session_id": session_id, "source_path": session.source_path})
            friendly_error = _build_scan_failure_message(exc)
            logs.append("Scan failed before the final verdict was produced.")
            logs.append(friendly_error)
            latest_scan_job = (
                await self._update_job(
                    session_id,
                    job_id,
                    status="failed",
                    stage="failed",
                    progress=100,
                    finished_at=failed_at,
                    error_message=friendly_error,
                )
                if job_id and self.job_repository is not None
                else None
            )
            await self.repository.update(
                session_id,
                {
                    "status": "failed",
                    "progress": 100,
                    "phase_progress": 100,
                    "progress_message": "Scan failed",
                    "current_phase": "Failed",
                    "elapsed_seconds": int(time.monotonic() - started_at),
                    "preview": "The scan stopped before a final result was produced. Review the failure reason and retry when the provider is available.",
                    "progress_logs": logs[-12:],
                    "runtime_metrics": getattr(self.ai_client, "snapshot_runtime_metrics", lambda **_: None)(),
                    "error_message": friendly_error,
                    "findings": [],
                    "candidate_findings": [],
                    "is_safe": False,
                    "security_score": None,
                    "score_rationale": {
                        "status": "failed",
                        "reason": "No security score is available because the scan did not complete successfully.",
                        "provider_failure": isinstance(exc, ExternalAIServiceError),
                    },
                    "coverage_summary": "Coverage is unavailable because the scan did not complete.",
                    "coverage_percent": 0,
                    "annotations": [],
                    "annotation_summary": {"ready": 0, "status": "failed"},
                    "progress_counters": {
                        "status": "failed",
                    },
                    "latest_scan_job": latest_scan_job,
                    "updated_at": failed_at,
                    "completed_at": failed_at,
                },
            )
            if self.workflow_persistence is not None:
                await self.workflow_persistence.record_audit(
                    session_id=session_id,
                    entity_type="scan_job",
                    entity_id=job_id or session_id,
                    action="scan.failed",
                    payload={
                        "status": "failed",
                        "error_message": friendly_error,
                    },
                )
        finally:
            if self.scan_lock_manager is not None:
                await self.scan_lock_manager.release_submission_locks(lock_lease)

    async def _update_with_logs(
        self,
        session_id: str,
        logs: list[str],
        progress_message: str,
        preview: str,
        lock_lease: ScanLockLease | None = None,
        status: str = "scanning",
        job_id: str | None = None,
        job_stage: str | None = None,
        scan_mode: str | None = None,
        current_phase: str | None = None,
        started_at: float | None = None,
        **extra_updates,
    ) -> None:
        elapsed_seconds = int(time.monotonic() - started_at) if started_at is not None else 0
        if scan_mode is None and "scan_mode" in extra_updates:
            scan_mode = str(extra_updates.pop("scan_mode"))
        else:
            extra_updates.pop("scan_mode", None)
        if current_phase is None and "current_phase" in extra_updates:
            current_phase = str(extra_updates.pop("current_phase"))
        else:
            extra_updates.pop("current_phase", None)
        progress_counters = extra_updates.get("progress_counters")
        progress_state = build_progress_state(current_phase or progress_message, progress_counters)
        latest_scan_job = None
        if self.scan_lock_manager is not None:
            await self.scan_lock_manager.refresh_submission_locks(lock_lease)
        if job_id and self.job_repository is not None:
            latest_scan_job = await self._update_job(
                session_id,
                job_id,
                status="running" if status == "scanning" else status,
                stage=job_stage or (current_phase or progress_message),
                progress=progress_state["progress"],
            )
        await self.repository.update(
            session_id,
            {
                "status": status,
                "progress": progress_state["progress"],
                "phase_progress": progress_state["phase_progress"],
                "progress_message": progress_message,
                "current_phase": current_phase or progress_message,
                "elapsed_seconds": elapsed_seconds,
                **({"scan_mode": scan_mode} if scan_mode else {}),
                "preview": preview,
                "progress_logs": logs[-12:],
                **({"latest_scan_job": latest_scan_job} if latest_scan_job else {}),
                "updated_at": utc_now(),
                **extra_updates,
            },
        )

    async def _update_job(
        self,
        session_id: str,
        job_id: str | None,
        *,
        status: str,
        stage: str,
        progress: int,
        attempts: int | None = None,
        started_at=None,
        finished_at=None,
        error_message: str | None = None,
    ) -> dict | None:
        if not job_id or self.job_repository is None:
            return None
        updates = {
            "status": status,
            "stage": stage,
            "progress": max(0, min(100, int(progress))),
            "error_message": error_message,
        }
        if attempts is not None:
            updates["attempts"] = attempts
        if started_at is not None:
            updates["started_at"] = started_at
        if finished_at is not None:
            updates["finished_at"] = finished_at
        job = await self.job_repository.update(job_id, updates)
        if job is None:
            return {
                "id": job_id,
                "session_id": session_id,
                "type": "scan",
                "status": status,
                "stage": stage,
                "progress": progress,
                "attempts": attempts or 0,
                "error_message": error_message,
                "created_at": utc_now(),
                "started_at": started_at,
                "finished_at": finished_at,
            }
        return build_scan_job_snapshot(job)

    def _append_runtime_events(self, logs: list[str]) -> None:
        for event in getattr(self.ai_client, "drain_runtime_events", lambda: [])():
            if not event:
                continue
            lowered = event.lower()
            if any(token in lowered for token in ("provider", "model", "key", "cache", "fallback", "cool", "retry", "coalesced")):
                continue
            logs.append(event)

    def _get_cached_analysis(self, cache_key: str) -> dict | None:
        payload = self._analysis_cache.get(cache_key)
        if payload is None:
            return None
        return copy.deepcopy(payload)

    def _set_cached_analysis(self, cache_key: str, payload: dict) -> None:
        self._analysis_cache[cache_key] = copy.deepcopy(payload)
        while len(self._analysis_cache) > self._MAX_ANALYSIS_CACHE_ENTRIES:
            oldest_key = next(iter(self._analysis_cache))
            del self._analysis_cache[oldest_key]

    async def _run_validation_passes(
        self,
        *,
        session: ScanSessionEntity,
        profile: dict,
        repository_map: dict,
        framework_profile: dict,
        repository_graph: dict,
        traced_paths: dict,
        candidate_findings: list[dict],
        mode_config: ScanModeConfig,
        logs: list[str],
    ) -> dict:
        validation_context = {
            **repository_map,
            "framework_profile": framework_profile,
            "repository_graph_summary": repository_graph["summary"],
            "path_summary": traced_paths["summary"],
        }

        try:
            first_pass = await self.ai_client.validate_findings(
                project_name=session.repo,
                source_path=session.source_path,
                repository_profile=profile,
                repository_map=validation_context,
                findings=candidate_findings,
                preset=session.preset,
            )
        except ExternalAIServiceError as exc:
            logger.warning("AI validation failed; returning no validated findings", exc_info=exc)
            logs.append("AI validation was unavailable; no findings were auto-validated.")
            return {"review_note": "", "safe_summary": "", "findings": []}

        review_notes = [str(first_pass.get("review_note", "")).strip()]
        merged_findings = list(first_pass.get("findings", []))

        if mode_config.validation_passes > 1 and candidate_findings:
            validated_keys = {build_candidate_key(item) for item in merged_findings}
            second_pass_candidates = [
                item
                for item in candidate_findings
                if build_candidate_key(item) not in validated_keys
                and int(item.get("confidence", 0) or 0) >= 70
                and not bool(item.get("has_sanitizer"))
            ][: max(1, int(mode_config.validation_candidates_per_pass))]
            if second_pass_candidates:
                logs.append(
                    f"Deep validation pass 2 is rechecking {len(second_pass_candidates)} high-signal candidates."
                )
                try:
                    second_pass = await self.ai_client.validate_findings(
                        project_name=session.repo,
                        source_path=session.source_path,
                        repository_profile=profile,
                        repository_map=validation_context,
                        findings=second_pass_candidates,
                        preset=session.preset,
                    )
                    review_notes.append(str(second_pass.get("review_note", "")).strip())
                    merged_findings.extend(second_pass.get("findings", []))
                except ExternalAIServiceError as exc:
                    logger.warning("Second validation pass failed; keeping first pass output", exc_info=exc)
                    logs.append("Deep validation pass 2 was unavailable; continuing with pass 1 output.")

        deduped_findings = cluster_findings(merged_findings)
        return {
            "review_note": " ".join(note for note in review_notes if note),
            "safe_summary": str(first_pass.get("safe_summary", "")),
            "findings": deduped_findings,
        }


def _build_scan_failure_message(exc: Exception) -> str:
    if isinstance(exc, ExternalAIServiceError):
        return sanitize_runtime_error(exc, operation="scan")
    return "The scan failed because CodeGuard could not complete its AI analysis. Check the server logs and retry the request."


def collect_heuristic_candidates(files: list[Path], source_root: Path) -> list[dict]:
    heuristic_findings: list[dict] = []
    for path in files:
        if path.suffix.lower() not in {".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".go", ".rb", ".php", ".cs", ".kt", ".rs", ".mjs", ".cjs"}:
            continue
        heuristic_findings.extend(run_precise_heuristics(path, read_text(path), source_root))
    return heuristic_findings


def merge_validated_findings(validated_findings: list[dict], heuristic_candidates: list[dict]) -> list[dict]:
    merged: list[dict] = []
    seen: set[tuple[str, int, str]] = set()

    for item in validated_findings:
        key = build_candidate_key(item)
        if key in seen:
            continue
        seen.add(key)
        merged.append(item)

    for item in heuristic_candidates:
        if int(item.get("confidence", 0)) < 80:
            continue
        key = build_candidate_key(item)
        if key in seen:
            continue
        seen.add(key)
        merged.append(item)

    return merged


def build_candidate_key(item: dict) -> tuple[str, int, str]:
    return (
        str(item.get("file", "")).strip(),
        int(item.get("line", 1)),
        str(item.get("title", "")).strip().lower(),
    )


def build_finding_fingerprint(item: dict) -> tuple[str, str, str, str, str, str]:
    file_path = str(item.get("file", "")).strip()
    title = str(item.get("title", "")).strip().lower()
    category = str(item.get("category", "")).strip().lower()
    path_hint = str(item.get("path_hint", "")).strip().lower()
    source_hint = str(item.get("source_hint", "")).strip().lower()
    sink_hint = str(item.get("sink_hint", "")).strip().lower()
    if not path_hint:
        line = int(item.get("line", 1))
        line_end = int(item.get("line_end", line))
        path_hint = f"{line}:{line_end}"
    return (file_path, title, category, path_hint, source_hint, sink_hint)


def dict_findings_to_entities(findings: list[dict]) -> list[FindingEntity]:
    entities: list[FindingEntity] = []
    seen: set[tuple[str, int, str]] = set()
    for item in findings:
        file_path = str(item.get("file", "")).strip()
        if not file_path:
            continue
        key = (file_path, int(item.get("line", 1)), str(item.get("title", "")).strip().lower())
        if key in seen:
            continue
        seen.add(key)
        entities.append(
            FindingEntity(
                id=build_finding_id(file_path, key[1], key[2] or "finding"),
                severity=normalize_severity(str(item.get("severity", "medium"))),
                title=str(item.get("title", "Security finding")),
                file=file_path,
                line=key[1],
                line_end=max(key[1], int(item.get("line_end", key[1]))),
                category=str(item.get("category", "Security review")),
                confidence=max(0, min(100, int(item.get("confidence", 70)))),
                summary=str(item.get("summary", "")),
                impact=str(item.get("impact", "")),
                attack_input=str(item.get("attack_input", "")),
                attack_execution=str(item.get("attack_execution", item.get("path_hint", ""))),
                attack_result=str(item.get("attack_result", "")),
                audit_log=[str(entry) for entry in item.get("audit_log", [])][:5],
                explanation=str(item.get("explanation", "")),
                fix_suggestions=item.get("fix_suggestions", []) or default_fix_suggestions(str(item.get("category", "Security review"))),
                evidence=str(item.get("evidence", "")),
            )
        )
    return entities


def normalize_severity(value: str) -> str:
    value = value.lower().strip()
    if value in {"critical", "high", "medium", "low"}:
        return value
    return "medium"


def build_preview(findings: list[FindingEntity], file_count: int, reviewed_hotspots: int) -> str:
    if not findings:
        return (
            f"Reviewed {file_count} files, prioritized {reviewed_hotspots} high-risk hotspots, "
            "and did not confirm a security issue."
        )
    highest = findings[0]
    return (
        f"Reviewed {file_count} files, prioritized {reviewed_hotspots} hotspots, and confirmed "
        f"{len(findings)} findings. Highest severity: {highest.severity} in {highest.file}:{highest.line}."
    )


def build_repository_summary(profile: dict, repository_artifacts: dict, findings: list[FindingEntity]) -> str:
    stack = ", ".join(profile["frameworks"][:4] or profile["languages"][:4]) or "unknown stack"
    coverage = repository_artifacts["coverage"]
    if not findings:
        return (
            f"CodeGuard reviewed a {stack} codebase, mapped {coverage['route_files']} route files and "
            f"{coverage['auth_files']} auth surfaces, and did not confirm a high-confidence issue in the selected scope."
        )
    return (
        f"CodeGuard reviewed a {stack} codebase, mapped {coverage['route_files']} route files and "
        f"{coverage['auth_files']} auth surfaces, and confirmed {len(findings)} validated findings."
    )


def build_path_review_work_items(work_items: list[dict[str, str]], traced_paths: dict) -> list[dict[str, str]]:
    path_lookup = {str(item["sink"]["file"]): item for item in traced_paths.get("paths", [])}
    enriched_items: list[dict[str, str]] = []
    for item in work_items:
        enriched = dict(item)
        snippet = str(enriched.get("snippet", ""))
        if snippet:
            snippet_lines = snippet.splitlines()[:10]
            enriched["snippet"] = "\n".join(snippet_lines)[:900]
        candidate_path = path_lookup.get(str(item.get("file", "")))
        if candidate_path:
            enriched["path_hint"] = str(candidate_path.get("path_hint", ""))
            enriched["path_type"] = str(candidate_path.get("path_type", ""))
            enriched["source_line"] = str(candidate_path["source"]["line"])
            enriched["sink_line"] = str(candidate_path["sink"]["line"])
            enriched["review_focus"] = (
                f"{item.get('review_focus', '')}. Trace path: {candidate_path.get('path_hint', '')}"
            ).strip(". ")
        enriched_items.append(enriched)
    return enriched_items


def attach_path_context(findings: list[dict], traced_paths: dict) -> list[dict]:
    if not findings:
        return []
    path_lookup = {(item["sink"]["file"], int(item["sink"]["line"])): item for item in traced_paths.get("paths", [])}
    fallback_paths_by_file: dict[str, dict] = {}
    for item in traced_paths.get("paths", []):
        fallback_paths_by_file.setdefault(item["sink"]["file"], item)

    enriched_findings: list[dict] = []
    for item in findings:
        enriched = dict(item)
        candidate_path = path_lookup.get((str(item.get("file", "")), int(item.get("line", 1))))
        if candidate_path is None:
            candidate_path = fallback_paths_by_file.get(str(item.get("file", "")))
        if candidate_path:
            enriched["path_hint"] = str(candidate_path.get("path_hint", ""))
            enriched["source_hint"] = f"{candidate_path['source']['file']}:{candidate_path['source']['line']}"
            enriched["sink_hint"] = f"{candidate_path['sink']['file']}:{candidate_path['sink']['line']}"
            enriched["path_line_sequence"] = [int(line) for line in candidate_path.get("line_sequence", [])]
            enriched["has_sanitizer"] = bool(candidate_path.get("has_sanitizer"))
            enriched["confidence"] = max(int(enriched.get("confidence", 0) or 0), int(candidate_path.get("confidence", 0) or 0))
            enriched.setdefault("attack_input", f"Untrusted input enters at {enriched['source_hint']}.")
            enriched["attack_execution"] = enriched.get("attack_execution") or enriched["path_hint"]
            audit_log = [str(entry) for entry in enriched.get("audit_log", [])]
            audit_log.append(f"Path hint: {enriched['path_hint']}")
            if candidate_path.get("has_sanitizer"):
                audit_log.append("Observed sanitizer activity on the traced path")
            enriched["audit_log"] = audit_log[:5]
        enriched_findings.append(enriched)
    return enriched_findings


def filter_validated_findings(
    findings: list[dict],
    source_root: Path,
    files: list[Path],
    traced_paths: dict,
) -> list[dict]:
    file_lookup = {path.relative_to(source_root).as_posix(): path for path in files if path.is_file()}
    valid_paths = {item.get("path_hint", ""): item for item in traced_paths.get("paths", []) if item.get("path_hint")}
    filtered: list[dict] = []
    for item in findings:
        file_path = str(item.get("file", "")).strip()
        path = file_lookup.get(file_path)
        if path is None:
            continue
        line_start = max(1, int(item.get("line", 1)))
        evidence = extract_evidence(path, line_start, int(item.get("line_end", line_start)))
        path_hint = str(item.get("path_hint", "")).strip()
        source_hint = str(item.get("source_hint", "")).strip()
        sink_hint = str(item.get("sink_hint", "")).strip()
        if not source_hint or not sink_hint or not path_hint or not evidence["snippet"]:
            continue
        traced_path = valid_paths.get(path_hint)
        if valid_paths and traced_path is None:
            continue
        if traced_path and traced_path.get("has_sanitizer") and int(item.get("confidence", 0)) < 90:
            continue
        normalized = dict(item)
        line_sequence = [int(line) for line in normalized.get("path_line_sequence", []) if int(line) > 0]
        if line_sequence:
            line_start = min(line_sequence)
            line_end = max(line_sequence)
            path_evidence = extract_evidence(path, line_start, line_end, radius=1)
            normalized["line"] = path_evidence["line_start"]
            normalized["line_end"] = path_evidence["line_end"]
            normalized["evidence"] = path_evidence["snippet"]
        else:
            normalized["line"] = evidence["line_start"]
            normalized["line_end"] = evidence["line_end"]
            normalized["evidence"] = evidence["snippet"]
        filtered.append(normalized)
    return filtered


def build_annotations(findings: list[dict]) -> list[dict]:
    annotations: list[dict] = []
    for item in findings:
        severity = normalize_severity(str(item.get("severity", "medium")))
        annotations.append(
            {
                "file": str(item.get("file", "")),
                "lineStart": int(item.get("line", 1)),
                "lineEnd": int(item.get("line_end", item.get("line", 1))),
                "severity": severity,
                "tone": "red" if severity in {"critical", "high"} else "yellow",
                "title": str(item.get("title", "Security finding")),
                "confidence": max(0, min(100, int(item.get("confidence", 70)))),
                "evidence": str(item.get("evidence", "")),
                "pathHint": str(item.get("path_hint", "")),
            }
        )
    return annotations


def build_repository_inventory(profile: dict, files: list[Path]) -> dict:
    return {
        "file_count": int(profile.get("file_count", len(files))),
        "directory_count": int(profile.get("directory_count", 0)),
        "languages": [str(item) for item in profile.get("languages", [])[:8]],
        "frameworks": [str(item) for item in profile.get("frameworks", [])[:8]],
        "files": [str(path.name) for path in files[:24]],
    }


def build_candidate_review_findings(
    candidate_findings: list[dict],
    validated_findings: list[dict],
    source_root: Path,
    files: list[Path],
) -> list[dict]:
    file_lookup = {path.relative_to(source_root).as_posix(): path for path in files if path.is_file()}
    validated_keys = {build_candidate_key(item) for item in validated_findings}
    validated_fingerprints = {build_finding_fingerprint(item) for item in validated_findings}
    candidate_review_items: list[dict] = []
    seen: set[tuple[str, str, str, str, str, str]] = set()

    for item in candidate_findings:
        key = build_candidate_key(item)
        fingerprint = build_finding_fingerprint(item)
        if key in validated_keys or fingerprint in validated_fingerprints or fingerprint in seen:
            continue
        seen.add(fingerprint)

        file_path = str(item.get("file", "")).strip()
        path = file_lookup.get(file_path)
        if path is None:
            continue

        source_hint = str(item.get("source_hint", "")).strip()
        sink_hint = str(item.get("sink_hint", "")).strip()
        path_hint = str(item.get("path_hint", "")).strip()
        if not source_hint or not sink_hint or not path_hint:
            continue

        line_sequence = [int(line) for line in item.get("path_line_sequence", []) if int(line) > 0]
        if line_sequence:
            evidence = extract_evidence(path, min(line_sequence), max(line_sequence), radius=1)
        else:
            line_number = max(1, int(item.get("line", 1)))
            evidence = extract_evidence(path, line_number, int(item.get("line_end", line_number)))

        confidence = max(35, min(79, int(item.get("confidence", 55))))
        candidate_review_items.append(
            {
                **item,
                "line": evidence["line_start"],
                "line_end": evidence["line_end"],
                "confidence": confidence,
                "evidence": evidence["snippet"],
                "summary": str(item.get("summary", "Suspicious path requires human review.")),
                "impact": str(item.get("impact", "This path may be risky, but it was not retained as a confirmed finding.")),
                "explanation": str(item.get("explanation", "The engine found a plausible source-to-sink path, but validation did not confirm exploitability with high confidence.")),
                "attack_result": str(item.get("attack_result", "This path needs manual review before it can be treated as a confirmed vulnerability.")),
                "audit_log": [*([str(entry) for entry in item.get("audit_log", [])][:4]), "Marked as candidate finding pending manual review."],
            }
        )

    return candidate_review_items[:12]


def promote_cross_file_candidates(
    validated_findings: list[dict],
    candidate_findings: list[dict],
    source_root: Path,
    files: list[Path],
    traced_paths: dict,
) -> list[dict]:
    promoted = list(validated_findings)
    validated_keys = {build_candidate_key(item) for item in validated_findings}
    file_lookup = {path.relative_to(source_root).as_posix(): path for path in files if path.is_file()}
    traced_lookup = {str(item.get("path_hint", "")): item for item in traced_paths.get("paths", []) if item.get("path_hint")}

    for item in candidate_findings:
        key = build_candidate_key(item)
        if key in validated_keys:
            continue
        path_hint = str(item.get("path_hint", "")).strip()
        traced = traced_lookup.get(path_hint)
        if traced is None or traced.get("path_type") != "cross_file":
            continue
        if traced.get("has_sanitizer"):
            continue

        confidence = int(item.get("confidence", 0))
        source_hint = str(item.get("source_hint", "")).strip()
        sink_hint = str(item.get("sink_hint", "")).strip()
        if confidence < 84 or not source_hint or not sink_hint:
            continue

        file_path = str(item.get("file", "")).strip()
        path = file_lookup.get(file_path)
        if path is None:
            continue

        line_sequence = [int(line) for line in item.get("path_line_sequence", []) if int(line) > 0]
        if not line_sequence:
            continue

        evidence = extract_evidence(path, min(line_sequence), max(line_sequence), radius=1)
        if not evidence["snippet"]:
            continue

        promoted.append(
            {
                **item,
                "line": evidence["line_start"],
                "line_end": evidence["line_end"],
                "evidence": evidence["snippet"],
                "confidence": max(confidence, 88),
                "summary": str(item.get("summary", "Cross-file source-to-sink path validated through repository tracing.")),
                "explanation": str(item.get("explanation", "A cross-file path from untrusted input to a dangerous sink remained reachable after sanitizer-aware validation.")),
                "audit_log": [
                    *([str(entry) for entry in item.get("audit_log", [])][:4]),
                    "Promoted from candidate to validated after cross-file path proof.",
                ],
            }
        )
        validated_keys.add(key)

    return promoted
