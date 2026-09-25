"""Profile makeover content, shown with copy buttons on the dashboard's /profile page.

LinkedIn's API can't edit profiles, so each step says where to paste.
Every field: step title, where to click, optional note, and blocks of text to copy.
"""

STEPS = [
    {
        "title": "Name",
        "where": "Profile → pencil icon (Edit intro) → First name / Last name",
        "note": "\"Eng Thanoon\" hides you from recruiters who search for your real name. Put your title in the headline, not the name field.",
        "blocks": [("First name", "Thanoon"), ("Last name", "Younis")],
    },
    {
        "title": "Headline",
        "where": "Edit intro → Headline (max 220 characters). This is the line people see next to your name everywhere on LinkedIn.",
        "note": "Pick one. Option A is written to match what recruiters search for.",
        "blocks": [
            ("Option A (recommended)",
             "Full-Stack Developer · Flutter & Django · I build apps that talk to AI and hardware | "
             "65 projects shipped | University Tech Trainer | Open to remote work"),
            ("Option B",
             "I build the whole thing: Flutter apps, Django backends, AI & IoT integration | "
             "Ex-Huawei on-site engineer | Tech trainer & published researcher"),
        ],
    },
    {
        "title": "Banner image",
        "where": "Profile → camera icon on the top-right of the banner → Upload photo",
        "note": "Download the banner below. Its lower-left corner is left empty because your profile photo covers that area.",
        "banner": True,
        "blocks": [],
    },
    {
        "title": "About",
        "where": "Profile → About → pencil icon (max 2,600 characters). Only the first 3 lines show before \"see more\", so they have to hook the reader.",
        "blocks": [("About (English)", """I build the whole thing: the app in your hand, the server behind it, and the device it talks to.

For 6+ years I've shipped Flutter apps backed by Django and Flask APIs, then connected them to the real world: Arduino and ESP32 hardware, attendance devices, OpenCV vision and AI models. I handle the full lifecycle myself, from requirements and database design to the mobile UI, deployment and the Linux server it runs on.

🚀 Things I've built
⚡ Moalidaty (مولدتي): runs neighbourhood power generators: subscribers, amperes, payments, payroll and profit.
🩺 Pediatric Clinic (عيادتي): admin, doctor and parent roles, vaccines, growth charts, live chat, Arabic PDF reports.
💉 Smart Syringe Pump: a Flutter app controlling an Arduino medical pump, with safety checks and a live 3D syringe.
📝 Bubble Sheet Scanner: marks exam sheets offline with OpenCV and exports results to Excel.
🏢 Employee Manager: surveys, official letters and a director's dashboard for a government department.

⚙️ I automate everything
My portfolio builds itself: a tool I wrote clones all 65 of my repositories, runs each app, screenshots it and deploys the site with one command. My Facebook page runs itself through an AI agent and the Graph API. Even this LinkedIn profile posts on autopilot.

🎓 I teach and research
Since 2021 I've trained university students, guided graduation projects and supported doctors and professors with research and publishing, with papers in international journals.

🛠️ Flutter · Dart · Python · Django · Flask · REST APIs · PostgreSQL · Redis · Firebase · Supabase · OpenCV · TensorFlow · Arduino · ESP32 · Raspberry Pi · IoT · Linux

📍 Mosul, Iraq, open to remote, hybrid or on-site roles and freelance projects.
🌐 See all 65 projects with screenshots: make1it.pythonanywhere.com
📩 engthanoon1@gmail.com · WhatsApp +964 770 279 0915

Hiring a developer who can take a product from idea to production alone? Let's talk.""")],
    },
    {
        "title": "Experience: rewrite your existing positions",
        "where": "Profile → Experience → pencil icon → click each position → Description. Also add Skills to each position (bottom of the form).",
        "note": "Descriptions for Huawei and Mosul Space are based only on the job titles. Change anything that doesn't match what you actually did. The Toptal entry lasted 1 month; add a line about what you built there, or remove it, because a lone 1-month entry makes recruiters ask questions.",
        "blocks": [
            ("Title for the freelance position (was: AI Software Engineer)",
             "Full-Stack Software Engineer (Flutter · Django · AI)"),
            ("Freelance · May 2021 – Present: description", """Designing and shipping complete software products for clients in Iraq, from requirements to a deployed server.
• Built cross-platform Flutter apps with Django / Flask REST backends for power-generator operators (Moalidaty), a pediatric clinic, and a government department.
• Integrated AI and hardware: OpenCV exam-sheet scanning, an Arduino-controlled medical syringe pump, ZKTeco attendance devices, ESP32/IoT sensors.
• Wrote "showcase", an automation tool that clones, runs, screenshots and deploys 65 projects to a live portfolio with one command.
• Run a self-publishing Facebook page with an AI agent and the Graph API.
Skills: Flutter · Django · Python · REST APIs · OpenCV · PostgreSQL"""),
            ("Huawei · On Site Engineer: description (check it)", """On-site engineering for Huawei projects in Iraq.
• Installed, configured and tested equipment on site, following Huawei standards and safety procedures.
• Troubleshot and resolved technical issues in the field and reported status to the project team.
• Worked with cross-functional teams to deliver sites on schedule.
Skills: Networking · Troubleshooting · Telecommunications"""),
            ("Mosul Space · Web Developer: description (check it)", """Built and maintained web pages and features for Mosul Space.
• Developed responsive web interfaces and backend features with Python / Django.
• Worked with the team to turn requirements into working releases.
Skills: Django · HTML · CSS · JavaScript"""),
        ],
    },
    {
        "title": "Experience: add the missing positions",
        "where": "Experience → + → Add position",
        "note": "These come from your GitHub README. They show 6+ years of work instead of a few short jobs.",
        "blocks": [
            ("Tech Trainer & Assistant · Self-employed · 2021 – Present", """• Train university students in programming, mobile (Flutter) and backend (Django) development.
• Guide graduation projects from idea to working prototype, especially hardware + software projects.
• Provide research and publishing support for doctors and professors; co-authored papers in international journals.
Skills: Technical Training · Mentoring · Research"""),
            ("Server Administrator · Freelance · 2021 – 2023", """• Administered Ubuntu servers running Django applications behind Gunicorn with Redis caching.
• Handled deployments, security hardening, backups and monitoring.
Skills: Linux · Gunicorn · Redis · DevOps"""),
            ("Mobile Developer & Technical Support · 2022 – 2023", """• Built Flutter + Firebase apps with push notifications and real-time databases.
• Supported users and maintained apps after release.
Skills: Flutter · Firebase · Dart"""),
            ("Desktop Developer · 2019 – 2020", """• Developed desktop business applications in Visual Basic and C/C++.
Skills: C++ · Visual Basic"""),
        ],
    },
    {
        "title": "Education",
        "where": "Education → pencil icon on \"Computer Technical Collage\"",
        "note": "Two things to fix: \"Collage\" is misspelled (it should be College), and your README says 2018–2022 while LinkedIn says 2019–2022. Pick the correct years. Search for and select the university's official page so its logo appears.",
        "blocks": [
            ("School", "Northern Technical University"),
            ("Degree", "Bachelor's degree (B.Sc.)"),
            ("Field of study", "Computer Technical Engineering (Networks & Communication)"),
            ("Description", "Graduation-level work in networks, communication systems and embedded systems. Continued as a trainer for university students after graduating."),
            ("Add as a certification", "Hello Muscat Programming Bootcamp (2023)"),
        ],
    },
    {
        "title": "Skills (you have 7; add up to 50)",
        "where": "Skills → + Add skill. Then drag your 5 most important skills to the top.",
        "blocks": [
            ("Top 5 (pin these)", "Flutter\nDjango\nPython\nREST APIs\nFull-Stack Development"),
            ("Add all of these", "Dart\nFlask\nPostgreSQL\nSQLite\nRedis\nFirebase\nSupabase\nBLoC Pattern\nMobile Application Development\nBackend Development\nOpenCV\nTensorFlow\nComputer Vision\nArtificial Intelligence (AI)\nArduino\nESP32\nRaspberry Pi\nInternet of Things (IoT)\nMQTT\nEmbedded Systems\nPlaywright\nAutomation\nLinux\nUbuntu\nGunicorn\nDevOps\nGit\nGitHub\nJavaScript\nReact.js\nHTML\nCSS\nC++\nTechnical Training\nMentoring\nResearch\nScientific Writing"),
        ],
    },
    {
        "title": "Featured",
        "where": "Add profile section → Recommended → Add featured → Add a link",
        "note": "This is the first section visitors see after About. Put your best proof here.",
        "blocks": [
            ("Link 1: Portfolio", "https://make1it.pythonanywhere.com"),
            ("Link 2: GitHub", "https://github.com/Thanoon12k"),
            ("Link 3: The self-building portfolio tool", "https://github.com/Thanoon12k/My-Work"),
            ("Link 4", "Your first published post (after the autopost publishes it). Open the post → ··· → Feature on top of profile"),
        ],
    },
    {
        "title": "Projects",
        "where": "Add profile section → Recommended → Add projects. Link each project to your freelance position.",
        "blocks": [
            ("Moalidaty (مولدتي)", "Flutter + Django system that runs neighbourhood power generators: subscribers, amperes, payments, payroll and profit.\nhttps://github.com/Thanoon12k/moalidaty-front-end"),
            ("Pediatric Clinic (عيادتي)", "Flutter, BLoC and Supabase clinic app with admin, doctor and parent roles, vaccines, growth charts, live chat and Arabic PDF reports.\nhttps://github.com/Thanoon12k/Pediatric-Clinic-manager"),
            ("Smart Syringe Pump", "Flutter app controlling an Arduino-based medical syringe pump, with safety checks and a live 3D syringe.\nhttps://github.com/Thanoon12k/flutter-arduino-based-syringe-pump"),
            ("Showcase: self-building portfolio", "Clones all 65 of my repositories, runs each app, screenshots it on desktop and mobile, draws mock-ups for apps that can't run in a browser, then builds and deploys the portfolio. One command, zero manual steps.\nhttps://github.com/Thanoon12k/My-Work"),
            ("Bubble Sheet Scanner", "Offline OpenCV exam-sheet marker that exports results to Excel.\nhttps://github.com/Thanoon12k/BubbleSheetScanner"),
            ("Employee Manager", "Surveys, official letters and a director's dashboard for a government department.\nhttps://github.com/Thanoon12k/Employee-Manager"),
        ],
    },
    {
        "title": "Open to work + Services",
        "where": "Profile → Open to → Finding a new job (edit) / Providing services",
        "note": "You already have \"Open to work · recruiters only\". Add these job titles. Also add Services: it gives you a free services page that shows up in LinkedIn search.",
        "blocks": [
            ("Job titles", "Flutter Developer\nFull Stack Developer\nBackend Developer\nPython Developer\nMobile Application Developer"),
            ("Services", "Mobile Application Development\nWeb Development\nApplication Development\nCustom Software Development\nIT Consulting\nTraining"),
            ("Services description", "I build complete apps: Flutter mobile apps, Django backends, admin dashboards, and integrations with AI and hardware (Arduino, ESP32, attendance devices). From the idea to a deployed server, and I train your team to run it."),
        ],
    },
    {
        "title": "Arabic profile (second language)",
        "where": "Profile → Add profile in another language (right sidebar) → العربية. Recruiters in Iraq and the Gulf will see this version.",
        "note": "Your profile language is currently set to Arabic. Switch the primary profile to English (Public profile & URL → Profile language) and add this as the Arabic version.",
        "blocks": [
            ("العنوان", "مطوّر Full-Stack · Flutter و Django · أبني تطبيقات تتكامل مع الذكاء الاصطناعي والأجهزة | 65 مشروعاً منجزاً | مدرّب تقني جامعي"),
            ("نبذة", """أبني المشروع كاملاً: التطبيق الذي في يدك، والخادم الذي خلفه، والجهاز الذي يتحدث معه.

منذ أكثر من 6 سنوات أطوّر تطبيقات Flutter مع أنظمة خلفية بـ Django و Flask، وأربطها بالعالم الحقيقي: أجهزة Arduino و ESP32، أجهزة البصمة، الرؤية الحاسوبية بـ OpenCV ونماذج الذكاء الاصطناعي. أتولّى دورة المشروع كاملة من التحليل وتصميم قاعدة البيانات إلى الواجهة والنشر على الخادم.

🚀 من أعمالي
⚡ مولدتي: إدارة المولدات الأهلية: المشتركين والأمبيرات والجباية والرواتب والأرباح.
🩺 عيادتي: تطبيق عيادة أطفال بأدوار المدير والطبيب وولي الأمر، اللقاحات، منحنيات النمو، دردشة مباشرة وتقارير PDF عربية.
💉 مضخة المحاقن الذكية: تطبيق Flutter يتحكم بمضخة طبية مبنية على Arduino مع فحوصات أمان ومحقنة ثلاثية الأبعاد حيّة.
📝 مصحح الاستمارات: يصحح أوراق الامتحانات دون إنترنت بـ OpenCV ويصدّر النتائج إلى Excel.

⚙️ أؤتمت كل شيء: موقع أعمالي يبني نفسه بأمر واحد، وصفحتي على فيسبوك تنشر تلقائياً بوكيل ذكاء اصطناعي.

🎓 مدرّب لطلبة الجامعات ومشرف على مشاريع التخرج، ولي بحوث منشورة في مجلات دولية.

📍 الموصل، العراق، متاح للعمل عن بُعد أو حضورياً.
🌐 make1it.pythonanywhere.com
📩 engthanoon1@gmail.com · واتساب ‎+964 770 279 0915"""),
        ],
    },
    {
        "title": "Quick wins (5 minutes)",
        "where": "Various",
        "blocks": [
            ("Custom URL: Public profile & URL (right sidebar) → Edit your custom URL", "thanoon12k"),
            ("Contact info → Website (type: Portfolio)", "https://make1it.pythonanywhere.com"),
            ("Contact info → Website (type: Other)", "https://github.com/Thanoon12k"),
            ("Languages section", "Arabic: Native or bilingual\nEnglish: Full professional"),
            ("Verification badge", "Click \"Verify now\" at the top of your profile. LinkedIn says verified members get about 60% more profile views."),
            ("Photo", "Use a clear, well-lit headshot looking at the camera, with a plain background. Profiles with a photo get far more views."),
            ("Grow your network (57 → 500+)", "Send 10–20 connection requests a day to developers, tech recruiters and HR people in Iraq, the Gulf and remote-first companies. Follow Iraq Jobs Foundation. Comment on posts in your field for 10 minutes a day."),
        ],
    },
]
