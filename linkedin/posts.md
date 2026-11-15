# LinkedIn post queue

12 ready-to-publish posts, built only from facts in the repos and README.
Suggested pace: 2 per week (Tuesday and Thursday, around 9:00 Iraq time) → about 6 weeks of content.
Images are in `assets/`. Attach the listed image and add the link in the **first comment**
(LinkedIn shows posts with outside links in the body to fewer people).

When the LinkedIn app token is ready, these become `posts/*.md` files that a GitHub Action publishes on schedule.

---

## 01 · My portfolio builds itself
**Image:** `assets/pipeline.svg` (export as PNG) · **First comment:** https://github.com/Thanoon12k/My-Work

```
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
```

---

## 02 · Moalidaty: software for neighbourhood generators
**Image:** `assets/work/moalidaty-front-end.webp` · **First comment:** https://github.com/Thanoon12k/moalidaty-front-end

```
In Iraq, whole neighbourhoods run on private power generators. Most of them are still managed with a notebook and a pen.

So I built Moalidaty (مولدتي), a complete management system for generator owners:

⚡ Subscribers and how many amperes each one takes
💵 Monthly payments and who still owes
👷 Operator payroll
📊 Profit at a glance

Flutter app in front, Django REST backend behind it.

The best software projects I've done didn't start with a technology. They started with a real problem I saw on my own street.

#Flutter #Django #MobileDevelopment #Iraq #SoftwareForGood
```

---

## 03 · Pediatric Clinic app
**Image:** `assets/work/Pediatric-Clinic-manager.webp` · **First comment:** https://github.com/Thanoon12k/Pediatric-Clinic-manager

```
A pediatric clinic has three kinds of users, and each needs a different app.

In عيادتي (Pediatric Clinic), I built one Flutter app with three roles:

👨‍💼 Admin: manages doctors, schedules and the clinic
🩺 Doctor: patient records, vaccines, growth charts
👪 Parent/patient: follows their child's vaccines and growth, chats live with the clinic

Plus Arabic PDF reports, which were harder to get right than they sound (RTL text and Arabic fonts in PDF are a whole topic).

Stack: Flutter · BLoC · Supabase

What's the hardest role-based app you've built?

#Flutter #Supabase #BLoC #HealthTech #MobileApps
```

---

## 04 · Smart Syringe Pump (Flutter + Arduino)
**Image:** `assets/work/flutter-arduino-based-syringe-pump.webp` · **First comment:** https://github.com/Thanoon12k/flutter-arduino-based-syringe-pump

```
When software controls a medical device, a bug is no longer just a bad UX problem.

I built a Flutter app that controls an Arduino-based syringe pump:

💉 Set the dose and flow rate from the phone
🛑 Safety checks before any command reaches the motor
🧊 A live 3D syringe that shows exactly what the pump is doing

Connecting mobile apps to hardware is my favourite kind of work. The screen and the motor have to agree, every time.

#Flutter #Arduino #IoT #EmbeddedSystems #BiomedicalEngineering
```

---

## 05 · Bubble Sheet Scanner
**Image:** a screenshot from the repo or portfolio · **First comment:** https://github.com/Thanoon12k/BubbleSheetScanner

```
Teachers spend hours marking multiple-choice exam sheets by hand.

Bubble Sheet Scanner does it with a camera:
📷 Reads the answer sheet with OpenCV
✅ Marks it against the answer key
📊 Exports all results to Excel
📴 Works fully offline, no internet or cloud needed

Computer vision doesn't have to mean big models and GPUs. Sometimes it's classic image processing that saves someone a weekend.

#OpenCV #Python #ComputerVision #EdTech #Automation
```

---

## 06 · The Facebook page that runs itself
**Image:** `assets/work/golden-code-page.webp` · **First comment:** https://www.facebook.com/goldencode114

```
My Facebook page, Golden Code, runs itself.

🎨 Code designs every post card
🤖 An AI agent schedules and publishes through the Graph API
📈 A script tracks growth and archives every post

I write the ideas. The pipeline does the rest.

(And yes, this LinkedIn post is my next step in automating the same way 😄)

#AIAgents #Automation #Python #SocialMediaAutomation #GraphAPI
```

---

## 07 · Employee Manager for a government department
**Image:** `assets/work/Employee-Manager.webp` · **First comment:** https://github.com/Thanoon12k/Employee-Manager

```
Government departments still run on paper letters and signatures. Digitizing that is less about code and more about respecting how people already work.

Employee Manager gives a department:
📋 Staff surveys
✉️ Official letters, generated and tracked
📊 A director's dashboard to see everything at a glance

The lesson: the director's dashboard mattered more than any fancy feature. If the decision-maker can see value in 10 seconds, the system gets adopted.

#Django #GovTech #DigitalTransformation #WebDevelopment
```

---

## 08 · Teaching: what I learned training university students
**Image:** a photo from a training session (yours) · **First comment:** https://make1it.pythonanywhere.com

```
Since 2021 I've trained university students and guided their graduation projects.

3 things teaching taught me about engineering:

1️⃣ If you can't explain it simply, you don't understand it yet. Students find the gaps in your knowledge fast.
2️⃣ A working prototype beats a perfect plan. The best graduation projects shipped something small in week 2 and improved it from there.
3️⃣ Hardware + software is where students light up. The moment an app moves a real motor, everything clicks.

To everyone I've mentored: I'm proud of you. 🎓

#Teaching #Mentorship #GraduationProject #EngineeringEducation
```

---

## 09 · Mosul Tourism + Fikra (bilingual web apps)
**Image:** `assets/work/mosul1tourism.webp` + `assets/work/Ideas-Store.webp` · **First comment:** https://github.com/Thanoon12k/mosul1tourism

```
Two bilingual (Arabic + English) web apps, two frameworks:

🕌 Mosul Tourism: showcasing my city to visitors (Flask)
💡 Fikra (فكرة): an ideas store where people share and browse ideas (Django)

Building for Arabic and English at the same time teaches you things no tutorial covers: RTL layouts, mixed-direction text, fonts, and search that works in both languages.

Mosul deserves to be seen. ❤️

#Flask #Django #Bilingual #RTL #Mosul #WebDevelopment
```

---

## 10 · My stack and why
**Image:** a stack graphic (skillicons row from the README, screenshot) · **First comment:** https://github.com/Thanoon12k

```
People ask why I use Flutter + Django for almost everything.

📱 Flutter: one codebase for Android, iOS, web and desktop. For a solo developer, that multiplies what I can deliver.
🐍 Django: admin panel, auth, ORM and migrations included. I can build a real backend in days, not weeks.
🐘 PostgreSQL / SQLite / Supabase: picked for the project's scale.
🔌 Arduino / ESP32 / Raspberry Pi: when the app needs to touch the physical world.
👁️ OpenCV / TensorFlow: when it needs to see.

Choose tools that let you ship the whole product yourself. Then go deep.

What's your go-to stack?

#Flutter #Django #Python #FullStack #TechStack
```

---

## 11 · Journey post (career story)
**Image:** `assets/hero-light.png` · **First comment:** https://make1it.pythonanywhere.com

```
My path, in one post:

2018 → Started Computer Technical Engineering (Networks & Communication) at Northern Technical University
2019 → First paid work: desktop apps in Visual Basic and C/C++
2021 → Running Ubuntu servers (Gunicorn, Redis) and starting to train university students
2022 → Graduated, building Flutter + Firebase apps
2023 → Hello Muscat programming bootcamp
Now → Full-stack Flutter & Django developer, AI + IoT integrator, trainer and published researcher, with 65 projects on GitHub

Be patient. The best things are built step by step.

I'm open to remote or on-site work. If you need an app, a management system or device integration, my messages are open.

#CareerJourney #OpenToWork #Flutter #Django #Iraq
```

---

## 12 · Open to work / services (call to action)
**Image:** `assets/about-light.png` · **First comment:** WhatsApp link https://wa.me/9647702790915

```
I'm taking on new projects. Here's what I can build for you:

📱 Mobile apps (Android + iOS) with Flutter
🖥️ Management systems (clinics, shops, generators, HR, government departments)
🔌 Apps that control hardware: Arduino, ESP32, attendance devices (ZKTeco)
👁️ AI features: OpenCV scanning, recognition, automation
📚 Research and publishing support for doctors and professors

From the idea to a deployed server, I handle the whole thing.

📍 Mosul, Iraq · remote or on-site
🌐 make1it.pythonanywhere.com
📧 engthanoon1@gmail.com

A repost could help me reach the right person 🙏

#Freelance #OpenToWork #Flutter #Django #AppDevelopment
```
