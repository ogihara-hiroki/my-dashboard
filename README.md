# 🚀 Work Analysis Pro

A premium Streamlit dashboard for analyzing productivity by correlating PC activity logs with Toggl Track time entries.

## ✨ Features

- **Real-time PC Activity Analysis**: Categorizes window titles into logical work areas (IDE, Design, Browser, etc.).
- **Toggl Integration**: Fetches summary time entries directly from Toggl Track API v3.
- **Efficiency Gap Analysis**: Automatically calculates the difference between "Active PC Time" and "Manual Tracks".
- **Remote Control**: Toggle your PC logger's recording state remotely via GitHub.
- **Premium UI**: Modern glassmorphism design with responsive charts.

## 🛠️ Setup

### 1. Prerequisites
- Python 3.8+
- GitHub Personal Access Token (with `repo` scope)
- Toggl Track API Token

### 2. Installation
```bash
pip install -r requirements.txt
```

### 3. Configuration (Secrets)
Create a `.streamlit/secrets.toml` file or set these in your Streamlit Cloud environment:

```toml
MY_GITHUB_TOKEN = "your_github_token"
REPO_NAME = "your_username/repo_name"
TOGGL_TOKEN = "your_toggl_token"
TOGGL_WORKSPACE_ID = "your_workspace_id"
```

## 📊 Analytics Logic
- **PC Logs**: Assumes a sampling interval (default: 10s) to calculate total hours per application category.
- **Categories**: Automatically groups keywords like 'vscode', 'excel', and 'slack' into high-level buckets.

---
*Created for maximum productivity and clarity.*
