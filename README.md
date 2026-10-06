# The mentor skill

Claude writes the code. You make the calls.
One Claude Code plugin that makes you learn while you build. Free, MIT, no signup, no API key.

Made by **Alex Chen** ([@nocodealex](https://instagram.com/nocodealex)), an AI creator who builds free Claude Code skills.

Ask Claude to build an app and it makes every decision for you: the features, the database, the
structure. You click yes on whatever it recommends, it writes thousands of lines, and you learn nothing.
`/mentor` flips that. Before each feature you answer three questions in your own words:

1. **Scope:** when someone opens this, what should they be able to do?
2. **Behavior:** what happens in the edge cases, like coming back tomorrow on another device, or
   deleting a folder that still has notes in it?
3. **Design:** where should the data live, and what talks to what?

No multiple choice, no "(recommended)" option to click. If you don't know, Claude asks a smaller
question until you get there.

**It actually forces it.** A hook blocks Claude's Write and Edit tools until all three answers are in.
Then Claude writes code that follows your decisions and tells you which decision each change came
from. When the feature works, you explain it back in your own words, and everything you decided and
learned goes into `.mentor/RECAP.md`.

**It never touches anything outside your project.** Its notes live in `.mentor/` in the folder you run it in.

## Install

Paste this into Claude:

```
https://github.com/alexyc9381/mentor-skill
Install this plugin, then confirm /mentor works.
```

Or as a plugin, in Claude Code:

```
/plugin marketplace add alexyc9381/mentor-skill
/plugin install mentor-skill@mentor-skill
```

Restart Claude Code (or run `/reload-plugins`). Installed as a plugin, it shows up as `/mentor-skill:mentor`.
The plugin install is the one that includes the hook that locks code until you've answered. Copying
only `skills/mentor` into `~/.claude/skills/` gives you the questions without the lock.

## Use

```
/mentor a Notion clone
```

| command | what it does |
| --- | --- |
| `/mentor <what you want to build>` | starts a session and asks the first question |
| `/mentor status` | what's answered, and whether code is locked |
| `/mentor recap` | writes `.mentor/RECAP.md`: every call you made and what you learned |
| `/mentor stop` | turns the lock off; Claude can write freely again |

Python 3 is the only requirement. Run the tests with:

```bash
python3 -m unittest discover -s tests
```

## Making a video or post about this?

Go ahead. Credit it like this, in your caption or description:

```text
/mentor plugin by Alex Chen (@nocodealex): github.com/alexyc9381/mentor-skill
```

Tag [@nocodealex](https://instagram.com/nocodealex) so I can see it. Every recap the plugin writes
already ends with the same credit, so leave it in the shot.

Writing about it or citing it in a paper? Use **Cite this repository** in the sidebar on GitHub.

## Thanks

The idea of a plugin that keeps you in the loop comes from Noah Kim's
[VibeWise](https://github.com/nykooi1/vibe-wise) (MIT). `/mentor` is a separate build with its own
take: a hard lock on code until you've answered, and an explain-back at the end of every feature.

## Uninstall

```
/plugin uninstall mentor-skill@mentor-skill
```

Not made by Anthropic.
