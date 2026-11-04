from datetime import datetime

from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


class AgentSource(BaseModel):
    number: int  # the [n] the answer cites
    competitor: str
    url: str
    text: str
    detected_at: datetime | None = None
    cited: bool = False


class ToolCallRecord(BaseModel):
    name: str
    args: dict
    error: str | None = None


class TokenUsage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0


class AskResponse(BaseModel):
    answer: str
    sources: list[AgentSource]
    # false: even after a retry the model stated facts it didn't cite, or cited
    # sources that don't exist (those markers are removed from the answer)
    citations_valid: bool
    tool_calls: list[ToolCallRecord]
    usage: TokenUsage
    model: str
