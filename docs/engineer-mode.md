# Engineer mode: one repo dashboard

Add repo-radar to the repo itself. From its top folder:

```bash
python <path to>/skills/repo-radar/scripts/dashboard.py init
```

This adds the scripts to `.github/dashboard/` and an Action to
`.github/workflows/dashboard.yml`. Add `--with-plan` for a starter plan, or
`--plan path/to/plan.yaml` to use one you have. Commit them, and the page rebuilds
every day at 11:00 UTC (change it with `--cron`). To open today's page:

```bash
git fetch origin dashboard && git show origin/dashboard:index.html > dashboard.html
```

For a public repo, you can turn on GitHub Pages for the `dashboard` branch instead and
get a web address.
