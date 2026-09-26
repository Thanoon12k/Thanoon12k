# Goals 2026 📦

Live: **https://goals2026.pythonanywhere.com**

Every goal is a box. Each box holds missions, each mission is a checklist.
The box fills up as steps get checked, and gets an **ACHIEVED** stamp when every mission is done.

- Flask + SQLite, vanilla JS, no build step.
- Anyone can view. Editing needs the owner password (browser) or the API token (agents).
  Both are stored only as hashes in `config.json` on the server (not in git).

## Agents

Full guide for agents: **https://goals2026.pythonanywhere.com/llms.txt**

**MCP server** — `https://goals2026.pythonanywhere.com/mcp` (Streamable HTTP, stateless JSON).
Tools: `get_board`, `get_goal`, `create_goal` (with nested missions/steps), `update_goal`, `delete_goal`,
`add_mission`, `update_mission`, `delete_mission`, `add_steps`, `update_step`, `check_steps`, `delete_step`.

```bash
# Claude Code
claude mcp add --transport http goals2026 https://goals2026.pythonanywhere.com/mcp \
  --header "Authorization: Bearer $GOALS_API_TOKEN"
```

Clients that can't send headers can use `https://goals2026.pythonanywhere.com/mcp/<API token>`.

**REST** — the same `/api/*` routes the page uses, with `Authorization: Bearer <API token>`.
See `/llms.txt` for every endpoint.

## Running and deploying

- Local: `pip install flask && python app.py` (first run creates `config.json` and prints a password).
- New or rotated API token: `python app.py --new-token` (prints it once; the old token stops working).
- Redeploy: `./deploy.sh` (needs `Goals2026_PA_TOKEN`). Server data (`goals.db`) and `config.json` are never overwritten.
