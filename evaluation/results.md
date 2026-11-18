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
