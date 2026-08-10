# Database Schema

SQLite database: `company.db`

## Tables

### projects
| Column | Type | Description |
|--------|------|-------------|
| id | TEXT (PK) | 12-char hex UUID |
| problem_statement | TEXT | Founder's input |
| status | TEXT | Current pipeline stage |
| created_at | TEXT | ISO timestamp |
| updated_at | TEXT | ISO timestamp |

**Status values:**
`created` → `ba_working` → `ba_review` → `research_working` → `research_review` → `architect_working` → `architect_review` → `engineer_working` → `engineer_review` → `ppt_working` → `completed`

### agent_outputs
| Column | Type | Description |
|--------|------|-------------|
| id | TEXT (PK) | 12-char hex UUID |
| project_id | TEXT (FK) | Links to projects |
| role | TEXT | Agent role (ceo, business_analyst, etc.) |
| content | TEXT | JSON blob of agent's output |
| status | TEXT | pending / approved / rejected |
| created_at | TEXT | ISO timestamp |

### conversations
| Column | Type | Description |
|--------|------|-------------|
| id | TEXT (PK) | 12-char hex UUID |
| project_id | TEXT (FK) | Links to projects |
| agent_role | TEXT | Which agent |
| messages | TEXT | JSON array of {role, content} |
| updated_at | TEXT | ISO timestamp |

### shared_memory
| Column | Type | Description |
|--------|------|-------------|
| id | TEXT (PK) | 12-char hex UUID |
| project_id | TEXT (FK) | Links to projects |
| key | TEXT | Memory key (unique per project) |
| value | TEXT | Memory value |
| updated_by | TEXT | Which agent wrote this |
| updated_at | TEXT | ISO timestamp |

**Unique constraint:** (project_id, key)

Related: [[Tech Stack]], [[Orchestrator]]
