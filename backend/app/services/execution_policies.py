"""
Employee Execution Policies — role-specific state machines.

Each employee role gets a different execution pipeline:
- Atlas (Software Engineer): full coding cycle with sandbox execution
- Scout (Researcher): research → analyze → synthesize
- Arc (Architect): design → evaluate → refine
- Sage (Business Analyst): analyze → structure → review
- Sentinel (QA Engineer): analyze → test → report
- Scribe (Technical Writer): research → write → review

The controller loads the policy for the employee's role and uses
its states, transitions, and phase prompts instead of hardcoded values.
"""

from enum import Enum
from dataclasses import dataclass, field


class Phase(str, Enum):
    PLANNING = "PLANNING"
    IMPLEMENTING = "IMPLEMENTING"
    EXECUTING = "EXECUTING"
    OBSERVING = "OBSERVING"
    REPAIRING = "REPAIRING"
    TESTING = "TESTING"
    QA = "QA"
    DELIVERING = "DELIVERING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    RESEARCHING = "RESEARCHING"
    ANALYZING = "ANALYZING"
    SYNTHESIZING = "SYNTHESIZING"
    DESIGNING = "DESIGNING"
    EVALUATING = "EVALUATING"
    REFINING = "REFINING"
    STRUCTURING = "STRUCTURING"
    REVIEWING = "REVIEWING"
    WRITING = "WRITING"
    REPORTING = "REPORTING"


TERMINAL_PHASES = {Phase.COMPLETED, Phase.FAILED, Phase.CANCELLED}


@dataclass
class ExecutionPolicy:
    role: str
    phases: list[Phase]
    transitions: dict[Phase, list[Phase]]
    phase_prompts: dict[Phase, str]
    tools_per_phase: dict[Phase, list[str] | None] = field(default_factory=dict)


# ── Atlas: Software Engineer ──────────────────────────────────────────

ATLAS_POLICY = ExecutionPolicy(
    role="software engineer",
    phases=[
        Phase.PLANNING, Phase.IMPLEMENTING, Phase.EXECUTING,
        Phase.OBSERVING, Phase.REPAIRING, Phase.TESTING,
        Phase.QA, Phase.DELIVERING,
    ],
    transitions={
        Phase.PLANNING: [Phase.IMPLEMENTING, Phase.FAILED],
        Phase.IMPLEMENTING: [Phase.EXECUTING, Phase.IMPLEMENTING, Phase.FAILED],
        Phase.EXECUTING: [Phase.OBSERVING, Phase.FAILED],
        Phase.OBSERVING: [Phase.REPAIRING, Phase.TESTING, Phase.IMPLEMENTING, Phase.FAILED],
        Phase.REPAIRING: [Phase.EXECUTING, Phase.REPAIRING, Phase.FAILED],
        Phase.TESTING: [Phase.QA, Phase.REPAIRING, Phase.FAILED],
        Phase.QA: [Phase.DELIVERING, Phase.REPAIRING, Phase.FAILED],
        Phase.DELIVERING: [Phase.COMPLETED, Phase.FAILED],
    },
    phase_prompts={
        Phase.PLANNING: (
            "PLANNING phase. Analyze the goal and create a concrete, step-by-step plan.\n"
            "Output a numbered list of implementation steps. Be specific about files, functions, and tests.\n"
            "End with a clear summary of what you will build. Do NOT start coding yet."
        ),
        Phase.IMPLEMENTING: (
            "IMPLEMENTING phase. Write the code according to your plan.\n"
            "Use write_file to create each file. Use read_file to check existing code.\n"
            "Implement ALL needed code — models, logic, endpoints, config.\n"
            "When all files are written, respond with your transition decision."
        ),
        Phase.EXECUTING: (
            "EXECUTING phase. Run the code you wrote to verify it works.\n"
            "Use run_code to execute the main entry point or start the application.\n"
            "Install packages if needed. Report the output exactly as it appears."
        ),
        Phase.OBSERVING: (
            "OBSERVING phase. Analyze the execution results.\n"
            "If errors occurred, identify root cause and what needs fixing.\n"
            "If execution succeeded, decide whether to run tests or proceed.\n"
            "Respond with your transition decision."
        ),
        Phase.REPAIRING: (
            "REPAIRING phase. Fix the issues identified in the previous phase.\n"
            "Read the failing files, identify the bug, and use write_file to fix them.\n"
            "When all fixes are applied, respond with your transition decision."
        ),
        Phase.TESTING: (
            "TESTING phase. Write and run tests for the code you built.\n"
            "Use write_file to create test files, then run_code to execute them.\n"
            "Report test results. Respond with your transition decision."
        ),
        Phase.QA: (
            "QA phase. Review the entire codebase you've built.\n"
            "List all files created. Check for: missing error handling, security issues,\n"
            "incomplete implementations, missing edge cases.\n"
            "Respond with your transition decision."
        ),
        Phase.DELIVERING: (
            "DELIVERING phase. Prepare a final summary of what was built.\n"
            "List all files created, key decisions made, and how to use the result.\n"
            "This summary will be shown to the user as the deliverable."
        ),
    },
)

# ── Scout: Researcher ─────────────────────────────────────────────────

SCOUT_POLICY = ExecutionPolicy(
    role="researcher",
    phases=[
        Phase.PLANNING, Phase.RESEARCHING, Phase.ANALYZING,
        Phase.SYNTHESIZING, Phase.QA, Phase.DELIVERING,
    ],
    transitions={
        Phase.PLANNING: [Phase.RESEARCHING, Phase.FAILED],
        Phase.RESEARCHING: [Phase.ANALYZING, Phase.RESEARCHING, Phase.FAILED],
        Phase.ANALYZING: [Phase.SYNTHESIZING, Phase.RESEARCHING, Phase.FAILED],
        Phase.SYNTHESIZING: [Phase.QA, Phase.ANALYZING, Phase.FAILED],
        Phase.QA: [Phase.DELIVERING, Phase.RESEARCHING, Phase.FAILED],
        Phase.DELIVERING: [Phase.COMPLETED, Phase.FAILED],
    },
    phase_prompts={
        Phase.PLANNING: (
            "PLANNING phase. Break the research goal into specific questions to investigate.\n"
            "List each question, potential sources, and what evidence would answer it.\n"
            "Do NOT start researching yet — just plan the investigation."
        ),
        Phase.RESEARCHING: (
            "RESEARCHING phase. Investigate the questions from your plan.\n"
            "Use web_search and read_url to gather information from multiple sources.\n"
            "Document key findings with source attribution.\n"
            "When you have enough evidence, respond with your transition decision."
        ),
        Phase.ANALYZING: (
            "ANALYZING phase. Analyze the research findings.\n"
            "Identify patterns, contradictions, gaps in the evidence.\n"
            "Compare different sources and assess credibility.\n"
            "If more research is needed, indicate that. Otherwise, proceed to synthesis."
        ),
        Phase.SYNTHESIZING: (
            "SYNTHESIZING phase. Synthesize findings into a coherent report.\n"
            "Structure the report with clear sections, evidence-backed conclusions.\n"
            "Highlight areas of uncertainty. Include recommendations where appropriate.\n"
            "Use write_file to save the report."
        ),
        Phase.QA: (
            "QA phase. Review the research report for quality.\n"
            "Check: Are conclusions supported by evidence? Are sources cited?\n"
            "Are there logical gaps? Is the report actionable?\n"
            "Respond with your transition decision."
        ),
        Phase.DELIVERING: (
            "DELIVERING phase. Prepare the final research deliverable.\n"
            "Summarize key findings, recommendations, and next steps.\n"
            "This summary will be shown to the user."
        ),
    },
)

# ── Arc: Architect ────────────────────────────────────────────────────

ARC_POLICY = ExecutionPolicy(
    role="architect",
    phases=[
        Phase.PLANNING, Phase.DESIGNING, Phase.EVALUATING,
        Phase.REFINING, Phase.QA, Phase.DELIVERING,
    ],
    transitions={
        Phase.PLANNING: [Phase.DESIGNING, Phase.FAILED],
        Phase.DESIGNING: [Phase.EVALUATING, Phase.DESIGNING, Phase.FAILED],
        Phase.EVALUATING: [Phase.REFINING, Phase.DESIGNING, Phase.FAILED],
        Phase.REFINING: [Phase.QA, Phase.EVALUATING, Phase.FAILED],
        Phase.QA: [Phase.DELIVERING, Phase.REFINING, Phase.FAILED],
        Phase.DELIVERING: [Phase.COMPLETED, Phase.FAILED],
    },
    phase_prompts={
        Phase.PLANNING: (
            "PLANNING phase. Understand the design requirements.\n"
            "List constraints, quality attributes, stakeholder concerns.\n"
            "Identify what architecture decisions need to be made.\n"
            "Do NOT start designing yet."
        ),
        Phase.DESIGNING: (
            "DESIGNING phase. Create the architecture design.\n"
            "Define components, interfaces, data flows, tech stack choices.\n"
            "Document trade-offs for each decision.\n"
            "Use write_file to save architecture docs and diagrams.\n"
            "When the design is complete, respond with your transition decision."
        ),
        Phase.EVALUATING: (
            "EVALUATING phase. Evaluate the architecture against requirements.\n"
            "Check scalability, security, maintainability, performance.\n"
            "Identify risks and mitigation strategies.\n"
            "If the design needs changes, indicate that."
        ),
        Phase.REFINING: (
            "REFINING phase. Refine the architecture based on evaluation.\n"
            "Address identified risks. Improve weak areas.\n"
            "Update architecture docs with refined design.\n"
            "When refinement is complete, respond with your transition decision."
        ),
        Phase.QA: (
            "QA phase. Final quality review of the architecture.\n"
            "Verify all requirements are addressed. Check for missing components.\n"
            "Validate tech stack compatibility. Confirm deployment strategy.\n"
            "Respond with your transition decision."
        ),
        Phase.DELIVERING: (
            "DELIVERING phase. Prepare the architecture deliverable.\n"
            "Summarize key decisions, component overview, deployment plan.\n"
            "This will be shared with the team."
        ),
    },
)

# ── Sage: Business Analyst ────────────────────────────────────────────

SAGE_POLICY = ExecutionPolicy(
    role="business analyst",
    phases=[
        Phase.PLANNING, Phase.ANALYZING, Phase.STRUCTURING,
        Phase.REVIEWING, Phase.QA, Phase.DELIVERING,
    ],
    transitions={
        Phase.PLANNING: [Phase.ANALYZING, Phase.FAILED],
        Phase.ANALYZING: [Phase.STRUCTURING, Phase.ANALYZING, Phase.FAILED],
        Phase.STRUCTURING: [Phase.REVIEWING, Phase.ANALYZING, Phase.FAILED],
        Phase.REVIEWING: [Phase.QA, Phase.STRUCTURING, Phase.FAILED],
        Phase.QA: [Phase.DELIVERING, Phase.ANALYZING, Phase.FAILED],
        Phase.DELIVERING: [Phase.COMPLETED, Phase.FAILED],
    },
    phase_prompts={
        Phase.PLANNING: (
            "PLANNING phase. Understand the business goal and stakeholder needs.\n"
            "List key questions, assumptions, and success criteria.\n"
            "Identify what data or context is needed for analysis."
        ),
        Phase.ANALYZING: (
            "ANALYZING phase. Analyze the business problem.\n"
            "Break down requirements, identify user stories, map processes.\n"
            "Document assumptions and dependencies.\n"
            "When analysis is sufficient, respond with your transition decision."
        ),
        Phase.STRUCTURING: (
            "STRUCTURING phase. Structure findings into formal deliverables.\n"
            "Create user stories, acceptance criteria, process flows.\n"
            "Use write_file to save structured documents.\n"
            "When structuring is complete, respond with your transition decision."
        ),
        Phase.REVIEWING: (
            "REVIEWING phase. Review structured deliverables for completeness.\n"
            "Check that all requirements are captured. Validate acceptance criteria.\n"
            "Identify gaps or ambiguities.\n"
            "If issues found, indicate what needs rework."
        ),
        Phase.QA: (
            "QA phase. Final quality check on business analysis deliverables.\n"
            "Verify traceability, consistency, and completeness.\n"
            "Respond with your transition decision."
        ),
        Phase.DELIVERING: (
            "DELIVERING phase. Prepare the final business analysis deliverable.\n"
            "Summarize requirements, user stories, and recommendations.\n"
            "This will be shared with the team for implementation."
        ),
    },
)

# ── Sentinel: QA Engineer ────────────────────────────────────────────

SENTINEL_POLICY = ExecutionPolicy(
    role="qa engineer",
    phases=[
        Phase.PLANNING, Phase.ANALYZING, Phase.TESTING,
        Phase.REPORTING, Phase.QA, Phase.DELIVERING,
    ],
    transitions={
        Phase.PLANNING: [Phase.ANALYZING, Phase.FAILED],
        Phase.ANALYZING: [Phase.TESTING, Phase.ANALYZING, Phase.FAILED],
        Phase.TESTING: [Phase.REPORTING, Phase.REPAIRING, Phase.FAILED],
        Phase.REPAIRING: [Phase.TESTING, Phase.FAILED],
        Phase.REPORTING: [Phase.QA, Phase.TESTING, Phase.FAILED],
        Phase.QA: [Phase.DELIVERING, Phase.TESTING, Phase.FAILED],
        Phase.DELIVERING: [Phase.COMPLETED, Phase.FAILED],
    },
    phase_prompts={
        Phase.PLANNING: (
            "PLANNING phase. Understand what needs to be tested.\n"
            "List test scenarios, edge cases, and quality criteria.\n"
            "Identify test types needed: unit, integration, end-to-end."
        ),
        Phase.ANALYZING: (
            "ANALYZING phase. Analyze the code/system under test.\n"
            "Read existing code to understand behavior. Identify risk areas.\n"
            "Map test coverage gaps.\n"
            "When analysis is complete, respond with your transition decision."
        ),
        Phase.TESTING: (
            "TESTING phase. Write and execute tests.\n"
            "Use write_file to create test files. Use run_code to execute them.\n"
            "Document all test results — pass, fail, and error.\n"
            "When testing is complete, respond with your transition decision."
        ),
        Phase.REPAIRING: (
            "REPAIRING phase. Fix test infrastructure issues (not the code under test).\n"
            "Fix test setup, fixtures, or configuration problems.\n"
            "When fixes are applied, respond with your transition decision."
        ),
        Phase.REPORTING: (
            "REPORTING phase. Compile test results into a structured report.\n"
            "Summarize: tests passed, tests failed, coverage, risk assessment.\n"
            "Use write_file to save the test report."
        ),
        Phase.QA: (
            "QA phase. Review the test report for thoroughness.\n"
            "Are all scenarios covered? Are failure descriptions actionable?\n"
            "Respond with your transition decision."
        ),
        Phase.DELIVERING: (
            "DELIVERING phase. Prepare the final QA deliverable.\n"
            "Summarize test results, found issues, and recommendations.\n"
            "This will be shared with the team."
        ),
    },
)

# ── Scribe: Technical Writer ─────────────────────────────────────────

SCRIBE_POLICY = ExecutionPolicy(
    role="technical writer",
    phases=[
        Phase.PLANNING, Phase.RESEARCHING, Phase.WRITING,
        Phase.REVIEWING, Phase.QA, Phase.DELIVERING,
    ],
    transitions={
        Phase.PLANNING: [Phase.RESEARCHING, Phase.FAILED],
        Phase.RESEARCHING: [Phase.WRITING, Phase.RESEARCHING, Phase.FAILED],
        Phase.WRITING: [Phase.REVIEWING, Phase.WRITING, Phase.FAILED],
        Phase.REVIEWING: [Phase.QA, Phase.WRITING, Phase.FAILED],
        Phase.QA: [Phase.DELIVERING, Phase.WRITING, Phase.FAILED],
        Phase.DELIVERING: [Phase.COMPLETED, Phase.FAILED],
    },
    phase_prompts={
        Phase.PLANNING: (
            "PLANNING phase. Understand the documentation goal.\n"
            "List topics to cover, target audience, and document structure.\n"
            "Identify what source material needs to be gathered."
        ),
        Phase.RESEARCHING: (
            "RESEARCHING phase. Gather source material for documentation.\n"
            "Read code, existing docs, and reference material.\n"
            "Note key concepts, APIs, and usage patterns.\n"
            "When research is sufficient, respond with your transition decision."
        ),
        Phase.WRITING: (
            "WRITING phase. Write the documentation.\n"
            "Use write_file to create documentation files.\n"
            "Follow best practices: clear headings, code examples, step-by-step guides.\n"
            "When writing is complete, respond with your transition decision."
        ),
        Phase.REVIEWING: (
            "REVIEWING phase. Review the documentation for quality.\n"
            "Check accuracy, completeness, clarity, and consistency.\n"
            "Verify code examples work. Check for broken links.\n"
            "If improvements needed, indicate what to revise."
        ),
        Phase.QA: (
            "QA phase. Final quality review of documentation.\n"
            "Verify technical accuracy. Check formatting and structure.\n"
            "Respond with your transition decision."
        ),
        Phase.DELIVERING: (
            "DELIVERING phase. Prepare the final documentation deliverable.\n"
            "Summarize what was documented and where files are located.\n"
            "This will be shared with the team."
        ),
    },
)

# ── Generic fallback ─────────────────────────────────────────────────

GENERIC_POLICY = ExecutionPolicy(
    role="generic",
    phases=[
        Phase.PLANNING, Phase.IMPLEMENTING, Phase.REVIEWING,
        Phase.QA, Phase.DELIVERING,
    ],
    transitions={
        Phase.PLANNING: [Phase.IMPLEMENTING, Phase.FAILED],
        Phase.IMPLEMENTING: [Phase.REVIEWING, Phase.IMPLEMENTING, Phase.FAILED],
        Phase.REVIEWING: [Phase.QA, Phase.IMPLEMENTING, Phase.FAILED],
        Phase.QA: [Phase.DELIVERING, Phase.IMPLEMENTING, Phase.FAILED],
        Phase.DELIVERING: [Phase.COMPLETED, Phase.FAILED],
    },
    phase_prompts={
        Phase.PLANNING: (
            "PLANNING phase. Analyze the goal and create a step-by-step plan.\n"
            "List what needs to be done. Do NOT start working yet."
        ),
        Phase.IMPLEMENTING: (
            "IMPLEMENTING phase. Execute the plan step by step.\n"
            "Use your tools to complete the work.\n"
            "When done, respond with your transition decision."
        ),
        Phase.REVIEWING: (
            "REVIEWING phase. Review your work for quality and completeness.\n"
            "Check for errors, gaps, or improvements.\n"
            "If issues found, indicate what needs rework."
        ),
        Phase.QA: (
            "QA phase. Final quality check.\n"
            "Verify the work meets the goal requirements.\n"
            "Respond with your transition decision."
        ),
        Phase.DELIVERING: (
            "DELIVERING phase. Prepare the final deliverable.\n"
            "Summarize what was done and the result."
        ),
    },
)


# ── Policy registry ──────────────────────────────────────────────────

_ROLE_POLICIES: dict[str, ExecutionPolicy] = {
    "software engineer": ATLAS_POLICY,
    "researcher": SCOUT_POLICY,
    "architect": ARC_POLICY,
    "business analyst": SAGE_POLICY,
    "qa engineer": SENTINEL_POLICY,
    "technical writer": SCRIBE_POLICY,
}


def get_policy_for_role(role: str) -> ExecutionPolicy:
    """Get the execution policy for an employee role. Falls back to generic."""
    return _ROLE_POLICIES.get(role.lower(), GENERIC_POLICY)


def get_valid_transitions(policy: ExecutionPolicy, current_phase: Phase) -> list[Phase]:
    """Get the valid next phases from the current phase."""
    return policy.transitions.get(current_phase, [Phase.FAILED])


def get_phase_prompt(policy: ExecutionPolicy, phase: Phase) -> str:
    """Get the phase-specific prompt."""
    return policy.phase_prompts.get(phase, f"You are in the {phase.value} phase. Complete this phase.")
