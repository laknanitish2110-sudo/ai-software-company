from __future__ import annotations
from pydantic import BaseModel
from enum import Enum
from typing import Any


class ProjectStatus(str, Enum):
    CREATED = "created"
    BA_WORKING = "ba_working"
    BA_REVIEW = "ba_review"
    RESEARCH_WORKING = "research_working"
    RESEARCH_REVIEW = "research_review"
    ARCHITECT_WORKING = "architect_working"
    ARCHITECT_REVIEW = "architect_review"
    ENGINEER_WORKING = "engineer_working"
    ENGINEER_REVIEW = "engineer_review"
    PPT_WORKING = "ppt_working"
    COMPLETED = "completed"
    PAUSED = "paused"


class AgentRole(str, Enum):
    CEO = "ceo"
    BUSINESS_ANALYST = "business_analyst"
    RESEARCHER = "researcher"
    ARCHITECT = "architect"
    ENGINEER = "engineer"
    PPT = "ppt"


PIPELINE_ORDER = [
    AgentRole.BUSINESS_ANALYST,
    AgentRole.RESEARCHER,
    AgentRole.ARCHITECT,
    AgentRole.ENGINEER,
    AgentRole.PPT,
]

REVIEW_STAGES = {
    AgentRole.BUSINESS_ANALYST: ProjectStatus.BA_REVIEW,
    AgentRole.RESEARCHER: ProjectStatus.RESEARCH_REVIEW,
    AgentRole.ARCHITECT: ProjectStatus.ARCHITECT_REVIEW,
    AgentRole.ENGINEER: ProjectStatus.ENGINEER_REVIEW,
}

WORKING_STAGES = {
    AgentRole.BUSINESS_ANALYST: ProjectStatus.BA_WORKING,
    AgentRole.RESEARCHER: ProjectStatus.RESEARCH_WORKING,
    AgentRole.ARCHITECT: ProjectStatus.ARCHITECT_WORKING,
    AgentRole.ENGINEER: ProjectStatus.ENGINEER_WORKING,
    AgentRole.PPT: ProjectStatus.PPT_WORKING,
}


class CreateProjectRequest(BaseModel):
    problem_statement: str


class ApprovalRequest(BaseModel):
    approved: bool
    feedback: str | None = None


class CallEmployeeRequest(BaseModel):
    role: AgentRole
    message: str


class Project(BaseModel):
    id: str
    problem_statement: str
    status: ProjectStatus
    created_at: str
    updated_at: str


class AgentOutput(BaseModel):
    id: str
    project_id: str
    role: AgentRole
    content: dict[str, Any]
    status: str  # pending, approved, rejected
    created_at: str


class ChatMessage(BaseModel):
    role: str  # user or assistant
    content: str


class ConversationHistory(BaseModel):
    project_id: str
    agent_role: AgentRole
    messages: list[ChatMessage]


class ProjectState(BaseModel):
    project: Project
    outputs: list[AgentOutput]
    current_agent: AgentRole | None
    pending_approval: bool


class WSMessage(BaseModel):
    type: str  # agent_started, agent_progress, agent_completed, approval_needed, status_update
    project_id: str
    data: dict[str, Any]
