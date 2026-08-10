# Call Agents

AI agents that make and receive phone calls — replacing IVR menus, human call centers, and outbound sales teams with real-time voice AI over telephony networks.

---

## What is a Call Agent?

A **call agent** is a voice agent connected to the phone network (PSTN/SIP). It handles real phone calls — inbound (answering) and outbound (dialing) — with the same natural conversation as a human, but available 24/7 at scale.

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  Phone       │────►│  Telephony   │────►│  Voice AI    │
│  Network     │     │  (Twilio/    │     │  Pipeline    │
│  (PSTN/SIP)  │◄────│   Telnyx)    │◄────│  (STT→LLM   │
└──────────────┘     └──────────────┘     │   →TTS)      │
                                          └──────────────┘
```

**Call Agent = [[Voice Agents|Voice Agent]] + Telephony Layer**

---

## Inbound vs Outbound

### Inbound Call Agents
The AI **answers** incoming calls.

| Feature | Description |
|---------|-------------|
| **Use case** | Customer support, reception, after-hours, appointment booking |
| **Trigger** | Customer dials your number |
| **Goal** | Resolve the issue or route to the right human |
| **Key metric** | Resolution rate, transfer rate, customer satisfaction |
| **Example** | "Hi, I'd like to schedule a dental appointment for next Thursday" |

### Outbound Call Agents
The AI **makes** calls proactively.

| Feature | Description |
|---------|-------------|
| **Use case** | Lead qualification, appointment reminders, collections, surveys |
| **Trigger** | System initiates call from a contact list |
| **Goal** | Complete the campaign objective (qualify lead, collect payment, etc.) |
| **Key metric** | Connection rate, conversion rate, cost per outcome |
| **Example** | "Hi John, this is a reminder about your appointment tomorrow at 3 PM. Would you like to confirm or reschedule?" |

---

## Architecture

### Full Stack

```
┌─────────────────────────────────────────────────────────┐
│                    Call Agent Platform                    │
│                                                         │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌───────────┐ │
│  │Telephony│  │  STT    │  │  LLM    │  │   TTS     │ │
│  │ Layer   │→ │(Deepgram│→ │(GPT-4o/ │→ │(ElevenLabs│ │
│  │(Twilio) │  │ Nova-3) │  │ Claude) │  │  /PlayHT) │ │
│  └────┬────┘  └─────────┘  └────┬────┘  └───────────┘ │
│       │                         │                       │
│  ┌────▼────────────────────────▼────┐                  │
│  │         Tool Execution           │                  │
│  │  (CRM lookup, calendar booking,  │                  │
│  │   payment processing, transfer)  │                  │
│  └──────────────────────────────────┘                  │
└─────────────────────────────────────────────────────────┘
```

### Key Architecture Components

| Component | Role | Options |
|-----------|------|---------|
| **Telephony** | Connect to phone network, manage calls | Twilio, Telnyx, Vonage, SIP trunk |
| **Number management** | Provision local/toll-free numbers | Twilio, Telnyx |
| **Call routing** | Direct calls to right agent/queue | Platform-managed or custom |
| **Recording** | Record calls for compliance/QA | Built-in to most platforms |
| **DTMF** | Handle keypad input fallback | "Press 1 for billing" |
| **Warm transfer** | Hand off to human with context | Critical for escalation |
| **Webhooks** | Notify your system of call events | Call started, ended, transferred |

---

## Call Agent Platforms (2026)

### Tier 1: Purpose-Built Call AI

| Platform | Architecture | Best For | Concurrency | Pricing |
|----------|-------------|----------|-------------|---------|
| **Retell AI** | Managed orchestration | Production call centers | 20 free concurrent | ~$0.07/min all-in |
| **Vapi** | Provider-agnostic orchestrator | Developer-built pipelines | Unlimited (paid) | ~$0.05/min + providers |
| **Bland AI** | Pathways (node-graph flows) | High-volume outbound | 1,000+ concurrent | ~$0.09/min |

### Tier 2: Platform + Voice

| Platform | Approach | Best For |
|----------|---------|----------|
| **ElevenLabs** | Full-stack with best voice quality | Voice-quality-critical applications |
| **Synthflow** | No-code voice agent builder | Non-developers, quick setup |
| **Air AI** | Autonomous outbound sales agent | Sales teams |

### Tier 3: Infrastructure

| Platform | Approach | Best For |
|----------|---------|----------|
| **Twilio** | Raw telephony APIs + Media Streams | Custom builds, existing Twilio users |
| **Telnyx** | Telephony + AI (TeXML) | Cost-sensitive, global reach |
| **LiveKit** | Open-source WebRTC + telephony bridge | Self-hosted, custom pipelines |

---

## Platform Deep Dives

### Vapi — "The Developer's Choice"

```
Vapi Orchestrator
    ├── STT: Deepgram (default), AssemblyAI, Google, Azure
    ├── LLM: OpenAI, Anthropic, Google, open-source
    ├── TTS: ElevenLabs, PlayHT, Deepgram, Azure
    └── Telephony: Twilio (default), Vonage, custom SIP
```

- 14+ provider integrations under one API
- 62 million calls/month processed
- 99.99% SLA
- Tool calling (CRM lookup, booking, etc.) during conversation
- Serverless functions for custom logic
- Squad feature: multiple AI agents on one call, specialist routing

### Bland AI — "The Outbound Machine"

```
Bland Pathways (node graph)
    ├── Node 1: Greeting → Route based on response
    ├── Node 2: Qualification questions
    ├── Node 3: Objection handling
    └── Node 4: Book meeting / end call
```

- **Pathways architecture**: deterministic conversation flows as node graphs
- Built for scale: 1,000+ concurrent outbound calls
- Managed Twilio tuned for mass dialing
- Best for: lead gen, debt collection, appointment reminders, surveys
- Send SMS during or after calls

### Retell AI — "The Quality Leader"

- Best interruption handling in the industry
- Custom LLM support (bring your own fine-tuned model)
- 20 free concurrent calls included
- Built-in evaluation and analytics
- Best for: inbound support, healthcare intake, high-touch sales

---

## Building a Call Agent (The Vapi Way)

### Step 1: Create an Assistant
```json
{
  "name": "Appointment Scheduler",
  "model": {
    "provider": "openai",
    "model": "gpt-4o",
    "systemPrompt": "You are an appointment scheduler for Dr. Smith's dental office..."
  },
  "voice": {
    "provider": "elevenlabs",
    "voiceId": "rachel"
  },
  "firstMessage": "Hi, thanks for calling Dr. Smith's office. How can I help you today?"
}
```

### Step 2: Connect a Phone Number
```json
{
  "provider": "twilio",
  "number": "+1234567890",
  "assistantId": "asst_xxx"
}
```

### Step 3: Add Tools
```json
{
  "tools": [
    {
      "type": "function",
      "function": {
        "name": "check_availability",
        "description": "Check available appointment slots",
        "parameters": {
          "date": { "type": "string" },
          "doctor": { "type": "string" }
        }
      },
      "server": { "url": "https://your-api.com/availability" }
    },
    {
      "type": "function",
      "function": {
        "name": "book_appointment",
        "description": "Book an appointment for the caller"
      },
      "server": { "url": "https://your-api.com/book" }
    }
  ]
}
```

### Step 4: Handle Outbound
```python
import requests

response = requests.post("https://api.vapi.ai/call/phone", json={
    "assistantId": "asst_xxx",
    "phoneNumberId": "pn_xxx",
    "customer": {
        "number": "+1987654321",
        "name": "John Doe"
    }
})
```

---

## Use Cases by Industry

### Healthcare
| Use Case | Description | Impact |
|----------|-------------|--------|
| Appointment scheduling | Book, reschedule, cancel appointments | 24/7 availability |
| Patient intake | Collect info before visit | Reduce wait times |
| Prescription refills | Process refill requests | Reduce staff load |
| Post-visit follow-up | Check on patient recovery | Improve outcomes |
| Insurance verification | Verify coverage before appointment | Reduce denials |

### Real Estate
| Use Case | Description | Impact |
|----------|-------------|--------|
| Property inquiries | Answer questions about listings | Never miss a lead |
| Showing scheduling | Book property viewings | 24/7 booking |
| Lead qualification | Qualify buyer/renter intent | Filter serious leads |
| Rent collection | Payment reminders | Reduce late payments |

### Financial Services
| Use Case | Description | Impact |
|----------|-------------|--------|
| Account inquiries | Balance, transactions, statements | Reduce wait times |
| Fraud alerts | Verify suspicious transactions | Faster response |
| Collections | Payment reminders and arrangements | ~$280K/month (case study) |
| Loan applications | Pre-qualification calls | Scale origination |

### Sales & Marketing
| Use Case | Description | Impact |
|----------|-------------|--------|
| Lead qualification | Score and qualify inbound leads | 24/7 qualification |
| Outbound campaigns | Cold/warm outreach at scale | 1,000+ calls/hour |
| Appointment setting | Book meetings with qualified leads | Higher conversion |
| Survey & feedback | Post-purchase or NPS surveys | Scale feedback |

---

## Key Metrics

| Metric | What it Measures | Good Target |
|--------|-----------------|-------------|
| **Latency (TTFB)** | Time to first agent word | <800ms |
| **Resolution rate** | % calls resolved without human | >70% |
| **Transfer rate** | % calls escalated to human | <30% |
| **CSAT** | Customer satisfaction score | >4.0/5.0 |
| **Cost per call** | Total cost including platform + providers | <$0.50 for 5-min call |
| **Connection rate** | % outbound calls answered | >30% |
| **Conversion rate** | % calls achieving objective | Varies by campaign |

---

## Compliance & Legal

| Requirement | Description |
|-------------|-------------|
| **TCPA** (US) | Consent required for automated calls, restrictions on call times |
| **Do Not Call** | Must check DNC registry before outbound |
| **Call recording disclosure** | Must inform callers if recording ("This call may be recorded") |
| **AI disclosure** | Some jurisdictions require disclosure that caller is speaking to AI |
| **HIPAA** (Healthcare) | Must use HIPAA-compliant platforms for patient data |
| **PCI DSS** (Payments) | Credit card info must be handled securely |
| **GDPR** (EU) | Data processing consent, right to human agent |

---

## Call Agents vs Our Project

> [!note] How Call Agents Connect to Our AI Software Company
>
> Our project's pipeline is text-based, but call agents represent a natural output format:
>
> **Potential integration:**
> - When the pipeline completes, a call agent could **phone the founder**: "Your project is ready. The Engineer generated 12 files and the PPT agent created your pitch deck. Should I walk you through the highlights?"
> - **Voice-activated pipeline**: "Hey, build me a crop disease detection app for Indian farmers" → triggers the full CEO → PPT pipeline
> - The PPT agent could generate a **voice script** alongside the pitch deck
>
> **For the hackathon pitch:** Call agents demonstrate the next evolution — from text-based agentic AI to voice-native agentic AI. Our pipeline + Vapi = a voice-first AI software company.

---

## Quick Decision Guide

| Need | Platform |
|------|----------|
| Best voice quality | ElevenLabs |
| Production inbound support | Retell AI |
| Developer flexibility | Vapi |
| Mass outbound campaigns | Bland AI |
| No-code setup | Synthflow |
| Self-hosted / open-source | LiveKit + Pipecat |
| Raw telephony control | Twilio + custom |

---

See [[Voice Agents]] | [[Agentic AI - Master Guide]] | [[Agentic AI Use Cases]]

#agentic-ai #call-agents #telephony #voice #knowledge
