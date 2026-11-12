# Claude Prompts: GenAI Multilingual Video Conferencing (4 parallel roles)

## How to use this file

1. Create the GitHub repo first. Save PART A as `shared/CONTRACT.md` and commit it.
2. Each person opens their own Claude setup and pastes **PART A first, then their own role prompt (B1 / B2 / B3 / B4)**.
3. Every role builds a **MOCK of its service first** (a few hours of work). That way the other three can integrate on day 2 without waiting for the real AI models.
4. The contract is the only thing that connects the four roles. **Do not change it alone.** If a change is needed, ask Claude for a "CONTRACT CHANGE REQUEST", send it to the group chat, and update CONTRACT.md only after all four agree.

---

# PART A: SHARED CONTRACT (paste into every Claude setup)

See `shared/CONTRACT.md`.

---

# PART B1: ROLE 1, FRONTEND (Video Call + UI + Final Integration Lead)
See detailed prompt in project documentation.

---

# PART B2: ROLE 2, CALL SERVER + NETWORK MONITORING (the Hub)
See detailed prompt in project documentation.

---

# PART B3: ROLE 3, SPEECH TRANSLATION PIPELINE (ASR -> MT -> TTS)
See detailed prompt in project documentation.

---

# PART B4: ROLE 4, SPEAKER DETECTION (VAD + TOKEN PASSING)
See detailed prompt in project documentation.
