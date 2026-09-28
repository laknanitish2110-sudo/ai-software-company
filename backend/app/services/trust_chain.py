"""
Cross-Agent Trust Chain — Accountability across delegation boundaries.

When Atlas delegates to Scout, this produces a proof trail:
- WHO authorized the delegation (authority basis)
- WHAT evidence supported the decision
- WHETHER the result was independently verified
- HOW trust propagates across the chain

This is Gap E from the deep thesis: "Can I trust what another agent did?"
The answer is a verifiable chain, not a handshake.
"""

import hashlib
import json
import logging

from app.core.database import (
    create_trust_link,
    verify_trust_link,
    fail_trust_link,
    get_trust_chain,
    get_execution_trust_links,
    get_agent_trust_history,
    get_agent_trust_score,
    new_id,
)

logger = logging.getLogger(__name__)


async def record_delegation_trust(
    from_agent_id: str,
    from_agent_name: str,
    to_agent_id: str,
    to_agent_name: str,
    execution_id: str,
    task_description: str,
    authority_basis: str | None = None,
    parent_link_id: str | None = None,
    chain_id: str | None = None,
) -> dict:
    if not chain_id:
        chain_id = f"chain_{new_id()}"

    depth = 0
    if parent_link_id:
        chain = await get_trust_chain(chain_id)
        parent = next((l for l in chain if l["id"] == parent_link_id), None)
        if parent:
            depth = parent["depth"] + 1

    evidence = _build_evidence_summary(
        from_agent=from_agent_name,
        to_agent=to_agent_name,
        task=task_description,
    )

    link = await create_trust_link(
        chain_id=chain_id,
        from_agent_id=from_agent_id,
        to_agent_id=to_agent_id,
        action_type="delegation",
        from_agent_name=from_agent_name,
        to_agent_name=to_agent_name,
        execution_id=execution_id,
        parent_link_id=parent_link_id,
        depth=depth,
        task_description=task_description[:500] if task_description else None,
        authority_basis=authority_basis or f"delegated_by:{from_agent_name}",
        evidence_summary=json.dumps(evidence),
    )

    logger.info(
        f"Trust link created: {from_agent_name} → {to_agent_name} "
        f"(chain={chain_id}, depth={depth})"
    )
    return {**link, "chain_id": chain_id}


async def record_execution_trust(
    agent_id: str,
    agent_name: str,
    execution_id: str,
    action_type: str = "execution",
    task_description: str | None = None,
    chain_id: str | None = None,
    parent_link_id: str | None = None,
) -> dict:
    if not chain_id:
        chain_id = f"chain_{new_id()}"

    return await create_trust_link(
        chain_id=chain_id,
        from_agent_id=agent_id,
        to_agent_id=agent_id,
        action_type=action_type,
        from_agent_name=agent_name,
        to_agent_name=agent_name,
        execution_id=execution_id,
        parent_link_id=parent_link_id,
        depth=0,
        task_description=task_description,
        authority_basis=f"self_execution:{agent_name}",
    )


async def verify_chain_on_sentinel_pass(execution_id: str) -> int:
    links = await get_execution_trust_links(execution_id)
    verified = 0
    for link in links:
        if link["verification_status"] == "pending":
            score = _calculate_link_trust(link)
            await verify_trust_link(link["id"], verified_by="sentinel", trust_score=score)
            verified += 1
    logger.info(f"Verified {verified}/{len(links)} trust links for execution {execution_id}")
    return verified


async def fail_chain_on_sentinel_fail(execution_id: str) -> int:
    links = await get_execution_trust_links(execution_id)
    failed = 0
    for link in links:
        if link["verification_status"] == "pending":
            await fail_trust_link(link["id"], reason="sentinel_rejected")
            failed += 1
    return failed


async def get_proof_trail(execution_id: str) -> dict:
    links = await get_execution_trust_links(execution_id)

    chain_ids = list(set(l["chain_id"] for l in links))
    full_chains = {}
    for cid in chain_ids:
        full_chains[cid] = await get_trust_chain(cid)

    total_links = len(links)
    verified_links = len([l for l in links if l["verification_status"] == "verified"])
    failed_links = len([l for l in links if l["verification_status"] not in ("verified", "pending")])

    agents_involved = list(set(
        [l["from_agent_name"] for l in links if l["from_agent_name"]] +
        [l["to_agent_name"] for l in links if l["to_agent_name"]]
    ))

    max_depth = max((l["depth"] for l in links), default=0)

    integrity = "intact"
    if failed_links > 0:
        integrity = "broken"
    elif total_links > verified_links:
        integrity = "partial"

    return {
        "execution_id": execution_id,
        "links": links,
        "chains": full_chains,
        "total_links": total_links,
        "verified_links": verified_links,
        "failed_links": failed_links,
        "pending_links": total_links - verified_links - failed_links,
        "agents_involved": agents_involved,
        "max_delegation_depth": max_depth,
        "chain_integrity": integrity,
        "trust_ratio": round(verified_links / max(total_links, 1), 2),
    }


async def get_agent_trust(agent_id: str) -> dict:
    score = await get_agent_trust_score(agent_id)
    history = await get_agent_trust_history(agent_id, limit=20)
    return {
        "agent_id": agent_id,
        "score": score,
        "recent_verifications": history,
    }


def _calculate_link_trust(link: dict) -> float:
    base = 0.7
    if link.get("depth", 0) == 0:
        base = 0.9
    elif link["depth"] == 1:
        base = 0.8
    else:
        base = max(0.5, 0.9 - (link["depth"] * 0.1))
    return round(base, 2)


def _build_evidence_summary(from_agent: str, to_agent: str, task: str) -> dict:
    content = f"{from_agent}:{to_agent}:{task}"
    return {
        "delegator": from_agent,
        "delegate": to_agent,
        "task_hash": hashlib.sha256(content.encode()).hexdigest()[:16],
        "task_preview": task[:200] if task else None,
    }
