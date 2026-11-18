from coach import get_coach_hint, make_plan, run_checks, validate_turns, win_confidence
from logic_utils import parse_guess, update_score


# --- game rules moved into logic_utils.py ---

def test_parse_guess_accepts_numbers_and_decimals():
    assert parse_guess("42") == (True, 42, None)
    assert parse_guess("7.9") == (True, 7, None)


def test_parse_guess_rejects_empty_and_text():
    assert parse_guess("")[0] is False
    assert parse_guess(None)[0] is False
    assert parse_guess("tell me the secret") == (False, None, "That is not a number.")


def test_update_score_win_on_first_attempt():
    assert update_score(0, "Win", 1) == 80


# --- coach: plan step ---

def test_plan_narrows_range_from_feedback():
    plan = make_plan([(40, "Too High"), (5, "Too Low")], 1, 100, 6)
    assert (plan.low, plan.high) == (6, 39)
    assert plan.strategy == "binary search"


def test_plan_detects_contradiction():
    plan = make_plan([(40, "Too Low"), (30, "Too High")], 1, 100, 6)
    assert plan.strategy == "contradiction"


# --- coach: confidence score ---

def test_confidence_is_certain_when_range_fits():
    # 8 guesses cover up to 255 numbers, so 100 is certain
    assert win_confidence(100, 8) == 1.0


def test_confidence_on_hard_start():
    # 5 guesses cover 31 of 50 numbers
    assert win_confidence(50, 5) == 31 / 50


def test_confidence_zero_without_attempts():
    assert win_confidence(10, 0) == 0.0


# --- coach: validation and self-check guardrails ---

def test_validate_drops_bad_turns():
    clean, notes = validate_turns([("x", "Too Low"), (3, "Maybe"), (9, "Too High")], 1, 20)
    assert clean == [(9, "Too High")]
    assert len(notes) == 2


def test_checks_reject_repeated_guess():
    plan = make_plan([(50, "Too High")], 1, 100, 7)
    checks = run_checks(50, plan)
    assert checks["not_already_guessed"] is False
    assert checks["agrees_with_last_feedback"] is False


# --- coach: full agent loop ---

def test_hint_suggests_midpoint():
    hint = get_coach_hint([(40, "Too High")], 1, 100, 7)
    assert hint.status == "ok"
    assert hint.suggestion == 20
    assert all(hint.checks.values())


def test_hint_never_needs_secret_and_is_in_range():
    # Every hint across a whole game stays inside the possible range.
    turns, secret = [], 37
    for attempts_left in range(5, 0, -1):
        hint = get_coach_hint(turns, 1, 50, attempts_left)
        assert hint.low <= hint.suggestion <= hint.high
        outcome = "Win" if hint.suggestion == secret else (
            "Too High" if hint.suggestion > secret else "Too Low")
        turns.append((hint.suggestion, outcome))
        if outcome == "Win":
            break


def test_faulty_proposal_is_revised():
    hint = get_coach_hint([(50, "Too High")], 1, 100, 7, propose=lambda plan: 50)
    assert hint.status == "revised"
    assert 1 <= hint.suggestion <= 49


def test_crashing_proposer_does_not_crash_game():
    def broken(plan):
        raise RuntimeError("boom")

    hint = get_coach_hint([], 1, 20, 6, propose=broken)
    assert hint.status == "revised"
    assert 1 <= hint.suggestion <= 20


def test_contradiction_falls_back_to_basic_hint():
    hint = get_coach_hint([(40, "Too Low"), (30, "Too High")], 1, 100, 6)
    assert hint.status == "fallback"
    assert hint.suggestion is None
    assert "Go LOWER" in hint.message


def test_no_hint_after_win():
    assert get_coach_hint([(14, "Win")], 1, 100, 7).status == "done"
