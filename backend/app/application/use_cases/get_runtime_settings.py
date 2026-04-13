from app.application.dto.runtime_settings_contracts import RuntimeSettingsResponse
from app.infrastructure.settings.runtime_settings_service import RuntimeSettingsService


class GetRuntimeSettingsUseCase:
    def __init__(self, service: RuntimeSettingsService) -> None:
        self.service = service

    async def execute(self) -> RuntimeSettingsResponse:
        return await self.service.get()
