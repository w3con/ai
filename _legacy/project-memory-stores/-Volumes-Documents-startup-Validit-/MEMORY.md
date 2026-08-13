# Validité project memory

Project-specific facts. **Cross-project facts about the user and his working style now live at the user level** (`~/.claude/memory/`, loaded everywhere via `~/.claude/CLAUDE.md`) — directness, writing-for-the-reader, Opus-plans/Sonnet-implements, reusable-tooling, decide-before-building, and the critic-agent discipline were promoted there and removed from here. See [Memory tiering](project_memory_promote_userlevel.md).

- [Capture strategy as restartable decision log + options map](feedback_strategy_capture.md) — persist decisions/threads to disk + Outline, attach reasons/goals, flag research for later (don't auto-run)
- [git mv fails on absolute paths here](reference_git_mv_accented_repo_path.md) — accented repo path "Validité" (NFD/NFC) breaks absolute-path git ops; use relative paths from repo root
- [Access the KB cheaply & safely](feedback_kb_data_access.md) — never MCP (cost), avoid ad-hoc curl (wrapper later), strip local paths in Outline, keep .env out of context
- [Don't read web repo unless asked](feedback_web_repo_boundary.md) — stay in KB repo; web repo (validite.eu site/decks) is out of scope by default
- [Retailer pitch build](project_retailer_pitch_build.md) — edit slides/*.html then run build.py; never edit generated index.html
- [Customer discovery: Collecter pain](project_customer_discovery_collecter.md) — Khalil Charef (textile quality eng.) confirms "request certs from suppliers one by one"; validates Collecter, not yet Prouver
- [Site update plan](project_site_update_plan.md) — validite.eu deck-aligned rewrite; plan doc + decisions in the web repo (prices held off site, footer trimmed, regulation = red thread)
- [.ai/relations: sound index, not an existence-authority](reference_relations_unreliable.md) — index is good for retrieval (domains/topics/entities/summary); weakness is partial coverage + uneven Haiku quality per 2026-05-21 audit, so verify Outline existence via id_mapping + live documents.info, not relations
- [BizDev collection = pipeline/CRM hub](project_bizdev_collection.md) — top-level Outline collection; Pipeline — Master Tracker (6f829d7f) owns who/stage/next-step; framing stays in Strategy/Intelligence
- [Memory tiering: user-level vs project](project_memory_promote_userlevel.md) — how/where person facts are promoted; user-profiler routes facts to the right tier
