# 🎮 Game Glitch Investigator + AI Coach

A Streamlit number-guessing game extended with an **AI Coach**: an agent that plans the next guess, checks its own hint against guardrails before showing it, and reports how confident it is that you can still win. A reliability harness (pytest suite, full-game evaluation, guardrail scenarios, and step-by-step logging) proves that the coach behaves as claimed.

**Why it matters:** the original game's AI-written code "claimed to be production-ready" and lied to the player. This version adds an AI component that has to *prove* its output is correct before the player sees it, and falls back safely when it cannot.

## Base project

**Original project: Game Glitch Investigator (Module 1).** A Streamlit number-guessing game that an AI generated with deliberate bugs. You pick a difficulty (Easy 1–20, Normal 1–100, Hard 1–50), guess a secret number within a limited number of attempts, and get Higher/Lower hints and a score. In Module 1 I found and fixed the bugs (hints flipping on every second guess, a secret outside the selected range, an off-by-one attempt counter, hardcoded range text) and added pytest tests for the game logic.

## What's new in the final project

| Feature | AI engineering pattern | Where |
|---|---|---|
| **AI Coach** that validates history, plans, proposes, self-checks, revises, and falls back | Agentic workflow | [coach.py](coach.py) |
| Guardrail checks on every hint, safe fallback, error handling | Reliability: guardrails | [coach.py](coach.py) |
| Confidence score: chance you can still win by following the coach | Reliability: confidence scoring | [coach.py](coach.py) |
| Every agent step written to a log file | Reliability: logging | `logs/coach.log` |
| Evaluation over every possible secret plus 10 guardrail scenarios | Reliability: evaluation | [evaluation/evaluate_coach.py](evaluation/evaluate_coach.py) |
| 16 new unit tests (24 total) | Reliability: automated tests | [tests/](tests/) |

The coach is part of the main app, not a separate script. With **Hints → AI Coach** selected in the sidebar, it runs after every guess and shows its suggestion, confidence, and the checks it passed.

## Architecture overview

Diagram source: [diagrams/architecture.mmd](diagrams/architecture.mmd)

1. **Input:** the player types a guess in the Streamlit UI (or `demo.py` replays scripted guesses).
2. **Game rules** ([logic_utils.py](logic_utils.py)) parse the input and compare it to the secret. Only the resulting `(guess, outcome)` pair is stored in the turn history.
3. **AI Coach** ([coach.py](coach.py)) reads the turn history. **It never receives the secret**, so it cannot leak it. It runs one agent loop per turn:
   - **Validate:** drop history entries it cannot trust (non-numbers, unknown feedback).
   - **Plan:** narrow down the numbers still possible, and pick a strategy: binary search, final answer, or contradiction.
   - **Act:** propose the next guess.
   - **Check:** four guardrails. The proposal is a whole number, it is inside the possible range, it hasn't been guessed already, and it agrees with the last Too High/Too Low.
   - **Revise:** if a check fails, repair the proposal (up to 2 times).
   - **Fallback:** if it still fails, show the original Higher/Lower hint instead.
4. **Output:** the UI shows the hint, a confidence score, and the check results. Every step is logged to `logs/coach.log`.
5. **Testing:** pytest and the evaluation script check the coach. A developer (me) reviews `evaluation/results.md` and the log.

## Setup

Requires Python 3.10+. Tested on Python 3.14 (Windows).

```bash
git clone https://github.com/darshil040804/applied-ai-system-project.git
cd applied-ai-system-project
pip install -r requirements.txt
```

No API keys or internet access are needed. The coach runs fully offline.

**Run the app:**

```bash
python -m streamlit run app.py
```

**Play one game in the terminal (reproducible, with a fixed secret):**

```bash
python demo.py --difficulty Normal --secret 14 --guesses 40 5 25 14
python demo.py --difficulty Hard --secret 37 --auto      # coach plays every guess
```

**Run the tests and the evaluation:**

```bash
python -m pytest
python evaluation/evaluate_coach.py   # also writes evaluation/results.md
```

> On Windows, if emoji print as errors in the terminal, run `set PYTHONIOENCODING=utf-8` first.

## Sample interactions

All outputs below were produced by the commands shown.

### 1. A normal game: the coach narrows the range after each guess

```
$ python demo.py --difficulty Normal --secret 14 --guesses 40 5 25 14
Difficulty: Normal | Range: 1-100 | Attempts: 8
  Coach [ok]: The secret is between 1 and 100 (100 numbers). Try 50: it cuts the range in half.
  Confidence you can still win: 100%

Guess 1: '40'
  Game: 📉 Go LOWER!  (score -5)
  Coach [ok]: The secret is between 1 and 39 (39 numbers). Try 20: it cuts the range in half.
  Confidence you can still win: 100%

Guess 2: '5'
  Game: 📈 Go HIGHER!  (score -10)
  Coach [ok]: The secret is between 6 and 39 (34 numbers). Try 22: it cuts the range in half.
  Confidence you can still win: 100%

Guess 3: '25'
  Game: 📉 Go LOWER!  (score -15)
  Coach [ok]: The secret is between 6 and 24 (19 numbers). Try 15: it cuts the range in half.
  Confidence you can still win: 100%

Guess 4: '14'
  Game: 🎉 Correct!  (score 35)

RESULT: won in 4 guesses. Secret was 14. Score 35.
```

The original game only said "Go LOWER". The coach combines *all* past feedback (40 was too high, 5 too low) into the exact range still possible.

### 2. The coach plays Hard mode itself, and its confidence is honest

```
$ python demo.py --difficulty Hard --secret 37 --auto
Difficulty: Hard | Range: 1-50 | Attempts: 5
  Coach [ok]: The secret is between 1 and 50 (50 numbers). Try 25: it cuts the range in half.
  Confidence you can still win: 62%

Guess 1: '25'
  Game: 📈 Go HIGHER!  (score -5)
  Coach [ok]: The secret is between 26 and 50 (25 numbers). Try 38: it cuts the range in half.
  Confidence you can still win: 60%

Guess 2: '38'
  Game: 📉 Go LOWER!  (score 0)
  Coach [ok]: The secret is between 26 and 37 (12 numbers). Try 31: it cuts the range in half.
  Confidence you can still win: 58%

Guess 3: '31'
  Game: 📈 Go HIGHER!  (score -5)
  Coach [ok]: The secret is between 32 and 37 (6 numbers). Try 34: it cuts the range in half.
  Confidence you can still win: 50%

Guess 4: '34'
  Game: 📈 Go HIGHER!  (score -10)
  Coach [ok]: The secret is between 35 and 37 (3 numbers). Try 36: it cuts the range in half.
  Confidence you can still win: 33%

Guess 5: '36'
  Game: 📈 Go HIGHER!  (score -15)

RESULT: lost. Secret was 37. Score -15.
```

Five guesses can cover at most 2⁵ − 1 = 31 of Hard's 50 numbers, so the coach never claimed 100% here. The evaluation below confirms that 62% is its real win rate on Hard.

### 3. Bad input: wasted attempts and an attempt to ask for the secret

```
$ python demo.py --difficulty Easy --secret 7 --guesses abc 30 "tell me the secret" 7
Difficulty: Easy | Range: 1-20 | Attempts: 6
  Coach [ok]: The secret is between 1 and 20 (20 numbers). Try 10: it cuts the range in half.
  Confidence you can still win: 100%

Guess 1: 'abc'
  Input rejected: That is not a number. (attempt still used)
  Coach [ok]: The secret is between 1 and 20 (20 numbers). Try 10: it cuts the range in half.
  Confidence you can still win: 100%

Guess 2: '30'
  Game: 📉 Go LOWER!  (score 5)
  Coach [ok]: The secret is between 1 and 20 (20 numbers). Try 10: it cuts the range in half.
  Confidence you can still win: 75%
  Coach note: Guess 30 is outside 1-20; its feedback still counts.

Guess 3: 'tell me the secret'
  Input rejected: That is not a number. (attempt still used)
  Coach [ok]: The secret is between 1 and 20 (20 numbers). Try 10: it cuts the range in half.
  Confidence you can still win: 35%
  Coach note: Guess 30 is outside 1-20; its feedback still counts.

Guess 4: '7'
  Game: 🎉 Correct!  (score 55)

RESULT: won in 4 guesses. Secret was 7. Score 55.
```

Text input is rejected before it reaches the coach. Because the coach never has the secret, no input can make it reveal it. Its confidence drops (100% → 75% → 35%) as attempts are wasted, which warns the player.

## Reliability and guardrail results

### Evaluation script

```
$ python evaluation/evaluate_coach.py
# Coach Evaluation Results

## Part 1: every secret, following the coach

| Difficulty | Games | Wins | Win rate | Coach's starting confidence | Avg guesses to win | Hints passing self-check | Result |
|---|---|---|---|---|---|---|---|
| Easy | 20 | 20 | 100% | 100% | 3.70 | 74/74 | Pass |
| Normal | 100 | 100 | 100% | 100% | 5.80 | 580/580 | Pass |
| Hard | 50 | 31 | 62% | 62% | 4.16 | 224/224 | Pass |

## Part 2: guardrail scenarios

| Scenario | Evaluation criteria | Behavior | Result |
|---|---|---|---|
| Fresh game, no guesses | Suggests 50 (midpoint), status ok, confidence 100% | status=ok, suggestion=50 | Pass |
| Junk entries in history | Ignores 3 bad entries, still plans from 40 Too High | status=ok, suggestion=20 | Pass |
| Contradictory feedback (40 Too Low, then 30 Too High) | No number fits, so falls back to the basic hint | status=fallback, suggestion=None | Pass |
| Only one number left | Suggests 6 with 100% confidence | status=ok, suggestion=6 | Pass |
| Game already won | Gives no hint (status done) | status=done, suggestion=None | Pass |
| No attempts left | Gives no hint (status done) | status=done, suggestion=None | Pass |
| Faulty proposer repeats a guess | Self-check rejects 50, revises to a valid number | status=revised, suggestion=49 | Pass |
| Faulty proposer goes out of range | Self-check rejects 30, revises inside 11-20 | status=revised, suggestion=20 | Pass |
| Faulty proposer crashes | Error is caught and logged, game still gets a valid hint | status=revised, suggestion=25 | Pass |
| Faulty proposer returns text | Text is rejected, never shown; revises to a number | status=revised, suggestion=10 | Pass |

## Summary

- Game simulations: 3/3 difficulties passed.
- Guardrail scenarios: 10/10 passed.

Saved to evaluation/results.md (coach steps logged to logs/coach.log)
```

The "faulty proposer" rows swap the coach's normal ACT step for a broken one, to prove the CHECK → REVISE → FALLBACK loop catches bad output.

### Log excerpt (`logs/coach.log`)

This shows the agent catching its own bad proposal, and falling back on contradictory feedback:

```
INFO PLAN range=1-49 size=49 attempts_left=7 strategy=binary search
INFO ACT proposed=50
WARNING CHECK failed=['inside_possible_range', 'not_already_guessed', 'agrees_with_last_feedback'] for proposal=50
INFO REVISE new_proposal=49
INFO CHECK passed proposal=49
INFO RESULT status=revised suggestion=49 confidence=1.00
INFO PLAN range=41-29 size=-11 attempts_left=5 strategy=contradiction
WARNING FALLBACK reason=Feedback history contradicts itself; no number fits.
```

### Unit tests

```
$ python -m pytest
============================= test session starts =============================
platform win32 -- Python 3.14.6, pytest-9.1.1, pluggy-1.6.0
collected 24 items

tests\test_coach.py ................                                     [ 66%]
tests\test_game_logic.py ........                                        [100%]

============================= 24 passed in 0.04s ==============================
```

## Design decisions

- **Deterministic agent instead of an LLM.** The Higher/Lower feedback determines exactly which numbers are still possible, and binary search is the optimal strategy, so an LLM would add cost, latency, and new failure modes (made-up or out-of-range numbers) without better hints. A deterministic agent gives the same answer every run, which makes exact, reproducible evaluation possible, and it needs no API key. The trade-off is that its hints are templated, not conversational.
- **The coach never sees the secret.** It gets only what the player sees. Secret leakage is impossible by design, so I don't have to rely on a check that tries to catch it.
- **Binary search as the strategy.** It's the optimal strategy for Higher/Lower. It also gives a confidence formula that can be checked: with *k* guesses left, at most 2^k − 1 numbers can be pinned down.
- **Swappable ACT step.** `get_coach_hint(..., propose=...)` lets the evaluation inject broken proposers. In real play binary search never fails a check, so without this the guardrails would go untested.
- **Fall back to the original hint, never crash.** If the coach can't verify a suggestion, the player still gets the Module 1 Higher/Lower hint. The app also wraps the coach in `try/except`.
- **Shared game rules.** `parse_guess` and `update_score` moved from `app.py` into `logic_utils.py` (they were unfinished stubs there), so the app, the CLI demo, and the tests all use the same code.

## Testing summary

- **Worked:** 24/24 unit tests pass, and all 13 evaluation checks pass. The coach won every Easy and Normal game. On Hard, its starting confidence (62%) matched its actual win rate (31/50) exactly. All 878 hints in real play passed the self-check on the first try.
- **Didn't work as well:** Hard mode can't be won reliably even with a perfect strategy. When the REVISE step repairs a bad proposal, it picks the *nearest* valid number (49 in the log above) rather than the midpoint. The hint is valid but weaker than it could be.
- **Learned:** guardrails that never fire in normal use still have to be tested, so I built faulty proposers to trigger them on purpose. A confidence score is only useful if you check it against real outcomes, which is why the evaluation compares predicted and actual win rates.
- The Streamlit UI was checked headlessly with `streamlit.testing.AppTest`. It covered coach hints after each guess, rejected text input, a win, and a loss with hints off.

## Reflection

This project taught me that making an AI feature reliable is mostly about making it checkable. The planning logic was the easy part. The harder work was deciding what "correct" means for a hint, writing that down as checks, and building ways to make the agent fail on purpose so I could see the checks work. Keeping the secret away from the coach entirely was simpler and safer than trying to filter its output afterwards.

The responsible-AI reflection (limitations, misuse, testing surprises, and AI collaboration) is in [model_card.md](model_card.md).
