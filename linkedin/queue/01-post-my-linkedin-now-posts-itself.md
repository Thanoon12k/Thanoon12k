---
title: My LinkedIn now posts itself (Autopost dashboard)
image: images/autopost-dashboard.jpg
comment: https://github.com/Thanoon12k
---
My LinkedIn now posts itself. 🤖

My portfolio already builds itself and my Facebook page already runs itself, so LinkedIn was next.

I built a small dashboard called Autopost:

✍️ Compose: write a post and see a live preview that looks exactly like LinkedIn
📋 Queue: drag posts up or down, with the planned date next to each one
📅 Schedule: pick the days and the hour, and it publishes one post from the top of the queue
🖼️ Images upload automatically through the LinkedIn API
📱 Works from my phone, so I never need my PC

How it runs:
• Flask app on PythonAnywhere (free plan)
• LinkedIn OAuth + Posts API
• GitHub Actions wakes it every hour; the app decides if it's time to post, and never posts twice in a day

The post you're reading was published by it. 😄

I built it in one evening with an AI pair-programmer. My job was deciding what to build; the boring parts went fast.

What would you automate first?

#Automation #Python #Flask #LinkedInAPI #GitHubActions #BuildInPublic
