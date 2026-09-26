# Goals 2026 📦

Live: **https://goals2026.pythonanywhere.com**

Every goal is a textured box. Each box holds missions, each mission is a checklist.
The box "fills up" as steps get checked, and gets an **ACHIEVED** stamp when every mission is done.

- Flask + SQLite, vanilla JS, no build step.
- Anyone can view; editing needs the owner password (hash stored in `config.json` on the server, not in git).
- Run locally: `pip install flask && python app.py` (first run creates `config.json` and prints a password).
- Redeploy: `./deploy.sh` (needs `Goals2026_PA_TOKEN`). Server data (`goals.db`) and `config.json` are never overwritten.
