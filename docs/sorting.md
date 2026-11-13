# How it sorts things

Only facts GitHub already has, no AI:

- **Pull requests:** draft → checks failing → changes requested → approved → anything
  else needs review. The first rule that fits wins.
- **Issues:** an open PR closes it → someone is assigned → nobody is on it.
- **Graph:** only links GitHub or the plan records: "Closes #12" in a PR, sub-issues,
  "blocked by", a PR opened on another PR's branch, a plan item naming a PR or issue.
