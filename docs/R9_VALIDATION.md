# R9 validation evidence and honest boundaries

## Test environment

- Source: `UnwrittenRealm_R8_Visual_Enemies_Source.zip` from the prior assistant delivery.
- Runtime in this tool environment: Linux / Python 3.13.x with dependencies already present; not Windows Python 3.11 or Godot 4.5.2.
- Commands (executed in the R9 source root):
  - `python -m pytest -q tests --disable-warnings`: **212 passed in 55.82s** (log: `/mnt/data/r9_full_212.log` in build environment).
  - `python -m compileall -q server shared tools tests`: completed, no error.
  - `python -m tools.check_contracts`: 9 documented examples accepted; only schema/format validation.
  - `python -m tools.check_evaluation_contracts`: 6 evaluation examples accepted; no actual run of the learning benchmark.
  - New `tests/test_r9_living_world.py`: 7 tests passed, plus R7 behavioral tests, verifies source-limited places, stale delivery clues, actual workshop item consumption, no magical forging, nearby potion aid, two HTTP lanes, shop/back, model configuration rejecting false success.

## What was checked by the test suite

- Free and paid contracts, idempotent payments, bounty witnesses, follow task authority, server-backed resource collection and regeneration.
- NPC inventories, trade/coins and provenance, equipment wear/repairs, elite monsters, artwork file references and role-specific action rules.
- NPC player-journal access isolation, B/World action decisions, learning/rollback DTOs.
- R9 no omniscient NPC place list; last-known quest clues are not raw coordinates; physical-workshop crafts and actual medicine aid.

## NOT VERIFIED - do not advertise these as finished

- Godot 4.5.2 import/parse/render, Windows launcher, actual player input/focus, 48x64 sprite alignment or in-game frame timing (no Godot binary in this execution environment).
- Live API/LLM round trips on the user's configured service, long NPC conversations, social and rumor consistency in every possible run.
- Save/load and world-version conflicts under concurrent LLM/model-vs-combat under a real Godot client (Python server tests pass, but the new GDScript dual lane is inspected statically only).
- Every combination of chest/merchant inventory, NPC emotions, arbitrary events, or all future game-generated narratives. The World Director still uses supported action/quest primitives.
- The sprite assets introduced by R8 remain a mix of authored still images and algorithmically generated animation proxies; not all monsters have hand-drawn attack frames.

## Manual Windows acceptance recipe

1. In a NEW directory run `Setup_Game.bat` then `Start_Game.bat` with Godot 4.5.2 Standard; shut down old service on 8765 before starting.
2. Open a fresh save; walk through towns, guards, elite monsters, loot and workshop props. Confirm no blank sprites or parser errors.
3. Enter real LLM settings. Ensure the returned `configured` property is true. Then conduct a live dialogue and confirm its `live` mode. Keep API Key out of screenshots/logs.
4. Trigger hiring as a free agreement, and as a 50-coin agreement; move and watch continuous follower, then save/load and dismiss.
5. Get a courier task; interrogate issuer for authentic recipient/location, move recipient afterward and confirm clue is *last-known*, not newly updated magically. Deliver actual item.
6. Observe a smith gather materials, walk to physical workshop, consume materials only when arriving, then compare weapon ownership and event ledger. Check that remote NPC cannot craft immediately.
7. Give a generous NPC a healing item and damage its nearby non-hostile neighbor. Confirm donor item consumed, target HP updated and relation event source recorded.
8. With a deliberately slow online model reply in flight, attack locally; ensure animation starts immediately, hit request goes to fast HTTP lane and server rejects stale proposals safely.
9. Test journal reading, return/close on all menus, buy and sell, spending, chest depletion, resource respawn and save/reload.
10. Repeat the existing two-run feedback/rollback demonstration, recording real before/after metrics with immutable settings.

## Patch applicability

The patch is generated from the exact source ZIP noted above. If the user's remote `main` has diverged, `git apply --check` may fail; **do not force it**, use the complete R9 source ZIP for testing and a reviewed port/merge for Git.
