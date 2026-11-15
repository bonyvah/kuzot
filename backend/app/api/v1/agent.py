from uuid import UUID

import openai
from fastapi import APIRouter, HTTPException
from pinecone.errors import PineconeError

from app.agent.data import load_context
from app.agent.graph import ask
from app.core.auth_dependencies import CurrentUser, require_org_role
from app.core.exceptions import AIServiceError
from app.crud.workspace import workspace_crud
from app.db.dependencies import DBSession, MongoDBDep
from app.models.org_member import MemberRole
from app.schemas.agent import AskRequest, AskResponse

router = APIRouter(tags=["Agent"])


@router.post("/workspaces/{workspace_id}/ask", response_model=AskResponse)
async def ask_about_competitors(
    workspace_id: UUID,
    body: AskRequest,
    current_user: CurrentUser,
    db: DBSession,
    mongo: MongoDBDep,
):
    workspace = await workspace_crud.get_by_id(db, workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    await require_org_role(current_user, workspace.org_id, MemberRole.MEMBER, db)
    ctx = await load_context(db, mongo, workspace)
    try:
        return await ask(body.question, ctx)
    except (openai.OpenAIError, PineconeError) as exc:
        raise AIServiceError(type(exc).__name__)
