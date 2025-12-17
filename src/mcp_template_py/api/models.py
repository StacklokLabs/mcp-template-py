"""
Defines request and response schemas for MCP tools as Pydantic models.
"""

from pydantic import BaseModel, Field

__all__ = [
    "HelloRequest",
    "HelloResponse",
]


class HelloRequest(BaseModel):
    name: str = Field(..., description="The name of the user making the request.")


class HelloResponse(BaseModel):
    result: str = Field(..., description="The greeting message.")
