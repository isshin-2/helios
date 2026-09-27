import requests
from typing import Tuple, Dict, Any, List
from pydantic import BaseModel, Field
from tools.base import BaseTool
import json

class GitHubIssuesSchema(BaseModel):
    github_token: str = Field(description="Your GitHub Personal Access Token (PAT)")
    repo: str = Field(description="The repository in format 'owner/repo' (e.g., 'microsoft/vscode')")
    state: str = Field(default="open", description="State of the issues to list: 'open', 'closed', or 'all'")

class GitHubListIssuesTool(BaseTool):
    @property
    def name(self) -> str:
        return "github_list_issues"

    @property
    def description(self) -> str:
        return "List issues from a GitHub repository."

    @property
    def input_schema(self) -> type[BaseModel]:
        return GitHubIssuesSchema
        
    @property
    def requires_permission(self) -> bool:
        return False

    async def execute(self, user_id: int, **kwargs) -> Tuple[str, str]:
        repo = kwargs.get("repo")
        state = kwargs.get("state", "open")
        headers = {
            "Authorization": f"token {kwargs.get('github_token')}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        url = f"https://api.github.com/repos/{repo}/issues?state={state}"
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code == 200:
                issues = resp.json()
                results = [{"number": i["number"], "title": i["title"], "state": i["state"]} for i in issues if "pull_request" not in i]
                return (json.dumps(results[:10], indent=2), self.name)
            else:
                return (f"GitHub API Error {resp.status_code}: {resp.text}", self.name)
        except Exception as e:
            return (f"Failed to fetch issues: {str(e)}", self.name)

class GitHubCreateIssueSchema(BaseModel):
    github_token: str = Field(description="Your GitHub Personal Access Token (PAT)")
    repo: str = Field(description="The repository in format 'owner/repo'")
    title: str = Field(description="The title of the issue")
    body: str = Field(description="The body text of the issue")

class GitHubCreateIssueTool(BaseTool):
    @property
    def name(self) -> str:
        return "github_create_issue"

    @property
    def description(self) -> str:
        return "Create a new issue in a GitHub repository."

    @property
    def input_schema(self) -> type[BaseModel]:
        return GitHubCreateIssueSchema
        
    @property
    def requires_permission(self) -> bool:
        return True # Creating issues requires permission

    async def execute(self, user_id: int, **kwargs) -> Tuple[str, str]:
        repo = kwargs.get("repo")
        headers = {
            "Authorization": f"token {kwargs.get('github_token')}",
            "Accept": "application/vnd.github.v3+json"
        }
        payload = {
            "title": kwargs.get("title"),
            "body": kwargs.get("body")
        }
        
        url = f"https://api.github.com/repos/{repo}/issues"
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=10)
            if resp.status_code == 201:
                data = resp.json()
                return (f"Successfully created issue #{data['number']}: {data['html_url']}", self.name)
            else:
                return (f"GitHub API Error {resp.status_code}: {resp.text}", self.name)
        except Exception as e:
            return (f"Failed to create issue: {str(e)}", self.name)
