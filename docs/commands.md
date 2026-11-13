# Commands

| Command | What it does |
|---|---|
| `dashboard.py build --out page.html` | Ask GitHub, then draw the page |
| `dashboard.py me` | One person's plan items, checked against their PRs |
| `dashboard.py init` | Add the scripts and the daily Action to a repo |
| `dashboard.py watch --out folder/` | A page per repo in `watchlist.yaml`, plus an overview |
| `dashboard.py init --watch` | Make a repo of yours watch other repos every day |
| `dashboard.py update` | Bring a repo's copy of the scripts up to date; leaves your watch list, plan, and Action alone |
| `dashboard.py fetch --out data.json` | Save what GitHub said, to draw later with `build --data` |

Each takes `--help`. To run the tests: `uv run pytest`.
