---
name: cap
description: Check remaining Claude Code session capacity percentage and time left in the current 5-hour window. Use when the user asks how much capacity is left, what percentage remains, how much time is left, or wants to check their session usage via the cc-cap or cc-time aliases.
---

Run both `cc-cap` and `cc-time` shell aliases in parallel to report session capacity. Since they are shell aliases, invoke via an interactive shell:

```bash
zsh -i -c 'cc-cap'
zsh -i -c 'cc-time'
```

Report both outputs to the user:
- `cc-cap` → percentage of tokens remaining in the 5-hour window
- `cc-time` → minutes remaining in the 5-hour window
