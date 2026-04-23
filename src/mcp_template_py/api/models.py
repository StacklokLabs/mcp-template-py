"""
Defines response schemas for MCP tools as Pydantic models.

Tool arguments are passed as flat parameters on the tool method (so MCP clients
see individual fields), not as a single Pydantic model. Responses stay as
Pydantic models so the MCP output schema is explicit and typed.
"""

from pydantic import BaseModel, Field

__all__ = [
    "HelloResponse",
]


class HelloResponse(BaseModel):
    result: str = Field(..., description="The greeting message.")
