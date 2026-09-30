---
title: Claims Assistant
emoji: 🛡️
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 8000
pinned: false
short_description: SOP harness for an insurance claims support chat agent
---

# Claims Assistant: live demo

A chat agent for insurance claims support that follows a four-phase standard operating procedure:

1. `VERIFY_ID`
2. `RESOLVE_INTENT`
3. `PROCESS_CASE`
4. `POST_PROCESS`

The verification, disclosure and consent rules are enforced in code, not by the language model.

Source, setup docs and design notes: https://github.com/HarshithKoriRaj/insurance-claims-sop-harness

Click the **Demo: Margaret Chen** suggestion above the message box to load the test message.

This Space runs the image that GitHub Actions publishes from `main` (see `Dockerfile`). It has no mail server, so an approved email summary is recorded and shown in the chat but not delivered to an inbox. Human handoff is simulated.
