# R9 team handoff

## A - Godot actors, combat and autonomous action execution

- Keep `game/actors/npc.gd` as the execution boundary. The world owns move destinations, health and results, so client animation never permanently changes authoritative items/coins.
- Verify autonomous NPC excursions in the continuous world, real workshop arrival, patient aid, and NPC follower behavior with long paths and checkpoint updates.
- Measure attack animation start time under long live dialogue; local feedback should not wait for LLM.

## B - NPC agent/memory

- Read `agent_runtime.build_context`; R9 only injects verified known places, personal visit history and scoped memories, not the global location registry.
- Distinguish hearsay from eyewitness observation. Do not infer exact position of a third party from a stale delivery clue; reference real actor/quest IDs internally.
- NPC creation is physically grounded with a fresh identity; visual sprites/guard appearance are not inherited biographies.
- Model may suggest supported actions, never directly mint money or force an item or emotion change.

## C - authoritative world API, storage

- R9 newly uses `visited_place_ids` in existing NPC metadata (optional, backward compatible) and quest `recipient_last_known_tile` (optional for older saves).
- `NPC_CRAFT`/`NPC_REPAIR` only settle at the identified actual worksite, with owned real ingredients, after an approved MOVE and reported arrival. Validate source events and inventory transfer.
- `npc_aided` includes a medication source and causes a recorded trust update. `npc_expedition_started` / `npc_explored` are separated by physical completion.
- Data version/permission checks remain decisive if a long LLM request finishes after a newer hit or world update.

## D - UI, routing and visual QA

- `game/net/game_api.gd` now has two request lanes: a fast HTTP lane and a model dialogue HTTP lane. Validate no duplicate signals or stale world-state application from slow dialogue.
- `game/ui/play_windows.gd` returns from shop to nearby NPC dialogue on button and Escape. Model configuration displays rejection instead of pretending successful activation.
- Keep only narrative fields of the journal UI; source IDs remain for diagnostics but not player prose. Test keyboard focus, screen size and back navigation in Windows Godot.

## Tests / release

Run the full pytest and contracts, then Godot headless import and actual visual F5 with API. Team-specific work should be reviewed in PRs, not force pushed to main. Save the rollback/evolution demo as an independent known-good judge path.
