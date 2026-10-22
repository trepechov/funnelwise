# Funnelwise (product repo)

Start by reading `memory/project-context.md`: current state, decisions, commands, what is verified
and what is still open. The to-do list is the "First test" section of `memory/plan.md`.

Rules for work in this repo:
- Servers stay **standard-library Python 3.9** (no pip installs at runtime); vendored libs live in `servers/_vendor/`.
- Product code and `reference/`, `skills/`, `docs/` must contain **no customer identifiers or secrets**
  (`tests/test_plugin_structure.py` enforces it). Customer facts belong only in `memory/`, which is gitignored and stays on this computer.
- Funnelwise is **read-only**: never add a tool that posts, replies, deletes or messages.
- Run the tests on Python 3.9 before committing (command in `memory/project-context.md`).
- Don't push or publish without being asked.
- Update `memory/project-context.md` when state or decisions change.
