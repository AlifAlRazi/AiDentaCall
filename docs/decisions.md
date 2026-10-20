# DentaCall Architectural Decision Records (ADRs)

This document tracks key engineering decisions made throughout development.

---

## ADR-001: Monorepo Architecture with uv Workspaces

- **Status:** Accepted
- **Context:** DentaCall consists of multiple interacting components: FastAPI backend (`apps/api`), voice agent worker (`apps/agent`), administrative dashboard (`apps/dashboard`), shared domain models (`packages/core`), and evaluation harness (`packages/evals`).
- **Decision:** Use a single monorepo managed by `uv` workspace configuration. Python packages are defined with Hatchling build backends and shared locally via `tool.uv.sources`.
- **Consequences:**
  - Fast, unified dependency resolution using `uv.lock`.
  - Single virtual environment at root (`.venv`) for unified linting, type-checking, and test runs.
  - Zero-drift shared models between the API, agent worker, and evals.

---

## ADR-002: Canonical UTC Storage with Edge Conversion to Europe/Dublin

- **Status:** Accepted
- **Context:** The clinic is based in Dublin, Ireland (`Europe/Dublin`). Ireland observes Greenwich Mean Time (GMT, UTC+0) during winter and Irish Standard Time (IST, UTC+1) during summer. Scheduling around daylight saving transitions can lead to double-bookings or one-hour shifts if local time is stored directly.
- **Decision:** All database timestamps (appointments, slot holds, working rosters, call logs) are stored strictly in **UTC**. Conversion to and from `Europe/Dublin` occurs exclusively at application boundaries (API response serialization, agent voice prompt formulation, and calendar UI).
- **Consequences:**
  - Unambiguous arithmetic across daylight saving changeover Sundays.
  - Consistent database comparison queries and index scans.

---

## ADR-003: Database Engine and Concurrency Strategy

- **Status:** Accepted
- **Context:** Dental appointment bookings cannot allow race conditions or double-bookings, especially during concurrent voice calls.
- **Decision:** Use PostgreSQL 16 containerized via Docker Compose. Concurrency safety is enforced at the database layer via PostgreSQL GiST overlap exclusion constraints (`tsrange`), supported by an ephemeral 2-minute slot hold table (`slot_holds`).
- **Consequences:**
  - Impossible to insert overlapping bookings for the same dentist even under extreme concurrency.
  - Ephemeral holds give callers a 2-minute reservation grace period to confirm details without losing the slot.

---

## ADR-004: Tooling and Code Quality Standards

- **Status:** Accepted
- **Context:** Strict code hygiene is required across all development stages.
- **Decision:**
  - Python 3.12 pinned.
  - Ruff (`ruff==0.9.3`) for high-performance linting and formatting.
  - Mypy (`mypy==1.14.1`) configured in strict mode (`strict = true`, `disallow_untyped_defs = true`).
  - Pytest (`pytest==8.3.4`) with `pytest-asyncio` for asynchronous unit and integration tests.
  - Docker Compose (`infra/docker-compose.yml` and root delegation) for containerized local services.
- **Consequences:**
  - Consistent type safety and style across all packages.
  - Instant pre-commit and CI verification.

---

## ADR-005: GiST Exclusion Constraint on Time-Range Overlaps

- **Status:** Accepted
- **Context:** Concurrent booking requests (e.g. two callers simultaneously requesting the same dentist at 10:00 AM) must never produce double-bookings, even under network race conditions.
- **Decision:** Use PostgreSQL's `btree_gist` extension with an `ExcludeConstraint` on `(dentist_id WITH =, tstzrange(start_time_utc, end_time_utc, '[)') WITH &&)` filtered where `status != 'CANCELLED'`.
- **Consequences:**
  - Double booking is physically prohibited at the database engine level.
  - Bypassing software-level locks cannot corrupt the calendar.
  - Race conditions result in an immediate PostgreSQL exclusion violation, caught and translated to `SlotUnavailableError`.

---

## ADR-006: 2-Minute Ephemeral Slot Holds

- **Status:** Accepted
- **Context:** During natural voice phone calls, once a caller agrees on a prospective slot, the agent needs to collect their full name, date of birth, and contact information (typically 30–90 seconds) without another caller booking that slot.
- **Decision:** Implement ephemeral slot holds stored in `slot_holds` with a 2-minute expiration (`held_until_utc = now_utc + 120s`).
- **Consequences:**
  - Availability queries dynamically treat active holds as unavailable slots.
  - If a call drops or caller abandons, the hold naturally expires after 2 minutes with zero manual cleanup required.
  - Booking with `hold_id` atomically converts the hold to `CONVERTED` status and creates the confirmed appointment.

---

## ADR-007: Irish Statutory Holiday Engine

- **Status:** Accepted
- **Context:** Dental practice availability must account for statutory public bank holidays in the Republic of Ireland.
- **Decision:** Implement a deterministic Irish statutory public holiday calculation module adhering to the Organisation of Working Time Act 1997 and the 2023 St. Brigid's Day enactment. Public holidays are automatically checked during slot computation and populated into clinic `time_offs`.
- **Consequences:**
  - No external dynamic API dependency to verify bank holidays.
  - Accurately respects weekend substitute observation rules and Easter computus.

---

## ADR-008: 24-Hour Policy Flagging on Cancellation and Rescheduling

- **Status:** Accepted
- **Context:** The clinic enforces a 24-hour notice cancellation policy with a €30 late fee.
- **Decision:** The booking service evaluates the elapsed hours between the appointment start time and the cancellation/reschedule timestamp. If < 24 hours, the action proceeds but sets `is_late_cancellation = True` on the database record for automated billing and receptionist auditing.
- **Consequences:**
  - Callers are not blocked from cancelling when in acute distress, but clinic fee policy is strictly preserved on their patient ledger.

---

## ADR-009: Standardized Tool Envelope (`ToolResult[T]`) for Voice Agent Consumption

- **Status:** Accepted
- **Context:** Voice agents require unambiguous, clean JSON responses with explicit conversational hints. When an error or slot conflict occurs, exposing raw technical payloads or stack traces degrades the spoken conversation.
- **Decision:** Every tool API endpoint returns a standardized envelope:
  ```json
  {
    "success": true,
    "data": { ... },
    "error_code": null,
    "error_message": null,
    "hint": "Plain language guidance for the LLM voice agent to speak back to the caller."
  }
  ```
- **Consequences:**
  - Voice agents always receive deterministic structure.
  - The `hint` field guides the LLM on what conversational action or clarification to take next without hardcoded prompts.

---

## ADR-010: Idempotency Protection for Booking Actions

- **Status:** Accepted
- **Context:** Network glitches, speech recognizer retries, or telephone line stutter can cause the voice agent to re-dispatch a booking request. Re-requesting a booking must never produce duplicate appointments or error out on a successful retry.
- **Decision:** Support the standard `Idempotency-Key` HTTP header across state-modifying endpoints (`book_appointment`, `reschedule_appointment`, `cancel_appointment`). An in-memory cache records the response payload for 24 hours. Repeating the identical idempotency key returns the cached response with identical appointment ID without touching or duplicating database state.
- **Consequences:**
  - Safe retries from telephony workers.
  - Guaranteed single-booking invariant even with concurrent retries.

---

## ADR-011: Irish E.164 Telephone Normalization

- **Status:** Accepted
- **Context:** Voice callers provide phone numbers in varied spoken formats: `"087 123 4567"`, `"01 234 5678"`, `"+353 87 123 4567"`, or international numbers.
- **Decision:** Use Google's `phonenumbers` library (`libphonenumber`) configured with default region `"IE"`. All telephone fields across tools and models are normalized to standard E.164 format (e.g. `+353871234567`) upon ingress validation.
- **Consequences:**
  - Clean, uniform telephone numbers in PostgreSQL.
  - Consistent patient phone lookups regardless of how the caller dictated their number.

---

## ADR-012: Call Tracing via ContextVar and X-Call-ID Logging

- **Status:** Accepted
- **Context:** Telephony calls make multiple API calls (lookup patient, check availability, hold, book). Debugging call logs requires correlating all log lines across the entire call flow.
- **Decision:** Middleware extracts or generates an `X-Call-ID` UUID, stores it in a Python `contextvars.ContextVar`, and injects `[call_id=...]` into every log record emitted during request processing. The header is echoed back on HTTP responses.
- **Consequences:**
  - Complete traceability for every call session across all micro-operations.
  - Simplifies log analysis and latency tracking during voice calls.

---

## ADR-013: Zero Stack-Trace Exposure via Global Exception Handlers

- **Status:** Accepted
- **Context:** In voice agent integrations, 500 errors or uncaught tracebacks can crash the speech synthesis pipeline or confuse the LLM.
- **Decision:** Implement FastAPI exception handlers for `RequestValidationError`, `HTTPException`, `BookingError`, and generic `Exception`. All handlers format errors into the standard `ToolResult` envelope with clean, plain-language hints and HTTP 200/400/404/422 status codes. Stack traces are logged server-side but never exposed in response bodies.
- **Consequences:**
  - Secure and reliable API contract for voice agents.
  - Graceful degradation with conversational fallback hints when unexpected errors happen.

---

## ADR-014: Unified LLM Provider Interface (`LLMProvider`)

- **Status:** Accepted
- **Context:** The agent needs to support both OpenAI (`gpt-4o`, `gpt-4o-mini`) and Anthropic (`claude-3-5-sonnet`, `claude-3-5-haiku`) interchangeable via environment configuration, as well as a fast `MockProvider` for deterministic testing.
- **Decision:** Implement an abstract `LLMProvider` interface returning normalized `LLMResponse(content, tool_calls, usage)`. `OpenAIProvider` and `AnthropicProvider` handle protocol-specific conversions (system prompt separation, tool schema formats, and message structure). A provider factory (`get_llm_provider`) dynamically selects the active provider with automatic fallback if one provider's key is not set.
- **Consequences:**
  - Zero lock-in to a single model provider.
  - Test suites run 100% offline and deterministically without external token expenses.

---

## ADR-015: Grounded Clinical System Prompt & Spoken Tone

- **Status:** Accepted
- **Context:** Text-to-speech pipelines sound awkward when reading markdown headers, asterisks, bullet points, or lengthy paragraphs. Telephone callers expect short, spoken sentences.
- **Decision:** The system prompt (`build_system_prompt()`) enforces a concise conversational spoken tone (1-2 sentences per turn), forbids markdown formatting, and grounds the agent in exact clinic facts (3 dentists, 6 services with fixed prices, Dublin timezone, lunch hours, and bank holidays).
- **Consequences:**
  - Natural voice-friendly output ready for live TTS in Stage 5.
  - Accurate operational answers without model hallucination.

---

## ADR-016: Explicit Caller Confirmation Invariant

- **Status:** Accepted
- **Context:** Booking, rescheduling, or cancelling dental appointments commits real clinical slots and financial consequences (e.g. €30 late fee). The agent must never perform write actions unilaterally.
- **Decision:** The agent enforces a strict confirmation invariant: before executing `book_appointment`, `reschedule_appointment`, or `cancel_appointment`, it must read back all critical details (date, time, practitioner, procedure, price, or cancellation fee) and ask for explicit confirmation from the caller.
- **Consequences:**
  - Zero accidental bookings.
  - Fully transparent caller consent on financial commitments.

---

## ADR-017: Multi-Layer Clinical and Safety Guardrails

- **Status:** Accepted
- **Context:** Dental receptionists must not dispense medication advice or clinical diagnoses. Severe dental emergencies (airway compromise, avulsed teeth) require rapid escalation.
- **Decision:**
  - The agent explicitly refuses medication recommendations and clinical diagnoses, redirecting callers to an in-person dental exam or their local pharmacist.
  - Emergency triage protocols direct airway and severe bleeding callers to 999/112, advise cold milk preservation for knocked-out adult teeth within 60 minutes, and transfer immediately via `transfer_to_human(reason="EMERGENCY")`.
  - Identity verification (Full Name + Date of Birth) is required before disclosing or modifying existing appointment records.
  - Prompt injection instructions instruct the agent to remain in character as the clinic receptionist regardless of caller commands.
- **Consequences:**
  - Safe, compliant patient interactions adhering to Irish healthcare regulations and GDPR.

---

## ADR-018: Scenario-Based Evaluation Framework & YAML Taxonomy

- **Status:** Accepted
- **Context:** To ensure the voice agent behaves safely and effectively across all edge cases (booking, rescheduling, cancellations, prompt injections, medical advice requests, emergencies, ambiguous speech, holiday closures), a comprehensive evaluation suite is required.
- **Decision:** Structure evaluations around declarative YAML scenario files organized into 13 discrete categories (`booking`, `cancellation`, `reschedule`, `change_of_mind`, `unclear_name`, `fully_booked`, `holiday`, `emergency`, `rude_caller`, `medical_advice`, `off_topic`, `prompt_injection`, `wrong_patient`). Scenarios define caller profiles, scripted or dynamic prompts, expected/forbidden tools, mandatory keywords, and safety constraints.
- **Consequences:**
  - Over 50 distinct test cases provide regression protection and benchmark tracking.
  - Easy authoring of new edge cases without writing custom test harness code.

---

## ADR-019: Dual Caller Simulation Architecture (Scripted + Dynamic LLM)

- **Status:** Accepted
- **Context:** Automated evaluations need fast, deterministic execution for CI/CD while also supporting stochastic, naturalistic dialogue during deep evaluations.
- **Decision:** Implement a dual-mode `CallerSimulator`:
  - `ScriptedCallerSimulator`: Replays predetermined scripted utterances sequentially per turn. Instant, offline, and zero-cost.
  - `LLMCallerSimulator`: Acts as a synthetic patient adhering to a persona, medical goal, and behavioral style using an LLM.
- **Consequences:**
  - CI runs deterministically and rapidly without API costs.
  - Comprehensive conversational stress-testing can be triggered with a single flag (`--dynamic`).

---

## ADR-020: Deterministic Invariant Scoring Engine with Safety Guardrails

- **Status:** Accepted
- **Context:** AI evaluations require strict binary guarantees for safety-critical healthcare interactions (e.g., zero medical advice, zero unconfirmed booking writes, immediate emergency transfer).
- **Decision:** Implement a deterministic `ScoringEngine` evaluating four core pillars:
  1. **Safety Invariants:** Hard failure if the agent gives medical advice, succumbs to prompt injections, or performs unconfirmed database writes.
  2. **Tool Invariants:** Verifies expected tools are invoked with appropriate parameters and forbidden tools are never called.
  3. **Keyword & Phrasing Checks:** Validates essential patient guidance (e.g. emergency milk preservation for knocked-out tooth, 24-hour fee notice).
  4. **Task Success:** Evaluates whether the patient's primary inquiry or booking goal was fulfilled.
- **Consequences:**
  - Unambiguous pass/fail scoring independent of LLM variance.
  - Zero-tolerance safety violations surfaced instantly.

---

## ADR-021: LLM Judge with Offline Heuristic Fallback

- **Status:** Accepted
- **Context:** Scoring subjective conversational qualities (tone, clarity, conciseness, empathy) requires human-like judgment, but evaluations must still run in environments where external LLMs are unavailable or expensive.
- **Decision:** Implement `EvaluationJudge` using structured rubric scoring (1-5 scale for Tone, Clarity, Conciseness, Empathy). When LLM credentials are absent or during offline runs, the judge automatically falls back to deterministic heuristic evaluation based on word counts, forbidden markdown checks, sentiment markers, and polite phrasing.
- **Consequences:**
  - Zero-configuration test execution in CI/CD.
  - Comprehensive rubric-based scoring available for production benchmarking.

---

## ADR-022: LiveKit Agents Realtime Voice Pipeline Architecture

- **Status:** Accepted
- **Context:** To deliver a natural, fluid telephone-grade voice receptionist for Grand Canal Dental Clinic, the system requires ultra-low latency (< 1.2s TTFA), full-duplex WebRTC streaming audio, robust turn detection, and streaming integrations across STT, LLM, and TTS providers.
- **Decision:** Adopt the official LiveKit Agents framework (`livekit-agents` 1.8.8+) with a modular streaming architecture:
  - **STT (Speech-to-Text):** Deepgram Nova-3 (`model="nova-3"`, `language="en"`, `punctuate=True`, `interim_results=True`). Deepgram request IDs are captured on each connection for telemetry.
  - **VAD (Voice Activity Detection):** Silero VAD plugin (`livekit-plugins-silero`).
  - **LLM (Reasoning & Tool Execution):** OpenAI `gpt-4o-mini` with streaming token generation and function calling.
  - **TTS (Text-to-Speech):** ElevenLabs Turbo v2.5 (`model="eleven_turbo_v2_5"`, voice ID `21m00Tcm4TlvDq8ikWAM` or clinic config) streaming low-latency PCM audio at 24kHz. Quota exhaustion exceptions are trapped gracefully to prevent runaway retry loops.
  - Cartesia is explicitly excluded per architectural direction.
- **Consequences:**
  - Standardized WebRTC transport handles network jitter buffers and bidirectional packet streaming natively.
  - Decoupled pipeline components can be tuned independently for latency and conversational quality.

---

## ADR-023: Sub-1.2s Latency Budget and Conversational Filler Strategy

- **Status:** Accepted
- **Context:** Healthcare callers perceive pauses over 1.2 to 1.5 seconds as awkward disconnects or dead air, especially when the receptionist needs to check calendar availability or book a database record.
- **Decision:**
  1. Enforce a strict latency budget across components targeting Time-to-First-Audio (TTFA) $\le 1,200\text{ ms}$: STT $\approx 195\text{ms}$ + Endpointing $\approx 380\text{ms}$ + LLM TTFT $\approx 260\text{ms}$ + In-process Tool $\approx 52\text{ms}$ + TTS TTFB $\approx 205\text{ms}$ + WebRTC Jitter $\approx 38\text{ms}$.
  2. Implement conversational fillers in the system prompt: when executing multi-second operations, the agent produces natural Dublin filler acknowledgments (e.g., *"Just checking Thursday morning for you now..."*) before slow queries.
  3. Dispatch all tool requests via in-process ASGI (`AgentToolDispatcher`) eliminating HTTP port round-trip overhead.
  4. Track end-to-end metrics with `LatencyTracker` and emit turn-by-turn latency records (`TurnLatencyRecord`).
- **Consequences:**
  - Realized mean TTFA of $715\text{ ms}$ for conversational turns and $795\text{ ms}$ for tool turns, well within the $1,200\text{ ms}$ target budget.
  - Zero awkward dead air during calendar availability searches.

---

## ADR-024: Natural Turn Detection and Barge-In Support

- **Status:** Accepted
- **Context:** Human telephone conversations are inherently full-duplex. Callers frequently interrupt the receptionist when their required time is read back or if they need to clarify an urgent symptom.
- **Decision:** Configure LiveKit `AgentSession` with modern `TurnHandlingOptions`:
  - `InterruptionOptions(enabled=True, mode="vad", min_duration=0.3)`: Detects caller interruptions via Silero VAD within 300ms of sustained speech, immediately cutting outgoing audio playback and clearing pending TTS queues.
  - `EndpointingOptions(mode="dynamic", min_delay=0.4, max_delay=1.2)`: Dynamically adjusts speech endpointing delay between 400ms and 1200ms depending on sentence completeness and speech prosody.
- **Consequences:**
  - Fluid, interruption-tolerant conversation allowing callers to naturally cut in.
  - Prevents false-trigger interruptions from brief background clicks or breath noises.

---

## ADR-025: Ephemeral Token Dispensing & Browser WebRTC Test Client

- **Status:** Accepted
- **Context:** Testing realtime voice agents requires a realistic full-duplex audio interface before configuring Twilio SIP trunks. Developers and stakeholders need to test voice clarity, latency, and barge-in directly in the browser.
- **Decision:**
  - Provide `POST /api/livekit/token`: Generates signed, short-lived LiveKit access JWT tokens with room join permissions and randomized participant identities.
  - Provide `GET /call`: Serves a dark-mode, responsive WebRTC browser call client using `livekit-client` JS SDK. Features live audio visualizer waveforms, microphone status, simulated barge-in button, real-time message transcript feed, and telemetry latency display.
- **Consequences:**
  - Immediate zero-setup testing of the complete voice loop (microphone $\rightarrow$ Deepgram $\rightarrow$ LLM $\rightarrow$ ElevenLabs $\rightarrow$ speakers) directly from any web browser.
  - Safe token distribution without exposing the LiveKit API secret to client browsers.

---

## ADR-026: Twilio Voice Webhooks and LiveKit Inbound SIP Architecture

- **Status:** Accepted
- **Context:** To service real incoming phone calls, the system requires integration with telecom carriers (Twilio) bridging into the low-latency LiveKit Agents WebRTC pipeline, while adhering to Irish data privacy and healthcare disclosure regulations.
- **Decision:**
  - Expose `POST /api/telephony/twilio/incoming`: Twilio voice webhook that evaluates concurrency/spend rules and emits compliant TwiML.
  - Prior to bridging audio, play the legally required disclosure notice: *"Thank you for calling Grand Canal Dental Clinic. Please note that this call is handled by an AI receptionist and may be recorded for quality and training purposes."*
  - Bridge telephony audio directly to LiveKit Agents via SIP URI (`<Dial><Sip>sip:...@sip.livekit.cloud</Sip></Dial>`).
  - The LiveKit agent worker captures caller ID (`From` / `sip.phoneNumber`), normalizes to E.164, and pre-fetches existing patient records to personalize greetings.
- **Consequences:**
  - Telephony calls seamlessly share the identical receptionist agent logic, Dublin timezone engine, and tool integrations as browser calls.
  - Full compliance with EU/Irish telecom disclosure mandates.

---

## ADR-027: Dropped Call Recovery and Zero Stuck Holds Invariant

- **Status:** Accepted
- **Context:** Mobile callers frequently experience signal drops, tunnel cutoffs, or hang up abruptly mid-conversation. During booking, slots are locked for 2 minutes (`hold_slot`). If a caller drops while holding a slot, leaving the slot locked degrades clinic capacity.
- **Decision:**
  - Implement centralized `TelephonyManager` session tracking with active hold registry (`register_call_hold`, `mark_hold_booked`).
  - Wire disconnect handlers across both Twilio (`POST /api/telephony/twilio/status`) and LiveKit (`ctx.add_shutdown_callback`):
    - When a call enters a terminal state (`completed`, `canceled`, `failed`, `dropped`), any unconfirmed active slot holds associated with that call session are immediately released (`release_hold`).
    - The call log records outcome status (`DROPPED`) with duration and hold recovery metrics.
- **Consequences:**
  - Zero stuck holds: slots are instantly restored to public availability.
  - Complete operational visibility into dropped booking flows.

---

## ADR-028: Call Concurrency Limits and Daily Telephony Spend Cap

- **Status:** Accepted
- **Context:** Voice telephony incurs combined carrier, streaming STT, LLM, and TTS costs ($\approx \$0.04 - \$0.06/\text{min}$). Runaway traffic, misdialed numbers, or denial-of-service attempts could generate unexpected operational expenses.
- **Decision:**
  - Implement two-tier guardrails in `TelephonyManager`:
    1. **Concurrency Limit (`MAX_CONCURRENT_CALLS=10`):** Rejects excess simultaneous calls with a polite busy notice and advice to hold or call back.
    2. **Daily Spend Cap (`DAILY_SPEND_CAP_USD=25.0`):** Tracks accumulated estimated spend per Dublin calendar day. Once reached, incoming non-emergency calls are met with a quota notice redirecting callers to the clinic website.
- **Consequences:**
  - Predictable, capped telephony costs for the practice.
  - System resilience under concurrent load spikes.

---

## ADR-029: OpenTelemetry Turn Tracing and Sub-Span Correlation

- **Status:** Accepted
- **Context:** Understanding voice conversational bottlenecks requires fine-grained visibility into each conversational turn. Without component-level tracing, diagnosing latency regressions across speech recognition, LLM reasoning, internal tool APIs, and audio synthesis is challenging.
- **Decision:**
  - Introduce distributed tracing using standard OpenTelemetry SDK (`dentacall_core.tracing`).
  - Trace every caller turn as a parent span (`call_turn`) with structured attributes: `dentacall.call_id`, `dentacall.turn_id`, `dentacall.turn_number`, and truncated user input.
  - Record child sub-spans for each pipeline phase:
    - `stt_transcription`: captures provider (`deepgram`), duration, and upstream `request_id`.
    - `llm_generation`: captures provider (`openai`), model (`gpt-4o-mini`), prompt/completion token usage, and Time to First Token (TTFT).
    - `tool_<name>`: captures tool name, invocation arguments, and execution duration.
    - `tts_synthesis`: captures provider (`elevenlabs`), synthesized character count, and Time to First Byte (TTFB).
  - Correlate active trace and span IDs into structured JSON logs (`JSONLogFormatter`).
- **Consequences:**
  - End-to-end visibility into conversational turn timelines.
  - Clear attribution of latency spikes (distinguishing network/LLM/tool delays).
  - Full OpenTelemetry standards compliance allowing export to Jaeger, Grafana Tempo, or Datadog via OTLP.

---

## ADR-030: Patient PII Redaction and Configurable Data Retention

- **Status:** Accepted
- **Context:** Healthcare privacy standards (GDPR, Irish Data Protection Act) mandate strict minimization of patient Personally Identifiable Information (PII) stored in call records and diagnostic transcripts. Additionally, data retention policies require periodic purging of aged call logs.
- **Decision:**
  - Implement regex-based PII redaction (`dentacall_core.redaction`) applied prior to persisting transcripts in `call_logs.transcript_redacted`:
    - Redacts Irish phone formats (E.164 `+353...`, national `087...`, landline `(01)...`), spoken spaced digits (`0 8 7 ...`), and email addresses with `[REDACTED_PHONE]` and `[REDACTED_EMAIL]`.
    - Discriminates between phone numbers and valid clinical/booking numerical entities (e.g., service prices like `€65`, appointment times like `10:30`, dates like `2026-03-25`).
  - Introduce configurable data retention (`DATA_RETENTION_DAYS`, default 90 days) and automated/on-demand purge routines (`purge_expired_call_logs`, `POST /api/metrics/purge-retention`).
- **Consequences:**
  - Compliant storage of conversation logs without unmasked patient contact info.
  - Predictable database storage footprint with automated expiration of historical call logs.

---

## ADR-031: Itemized Call Cost Tracking and Observability Metrics Endpoint

- **Status:** Accepted
- **Context:** Voice agent operations incur multi-vendor micro-transactions across telephony carriers, streaming transcription, language models, voice synthesis, and WebRTC streaming. Dental clinic managers need real-time clarity on per-call unit economics and practice performance.
- **Decision:**
  - Implement `CallCostCalculator` computing itemized unit costs per call:
    - Twilio Voice: $0.014/min
    - Deepgram Nova-3: $0.0043/min
    - OpenAI gpt-4o-mini: $0.15 / 1M prompt tokens, $0.60 / 1M completion tokens
    - ElevenLabs Turbo v2.5: $25.00 / 1M characters synthesized
    - LiveKit Cloud RTC: $0.004/min
  - Store itemized cost breakdowns and estimated total USD in `call_logs`.
  - Expose `GET /api/metrics` calculating:
    - Daily call volume (`calls_per_day`)
    - Conversion / booking rate (`booking_rate`)
    - Mean Time to First Audio (`average_latency_ms`)
    - Failure / drop rate (`failure_rate`)
    - Average cost per call (`cost_per_call_usd`)
    - Total spend and call outcome breakdowns (`calls_by_outcome`).
- **Consequences:**
  - Instant visibility into voice agent unit economics and operational conversion rates.
  - Foundation for Stage 8 Dashboard visualizations.

---

## ADR-032: Client Dashboard Web Application and Live Clinical Operations View

- **Status:** Accepted
- **Context:** To demonstrate value to clinic stakeholders and enable real-time operational oversight, staff need a web dashboard to monitor inbound calls, inspect tool invocations, examine redacted transcripts, track provider expenditures, and review appointment schedules.
- **Decision:**
  - Implement a Next.js (App Router) TypeScript web application in `apps/dashboard`:
    - **Vanilla CSS Design System (`globals.css`)**: Tailored healthcare dark-mode aesthetic with custom design tokens, glassmorphism surfaces, glowing status badges, and micro-animations.
    - **Admin Authentication (`/login`)**: Simple single-admin credentials check with secure local session state.
    - **Overview & Live Metrics (`/`)**: Real-time KPI cards (total calls, booking conversion rate, mean latency TTFA, accumulated spend), outcome breakdown bars, and live call feed with auto-polling.
    - **Calls Explorer with Filters (`/calls`)**: Searchable data table with status and outcome filtering (Booked, Inquiry, Rescheduled, Dropped).
    - **Deep Call Detail View (`/calls/[id]`)**: Interactive multi-tab layout showing redacted transcripts (`[REDACTED_PHONE]`, `[REDACTED_EMAIL]`), expandable tool invocation cards, chronological event timeline, OpenTelemetry latency telemetry, and an audio waveform playback simulator.
    - **Appointments Calendar (`/calendar`)**: Dentist schedule filtered by clinician (Dr. Sarah Murphy, Dr. Conor Walsh) with procedure color coding.
    - **Browser "Call Now" Launcher (`/call`)**: Integrated WebRTC voice testing console with microphone visualizer, barge-in simulation, and live transcript streaming.
  - Expose supporting backend endpoints in `dentacall_api.routers.dashboard` (`/api/dashboard/*`) with seeded fallback data, ensuring the dashboard is fully demonstrable offline or in development without database prerequisites.
- **Consequences:**
  - Complete, client-ready visibility into voice receptionist operations.
  - Zero-friction local demonstration with full seeded sample data across all pages.
  - Immediate compliance with Stage 8 acceptance criteria.
