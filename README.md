# Split Is Simple skill

Create and update shared-expense events from text or receipt images using an LLM client with image understanding and HTTP or shell tools. Returns an editable [Split Is Simple](https://splitissimple.com) link. No account or API key required.

## Install

Clone this repository and install the `skills/split-is-simple` directory using your client's skills mechanism. For Codex, copy that directory into `~/.codex/skills/split-is-simple`, then start a new session. Other clients can load `SKILL.md` and its referenced API documentation if they support skills and network tools. This is a skill, not a hosted MCP server or a standalone OCR service.

```sh
git clone https://github.com/onlinecco/split-is-simple-skill.git
mkdir -p ~/.codex/skills
cp -R split-is-simple-skill/skills/split-is-simple ~/.codex/skills/
```

Example requests:

> Create a beach trip for me, my spouse Sam, and Blair. Call me Alex. Sam and I share a household. I paid $90 USD for dinner, split equally among all three.

> Add this receipt to the event at [your private event link]. Sam paid, and everyone participated.

The skill defaults to Group mode, keeps every person as a distinct participant, explains conversation-based household assumptions, and asks about ambiguous totals, payers or splits. Receipt interpretation happens in your LLM client; the API receives only structured event data. USD and equal per-person splits are currently supported; household balances are then combined in Group mode.

Anyone with an event link can edit or delete the event. Keep links and creation retry keys private. Do not submit real receipts, participant names, or event links in public issues.

API contract: [skills/split-is-simple/references/api.md](skills/split-is-simple/references/api.md).
The Python helper needs Python 3 and no dependencies. Run `python3 -m unittest discover -s tests` to verify it.
