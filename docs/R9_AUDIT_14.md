# R9 audit: the 14 user acceptance items

**Status key:** `Backend validated` = tests prove rule/DB behavior, not Godot rendering; `Partial` = feature exists but the full requested player experience is incomplete; `Visual pending` = user must actually test Godot + online LLM. R9 does not claim any game is perfect or fully bug free.

| # | Requirement | Source of implementation in R8/R9 | Honest status and remaining work |
|---|---|---|---|
| 1 | Free/conditional hire, pay, follow, termination | `server/world/continuity.py`, `server/world/tasks.py`, `game/actors/npc.gd`; tests in `tests/test_continuity_r7.py` | Backend validated: contracts, idempotent wallet transfer, task lifecycle; persistent FOLLOW dynamic target. Visual pending for active following under Godot, obstruction and long saves. |
| 2 | Cascading world events and real information spread | `continuity.tick/observe`, `living_world`, board UI | Partial: real witnessed attacks, reports, guard actions, local notices and funded hunt commissions. No arbitrary event choreography or full social economy simulation; events must have implemented primitives. |
| 3 | Grounded quest targets, realistic clues | `continuity.quest_view`, `dialogue_action`, `living_world._create_errand` | Backend validated for known task kinds, recipient/item/reward, last-known not live-tracked. Broader natural language, incorrect rumors and off-route quests need playtesting. |
| 4 | Readable personal journal, no raw IDs or spam | `living_world.journal`, `game/ui/play_windows.gd` | Backend validated human-readable summaries of key observed events. Narrative quality, grouping and all viewport sizes still require UI review. |
| 5 | Modal navigation/back/close/reopen | `game/ui/play_windows.gd`, HUD screens | Partial: trade back-to-dialogue and Esc implemented; all other modal combinations and keyboard focus remain unverified. |
| 6 | Two-way trade, items and coins with one wallet | `server/world/continuity.py`, world economy, shop views | Backend validated buy/sell, actual ownership transfer, single authoritative wallet and projected currency item; refusal/price depends on actor relationship. Visual pending. |
| 7 | Guards, replacement identities, safe zones | `continuity.initialize/tick`, guards, monster ecology | Backend validated zones and new guard IDs/memories after deaths; guard decision depth and patrol presentation partial. |
| 8 | Elites/chests/economy | `monster_ecology.py`, `continuity.initialize`, art mapping | Backend validated elite scaling and scarce gear; visual balancing and difficulty require extended game testing. |
| 9 | Attack delay/background LLM | `game/net/game_api.gd` R9 dual HTTP lanes, A local attack FX | Partial: separate slow dialogue channel; backend still validates version. Real-time input latency, model timeout and Godot callback ordering need actual engine/network measurement. |
| 10 | Four renewable gathering resources | `continuity.py`, resource nodes, map art | Backend validated depletion, regen by tick, item ownership, submission and trade. Art/collision usability needs Godot. |
| 11 | NPC livelihoods: collect/trade/explore/craft/repair/buy/use meds | `continuity.tick/arrival`, R9 station and healing additions | Partial but substantially implemented. Real inventory, gold, material consumption and move-to-workshop; bounded path exploration + neighbor aid. Does not provide unlimited creative ability or complex crafting professions/indefinite plans. |
| 12 | Independent credible memories/relations | `agent_runtime`, `agents/memory`, `living_world`, R9 place filtering and visit records | Partial: provenance isolation, gossip skepticism, bounded known geography, source-based aid relation. Long chains of social beliefs and all model hallucinations cannot be eliminated by these checks alone. |
| 13 | Artwork from six reference images without treating captions as specifications | R8 asset extraction/manifest, creature proxies | R8 asset references checked by tests; independently painted animations for every species not provided (some generated proxy motion). No extra drawing imported in R9; original R8 art retained. |
| 14 | Whole game integration/save/load/source/tests/merge | Existing Godot/FastAPI + R9 tests/docs | Backend full regression, resource/contract checks and patch verification can be done here. Actual Godot 4.5.2 Windows, live API, multi-save and long play session remain to be performed by team. |

## High priority manual acceptance checklist

1. Start **fresh** test save; verify no script parser errors or missing sprites.
2. Approach merchant: free-hire, walk 40+ tiles and watch follower; reload, dismiss. Repeat paid-hire at 50 coins and confirm exact one-time transfer.
3. Propose delivery: ask issuer the identity/landmark, verify the recipient and item exist; move recipient after offer and verify old clue stays as *last known* rather than becoming omniscient.
4. Gather herb/wood/stone/iron: depletion, wallet/backpack, regen, save/reload and material quest completion.
5. Watch an NPC collect wood/iron and approach real workshop; make sure the actor does not craft from nowhere while far away.
6. Damage two nearby NPCs: give one a potion, set it to generous, observe actual aid, consumption and trust; ensure no ghost items.
7. Create hostile rumor: verify witness reports only after reaching guard, not instant world-wide omniscience.
8. Read personal journal, check only witnessed important events and no `evt_` strings or coordinate pairs.
9. Open buy/sell, back-to-dialogue, Esc/backpack, save/reload; attempt transactions with empty wallet and duplicate requests.
10. With a live model call pending, attack and measure visual first-frame delay and authoritative hit confirmation; compare to fallback.
11. Trigger two-run learn/rollback evaluation; compare actual metrics, learned policy diff and restore baseline.
