import structlog

from mcp_template_py.api.models import HelloResponse


class Tools:
    def __init__(self):
        self._logger: structlog.BoundLogger = structlog.get_logger()

    async def hello(self, name: str) -> HelloResponse:
        """Say hello to the user."""
        self._logger.info("hello tool called", name=name)
        return HelloResponse(result=f"Hello, {name}!")
