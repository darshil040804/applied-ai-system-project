"""
Glitch Coach: an offline agent that plans, proposes, and checks its own hints.

The coach runs one agent loop per turn:

1. VALIDATE: clean the turn history; drop entries it cannot trust.
2. PLAN:     work out which numbers are still possible and how many guesses remain.
3. ACT:      propose the next guess (binary search by default).
4. CHECK:    run guardrail checks on its own proposal.
5. REVISE:   if a check fails, repair the proposal and check again.
6. FALLBACK: if it still fails, give the plain Higher/Lower hint instead.

The coach is never given the secret number. It only sees what the player sees:
their guesses and the Too High / Too Low feedback. It cannot leak the secret.

Every step is written to the "coach" logger (logs/coach.log once set_up_logging runs).
"""

import logging
import os
from dataclasses import dataclass, field

logger = logging.getLogger("coach")

VALID_OUTCOMES = {"Too High", "Too Low", "Win"}
MAX_REVISIONS = 2


@dataclass
class Plan:
    """What the coach knows before it proposes a guess."""

    low: int                # smallest number the secret can still be
    high: int               # largest number the secret can still be
    attempts_left: int
    guessed: list           # valid guesses made so far
    last_turn: tuple | None  # (guess, outcome) of the most recent valid turn
    strategy: str

    @property
    def size(self) -> int:
        return self.high - self.low + 1


@dataclass
class CoachHint:
    """What the coach returns to the app."""

    status: str              # "ok", "revised", "fallback", or "done"
    message: str
    suggestion: int | None = None
    low: int | None = None
    high: int | None = None
    confidence: float = 0.0  # chance the player can still win by following the coach
    checks: dict = field(default_factory=dict)  # guardrail name -> passed?
    notes: list = field(default_factory=list)   # validation and revision notes


def set_up_logging(path: str = "logs/coach.log") -> None:
    """Send coach logs to a file. Safe to call on every Streamlit rerun."""
    if any(getattr(h, "_coach_handler", False) for h in logger.handlers):
        return
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    handler = logging.FileHandler(path, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    handler._coach_handler = True
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


# ---------------------------------------------------------------- 1. VALIDATE


def validate_turns(turns, low: int, high: int):
    """
    Keep only turns the coach can trust.

    A turn is (guess, outcome). Non-integer guesses and unknown outcome labels
    are dropped with a note, so a bad entry cannot corrupt the plan.
    """
    clean, notes = [], []
    for turn in turns or []:
        try:
            guess, outcome = turn
        except (TypeError, ValueError):
            notes.append(f"Ignored malformed turn {turn!r}.")
            continue
        if isinstance(guess, bool) or not isinstance(guess, int):
            notes.append(f"Ignored non-numeric guess {guess!r}.")
            continue
        if outcome not in VALID_OUTCOMES:
            notes.append(f"Ignored guess {guess} with unknown feedback {outcome!r}.")
            continue
        if not low <= guess <= high:
            notes.append(f"Guess {guess} is outside {low}-{high}; its feedback still counts.")
        clean.append((guess, outcome))
    return clean, notes


# -------------------------------------------------------------------- 2. PLAN


def make_plan(turns, low: int, high: int, attempts_left: int) -> Plan:
    """Narrow the range using every Too High / Too Low result."""
    lo, hi = low, high
    for guess, outcome in turns:
        if outcome == "Too High":
            hi = min(hi, guess - 1)
        elif outcome == "Too Low":
            lo = max(lo, guess + 1)

    if lo > hi:
        strategy = "contradiction"
    elif lo == hi:
        strategy = "final answer"
    else:
        strategy = "binary search"

    return Plan(
        low=lo,
        high=hi,
        attempts_left=attempts_left,
        guessed=[g for g, _ in turns],
        last_turn=turns[-1] if turns else None,
        strategy=strategy,
    )


def win_confidence(size: int, attempts_left: int) -> float:
    """
    Chance the player wins by following the coach from here.

    With k guesses, binary search can pin down at most 2**k - 1 numbers,
    so the coach is sure (1.0) only when the remaining range fits.
    """
    if size <= 0 or attempts_left <= 0:
        return 0.0
    return min(1.0, (2 ** attempts_left - 1) / size)


# --------------------------------------------------------------------- 3. ACT


def binary_search_proposal(plan: Plan):
    """Default proposer: the middle of the numbers still possible."""
    return (plan.low + plan.high) // 2


# ------------------------------------------------------------------- 4. CHECK


def run_checks(suggestion, plan: Plan) -> dict:
    """Guardrails the coach applies to its own proposal before showing it."""
    is_int = isinstance(suggestion, int) and not isinstance(suggestion, bool)
    checks = {
        "is_whole_number": is_int,
        "inside_possible_range": is_int and plan.low <= suggestion <= plan.high,
        "not_already_guessed": is_int and suggestion not in plan.guessed,
        "agrees_with_last_feedback": True,
    }
    if plan.last_turn and is_int:
        last_guess, last_outcome = plan.last_turn
        if last_outcome == "Too High":
            checks["agrees_with_last_feedback"] = suggestion < last_guess
        elif last_outcome == "Too Low":
            checks["agrees_with_last_feedback"] = suggestion > last_guess
    elif not is_int:
        checks["agrees_with_last_feedback"] = False
    return checks


# ------------------------------------------------------------------ 5. REVISE


def revise(suggestion, plan: Plan):
    """Repair a failed proposal: nearest unguessed number inside the possible range."""
    options = [n for n in range(plan.low, plan.high + 1) if n not in plan.guessed]
    if not options:
        return None
    target = suggestion if isinstance(suggestion, int) else (plan.low + plan.high) // 2
    return min(options, key=lambda n: (abs(n - target), n))


# ---------------------------------------------------------------- 6. FALLBACK


def fallback_hint(plan: Plan, reason: str, checks=None, notes=None) -> CoachHint:
    """The plain Higher/Lower hint from the original game, used when the coach is unsure."""
    if plan.last_turn is None:
        message = "Coach is unsure. Make any guess to get started."
    elif plan.last_turn[1] == "Too High":
        message = "Coach is unsure, so here is the basic hint: 📉 Go LOWER!"
    else:
        message = "Coach is unsure, so here is the basic hint: 📈 Go HIGHER!"
    logger.warning("FALLBACK reason=%s", reason)
    return CoachHint(
        status="fallback",
        message=message,
        checks=checks or {},
        notes=(notes or []) + [reason],
    )


# --------------------------------------------------------------- agent loop


def get_coach_hint(turns, low: int, high: int, attempts_left: int,
                   propose=binary_search_proposal) -> CoachHint:
    """
    Run the full agent loop for one turn and return a checked hint.

    `turns` is a list of (guess, outcome) pairs. `propose` is the ACT step; it can
    be swapped out (the evaluation uses a faulty proposer to test the guardrails).
    """
    turns, notes = validate_turns(turns, low, high)
    for note in notes:
        logger.warning("VALIDATE %s", note)

    if any(outcome == "Win" for _, outcome in turns):
        logger.info("DONE game already won")
        return CoachHint(status="done", message="You already won. No hint needed.", notes=notes)
    if attempts_left <= 0:
        logger.info("DONE no attempts left")
        return CoachHint(status="done", message="No attempts left.", notes=notes)

    plan = make_plan(turns, low, high, attempts_left)
    logger.info(
        "PLAN range=%s-%s size=%s attempts_left=%s strategy=%s",
        plan.low, plan.high, plan.size, attempts_left, plan.strategy,
    )
    if plan.strategy == "contradiction":
        return fallback_hint(plan, "Feedback history contradicts itself; no number fits.",
                             notes=notes)

    try:
        suggestion = propose(plan)
    except Exception as exc:  # a broken proposer must not crash the game
        logger.exception("ACT proposer raised an error")
        suggestion = None
        notes.append(f"Proposer error: {exc}")
    logger.info("ACT proposed=%r", suggestion)

    status = "ok"
    checks = run_checks(suggestion, plan)
    revisions = 0
    while not all(checks.values()) and revisions < MAX_REVISIONS:
        failed = [name for name, ok in checks.items() if not ok]
        logger.warning("CHECK failed=%s for proposal=%r", failed, suggestion)
        notes.append(f"Rejected {suggestion!r}: failed {', '.join(failed)}.")
        suggestion = revise(suggestion, plan)
        checks = run_checks(suggestion, plan)
        status = "revised"
        revisions += 1
        logger.info("REVISE new_proposal=%r", suggestion)

    if not all(checks.values()):
        return fallback_hint(plan, "Could not produce a hint that passes every check.",
                             checks=checks, notes=notes)

    logger.info("CHECK passed proposal=%s", suggestion)
    confidence = win_confidence(plan.size, attempts_left)
    if plan.strategy == "final answer":
        message = f"Only {suggestion} is left. Guess {suggestion}!"
    elif status == "revised":
        message = (
            f"The secret is between {plan.low} and {plan.high} "
            f"({plan.size} numbers). Try {suggestion}."
        )
    else:
        message = (
            f"The secret is between {plan.low} and {plan.high} "
            f"({plan.size} numbers). Try {suggestion}: it cuts the range in half."
        )
    logger.info("RESULT status=%s suggestion=%s confidence=%.2f", status, suggestion, confidence)
    return CoachHint(
        status=status,
        message=message,
        suggestion=suggestion,
        low=plan.low,
        high=plan.high,
        confidence=confidence,
        checks=checks,
        notes=notes,
    )
