from fastapi import APIRouter, Depends

from app.application.dto.runtime_settings_contracts import RuntimeSettingsResponse, UpdateRuntimeSettingsRequest
from app.application.use_cases.get_runtime_settings import GetRuntimeSettingsUseCase
from app.application.use_cases.update_runtime_settings import UpdateRuntimeSettingsUseCase
from app.presentation.api.v1.routes.dependencies import (
    get_runtime_settings_use_case,
    get_update_runtime_settings_use_case,
)


router = APIRouter()


@router.get("/settings/runtime", response_model=RuntimeSettingsResponse)
async def get_runtime_settings(
    use_case: GetRuntimeSettingsUseCase = Depends(get_runtime_settings_use_case),
):
    return await use_case.execute()


@router.patch("/settings/runtime", response_model=RuntimeSettingsResponse)
async def update_runtime_settings(
    payload: UpdateRuntimeSettingsRequest,
    use_case: UpdateRuntimeSettingsUseCase = Depends(get_update_runtime_settings_use_case),
):
    return await use_case.execute(payload)
