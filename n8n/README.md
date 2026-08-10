# n8n Integration — AI Software Company

## Quick Setup

1. Install n8n: `npm install -g n8n` or use Docker
2. Start n8n: `n8n start` (runs on http://localhost:5678)
3. Import the workflow: In n8n, go to Workflows > Import > paste the JSON from `workflow_main.json`
4. Activate the workflow
5. Copy the webhook URL from the Webhook node (e.g., `http://localhost:5678/webhook/ai-company`)
6. Set it in `backend/.env`:
   ```
   N8N_WEBHOOK_URL=http://localhost:5678/webhook/ai-company
   ```
7. Restart the backend

## What It Does

The n8n workflow receives events from the AI Software Company backend and routes them:

### Event Types

| Event | When | What n8n Does |
|-------|------|---------------|
| `agent_completed` | Each agent finishes | Logs to Google Sheets, sends notification |
| `founder_decision` | You approve/reject | Logs decision + feedback to Sheets |
| `research_completed` | Researcher finishes | Logs sources to a separate sheet tab |
| `deliverables_ready` | Project completes | Notification + optional Drive upload |
| `project_completed` | All done | Final notification with summary |
| `share_drive` | You click "Google Drive" | Uploads files to Drive folder |
| `share_sheets` | You click "Google Sheets" | Exports structured data to Sheets |
| `share_email` | You click "Email Report" | Sends report email |
| `share_all` | You click "Share All" | Does all three |

### Required Credentials in n8n

- **Google Sheets** — for logging (create a sheet called "AI Company Log")
- **Google Drive** — for file uploads (create a folder called "AI Company Projects")
- **Gmail / SMTP** — for email notifications (optional)
- **Slack / Discord / Telegram** — for real-time notifications (pick one)

## Customization

Edit the workflow in n8n to:
- Change notification channels (Slack, Discord, Telegram, email)
- Change the Google Sheet/Drive structure
- Add more automation (e.g., auto-create Notion pages, Trello cards)
- Filter which events trigger notifications
