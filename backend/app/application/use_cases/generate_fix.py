from app.application.dto.remediation_contracts import GenerateFixRequest, RemediationPlanResponse
from app.application.use_cases.remediation_mapper import map_remediation_plan
from app.domain.entities.remediation import (
    ExplanationEntity,
    FixStrategyEntity,
    PatchCandidateEntity,
    RemediationMetricsEntity,
    RemediationPlanEntity,
    RemediationStepEntity,
)
from app.domain.entities.scan import utc_now
from app.domain.repositories.scan_repository import ScanSessionRepository
from app.infrastructure.ai.orchestration.remediation_router import RemediationRouter
from app.infrastructure.services.remediation_context import (
    build_remediation_context,
    count_analyzed_lines,
    count_path_steps,
    locate_finding,
)
from app.infrastructure.services.decision_summary import append_approval_history, build_finding_decision_summary
from app.infrastructure.services.remediation_quality import assess_remediation_quality
from app.infrastructure.services.remediation_feedback_store import RemediationFeedbackStore
from app.infrastructure.services.remediation_scoring import score_remediation
from app.infrastructure.services.remediation_tuning import (
    build_tuning_context,
    choose_better_plan,
    evaluate_tuning_need,
    extract_failure_case,
)
from app.infrastructure.services.workflow_persistence import WorkflowPersistenceService
from app.infrastructure.settings.runtime_settings_service import RuntimeSettingsService


class GenerateFixUseCase:
    def __init__(
        self,
        repository: ScanSessionRepository,
        agent_router: RemediationRouter,
        workflow_persistence: WorkflowPersistenceService | None = None,
        runtime_settings_service: RuntimeSettingsService | None = None,
    ) -> None:
        self.repository = repository
        self.agent_router = agent_router
        self.feedback_store = RemediationFeedbackStore()
        self.workflow_persistence = workflow_persistence
        self.runtime_settings_service = runtime_settings_service

    async def execute(self, payload: GenerateFixRequest) -> RemediationPlanResponse | None:
        session = await self.repository.get_by_id(payload.session_id)
        if session is None:
            return None

        finding = locate_finding(session, payload.finding_id)
        if finding is None:
            return None

        context = build_remediation_context(session, finding)
        entity = await self._generate_with_tuning(context=context, finding_id=finding.id, mode="single")
        finding.remediation_status = "patch_generated"
        decision_summary = build_finding_decision_summary(finding)
        finding.decision_summary = decision_summary
        if decision_summary["policy_outcome"] == "review-required" and finding.approval_status not in {"approved", "escalated", "rejected"}:
            append_approval_history(
                finding,
                "pending",
                "Patch review is pending before workspace apply can proceed.",
                timestamp=utc_now().isoformat(),
            )
        await self.repository.update(
            session.id,
            {
                "findings": session.findings,
                "updated_at": utc_now(),
            },
        )
        if self.workflow_persistence is not None:
            await self.workflow_persistence.record_audit(
                session_id=session.id,
                entity_type="finding",
                entity_id=finding.id,
                action="remediation.plan_generated",
                payload={
                    "recommended_strategy_id": entity.recommended_strategy_id,
                    "strategy_count": len(entity.strategies),
                    "review_summary": entity.review_summary,
                },
            )
        return map_remediation_plan(entity)

    async def _generate_with_tuning(self, *, context: dict, finding_id: str, mode: str) -> RemediationPlanEntity:
        category = str(context["finding"]["category"]).strip().lower()
        previous_failures = self.feedback_store.get_recent_failures(category)
        best_plan: RemediationPlanEntity | None = None
        excluded_ids: list[str] = []
        max_attempts = 3
        reuse_explanation = True
        if self.runtime_settings_service is not None:
            runtime_settings = await self.runtime_settings_service.get()
            max_attempts = max(1, min(5, int(runtime_settings.remediation_max_attempts)))
            reuse_explanation = bool(runtime_settings.remediation_reuse_explanation)
        explanation_cache: dict | None = None
        attempt = 1
        while attempt <= max_attempts:
            current_context = build_tuning_context(
                base_context=context,
                category=category,
                previous_failures=previous_failures,
                excluded_strategy_ids=excluded_ids,
                attempt=attempt,
            )
            if best_plan:
                current_context["retry"]["attempted_strategy_ids"] = [item.id for item in best_plan.strategies]
            plan, generated_explanation = await self._run_generation(
                current_context,
                finding_id=finding_id,
                mode=mode,
                explanation_override=explanation_cache if reuse_explanation else None,
            )
            if reuse_explanation and explanation_cache is None:
                explanation_cache = generated_explanation
            best_plan = plan if best_plan is None else choose_better_plan(best_plan, plan)
            decision = evaluate_tuning_need(best_plan)
            if not decision.should_retry:
                return best_plan

            self.feedback_store.record_failure(extract_failure_case(plan=best_plan, context=current_context))
            excluded_ids = sorted(set(excluded_ids + decision.excluded_strategy_ids))
            previous_failures = self.feedback_store.get_recent_failures(category)
            attempt += 1

        if best_plan and best_plan.score and best_plan.score.total < 70:
            self.feedback_store.record_failure(extract_failure_case(plan=best_plan, context=context))
        if best_plan is not None:
            return best_plan
        return (
            await self._run_generation(
                context,
                finding_id=finding_id,
                mode=mode,
                explanation_override=explanation_cache if reuse_explanation else None,
            )
        )[0]

    async def _run_generation(
        self,
        context: dict,
        *,
        finding_id: str,
        mode: str,
        explanation_override: dict | None = None,
    ) -> tuple[RemediationPlanEntity, dict]:
        await self.agent_router.start_run(context, mode)
        explanation = explanation_override or await self.agent_router.explain(context, mode=mode)
        remediation = await self.agent_router.generate_fix(context, mode=mode)
        return (
            _build_plan_entity(
                finding_id,
                explanation,
                remediation,
                context,
                await self.agent_router.build_trace(context, mode),
                mode=mode,
            ),
            explanation,
        )


def _build_plan_entity(
    finding_id: str,
    explanation: dict,
    remediation: dict,
    context: dict,
    trace: list,
    mode: str,
) -> RemediationPlanEntity:
    explanation_entity = ExplanationEntity(
        finding_id=finding_id,
        summary=str(explanation.get("summary") or context["finding"]["summary"]),
        exploit_scenario=str(explanation.get("exploit_scenario") or context["finding"]["explanation"]),
        request_example=str(explanation.get("request_example") or ""),
        payload_example=str(explanation.get("payload_example") or ""),
        attack_steps=[str(item) for item in explanation.get("attack_steps", []) if str(item).strip()] or [
            f"Reach {context['finding']['attack_input']}",
            f"Follow {context['finding']['attack_execution']}",
            f"Cause {context['finding']['attack_result']}",
        ],
        entry_point=str(explanation.get("entry_point") or context["finding"]["attack_input"]),
        execution_path=str(explanation.get("execution_path") or context["finding"]["attack_execution"]),
        sink=str(explanation.get("sink") or f"{context['finding']['file']}:{context['finding']['line']}"),
        impact=str(explanation.get("impact") or context["finding"]["impact"]),
    )

    strategies = [
        FixStrategyEntity(
            id=str(item.get("id", "recommended")),
            label=str(item.get("label", "Fix strategy")),
            kind=str(item.get("kind", "guard")),
            confidence=int(item.get("confidence", 70)),
            impact=str(item.get("impact", "medium")),
            effort=str(item.get("effort", "medium")),
            summary=str(item.get("summary", "Mitigate the reachable sink with a code-level fix.")),
            rationale=str(item.get("rationale", "Derived from the real execution path and code evidence.")),
            diff=str(item.get("diff", "")),
            recommended=bool(item.get("recommended", False)),
        )
        for item in remediation.get("strategies", [])
    ]
    patch_data = remediation.get("patch", {}) or {}
    patch_entity = PatchCandidateEntity(
        file=str(patch_data.get("file") or context["finding"]["file"]),
        language=str(patch_data.get("language") or context["code"]["language"]),
        summary=str(patch_data.get("summary") or "Patch candidate generated from the traced execution path."),
        diff=str(patch_data.get("diff", "")),
        validation_notes=[str(item) for item in patch_data.get("validation_notes", []) if str(item).strip()],
        before_snippet=str(patch_data.get("before_snippet") or context["code"]["window"]["snippet"]),
        after_snippet=str(patch_data.get("after_snippet", "")),
    )
    if not patch_entity.diff.strip():
        for strategy in strategies:
            if strategy.diff.strip():
                patch_entity.diff = strategy.diff
                patch_entity.summary = "Patch candidate derived from the recommended remediation strategy."
                break
    if patch_entity.diff.strip() and not patch_entity.after_snippet.strip():
        patch_entity.after_snippet = _derive_snippet_from_diff(patch_entity.diff)
    if not strategies and patch_entity.diff.strip():
        category = str(context["finding"]["category"]).lower()
        preferred_kind = "refactor" if any(token in category for token in ("sql injection", "command injection", "nosql", "auth", "session")) else "guard"
        strategies = [
            FixStrategyEntity(
                id="recommended",
                label="Code-level remediation",
                kind=preferred_kind,
                confidence=72,
                impact="medium",
                effort="medium",
                summary="Apply the code change captured in the patch diff to reduce exposure along the traced path.",
                rationale="Derived from the validated patch diff when strategies were unavailable.",
                diff=patch_entity.diff,
                recommended=True,
            )
        ]
    if not patch_entity.diff.strip() or not patch_entity.after_snippet.strip():
        patch_entity.summary = "No remediation patch was produced for this finding."
        patch_entity.validation_notes = [
            *patch_entity.validation_notes,
            "No remediation strategy produced a concrete patch diff.",
        ]
        patch_entity.manual_review_required = True
    strategies, patch_entity, recommended_strategy_id = assess_remediation_quality(
        finding=context["finding"],
        strategies=strategies,
        patch=patch_entity,
    )
    chosen_strategy = next((item for item in strategies if item.id == recommended_strategy_id), strategies[0] if strategies else None)
    score_entity = score_remediation(
        finding=context["finding"],
        strategy=chosen_strategy,
        patch=patch_entity,
    )
    metrics_entity = RemediationMetricsEntity(
        file=str(context["finding"]["file"]),
        vulnerability_type=str(context["finding"]["category"]),
        remediation_mode=mode,
        analyzed_lines=count_analyzed_lines(context),
        path_steps=count_path_steps(context, explanation_entity),
        evidence_location=f"{context['finding']['file']}:{context['finding']['line']}-{context['finding']['line_end']}",
    )
    steps = _build_step_entities(trace=trace, context=context, explanation=explanation_entity, remediation=remediation, metrics=metrics_entity)

    return RemediationPlanEntity(
        mode=mode,
        finding_ids=[finding_id],
        review_summary=_build_review_summary(
            remediation.get("review_summary"),
            strategies,
            patch_entity,
        ),
        explanation=explanation_entity,
        strategies=strategies,
        recommended_strategy_id=recommended_strategy_id or str(remediation.get("recommended_strategy_id") or ""),
        patch=patch_entity,
        steps=steps,
        metrics=metrics_entity,
        score=score_entity,
    )


def _build_step_entities(trace: list, context: dict, explanation: ExplanationEntity, remediation: dict, metrics: RemediationMetricsEntity) -> list[RemediationStepEntity]:
    strategy_labels = [str(item.get("label", "strategy")) for item in remediation.get("strategies", [])[:3]]
    details_map = {
        "context_shape": [
            f"Loaded evidence from {metrics.evidence_location}",
            f"Analyzing {metrics.analyzed_lines} relevant lines",
            f"Tracing {metrics.path_steps} execution steps",
        ],
        "explain_draft": [
            f"Detected {metrics.vulnerability_type} pattern",
            f"Entry point: {explanation.entry_point}",
            f"Sink: {explanation.sink}",
        ],
        "fix_draft": [
            *(f"Generating {label}" for label in strategy_labels),
            "Comparing safe, guard, and structural remediation options",
        ],
        "fix_validate": [
            "Validating patch structure",
            "Checking logic safety against the original path",
            "Rejecting unsafe remediation variants",
        ],
        "fix_retry": [
            "Previous remediation scored below the decision threshold",
            "Applying category-specific corrective constraints",
            "Regenerating materially stronger alternatives",
        ],
        "final_patch": [
            "Rendering code diff",
            "Summarizing security improvement",
            "Preparing review-ready remediation plan",
        ],
        "batch_plan": [
            f"Grouping {len(context.get('batch', {}).get('findings', []))} validated findings",
            "Building a shared remediation plan for the selected findings",
        ],
    }
    return [
        RemediationStepEntity(
            id=item.task_name,
            title=item.label,
            status="done",
            agent=item.agent,
            model=getattr(item, "model", ""),
            details=[
                *details_map.get(item.task_name, []),
                *list(getattr(item, "details", []) or []),
            ],
        )
        for item in trace
    ]


def _build_review_summary(review_summary: object, strategies: list[FixStrategyEntity], patch: PatchCandidateEntity) -> str:
    if strategies:
        recommended = strategies[0]
        return (
            f"{recommended.label} was selected as the preferred remediation because it provides a "
            f"{recommended.fix_type.replace('_', ' ')} with {recommended.security_strength} security strength. "
            f"Patch review focuses on {patch.file}."
        )
    if isinstance(review_summary, str) and review_summary.strip():
        return review_summary
    return "Generated a remediation plan from the real scan evidence."


def _derive_snippet_from_diff(diff: str) -> str:
    lines: list[str] = []
    for raw_line in diff.splitlines():
        line = raw_line.rstrip("\n")
        if line.startswith(("+++ ", "--- ", "@@")):
            continue
        if line.startswith("+") and not line.startswith("+++"):
            lines.append(line[1:])
    if not lines:
        return ""
    return "\n".join(lines[:16])


def remediation_plan_is_usable(plan: RemediationPlanResponse) -> bool:
    has_strategies = bool(plan.strategies)
    has_patch = bool(plan.patch and plan.patch.diff.strip() and plan.patch.after_snippet.strip())
    return has_strategies and has_patch


def remediation_plan_failure_reason(plan: RemediationPlanResponse) -> str:
    reasons: list[str] = []
    if not plan.strategies:
        reasons.append("No remediation strategy was produced.")
    if not plan.patch:
        reasons.append("No patch candidate was produced.")
    else:
        if not plan.patch.diff.strip():
            reasons.append("No patch diff was generated.")
        if not plan.patch.after_snippet.strip():
            reasons.append("No updated code snippet was generated.")
        for note in plan.patch.validation_notes[:4]:
            if note and note not in reasons:
                reasons.append(note)
    if plan.score and plan.score.rationale:
        for note in plan.score.rationale[:2]:
            if note and note not in reasons:
                reasons.append(note)
    if not reasons:
        reasons.append("The remediation engine did not return a review-ready patch.")
    return " ".join(reasons[:4])
