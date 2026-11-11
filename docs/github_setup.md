# Publish to GitHub

After reviewing the code and running the local demo, create a repository from
the extracted project folder.

```bash
cd ~/aicontrolhub
python -m pytest -q
ruff check .
git init -b main
git add .
git commit -m "feat: initialize AIControlHub governance workflow"
gh repo create aicontrolhub --public --source=. --remote=origin --push
```

Verify GitHub Actions across Python 3.11, 3.12 and 3.13. Keep SQLite data,
authentication keys, internal reviews, private compliance evidence and any
customer or employee records outside the repository.
