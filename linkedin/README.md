# LinkedIn Autopost

A small Flask dashboard running at **https://apps1monitor.pythonanywhere.com** that publishes
the posts in `queue/` to your LinkedIn profile. Nothing runs on your PC.

- `app.py`, `templates/`, `static/`: dashboard (Overview, Compose with live preview, Posts queue, Profile makeover, Setup) and `/cron`
- `post.py`: LinkedIn Posts API code shared by the dashboard and `/cron`
- `queue/`: posts waiting to be published, in file-name order
- `images/`: post images (JPG/PNG/GIF)
- `profile_kit.py`: profile makeover steps shown with copy buttons at `/profile`
- `posts.md`: the original post drafts
- `../.github/workflows/linkedin-cron.yml`: calls `/cron` hourly; the app publishes at most one post per posting day

The live copy on PythonAnywhere (`/home/apps1monitor/linkedin`) is the source of truth for the
queue once you start editing in the dashboard. Settings and the LinkedIn token stay in
`data/config.json` on the server and are never committed.

Every 60 days: open the dashboard and click **Reconnect LinkedIn**.
Every month: PythonAnywhere free web apps expire. Log in to PythonAnywhere → Web → **Run until 3 months from today**.
