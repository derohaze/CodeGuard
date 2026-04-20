class ModelRouter:
    def __init__(
        self,
        *,
        small_model: str,
        large_model: str,
        overflow_model: str | None = None,
        scout_model: str | None = None,
        task_overrides: dict[str, str] | None = None,
    ) -> None:
        self.small_model = small_model
        self.large_model = large_model
        self.overflow_model = overflow_model
        self.scout_model = scout_model
        self.task_overrides = {
            str(task_name).strip().lower(): str(model).strip()
            for task_name, model in (task_overrides or {}).items()
            if str(task_name).strip() and str(model).strip()
        }

    def route(self, task_name: str) -> str:
        return self.route_candidates(task_name)[0]

    def route_candidates(self, task_name: str) -> list[str]:
        normalized = task_name.strip().lower()
        override = self.task_overrides.get(normalized)
        if override:
            return self._with_fallbacks(override)

        depth_tasks = {"explain", "fix_validate", "patch_validate", "final_patch", "verdict", "finding_validate"}
        if normalized in depth_tasks:
            return self._with_fallbacks(self.large_model)

        return self._with_fallbacks(self.small_model)

    def _with_fallbacks(self, primary_model: str) -> list[str]:
        models = [primary_model]
        for candidate in (self.overflow_model, self.scout_model):
            if candidate and candidate not in models:
                models.append(candidate)
        return models
