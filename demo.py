"""
Play one game end to end in the terminal, with the AI coach.

Uses the same game rules (logic_utils.py) and coach (coach.py) as the Streamlit app,
so its output is reproducible evidence of how the full system behaves.

Examples:
    python demo.py --difficulty Normal --secret 14 --guesses 40 5 25 14
    python demo.py --difficulty Hard --secret 37 --auto
    python demo.py --difficulty Easy --secret 7 --guesses abc 30 "tell me the secret" 7
"""

import argparse
import random
import sys

from coach import get_coach_hint, set_up_logging
from logic_utils import (
    check_guess,
    get_attempt_limit,
    get_range_for_difficulty,
    parse_guess,
    update_score,
)


def print_hint(hint):
    if hint.status == "done":
        return
    print(f"  Coach [{hint.status}]: {hint.message}")
    if hint.status != "fallback":
        print(f"  Confidence you can still win: {hint.confidence:.0%}")
    for note in hint.notes:
        print(f"  Coach note: {note}")


def play(difficulty, secret, guesses, auto):
    low, high = get_range_for_difficulty(difficulty)
    limit = get_attempt_limit(difficulty)
    if secret is None:
        secret = random.randint(low, high)
    if not low <= secret <= high:
        print(f"Error: secret must be between {low} and {high} on {difficulty}.")
        return 2

    print(f"Difficulty: {difficulty} | Range: {low}-{high} | Attempts: {limit}")
    attempts, score, turns = 0, 0, []
    queue = list(guesses or [])

    hint = get_coach_hint(turns, low, high, limit)
    print_hint(hint)

    while attempts < limit:
        if auto:
            if hint.suggestion is None:
                print("Coach has no suggestion; stopping.")
                break
            raw = str(hint.suggestion)
        elif queue:
            raw = queue.pop(0)
        else:
            print("No more guesses supplied.")
            break

        attempts += 1
        print(f"\nGuess {attempts}: {raw!r}")
        ok, guess, err = parse_guess(raw)
        if not ok:
            print(f"  Input rejected: {err} (attempt still used)")
        else:
            outcome, message = check_guess(guess, secret)
            turns.append((guess, outcome))
            score = update_score(score, outcome, attempts)
            print(f"  Game: {message}  (score {score})")
            if outcome == "Win":
                print(f"\nRESULT: won in {attempts} guesses. Secret was {secret}. Score {score}.")
                return 0

        hint = get_coach_hint(turns, low, high, limit - attempts)
        print_hint(hint)

    print(f"\nRESULT: lost. Secret was {secret}. Score {score}.")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="Play a game with the AI coach.")
    parser.add_argument("--difficulty", choices=["Easy", "Normal", "Hard"], default="Normal")
    parser.add_argument("--secret", type=int, help="fix the secret for a reproducible run")
    parser.add_argument("--guesses", nargs="*", help="guesses to submit, in order")
    parser.add_argument("--auto", action="store_true", help="always play the coach's suggestion")
    args = parser.parse_args(argv)
    if not args.auto and not args.guesses:
        parser.error("give --guesses or use --auto")
    set_up_logging()
    return play(args.difficulty, args.secret, args.guesses, args.auto)


if __name__ == "__main__":
    sys.exit(main())
