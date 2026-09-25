---
title: My portfolio builds itself
image: images/pipeline.png
comment: https://github.com/Thanoon12k/My-Work
post_urn: urn:li:share:7509374867117608960
published: 2026-09-25
---
I have 65 projects on GitHub. I didn't screenshot a single one by hand.

I wrote a tool called showcase that does the whole job with one command:

1️⃣ Clones all 65 repositories
2️⃣ Runs each app: migrates the database for Django apps, creates a demo user, logs in
3️⃣ Crawls every app in a headless browser and takes desktop and mobile screenshots
4️⃣ For apps that can't run in a browser (Flutter screens, desktop windows, Arduino serial output), it draws a mock-up from the source code
5️⃣ Builds the portfolio site and deploys it to PythonAnywhere

Zero manual steps. When I push a new project, the portfolio updates itself.

My rule: if I do something twice, I automate it the third time.

🌐 Live result: make1it.pythonanywhere.com
Code in the first comment 👇

#Automation #Python #Playwright #Django #DeveloperPortfolio #OpenSource
