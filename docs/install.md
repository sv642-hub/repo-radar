# Install

You need Python 3.10 or newer, PyYAML (`pip install pyyaml`), and the
[GitHub CLI](https://cli.github.com/) (`gh`), signed in.

**With Claude Code**, install the plugin:

```
/plugin install repo-radar --marketplace sv642-hub/repo-radar
```

Then ask Claude to "set up repo-radar". It asks which mode you want ([Engineer](engineer-mode.md) or [Manager](manager-mode.md)),
builds the pages once so you can see them, and adds the daily rebuild.

**With Codex**, copy the skill folder to where Codex looks for skills. For one repo,
put it in that repo:

```bash
git clone https://github.com/sv642-hub/repo-radar.git /tmp/repo-radar
mkdir -p .agents/skills && cp -R /tmp/repo-radar/skills/repo-radar .agents/skills/
```

Or, to have it in every repo, copy it to `~/.agents/skills/` instead. Restart Codex,
then ask it to "set up repo-radar". (Codex reads skills from `.agents/skills`; older
guides say `.codex/skills`.)

**Without an AI assistant**, run the script inside any repo, or name one:

```bash
python skills/repo-radar/scripts/dashboard.py build --out dashboard.html
python skills/repo-radar/scripts/dashboard.py build --repo owner/name --out dashboard.html
```

Either way, the daily rebuild is a GitHub Action with no AI in it, so it needs no API
key. The pages live on a branch called `dashboard`, replaced each day.
