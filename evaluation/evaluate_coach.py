"""
Reliability evaluation for the AI coach.

Part 1 plays every possible secret on every difficulty, always following the coach,
and checks that the coach's starting confidence matches the win rate it actually gets.

Part 2 runs guardrail scenarios: bad input, contradictory feedback, and a deliberately
faulty proposer, to show the self-check / revise / fallback loop working.

Run:  python evaluation/evaluate_coach.py
Writes the same markdown report to evaluation/results.md.
Exits with code 1 if any check fails.
"""

import os
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from coach import get_coach_hint, set_up_logging, win_confidence  # noqa: E402
from logic_utils import check_guess, get_attempt_limit, get_range_for_difficulty  # noqa: E402


# ------------------------------------------------------------ Part 1: games


def play_following_coach(difficulty, secret):
    """Play one game taking every coach suggestion. Returns (won, guesses, statuses)."""
    low, high = get_range_for_difficulty(difficulty)
    limit = get_attempt_limit(difficulty)
    turns, statuses = [], []
    for attempt in range(1, limit + 1):
        hint = get_coach_hint(turns, low, high, limit - (attempt - 1))
        statuses.append(hint.status)
        if hint.suggestion is None:
            return False, attempt - 1, statuses
        outcome, _ = check_guess(hint.suggestion, secret)
        turns.append((hint.suggestion, outcome))
        if outcome == "Win":
            return True, attempt, statuses
    return False, limit, statuses


def evaluate_games():
    rows, all_ok = [], True
    for difficulty in ["Easy", "Normal", "Hard"]:
        low, high = get_range_for_difficulty(difficulty)
        limit = get_attempt_limit(difficulty)
        wins, guess_counts, statuses = 0, [], Counter()
        for secret in range(low, high + 1):
            won, guesses, game_statuses = play_following_coach(difficulty, secret)
            statuses.update(game_statuses)
            if won:
                wins += 1
                guess_counts.append(guesses)
        games = high - low + 1
        win_rate = wins / games
        predicted = win_confidence(games, limit)
        calibrated = abs(predicted - win_rate) < 0.01
        all_hints_ok = set(statuses) == {"ok"}
        all_ok = all_ok and calibrated and all_hints_ok
        rows.append({
            "difficulty": difficulty,
            "games": games,
            "wins": wins,
            "win_rate": win_rate,
            "predicted": predicted,
            "avg_guesses": sum(guess_counts) / len(guess_counts),
            "hints": sum(statuses.values()),
            "hints_ok": statuses["ok"],
            "result": "Pass" if calibrated and all_hints_ok else "Fail",
        })
    return rows, all_ok


# -------------------------------------------------------- Part 2: guardrails


def repeat_last_guess(plan):
    """Faulty proposer: suggests a number the player already tried."""
    return plan.guessed[-1]


def out_of_range(plan):
    """Faulty proposer: suggests a number outside the possible range."""
    return plan.high + 10


def crashes(plan):
    """Faulty proposer: raises an error."""
    raise RuntimeError("proposer crashed")


def returns_text(plan):
    """Faulty proposer: returns text instead of a number."""
    return "the secret is 42"


SCENARIOS = [
    {
        "name": "Fresh game, no guesses",
        "args": dict(turns=[], low=1, high=100, attempts_left=8),
        "criteria": "Suggests 50 (midpoint), status ok, confidence 100%",
        "expect": lambda h: h.status == "ok" and h.suggestion == 50 and h.confidence == 1.0,
    },
    {
        "name": "Junk entries in history",
        "args": dict(turns=[("abc", "Too Low"), (30, "Maybe"), None, (40, "Too High")],
                     low=1, high=100, attempts_left=5),
        "criteria": "Ignores 3 bad entries, still plans from 40 Too High",
        "expect": lambda h: h.status == "ok" and h.high == 39 and len(h.notes) == 3,
    },
    {
        "name": "Contradictory feedback (40 Too Low, then 30 Too High)",
        "args": dict(turns=[(40, "Too Low"), (30, "Too High")], low=1, high=100, attempts_left=5),
        "criteria": "No number fits, so falls back to the basic hint",
        "expect": lambda h: h.status == "fallback" and h.suggestion is None,
    },
    {
        "name": "Only one number left",
        "args": dict(turns=[(5, "Too Low"), (7, "Too High")], low=1, high=20, attempts_left=3),
        "criteria": "Suggests 6 with 100% confidence",
        "expect": lambda h: h.status == "ok" and h.suggestion == 6 and h.confidence == 1.0,
    },
    {
        "name": "Game already won",
        "args": dict(turns=[(14, "Win")], low=1, high=100, attempts_left=7),
        "criteria": "Gives no hint (status done)",
        "expect": lambda h: h.status == "done" and h.suggestion is None,
    },
    {
        "name": "No attempts left",
        "args": dict(turns=[(10, "Too Low")], low=1, high=20, attempts_left=0),
        "criteria": "Gives no hint (status done)",
        "expect": lambda h: h.status == "done",
    },
    {
        "name": "Faulty proposer repeats a guess",
        "args": dict(turns=[(50, "Too High")], low=1, high=100, attempts_left=7,
                     propose=repeat_last_guess),
        "criteria": "Self-check rejects 50, revises to a valid number",
        "expect": lambda h: h.status == "revised" and 1 <= h.suggestion <= 49,
    },
    {
        "name": "Faulty proposer goes out of range",
        "args": dict(turns=[(10, "Too Low")], low=1, high=20, attempts_left=5,
                     propose=out_of_range),
        "criteria": "Self-check rejects 30, revises inside 11-20",
        "expect": lambda h: h.status == "revised" and 11 <= h.suggestion <= 20,
    },
    {
        "name": "Faulty proposer crashes",
        "args": dict(turns=[], low=1, high=50, attempts_left=5, propose=crashes),
        "criteria": "Error is caught and logged, game still gets a valid hint",
        "expect": lambda h: h.status == "revised" and 1 <= h.suggestion <= 50,
    },
    {
        "name": "Faulty proposer returns text",
        "args": dict(turns=[], low=1, high=20, attempts_left=6, propose=returns_text),
        "criteria": "Text is rejected, never shown; revises to a number",
        "expect": lambda h: h.status == "revised" and isinstance(h.suggestion, int)
        and "42" not in h.message,
    },
]


def evaluate_guardrails():
    rows, all_ok = [], True
    for scenario in SCENARIOS:
        args = dict(scenario["args"])
        try:
            hint = get_coach_hint(args.pop("turns"), **args)
            passed = bool(scenario["expect"](hint))
            behavior = f"status={hint.status}, suggestion={hint.suggestion}"
        except Exception as exc:
            passed, behavior = False, f"crashed: {exc}"
        all_ok = all_ok and passed
        rows.append((scenario["name"], scenario["criteria"], behavior,
                     "Pass" if passed else "Fail"))
    return rows, all_ok


# ----------------------------------------------------------------- report


def build_report():
    game_rows, games_ok = evaluate_games()
    guard_rows, guards_ok = evaluate_guardrails()

    lines = ["# Coach Evaluation Results", "",
             "## Part 1: every secret, following the coach", "",
             "| Difficulty | Games | Wins | Win rate | Coach's starting confidence "
             "| Avg guesses to win | Hints passing self-check | Result |",
             "|---|---|---|---|---|---|---|---|"]
    for r in game_rows:
        lines.append(
            f"| {r['difficulty']} | {r['games']} | {r['wins']} | {r['win_rate']:.0%} "
            f"| {r['predicted']:.0%} | {r['avg_guesses']:.2f} "
            f"| {r['hints_ok']}/{r['hints']} | {r['result']} |"
        )

    lines += ["", "## Part 2: guardrail scenarios", "",
              "| Scenario | Evaluation criteria | Behavior | Result |",
              "|---|---|---|---|"]
    for name, criteria, behavior, result in guard_rows:
        lines.append(f"| {name} | {criteria} | {behavior} | {result} |")

    game_passes = sum(r["result"] == "Pass" for r in game_rows)
    guard_passes = sum(row[3] == "Pass" for row in guard_rows)
    lines += ["", "## Summary", "",
              f"- Game simulations: {game_passes}/{len(game_rows)} difficulties passed.",
              f"- Guardrail scenarios: {guard_passes}/{len(guard_rows)} passed.",
              ""]
    return "\n".join(lines), games_ok and guards_ok


def main():
    set_up_logging(os.path.join(ROOT, "logs", "coach.log"))
    report, ok = build_report()
    print(report)
    out_path = os.path.join(ROOT, "evaluation", "results.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(report)
    print("Saved to evaluation/results.md (coach steps logged to logs/coach.log)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
