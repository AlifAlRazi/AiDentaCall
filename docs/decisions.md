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
