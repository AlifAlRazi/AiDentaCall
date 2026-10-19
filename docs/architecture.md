# DentaCall System Architecture

This document describes the architectural design, component interactions, data flow, concurrency models, and security boundaries of **DentaCall**: a production-grade voice appointment agent for dental practices.

---

## 1. High-Level System Architecture Diagram

```mermaid
flowchart TB
    subgraph InboundChannels["Inbound Calling Channels"]
        PSTN["Caller on Phone (PSTN)"]
        Browser["Caller in Web Browser (WebRTC)"]
    end

    subgraph TelephonyLayer["Telephony & WebRTC Media Layer"]
        Twilio["Twilio Telephony (SIP Trunk / Media Streams)"]
        LiveKit["LiveKit Real-Time Media Server"]
    end

    subgraph VoiceWorker["Voice Agent Worker (apps/agent)"]
        VAD["Voice Activity Detection (Silero VAD)"]
        STT["Streaming STT (Deepgram Nova-2)"]
        AgentCore["Conversation Orchestrator & State Machine"]
        TTS["Streaming TTS (ElevenLabs / Cartesia)"]
        BargeIn["Barge-In / Turn Detector"]
    end

    subgraph LLMInterface["LLM Provider Interface"]
        Claude["Anthropic Claude 3.5 Sonnet"]
        OpenAI["OpenAI GPT-4o"]
        Guardrails["Safety & Guardrail Filters (Medical/Emergency)"]
    end

    subgraph APILayer["Tool API Service (apps/api)"]
        FastAPI["FastAPI Gateway"]
        AuthMiddleware["API Key Auth & Rate Limiter"]
        Idempotency["Idempotency Filter (Cache / Redis / DB)"]
        PhoneValidator["Irish E.164 Phone Normalizer"]
    end

    subgraph DomainCore["Domain Core Engine (packages/core)"]
        AvailEngine["Availability Engine (Working Hours, Buffers)"]
        HoldEngine["Slot Hold Manager (2-min TTL)"]
        BookingEngine["Booking & Transaction Coordinator"]
        TZConverter["Europe/Dublin <-> UTC Converter"]
    end

    subgraph Persistence["Storage & Database Layer"]
        Postgres[("PostgreSQL 16 (Alembic Migrations)")]
    end

    subgraph Observability["Observability & Auditing (Stage 7)"]
        OTel["OpenTelemetry Collector (Traces & Latency)"]
        Redactor["PII Redactor (Phone / Email Masking)"]
        LogStore["Structured JSON Call Logs"]
    end

    subgraph StaffPortal["Clinic Staff Portal (apps/dashboard)"]
        NextApp["Next.js 14 Dashboard"]
    end

    subgraph EvalSystem["Evaluation Harness (packages/evals)"]
        SimCaller["Simulated Persona Caller"]
        Scenarios["50 Benchmark Scenarios"]
        LLMJudge["LLM Rubric Judge"]
    end

    %% Channel Connections
    PSTN --> Twilio
    Twilio --> LiveKit
    Browser --> LiveKit

    %% Media & Voice Pipeline
    LiveKit <--> VAD
    VAD --> STT
    STT --> AgentCore
    AgentCore --> BargeIn
    BargeIn --> LiveKit
    AgentCore --> TTS
    TTS --> LiveKit

    %% Agent to LLM
    AgentCore <--> Guardrails
    Guardrails <--> Claude
    Guardrails <--> OpenAI

    %% Agent to Tool API
    AgentCore -- "Secure REST (JSON / Idempotent)" --> AuthMiddleware
    AuthMiddleware --> Idempotency
    Idempotency --> PhoneValidator
    PhoneValidator --> FastAPI

    %% API to Domain Core
    FastAPI --> AvailEngine
    FastAPI --> HoldEngine
    FastAPI --> BookingEngine
    AvailEngine --> TZConverter
    HoldEngine --> TZConverter
    BookingEngine --> TZConverter

    %% Core to Database
    BookingEngine --> Postgres
    HoldEngine --> Postgres
    AvailEngine --> Postgres

    %% Observability
    AgentCore -.-> OTel
    FastAPI -.-> OTel
    AgentCore -.-> Redactor
    Redactor -.-> LogStore
    LogStore -.-> Postgres

    %% Dashboard
    NextApp --> FastAPI

    %% Evaluation
    SimCaller --> AgentCore
    Scenarios --> SimCaller
    AgentCore --> LLMJudge
```

---

## 2. Component Breakdown & Responsibilities

### 2.1 Apps

- **`apps/api` (FastAPI Tool Service)**
  - Exposes domain capabilities as discrete, validated REST endpoints matching LLM tool call signatures (`find_patient`, `check_availability`, `hold_slot`, `book_appointment`, `reschedule_appointment`, `cancel_appointment`, `get_clinic_info`, `take_message`, `transfer_to_human`).
  - Enforces API key authentication between agent workers and backend services.
  - Generates OpenAPI 3.1 specifications.
  - Enforces idempotency via `Idempotency-Key` headers on mutating requests.
  - Normalizes phone numbers to standard Irish E.164 formats (e.g., `+353871234567`).

- **`apps/agent` (Voice Agent Worker)**
  - Runs as an asynchronous LiveKit Agents Python worker process.
  - Subscribes to inbound audio tracks and runs streaming VAD (Silero) to detect speaker pauses and interruptions (barge-in).
  - Streams transcribed speech chunks from Deepgram Nova-2 into the conversational state machine.
  - Executes tool calling loops with timeouts and conversational filler phrases (e.g. *"Checking the schedule for you now..."*) to avoid dead air.
  - Streams LLM response tokens directly to text-to-speech (Cartesia / ElevenLabs) with minimal Time-To-First-Audio (TTFA).

- **`apps/dashboard` (Next.js Application)**
  - Interactive management interface for receptionists and clinic partners.
  - Visual calendar displaying confirmed bookings, held slots, and doctor rosters.
  - Call log explorer with turn-by-turn transcripts, tool invocation records, audio recordings, and token cost metrics.
  - WebRTC browser calling widget allowing instant testing of agent flows.

### 2.2 Packages

- **`packages/core` (Domain Logic & Availability Engine)**
  - Shared domain models: `Clinic`, `Dentist`, `Service`, `WorkingHours`, `TimeOff`, `Patient`, `Appointment`, `SlotHold`, `CallLog`.
  - Canonical time representation: All timestamps stored in **UTC**; converted to **Europe/Dublin** (handling Irish Standard Time vs. GMT daylight saving transitions) only when presenting or calculating clinic slots.
  - Availability algorithm: Computes free time windows considering:
    - Dentist working hours
    - Daily lunch break (13:00 – 14:00)
    - Irish statutory bank holidays
    - Planned doctor time off / sick leave
    - Service duration + cleaning buffer
    - Existing confirmed appointments & active slot holds
  - Slot hold system: Ephemeral 2-minute reservation holds to prevent race conditions during caller confirmation dialogue.

- **`packages/evals` (Testing & Quality Assurance Suite)**
  - 50 diverse test scenarios covering routine bookings, date ambiguities, accent variations, emergency triages, prompt injection attacks, and cancellations.
  - Simulated caller LLM with goal state and persona.
  - Automated rubric-based judge measuring task completion, tool call validity, guardrail adherence, and conversational latency.

---

## 3. Concurrency Control & Double-Booking Prevention

Preventing double-booking under concurrent phone calls is a critical safety requirement. DentaCall enforces a multi-layered defense strategy:

```mermaid
sequenceDiagram
    autonumber
    actor Caller1 as Caller 1 (Phone)
    actor Caller2 as Caller 2 (Browser)
    participant Agent1 as Voice Agent 1
    participant Agent2 as Voice Agent 2
    participant API as Tool API Gateway
    participant Core as Availability Engine
    participant DB as PostgreSQL 16

    Caller1->>Agent1: "I'd like a checkup Tuesday at 10am"
    Caller2->>Agent2: "Can I book Tuesday at 10am?"
    Agent1->>API: POST /tools/hold_slot (Dentist A, 10:00, 35m)
    Agent2->>API: POST /tools/hold_slot (Dentist A, 10:00, 35m)
    API->>Core: Acquire slot lock
    Core->>DB: INSERT INTO slot_holds (expires_at = now() + 2min)
    Note over DB: Postgres EXCLUDE constraint ensures no overlapping holds or appointments
    DB-->>Core: Success (Hold ID: hld_1)
    Core-->>API: 200 OK (Hold ID: hld_1)
    API-->>Agent1: Slot Held for 2 mins
    DB--xCore: Conflict (Constraint violation: slot overlapping with hld_1)
    Core-->>API: 409 Conflict (SLOT_UNAVAILABLE)
    API-->>Agent2: Slot already taken
    Agent2-->>Caller2: "10:00 AM just became unavailable. Would 10:45 AM work?"
    Agent1->>Caller1: "I have held Tuesday at 10:00 AM. May I have your name to confirm?"
    Caller1->>Agent1: "Yes, Sean Kelly"
    Agent1->>API: POST /tools/book_appointment (Hold ID: hld_1, Idempotency-Key: idm_99)
    API->>DB: BEGIN TRANSACTION
    API->>DB: Convert hold to confirmed appointment
    API->>DB: COMMIT TRANSACTION
    API-->>Agent1: Appointment Confirmed
```

### Concurrency Mechanisms:
1. **PostgreSQL GiST Overlap Exclusion Constraint:**
   ```sql
   ALTER TABLE appointments ADD CONSTRAINT no_dentist_appointment_overlap
   EXCLUDE USING gist (
       dentist_id WITH =,
       tsrange(start_time_utc, end_time_utc, '[)') WITH &&
   ) WHERE (status != 'cancelled');
   ```
2. **Ephemeral Slot Holds (2-minute TTL):**
   Active holds prevent other callers from selecting the slot while the first caller spells their name and details.
3. **Idempotency Keys:**
   Every mutating request carries an `Idempotency-Key` UUID. Retrying a failed voice network request returns the cached result without creating duplicate records.

---

## 4. Latency Budget & Audio Pipeline Optimization

For a voice receptionist to feel responsive and natural, end-to-end turn latency (Time-to-First-Audio) must remain below **1.2 seconds**.

| Stage | Component | Target Latency | Optimization Strategy |
| :--- | :--- | :--- | :--- |
| **Voice Activity Detection** | Silero VAD | < 80 ms | Run locally in-memory; low-threshold pause detection (450ms). |
| **Speech-to-Text (STT)** | Deepgram Nova-2 | < 250 ms | Websocket streaming, interim transcripts, customized dental vocabulary keyterms. |
| **Agent / LLM TTFT** | Claude 3.5 / GPT-4o | < 400 ms | Stream tokens; prioritize concise 1-2 sentence replies; prompt caching. |
| **Conversational Fillers** | Agent Worker | < 50 ms | Play filler audio (*"Let me check that..."*) immediately when tool call is initiated. |
| **Tool Execution** | FastAPI + DB | < 120 ms | Indexed queries, local database connection pooling, async I/O. |
| **Text-to-Speech (TTS)** | Cartesia / ElevenLabs | < 250 ms | Streaming chunked generation; sentence-boundary chunking. |
| **Network & WebRTC** | LiveKit SFU | < 50 ms | Edge media routing, WebRTC OPUS codec. |
| **Total Round-Trip** | **End-to-End** | **< 1,150 ms** | **Within 1.2s SLA** |

---

## 5. Security, Privacy, and Data Governance

1. **Authentication & Authorization:**
   - Agent-to-API communication is protected by internal bearer tokens (`X-API-Key`).
   - Dashboard endpoints use secure session cookies.
2. **PII Masking & Redaction:**
   - In accordance with Irish and European GDPR standards, phone numbers and email addresses are masked in stored logs and telemetry traces (`+353 87 *** *123`).
   - Raw audio recordings can be toggled off or subjected to an automated data retention cleanup job (`DATA_RETENTION_DAYS=90`).
3. **Emergency Escalation Bypass:**
   - When emergency symptoms are flagged (severe swelling, uncontrollable bleeding, avulsed tooth), all routine state machines are suspended, and the call is immediately transferred or directed to emergency services (999/112).
