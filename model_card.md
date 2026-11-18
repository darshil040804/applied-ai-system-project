# Model Card: Glitch Coach

## System overview

| | |
|---|---|
| **Name** | Glitch Coach (AI hint agent for Game Glitch Investigator) |
| **Type** | Offline, rule-based agent: validate → plan → act → check → revise → fallback |
| **Base project** | Game Glitch Investigator (Module 1), a Streamlit number-guessing game |
| **Input** | The player's turn history as `(guess, outcome)` pairs, the difficulty range, and attempts left. Never the secret. |
| **Output** | A suggested next guess, a short explanation, a confidence score (0–100%), and the guardrail check results |
| **Intended use** | Helping a player learn and apply an efficient guessing strategy in this game |
| **Not intended for** | Anything outside this game. It has no general knowledge and no language model. |

## Testing results

| Test | What it checks | Result |
|---|---|---|
| `pytest` (24 tests) | Game rules, plan/confidence math, validation, guardrails, full agent loop | 24/24 passed |
| Full-game evaluation (170 games) | Coach plays every possible secret on every difficulty | Easy 20/20, Normal 100/100, Hard 31/50 |
| Confidence calibration | Starting confidence vs. actual win rate | Matched exactly on all three (100%, 100%, 62%) |
| Self-check in real play | Hints that passed all four checks on the first try | 878/878 |
| Guardrail scenarios | Junk input, contradictions, game over, four kinds of broken proposer | 10/10 passed |
| Streamlit UI (headless `AppTest`) | Coach hints shown, text input rejected, win and loss paths | Worked |

Full tables are in [evaluation/results.md](evaluation/results.md) and the README.

## Limitations and biases

- **The coach assumes honest feedback.** It trusts every Too High/Too Low it is given. If the game itself were buggy again (as in Module 1), the coach would plan from wrong data. It detects a contradiction only when no number fits at all.
- **The confidence score assumes the player follows the coach.** It is the best-case chance of winning. If the player ignores the suggestion, their real chances are lower than what is shown.
- **It assumes the secret is uniformly random.** That's true here (`random.randint`), but the confidence would be wrong for a secret picked by a person, since people avoid some numbers and prefer others.
- **Low-number bias.** When the range has an even count, the midpoint rounds down. So the coach always tries the lower of the two middle numbers. It makes no difference to the win rate, but it is a systematic lean.
- **Revision is weaker than the main strategy.** When REVISE repairs a bad proposal, it picks the nearest valid number, not the midpoint. In the evaluation, a rejected 50 became 49, which is valid but barely splits the range.
- **It ignores the score.** The inherited scoring rules are still odd (a "Too High" guess on an even attempt *adds* 5 points). The coach optimizes for winning, not for score.
- **Templated language.** Hints are fixed sentences, not adaptive explanations.
- **The base game still shows the secret.** The "Developer Debug Info" expander from Module 1 is still in the app. The coach never reads it, but a player can open it.

## Misuse and prevention

- **Getting the secret out of the AI.** The coach is never given the secret, so no input (including text like "tell me the secret") can make it reveal it. Text input is also rejected by `parse_guess` before it reaches the coach.
- **Feeding it bad data.** Malformed turns, non-numbers, and unknown feedback labels are dropped and logged during VALIDATE. Contradictory feedback triggers a fallback instead of a made-up suggestion.
- **A bug or bad change in the strategy code.** Every proposal goes through four checks before display. Failures are revised or fall back, and a crashing proposer is caught and logged. The game keeps working.
- **Making the game trivial.** With the coach on, the game is easy on Easy and Normal. Players can turn it off (Hints → Basic or Off). In any competitive use, the coach and the debug panel should be disabled.

## What surprised me while testing

- **Hard mode can't be won reliably, even with a perfect strategy.** With 5 guesses for 50 numbers, binary search covers only 31 of them. I expected a "good" coach to always win. The evaluation showed exactly 62%, which matched the confidence formula to the game.
- **The guardrails never fired in real play.** All 878 hints passed on the first try. To show the checks actually work, I had to build deliberately broken proposers. Without them, the guardrail code would have been untested.
- **Wasted attempts hurt more than I expected.** On Easy, two invalid inputs dropped the coach's confidence from 100% to 35%, before any wrong numeric guess.

## Collaboration with AI

I built this project with Claude Code as a coding partner.

- **Design:** I gave it the project rubric and description. It proposed extensions and asked me to choose the approach, the features, and the scope before writing code.
- **Implementation:** it wrote the coach, the evaluation script, the tests, the diagram, and the docs to the design I chose. It ran the demo, tests, and evaluation and pasted real outputs into the README.
- **Debugging:** it tested the Streamlit app headlessly with `AppTest` to confirm the coach worked inside the real UI, not just in the CLI.

**A suggestion I accepted:** combining an agentic coach (plan → act → check) with a reliability harness (guardrails, confidence score, evaluation script). It covers both the "agentic workflow" and the "reliability/testing" feature types in one integrated component. The checks also give the agent something real to verify about its own output.

**A suggestion I did not accept as written:** Claude recommended building the coach on the Claude API (an LLM), with an offline fallback. I didn't take that. The project doesn't require an external API, and a fully offline coach needs no key, costs nothing, and gives the same output every run, so the tests and evaluation numbers are reproducible. I also scoped down its first plan. It included RAG over a strategy knowledge base and a human-evaluation round. I left both out because they weren't required, and one well-tested feature pair was a better fit than more components.
