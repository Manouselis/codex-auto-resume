"""Explicit protocol-neutral types and state transitions."""
from dataclasses import dataclass
from enum import Enum
from typing import Protocol


class State(str, Enum):
    DISABLED = "DISABLED"
    ARMED = "ARMED"
    RUNNING = "RUNNING"
    FIVE_HOUR_LIMIT_REACHED = "FIVE_HOUR_LIMIT_REACHED"
    WAITING_FOR_RESET = "WAITING_FOR_RESET"
    VERIFYING_ALLOWANCE = "VERIFYING_ALLOWANCE"
    RESUMING = "RESUMING"
    COMPLETED = "COMPLETED"
    WEEKLY_LIMIT_REACHED = "WEEKLY_LIMIT_REACHED"
    PAUSED_FOR_USER = "PAUSED_FOR_USER"
    ERROR = "ERROR"


TRANSITIONS = {
    State.DISABLED: {State.ARMED},
    State.ARMED: {State.RUNNING, State.FIVE_HOUR_LIMIT_REACHED, State.VERIFYING_ALLOWANCE, State.COMPLETED},
    State.RUNNING: {State.ARMED, State.FIVE_HOUR_LIMIT_REACHED, State.VERIFYING_ALLOWANCE, State.COMPLETED},
    State.FIVE_HOUR_LIMIT_REACHED: {State.WAITING_FOR_RESET},
    State.WAITING_FOR_RESET: {State.VERIFYING_ALLOWANCE, State.COMPLETED},
    State.VERIFYING_ALLOWANCE: {State.WAITING_FOR_RESET, State.RESUMING, State.COMPLETED},
    State.RESUMING: {State.RUNNING, State.COMPLETED},
    State.COMPLETED: set(),
    State.WEEKLY_LIMIT_REACHED: {State.ARMED},
    State.PAUSED_FOR_USER: {State.ARMED},
    State.ERROR: {State.ARMED},
}


def transition_allowed(old: State, new: State) -> bool:
    return old == new or new in TRANSITIONS[old] or (
        old != State.COMPLETED
        and new in {State.DISABLED, State.PAUSED_FOR_USER, State.WEEKLY_LIMIT_REACHED, State.ERROR}
    )


@dataclass(frozen=True)
class Observation:
    thread_id: str
    account_id: str
    model: str
    bucket_ids: tuple[str, ...]
    cwd: str
    config_hash: str
    turn_id: str
    turn_status: str
    error_code: str | None
    revision: str
    observed_at: float
    history_available: bool = True
    project_exists: bool = True
    approval_pending: bool = False
    user_work_active: bool = False
    cancelled: bool = False
    incomplete: bool | None = True
    # Stored history from another runtime can contain a synthetic interruption
    # for a still-open turn. It permits monitoring, never continuation dispatch.
    external_unresolved: bool = False
    stop_reason: str | None = None
    # Dispatch rechecks these pinned facts; the public protocol is not atomic.


@dataclass(frozen=True)
class Usage:
    payload: dict
    fetched_at: float
    auth_mode: str


@dataclass(frozen=True)
class Capabilities:
    included_only_execution: bool = False
    conditional_thread_execution: bool = False
    original_runtime: bool = False
    backend_idempotency: bool = False

    @property
    def safe(self) -> bool:
        return all((self.included_only_execution, self.conditional_thread_execution,
                    self.original_runtime, self.backend_idempotency))


@dataclass(frozen=True)
class Request:
    continuation_id: str
    thread_id: str
    expected_revision: str
    expected_account_id: str
    expected_model: str
    expected_config_hash: str
    bucket_ids: tuple[str, ...]
    included_only: bool = True
    text: str = (
        "Continue the previously interrupted task from its current state. First inspect existing "
        "progress, files, and test results. Do not redo completed work. Resume only the outstanding "
        "objectives, preserve the original requirements, and stop when the task is genuinely complete."
    )
    trigger: str = "usage_limit"


class TransientError(Exception):
    """A read can be retried with a bounded delay; never retry a model submission."""


class UnsafeError(Exception):
    """Authentication, protocol or safety information is unavailable."""


class NotSentError(UnsafeError):
    """A confirmed failure before any continuation could be delivered."""


class WriterConflictError(NotSentError):
    """The original desktop still owns the conversation writer."""


class Adapter(Protocol):
    capabilities: Capabilities

    def observe(self, thread_id: str) -> Observation: ...
    def usage(self) -> Usage: ...
    def submit(self, request: Request) -> str: ...
