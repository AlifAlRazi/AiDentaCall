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
