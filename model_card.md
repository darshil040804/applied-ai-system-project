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

## Future improvements

- **Smarter revision.** Make the REVISE step choose the unguessed number closest to the *midpoint* of the possible range, so a repaired hint is as strong as a normal one.
- **Remove the secret from the UI.** Put the "Developer Debug Info" panel behind a developer flag so players can't see the secret.
- **Score-aware coaching.** Let the coach weigh the scoring rules as well as the chance of winning, and show both.
- **Teach, don't just tell.** Explain *why* the midpoint is the best guess (each guess halves what's left), so the player learns the strategy instead of only following it.
- **Contradiction recovery.** When feedback contradicts itself, find the smallest set of turns to drop to make it consistent, instead of only falling back.

## Collaboration with AI

I used Claude Code as an agentic coding assistant. My role was the engineer: I set the constraints, made the architecture decisions, and decided what counted as "done". The assistant drafted code and docs inside those decisions.

- **Plan before generating.** Before any code was written, I had the assistant restate its understanding of the system and list the decisions it needed from me, and I held back implementation until those were settled. That brought the important trade-offs (LLM vs. offline, which AI patterns, how much scope) up front, instead of discovering them later in generated code.
- **Explicit constraints.** I gave the assistant firm boundaries: offline only, no components the system doesn't use, and keep the existing game behavior intact. Constraints like these keep generated code focused and easier to review.
- **Verification over trust.** Nothing was accepted because it looked right. Each piece is backed by something that runs: unit tests for the game rules and every coach step, an exhaustive evaluation over all 170 possible games, and a headless Streamlit `AppTest` run to confirm the coach works inside the real UI. Every output in the README is pasted from an actual run.
- **Testing the guardrails adversarially.** The guardrails never fire during normal play, so their tests could have passed while the guardrails themselves were broken. The design makes the ACT step swappable, so the evaluation can inject broken proposers (repeated guesses, out-of-range numbers, crashes, text) and prove that the check → revise → fallback loop catches each one.
- **Observability.** Every agent step is logged with its inputs and decision, so a wrong hint can be traced back to the exact step that produced it.

**A suggestion I accepted:** combining an agentic coach (plan → act → check) with a reliability harness (guardrails, confidence score, evaluation). The two strengthen each other. The guardrails give the agent a precise, testable definition of a correct hint, and the agent loop gives the guardrails a natural place to run: between proposing a hint and showing it.

**A suggestion I did not accept as written:** the assistant recommended building the coach on an LLM (the Claude API) with an offline fallback. I chose a deterministic agent instead. In this game, the Higher/Lower feedback determines exactly which numbers are still possible, and binary search is provably the optimal strategy. An LLM would add nondeterminism, cost, latency, and new failure modes (made-up or out-of-range numbers) without improving the hints. A deterministic agent also allows *exact* evaluation: the same input always gives the same hint, so the evaluation numbers are reproducible. I also scoped down the assistant's first plan, which included RAG over a strategy knowledge base and a human-evaluation round. Retrieval adds nothing here, because everything the coach needs is already in the turn history. Human review is weaker than an exhaustive check when every possible game (170 of them) can be evaluated automatically.
