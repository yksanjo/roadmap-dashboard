# Roadmap Health Dashboard

Live dashboard that syncs Jira/Linear/Asana + GitHub to show feature progress, blockers, and team velocity.

## Features

- Syncs with Jira, Linear, Asana, and GitHub
- Shows feature progress (%)
- Identifies blockers (e.g., "PR open > 3 days")
- Tracks team velocity vs. plan
- Real-time updates
- Beautiful Streamlit interface

## Installation

```bash
pip install -r requirements.txt
```

## Setup

1. Get API credentials for your project management tool:
   - **Jira**: API token from account settings
   - **Linear**: API key from settings
   - **Asana**: Personal access token
   - **GitHub**: Personal access token with `repo` scope

2. Create `.env` file:
```env
# GitHub
GITHUB_TOKEN=your_github_token
GITHUB_ORG=your_org  # Optional, for filtering repos

# Jira (optional)
JIRA_URL=https://your-domain.atlassian.net
JIRA_EMAIL=your_email
JIRA_API_TOKEN=your_jira_token

# Linear (optional)
LINEAR_API_KEY=your_linear_key

# Asana (optional)
ASANA_ACCESS_TOKEN=your_asana_token
```

## Usage

### Run Dashboard

```bash
streamlit run app.py
```

The dashboard will open in your browser at http://localhost:8501

### Configuration

Edit `config.yaml` to configure:
- Which project management tool to use
- Which repositories to track
- Blockers threshold (days)
- Velocity calculation method

## Features

### Feature Progress
- Shows completion percentage for each feature
- Tracks tasks vs. completed
- Visual progress bars

### Blockers
- PRs open > N days
- Issues without assignees
- Blocked tasks
- Dependencies

### Team Velocity
- Commits per day/week
- PRs merged per week
- Story points completed
- Velocity trend

## License

MIT
