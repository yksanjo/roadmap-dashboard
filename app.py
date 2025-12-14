#!/usr/bin/env python3
"""
Roadmap Health Dashboard

Live dashboard showing feature progress, blockers, and team velocity.
"""

import os
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import yaml

try:
    from github import Github
    GITHUB_AVAILABLE = True
except ImportError:
    GITHUB_AVAILABLE = False

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


# Page config
st.set_page_config(
    page_title="Roadmap Health Dashboard",
    page_icon="📊",
    layout="wide"
)

# Load config
def load_config():
    """Load configuration from config.yaml or use defaults."""
    default_config = {
        "github": {
            "org": os.getenv("GITHUB_ORG", ""),
            "repos": []
        },
        "jira": {
            "enabled": False,
            "url": os.getenv("JIRA_URL", ""),
            "project_key": ""
        },
        "linear": {
            "enabled": False,
            "team_id": ""
        },
        "asana": {
            "enabled": False,
            "workspace_id": ""
        },
        "blockers": {
            "pr_threshold_days": 3,
            "issue_threshold_days": 7
        }
    }
    
    if os.path.exists("config.yaml"):
        with open("config.yaml", "r") as f:
            user_config = yaml.safe_load(f) or {}
            default_config.update(user_config)
    
    return default_config


def get_github_data(github_token: str, org: Optional[str] = None, repos: Optional[List[str]] = None) -> Dict:
    """Fetch data from GitHub."""
    if not GITHUB_AVAILABLE:
        return {"error": "PyGithub not installed"}
    
    g = Github(github_token)
    
    data = {
        "prs": [],
        "issues": [],
        "commits": [],
        "repos": []
    }
    
    try:
        # Get repositories
        if org:
            repos_list = g.get_organization(org).get_repos()
        elif repos:
            repos_list = [g.get_repo(repo) for repo in repos]
        else:
            repos_list = list(g.get_user().get_repos())[:10]  # Limit to 10
        
        for repo in repos_list:
            repo_name = repo.full_name
            
            # Get open PRs
            for pr in repo.get_pulls(state="open"):
                days_open = (datetime.now() - pr.created_at.replace(tzinfo=None)).days
                data["prs"].append({
                    "repo": repo_name,
                    "number": pr.number,
                    "title": pr.title,
                    "author": pr.user.login,
                    "created_at": pr.created_at.isoformat(),
                    "days_open": days_open,
                    "url": pr.html_url
                })
            
            # Get open issues
            for issue in repo.get_issues(state="open"):
                if issue.pull_request:  # Skip PRs
                    continue
                days_open = (datetime.now() - issue.created_at.replace(tzinfo=None)).days
                data["issues"].append({
                    "repo": repo_name,
                    "number": issue.number,
                    "title": issue.title,
                    "author": issue.user.login,
                    "assignee": issue.assignee.login if issue.assignee else "Unassigned",
                    "created_at": issue.created_at.isoformat(),
                    "days_open": days_open,
                    "labels": [label.name for label in issue.labels],
                    "url": issue.html_url
                })
            
            # Get recent commits (last 30 days)
            try:
                commits = repo.get_commits(since=datetime.now() - timedelta(days=30))
                for commit in commits:
                    data["commits"].append({
                        "repo": repo_name,
                        "sha": commit.sha[:7],
                        "author": commit.commit.author.name,
                        "date": commit.commit.author.date.isoformat(),
                        "message": commit.commit.message.split("\n")[0]
                    })
            except:
                pass
            
            data["repos"].append({
                "name": repo_name,
                "stars": repo.stargazers_count,
                "forks": repo.forks_count,
                "open_issues": repo.open_issues_count
            })
    
    except Exception as e:
        return {"error": str(e)}
    
    return data


def get_jira_data(jira_url: str, email: str, api_token: str, project_key: str) -> Dict:
    """Fetch data from Jira."""
    if not REQUESTS_AVAILABLE:
        return {"error": "requests not installed"}
    
    auth = (email, api_token)
    base_url = f"{jira_url}/rest/api/3"
    
    data = {
        "issues": [],
        "sprints": []
    }
    
    try:
        # Get issues from project
        url = f"{base_url}/search"
        params = {
            "jql": f"project = {project_key}",
            "maxResults": 100
        }
        response = requests.get(url, auth=auth, params=params, timeout=30)
        response.raise_for_status()
        
        issues_data = response.json()
        for issue in issues_data.get("issues", []):
            fields = issue.get("fields", {})
            data["issues"].append({
                "key": issue.get("key"),
                "summary": fields.get("summary", ""),
                "status": fields.get("status", {}).get("name", ""),
                "assignee": fields.get("assignee", {}).get("displayName", "Unassigned"),
                "created": fields.get("created", ""),
                "priority": fields.get("priority", {}).get("name", ""),
                "story_points": fields.get("customfield_10016")  # Common story points field
            })
    except Exception as e:
        return {"error": str(e)}
    
    return data


def calculate_feature_progress(issues: List[Dict]) -> Dict:
    """Calculate feature progress from issues."""
    if not issues:
        return {"total": 0, "completed": 0, "percentage": 0}
    
    total = len(issues)
    completed = sum(1 for issue in issues if issue.get("status", "").lower() in ["done", "closed", "completed"])
    percentage = (completed / total * 100) if total > 0 else 0
    
    return {
        "total": total,
        "completed": completed,
        "in_progress": sum(1 for issue in issues if "progress" in issue.get("status", "").lower()),
        "percentage": percentage
    }


def identify_blockers(prs: List[Dict], issues: List[Dict], pr_threshold: int = 3, issue_threshold: int = 7) -> List[Dict]:
    """Identify blockers from PRs and issues."""
    blockers = []
    
    # PRs open too long
    for pr in prs:
        if pr["days_open"] > pr_threshold:
            blockers.append({
                "type": "PR",
                "severity": "high" if pr["days_open"] > 7 else "medium",
                "title": pr["title"],
                "repo": pr["repo"],
                "days": pr["days_open"],
                "url": pr["url"],
                "description": f"PR #{pr['number']} open for {pr['days_open']} days"
            })
    
    # Issues without assignees
    for issue in issues:
        if issue.get("assignee") == "Unassigned" and issue["days_open"] > issue_threshold:
            blockers.append({
                "type": "Issue",
                "severity": "medium",
                "title": issue["title"],
                "repo": issue["repo"],
                "days": issue["days_open"],
                "url": issue["url"],
                "description": f"Issue #{issue['number']} unassigned for {issue['days_open']} days"
            })
    
    return sorted(blockers, key=lambda x: x["days"], reverse=True)


def calculate_velocity(commits: List[Dict], prs: List[Dict], days: int = 7) -> Dict:
    """Calculate team velocity."""
    cutoff_date = datetime.now() - timedelta(days=days)
    
    recent_commits = [
        c for c in commits
        if datetime.fromisoformat(c["date"].replace("Z", "+00:00")).replace(tzinfo=None) > cutoff_date
    ]
    
    # Count commits per day
    commits_by_day = {}
    for commit in recent_commits:
        date = datetime.fromisoformat(commit["date"].replace("Z", "+00:00")).date()
        commits_by_day[date] = commits_by_day.get(date, 0) + 1
    
    return {
        "commits_last_7d": len(recent_commits),
        "commits_per_day": len(recent_commits) / days if days > 0 else 0,
        "commits_by_day": commits_by_day,
        "total_commits": len(commits)
    }


# Main app
def main():
    st.title("📊 Roadmap Health Dashboard")
    
    config = load_config()
    
    # Sidebar configuration
    with st.sidebar:
        st.header("Configuration")
        
        github_token = st.text_input(
            "GitHub Token",
            value=os.getenv("GITHUB_TOKEN", ""),
            type="password"
        )
        
        github_org = st.text_input(
            "GitHub Organization (optional)",
            value=config.get("github", {}).get("org", "")
        )
        
        repos_input = st.text_area(
            "Repositories (one per line, format: owner/repo)",
            value="\n".join(config.get("github", {}).get("repos", []))
        )
        
        pr_threshold = st.number_input(
            "PR Blocker Threshold (days)",
            min_value=1,
            value=config.get("blockers", {}).get("pr_threshold_days", 3)
        )
        
        if st.button("Refresh Data"):
            st.rerun()
    
    if not github_token:
        st.warning("⚠️ Please enter a GitHub token in the sidebar to load data.")
        return
    
    # Parse repos
    repos = [r.strip() for r in repos_input.split("\n") if r.strip()] if repos_input else None
    
    # Load data
    with st.spinner("Loading data from GitHub..."):
        github_data = get_github_data(github_token, github_org, repos)
    
    if "error" in github_data:
        st.error(f"Error loading data: {github_data['error']}")
        return
    
    # Calculate metrics
    blockers = identify_blockers(
        github_data["prs"],
        github_data["issues"],
        pr_threshold=pr_threshold
    )
    
    velocity = calculate_velocity(github_data["commits"], github_data["prs"])
    
    # Feature progress (simplified - using issues as features)
    feature_progress = calculate_feature_progress(github_data["issues"])
    
    # Display metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Open PRs", len(github_data["prs"]))
    
    with col2:
        st.metric("Open Issues", len(github_data["issues"]))
    
    with col3:
        st.metric("Blockers", len(blockers))
    
    with col4:
        st.metric("Commits (7d)", velocity["commits_last_7d"])
    
    # Feature Progress
    st.header("Feature Progress")
    col1, col2 = st.columns([2, 1])
    
    with col1:
        if feature_progress["total"] > 0:
            fig = go.Figure(go.Indicator(
                mode="gauge+number",
                value=feature_progress["percentage"],
                domain={'x': [0, 1], 'y': [0, 1]},
                title={'text': "Completion %"},
                gauge={
                    'axis': {'range': [None, 100]},
                    'bar': {'color': "darkblue"},
                    'steps': [
                        {'range': [0, 50], 'color': "lightgray"},
                        {'range': [50, 80], 'color': "gray"}
                    ],
                    'threshold': {
                        'line': {'color': "red", 'width': 4},
                        'thickness': 0.75,
                        'value': 90
                    }
                }
            ))
            fig.update_layout(height=300)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No issues found to calculate progress")
    
    with col2:
        st.metric("Total Features", feature_progress["total"])
        st.metric("Completed", feature_progress["completed"])
        st.metric("In Progress", feature_progress.get("in_progress", 0))
    
    # Blockers
    st.header("🚨 Blockers")
    
    if blockers:
        blockers_df = pd.DataFrame(blockers)
        
        # Group by severity
        severity_counts = blockers_df["severity"].value_counts()
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("High", severity_counts.get("high", 0))
        with col2:
            st.metric("Medium", severity_counts.get("medium", 0))
        with col3:
            st.metric("Low", severity_counts.get("low", 0))
        
        # Display blockers table
        for blocker in blockers[:10]:  # Show top 10
            with st.expander(f"{blocker['type']}: {blocker['title'][:60]}... ({blocker['days']} days)"):
                st.write(f"**Repository:** {blocker['repo']}")
                st.write(f"**Description:** {blocker['description']}")
                st.write(f"**Severity:** {blocker['severity']}")
                st.markdown(f"[View →]({blocker['url']})")
    else:
        st.success("✅ No blockers found!")
    
    # Team Velocity
    st.header("Team Velocity")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if velocity["commits_by_day"]:
            dates = sorted(velocity["commits_by_day"].keys())
            counts = [velocity["commits_by_day"][d] for d in dates]
            
            fig = px.bar(
                x=[str(d) for d in dates],
                y=counts,
                labels={"x": "Date", "y": "Commits"},
                title="Commits per Day (Last 7 Days)"
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No commit data available")
    
    with col2:
        st.metric("Commits per Day", f"{velocity['commits_per_day']:.1f}")
        st.metric("Total Commits (30d)", velocity["total_commits"])
    
    # PRs and Issues tables
    col1, col2 = st.columns(2)
    
    with col1:
        st.header("Recent PRs")
        if github_data["prs"]:
            prs_df = pd.DataFrame(github_data["prs"])
            prs_df = prs_df[["repo", "title", "author", "days_open"]].head(10)
            st.dataframe(prs_df, use_container_width=True)
        else:
            st.info("No open PRs")
    
    with col2:
        st.header("Recent Issues")
        if github_data["issues"]:
            issues_df = pd.DataFrame(github_data["issues"])
            issues_df = issues_df[["repo", "title", "assignee", "days_open"]].head(10)
            st.dataframe(issues_df, use_container_width=True)
        else:
            st.info("No open issues")


if __name__ == "__main__":
    main()
