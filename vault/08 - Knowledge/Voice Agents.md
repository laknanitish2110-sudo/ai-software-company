# Voice Agents

AI agents that communicate through speech — real-time conversational AI that listens, thinks, and talks back.

---

## What is a Voice Agent?

A **voice agent** is an AI system that conducts real-time spoken conversations. Unlike chatbots (text) or IVR systems (pre-recorded menus), voice agents understand natural speech, reason with an LLM, and respond in natural-sounding voice — all in under a second.

```
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│  Human   │────►│   STT    │────►│   LLM    │────►│   TTS    │────►🔊
│  Speech  │     │ (Speech  │     │ (Think/  │     │ (Text to │
│  🎤      │     │  to Text)│     │  Reason) │     │  Speech) │
└──────────┘     └──────────┘     └──────────┘     └──────────┘
```

---

## Core Architecture: The STT → LLM → TTS Pipeline

### The Classic Pipeline (Turn-Based)

```
Audio In → VAD (Voice Activity Detection) → Endpointing
    → STT (transcribe) → LLM (generate response) → TTS (synthesize)
        → Audio Out
```

**Component breakdown:**

| Component | What it Does | Latency Target | Key Providers |
|-----------|-------------|----------------|---------------|
| **VAD** | Detects when the human starts/stops speaking | <50ms | Silero VAD, WebRTC VAD |
| **Endpointing** | Decides when the speaker is done (not just pausing) | 200–500ms | Built into STT providers |
| **STT** | Converts speech to text | 90–150ms (streaming) | Deepgram Nova-3, AssemblyAI, Whisper |
| **LLM** | Understands intent, generates response | 200–500ms (first token) | GPT-4o, Claude, Gemini |
| **TTS** | Converts text back to natural speech | 100–300ms (first audio) | ElevenLabs, PlayHT, Cartesia |
| **Transport** | Moves audio in real-time | 5–20ms | WebSocket, WebRTC |

### The New Architecture (Speech-to-Speech)

Multimodal models skip the STT/TTS steps entirely:

```
Audio In → Multimodal LLM (audio-native) → Audio Out
```

- **GPT-4o Realtime API** — processes audio directly, sub-300ms latency
- **Gemini 2.0 Live** — native audio understanding and generation
- Reduces pipeline complexity but costs more and offers less control

---

## Latency — The Make-or-Break Metric

Human conversation has a ~200–300ms gap between speakers. Voice agents must match this.

| Component | Target | Acceptable | Broken |
|-----------|--------|-----------|--------|
| **VAD + Endpointing** | <300ms | <500ms | >800ms |
| **STT** | <150ms | <300ms | >500ms |
| **LLM (first token)** | <300ms | <500ms | >1000ms |
| **TTS (first audio)** | <200ms | <400ms | >600ms |
| **Total round-trip** | <500ms | <800ms | >1500ms |

> **The 1-second rule:** If total response time exceeds 1 second, callers perceive the agent as slow. Beyond 1.5 seconds, they hang up.

### Latency Optimization Techniques

1. **Streaming everything** — Don't wait for full transcription; stream partial text to LLM, stream LLM tokens to TTS
2. **Sentence-level chunking** — Send first complete sentence to TTS while LLM is still generating
3. **Speculative generation** — Start generating before the human finishes speaking
4. **Edge deployment** — Run STT/TTS close to the user
5. **Model selection** — Smaller/faster LLMs for simple turns, larger for complex reasoning

---

## Barge-In (Interruption Handling)

Critical for natural conversation — the human should be able to interrupt the agent mid-sentence.

```
Agent speaking → Human starts talking → VAD detects
    → Stop TTS playback immediately
    → Cancel pending LLM generation
    → Start processing new human input
```

Good barge-in handling separates production voice agents from demos. ElevenLabs and Retell are considered best-in-class here.

---

## Voice Agent Platforms (2026)

### Full-Stack Platforms

| Platform | Approach | Latency | Voices | Best For |
|----------|---------|---------|--------|----------|
| **ElevenLabs** | All-in-one (own STT+LLM+TTS) | <100ms | 11,000+ | Voice quality, multilingual |
| **Retell AI** | Managed orchestration | ~800ms | Multiple TTS providers | Production call centers |
| **Synthflow** | No-code builder | ~1s | Built-in | Non-developers |

### Orchestration Platforms (BYO Providers)

| Platform | Approach | Best For |
|----------|---------|----------|
| **Vapi** | Provider-agnostic orchestrator | Developers wanting flexibility |
| **Bland AI** | Raw WebSocket + BYO LLM | High-volume outbound |
| **LiveKit** | Open-source WebRTC infra | Custom real-time apps |
| **Pipecat** | Open-source composable pipelines | Custom voice pipelines |

### Open-Source Frameworks

| Framework | What it Does |
|-----------|-------------|
| **LiveKit Agents** | WebRTC-based real-time voice agent framework |
| **Pipecat** | Composable streaming pipelines for voice AI (by Daily.co) |
| **Vocode** | Open-source voice agent library |
| **Livekit + OpenAI Realtime** | WebRTC transport + GPT-4o native audio |

---

## STT Providers (2026)

| Provider | Model | Latency | Accuracy | Languages |
|----------|-------|---------|----------|-----------|
| **Deepgram** | Nova-3 | ~90ms | 91%+ (English) | 50+ |
| **AssemblyAI** | Universal-2 | ~150ms | 90%+ | 20+ |
| **OpenAI** | Whisper (streaming) | ~200ms | 89%+ | 99 |
| **Google** | Chirp 2 | ~150ms | 90%+ | 100+ |
| **Azure** | Speech Services | ~150ms | 89%+ | 100+ |

---

## TTS Providers (2026)

| Provider | Latency | Voice Quality | Clone? | Languages |
|----------|---------|--------------|--------|-----------|
| **ElevenLabs** | ~90ms | Best-in-class | Yes | 70+ |
| **PlayHT** | ~150ms | Excellent | Yes | 30+ |
| **Cartesia** | ~100ms | Very good | Yes | 20+ |
| **LMNT** | ~80ms | Good | Yes | English |
| **OpenAI TTS** | ~200ms | Good | No | 50+ |
| **Azure Neural** | ~150ms | Very good | Yes (Custom Neural) | 100+ |

---

## Key Concepts

### Voice Activity Detection (VAD)
Determines when the user is speaking vs. silence/background noise. Critical for knowing when to start processing and when the user is done talking.

### Endpointing
Deciding that the speaker has finished their turn (vs. just pausing to think). Too aggressive = cuts off the speaker. Too slow = awkward silence before response.

### Turn-Taking
The protocol for who speaks when. Natural conversation has overlapping speech, backchannels ("uh-huh"), and smooth handoffs. Advanced voice agents handle these.

### Voice Cloning
Creating a synthetic voice that sounds like a specific person. Used for brand voices, character voices, or personalized agents. ElevenLabs and PlayHT lead here.

### Emotion Detection
Analyzing the speaker's tone, pitch, and pace to detect emotional state. Used to adjust agent behavior (e.g., transfer to human if caller is frustrated).

---

## Architecture Patterns

### Pattern 1: Orchestrated Pipeline (Most Common)
```
Vapi/Retell manages the pipeline:
  Twilio (telephony) → Deepgram (STT) → GPT-4o (LLM) → ElevenLabs (TTS) → Twilio
```

### Pattern 2: Native Speech-to-Speech
```
Audio → GPT-4o Realtime API → Audio
(Single model handles everything)
```

### Pattern 3: Custom Open-Source Stack
```
LiveKit (WebRTC) → Whisper (STT) → Local LLM → Piper TTS → LiveKit
(Self-hosted, full control, no per-minute costs)
```

### Pattern 4: Hybrid
```
Simple queries → Speech-to-Speech (fast, cheap)
Complex queries → Full pipeline with specialized LLM (accurate)
```

---

## Use Cases

| Domain | Application | Example |
|--------|------------|---------|
| **Customer service** | 24/7 phone support, ticket resolution | Airlines, banks, telecom |
| **Healthcare** | Patient intake, appointment scheduling, triage | Mayo Clinic VoiceCare |
| **Sales** | Lead qualification, outbound campaigns | SDR automation |
| **Real estate** | Property inquiries, showing scheduling | Rental/sales agents |
| **Food service** | Drive-through ordering, reservations | Fast food chains |
| **Education** | Language tutoring, exam practice | Duolingo-style conversation |
| **Personal assistant** | Calendar, reminders, smart home | Alexa, Google Home, Apple Intelligence |
| **Accessibility** | Screen readers, navigation for visually impaired | Voice-first interfaces |

---

## Voice Agent vs Chatbot vs IVR

| Feature | IVR (Legacy) | Chatbot | Voice Agent |
|---------|-------------|---------|-------------|
| **Input** | DTMF keypad | Text | Natural speech |
| **Understanding** | Menu trees | NLU/LLM | STT + LLM |
| **Response** | Pre-recorded | Text | Synthesized speech |
| **Flexibility** | Fixed paths | Semi-flexible | Open-ended conversation |
| **Personalization** | None | Some | Full (tone, pace, empathy) |
| **User experience** | Frustrating | OK | Natural |

---

## Our Project's Connection

> [!note] Voice Agents and Our AI Software Company
>
> Our project is text-based today, but voice is a natural extension:
> - The **CEO agent** could accept voice input (problem statement spoken, not typed)
> - **Approval gates** could be voice-activated ("approve" / "reject" / "send back with feedback")
> - A **voice dashboard** could narrate agent progress in real-time
>
> **For hackathon pitch:** "We can add voice interface to our AI Software Company using Vapi or ElevenLabs — the founder speaks the problem, agents work, and the system calls them back when deliverables are ready."

---

See [[Call Agents]] | [[Agentic AI - Master Guide]] | [[Agent Design Patterns]]

#agentic-ai #voice #STT #TTS #real-time #knowledge
