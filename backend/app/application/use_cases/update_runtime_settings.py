from app.application.dto.runtime_settings_contracts import RuntimeSettingsResponse, UpdateRuntimeSettingsRequest
from app.infrastructure.settings.runtime_settings_service import RuntimeSettingsService


class UpdateRuntimeSettingsUseCase:
    def __init__(self, service: RuntimeSettingsService) -> None:
        self.service = service

    async def execute(self, payload: UpdateRuntimeSettingsRequest) -> RuntimeSettingsResponse:
        return await self.service.update(payload.model_dump(exclude_none=True))
