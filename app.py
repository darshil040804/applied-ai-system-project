import logging
import random
import streamlit as st
# FIX: Moved get_range_for_difficulty into logic_utils.py as the single source of truth;
# I described the refactor and Claude (agent mode) deleted the duplicate here and imported it.
from logic_utils import (
    check_guess,
    get_attempt_limit,
    get_range_for_difficulty,
    parse_guess,
    update_score,
)
from coach import get_coach_hint, set_up_logging

set_up_logging()
log = logging.getLogger("coach")

st.set_page_config(page_title="Glitchy Guesser", page_icon="🎮")

st.title("🎮 Game Glitch Investigator")
st.caption("A number-guessing game with an AI coach that checks its own hints.")

st.sidebar.header("Settings")

difficulty = st.sidebar.selectbox(
    "Difficulty",
    ["Easy", "Normal", "Hard"],
    index=1,
    filter_mode=None,  # FIX: I asked for a plain dropdown (no search box); Claude suggested filter_mode=None.
)

attempt_limit = get_attempt_limit(difficulty)

low, high = get_range_for_difficulty(difficulty)

st.sidebar.caption(f"Range: {low} to {high}")
st.sidebar.caption(f"Attempts allowed: {attempt_limit}")

hint_mode = st.sidebar.radio(
    "Hints",
    ["AI Coach", "Basic", "Off"],
    help="AI Coach plans the next guess and checks it before showing it. "
         "Basic is the original Higher/Lower hint.",
)


def reset_game():
    st.session_state.secret = random.randint(low, high)
    st.session_state.attempts = 0
    st.session_state.status = "playing"
    st.session_state.history = []
    st.session_state.turns = []  # (guess, outcome) pairs: all the coach is allowed to see


# FIX: Secret was generated once and could fall outside the selected range. Claude diagnosed it
# when I reported the bug; I approved the fix, and Claude verified it with a headless AppTest run.
# Start a fresh game whenever the difficulty changes so the secret always
# matches the selected range.
if st.session_state.get("game_difficulty") != difficulty:
    st.session_state.game_difficulty = difficulty
    reset_game()

if "score" not in st.session_state:
    st.session_state.score = 0

st.subheader("Make a guess")

# FIX: "Attempts left" lagged one guess and the game ended a guess early. I reported the symptoms;
# Claude traced it to attempts starting at 1 and the info box rendering before the submit was handled.
# Filled in after a guess is processed so "attempts left" is never one behind.
info_box = st.empty()


def show_info():
    # FIX: Text used a hardcoded "1 and 100"; I asked for low/high, Claude made the change.
    info_box.info(
        f"Guess a number between {low} and {high}. "
        f"Attempts left: {attempt_limit - st.session_state.attempts}"
    )


def show_coach():
    """Run the coach's plan -> act -> check loop and display its hint."""
    try:
        hint = get_coach_hint(
            st.session_state.turns,
            low,
            high,
            attempt_limit - st.session_state.attempts,
        )
    except Exception:
        # Guardrail: a coach failure must never break the game.
        log.exception("Coach crashed; showing no coach hint")
        st.warning("The coach hit an error, so no coach hint this turn.")
        return

    if hint.status == "done":
        return
    with st.container(border=True):
        st.markdown(f"**🧠 AI Coach:** {hint.message}")
        if hint.status == "fallback":
            st.caption("The coach could not verify a suggestion, so it fell back to the basic hint.")
        else:
            st.caption(
                f"Confidence you can still win by following the coach: {hint.confidence:.0%}"
                + (" · suggestion was revised after a failed self-check" if hint.status == "revised" else "")
            )
        with st.expander("How the coach checked this hint"):
            for name, passed in hint.checks.items():
                st.write(("✅ " if passed else "❌ ") + name.replace("_", " "))
            for note in hint.notes:
                st.write("• " + note)


with st.expander("Developer Debug Info"):
    st.write("Secret:", st.session_state.secret)
    st.write("Attempts:", st.session_state.attempts)
    st.write("Score:", st.session_state.score)
    st.write("Difficulty:", difficulty)
    st.write("History:", st.session_state.history)

# FIX: First guess seemed to do nothing. I described it; Claude's hypothesis was Enter in a bare
# text_input reruns without a submit, so it moved the input into a form (not confirmed in a browser).
# A form sends the text and the submit together, so pressing Enter or clicking
# the button both count as one guess (a bare text_input reruns on Enter alone).
with st.form("guess_form", clear_on_submit=True):
    raw_guess = st.text_input(
        "Enter your guess:",
        key=f"guess_input_{difficulty}"
    )
    submit = st.form_submit_button("Submit Guess 🚀")

new_game = st.button("New Game 🔁")

if new_game:
    reset_game()
    log.info("NEW GAME difficulty=%s", difficulty)
    st.success("New game started.")
    st.rerun()

if st.session_state.status != "playing":
    show_info()
    if st.session_state.status == "won":
        st.success("You already won. Start a new game to play again.")
    else:
        st.error("Game over. Start a new game to try again.")
    st.stop()

if submit:
    st.session_state.attempts += 1

    ok, guess_int, err = parse_guess(raw_guess)

    if not ok:
        st.session_state.history.append(raw_guess)
        log.info("INPUT rejected raw=%r reason=%s", raw_guess, err)
        st.error(err)
    else:
        st.session_state.history.append(guess_int)

        # FIX: Secret was cast to str on even attempts, flipping Higher/Lower hints. I spotted the
        # odd hints; Claude found the str() cast and removed it, then re-tested with secret=14, guess=5.
        outcome, message = check_guess(guess_int, st.session_state.secret)
        st.session_state.turns.append((guess_int, outcome))
        log.info("GUESS %s -> %s", guess_int, outcome)

        if hint_mode != "Off":
            st.warning(message)

        st.session_state.score = update_score(
            current_score=st.session_state.score,
            outcome=outcome,
            attempt_number=st.session_state.attempts,
        )

        if outcome == "Win":
            st.balloons()
            st.session_state.status = "won"
            st.success(
                f"You won! The secret was {st.session_state.secret}. "
                f"Final score: {st.session_state.score}"
            )

    if st.session_state.status == "playing" and st.session_state.attempts >= attempt_limit:
        st.session_state.status = "lost"
        st.error(
            f"Out of attempts! "
            f"The secret was {st.session_state.secret}. "
            f"Score: {st.session_state.score}"
        )

if hint_mode == "AI Coach" and st.session_state.status == "playing":
    show_coach()

show_info()

st.divider()
st.caption("Built by an AI that claims this code is production-ready.")
