from app.infrastructure.permission.models import Decision, PermissionRequest, Prompter


class YoloPrompter(Prompter):
    def __init__(self, inner: Prompter, initial: bool = False):
        self._inner = inner
        self._yolo = initial

    def set_yolo(self, on: bool) -> None:
        self._yolo = on

    def is_yolo(self) -> bool:
        return self._yolo

    async def ask(self, request: PermissionRequest) -> Decision:
        if self._yolo and not request.bypass_yolo:
            return "allow-once"
        return await self._inner.ask(request)


class AlwaysAllow(Prompter):
    async def ask(self, request: PermissionRequest) -> Decision:
        return "allow-once"


class AlwaysDeny(Prompter):
    async def ask(self, request: PermissionRequest) -> Decision:
        return "deny"
