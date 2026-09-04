name: Run news bot

on:
  schedule:
    - cron: '*/5 * * * *'
  workflow_dispatch:

jobs:
  build:
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.10'
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run script
        env:
          TELEGRAM_TOKEN: ${{ secrets.TELEGRAM_TOKEN }}
          CHANNEL_ID: ${{ secrets.CHANNEL_ID }}
        run: python news_bot.py
      - name: Commit sent links
        run: |
          git config --global user.name "github-actions[bot]"
          git config --global user.email "github-actions[bot]@users.noreply.github.com"
          git add sent_links.txt
          if git diff --cached --quiet; then
            echo "No changes to commit"
          else
            git commit -m "Update sent links"
            git pull --rebase
            git push
          fi
