---
name: recent-work
description: Summarize the last 10 things done in this project by reading the most recent changelog entries. Use when the user asks "what was recently done", "what did we do lately", "show recent work", "what have we been working on", "recent activity", "catch me up", or any similar request for a summary of recent project activity.
---

# Recent Work

## Workflow

1. **List changelog files** sorted by date (descending):
   ```bash
   ls /Users/ggpropersi/code/urls4irl/changelog/ | sort -r
   ```

2. **Read entries from the most recent file(s)** — changelog files are named `MM-DD-YYYY-changelog.md` and entries follow this format:
   ```
   - [HH:MM] <action>: <summary>
   ```
   Start from the end of the most recent file. If fewer than 10 entries exist there, continue to the next most recent file until 10 total entries are collected.

3. **Display the 10 most recent entries** in reverse chronological order (newest first), grouped by date:

```
## Recent Work

### MM/DD/YYYY
- [HH:MM] action: summary
- [HH:MM] action: summary

### MM/DD/YYYY
- [HH:MM] action: summary
...
```

Keep the output concise — one line per entry, grouped by date heading. No extra commentary unless the user asks follow-up questions.
