"""
ShellMentor - github_sync.py
GitHub integration: authentication, portfolio publishing, progress sync.
Uses Personal Access Tokens or OAuth Device Flow — never stores passwords.
"""

from __future__ import annotations

import json
import logging
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from data_manager import DataManager

logger = logging.getLogger("shellmentor")

GITHUB_API   = "https://api.github.com"
GITHUB_RAW   = "https://raw.githubusercontent.com"
OAUTH_CLIENT = "Iv23liShellMentor01"   # placeholder — replace with real OAuth app ID

REPO_STRUCTURE = {
    "README.md":               "Main portfolio overview",
    "reports/skills.md":       "Skill mastery report",
    "reports/challenges.md":   "Challenge completion report",
    "achievements/earned.md":  "All earned achievements",
    "progress/history.json":   "Raw progress data",
    "notes/":                  "Exported notes directory",
}


@dataclass
class GitHubUser:
    login:      str
    name:       str
    avatar_url: str
    public_repos: int
    html_url:   str


@dataclass
class SyncResult:
    success:   bool
    message:   str
    files_pushed: list[str]
    repo_url:  str = ""
    error:     str = ""


class GitHubSync:
    """Handles GitHub authentication and portfolio publishing."""

    def __init__(self, db: DataManager):
        self.db = db
        self._token: str = ""
        self._user:  GitHubUser | None = None
        self._on_status_callbacks: list[Callable] = []
        self._load_token()

    # ── Token Management ──────────────────────────────────────

    def _load_token(self) -> None:
        user = self.db.get_user()
        self._token = user.get("github_token", "") or ""

    def _save_token(self, token: str, username: str) -> None:
        self.db.update_user(github_token=token, github_user=username)
        self._token = token

    @property
    def is_authenticated(self) -> bool:
        return bool(self._token)

    @property
    def github_username(self) -> str:
        user = self.db.get_user()
        return user.get("github_user", "") or ""

    # ── Callbacks ─────────────────────────────────────────────

    def on_status(self, callback: Callable) -> None:
        self._on_status_callbacks.append(callback)

    def _status(self, message: str) -> None:
        logger.info(f"[GitHub] {message}")
        for cb in self._on_status_callbacks:
            try:
                cb(message)
            except Exception:
                pass

    # ── API Helpers ───────────────────────────────────────────

    def _api_request(self, method: str, endpoint: str,
                     data: dict | None = None,
                     token: str | None = None) -> dict:
        """Make a GitHub API request. Returns response dict."""
        url = f"{GITHUB_API}{endpoint}"
        tok = token or self._token
        headers = {
            "Accept":        "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent":    "ShellMentor/1.0",
        }
        if tok:
            headers["Authorization"] = f"Bearer {tok}"

        body = json.dumps(data).encode() if data else None
        req = urllib.request.Request(url, data=body, headers=headers, method=method)

        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            error_body = e.read().decode()
            try:
                error_data = json.loads(error_body)
            except Exception:
                error_data = {"message": error_body}
            raise RuntimeError(f"GitHub API {e.code}: {error_data.get('message', error_body)}")
        except urllib.error.URLError as e:
            raise RuntimeError(f"Network error: {e.reason}")

    def _api_get(self, endpoint: str, **kwargs) -> dict:
        return self._api_request("GET", endpoint, **kwargs)

    def _api_post(self, endpoint: str, data: dict, **kwargs) -> dict:
        return self._api_request("POST", endpoint, data=data, **kwargs)

    def _api_put(self, endpoint: str, data: dict, **kwargs) -> dict:
        return self._api_request("PUT", endpoint, data=data, **kwargs)

    # ── Authentication Methods ────────────────────────────────

    def authenticate_pat(self, token: str) -> tuple[bool, str]:
        """Authenticate using a Personal Access Token."""
        try:
            self._status("Verifying Personal Access Token...")
            user_data = self._api_get("/user", token=token)
            username = user_data.get("login", "")
            if not username:
                return False, "Invalid token — no user found"

            self._save_token(token, username)
            self._user = GitHubUser(
                login=username,
                name=user_data.get("name", username),
                avatar_url=user_data.get("avatar_url", ""),
                public_repos=user_data.get("public_repos", 0),
                html_url=user_data.get("html_url", ""),
            )
            self._status(f"✓ Authenticated as @{username}")
            return True, f"Authenticated as @{username}"

        except RuntimeError as e:
            return False, str(e)

    def start_device_flow(self) -> dict:
        """
        Start GitHub OAuth Device Flow.
        Returns device_code info for the user to enter at github.com/login/device.
        """
        try:
            url = "https://github.com/login/device/code"
            headers = {
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "ShellMentor/1.0",
            }
            body = f"client_id={OAUTH_CLIENT}&scope=repo".encode()
            req = urllib.request.Request(url, data=body, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode())

            self._status(f"Device flow started. Code: {data.get('user_code', '')}")
            return data
        except Exception as e:
            return {"error": str(e)}

    def poll_device_flow(self, device_code: str, interval: int = 5,
                          timeout: int = 300) -> tuple[bool, str]:
        """
        Poll for device flow completion.
        Returns (success, message).
        """
        url = "https://github.com/login/oauth/access_token"
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "ShellMentor/1.0",
        }
        deadline = time.time() + timeout

        while time.time() < deadline:
            time.sleep(interval)
            body = (
                f"client_id={OAUTH_CLIENT}"
                f"&device_code={device_code}"
                f"&grant_type=urn:ietf:params:oauth:grant-type:device_code"
            ).encode()
            try:
                req = urllib.request.Request(url, data=body, headers=headers, method="POST")
                with urllib.request.urlopen(req, timeout=15) as resp:
                    data = json.loads(resp.read().decode())

                if "access_token" in data:
                    token = data["access_token"]
                    ok, msg = self.authenticate_pat(token)
                    return ok, msg
                elif data.get("error") == "authorization_pending":
                    self._status("Waiting for authorization...")
                    continue
                elif data.get("error") == "slow_down":
                    interval += 5
                    continue
                else:
                    return False, data.get("error_description", "Authorization failed")
            except Exception as e:
                return False, str(e)

        return False, "Device flow timed out"

    def disconnect(self) -> None:
        """Remove stored GitHub credentials."""
        self.db.update_user(github_token="", github_user="")
        self._token = ""
        self._user = None
        self._status("Disconnected from GitHub")

    # ── Repository Management ─────────────────────────────────

    def ensure_repo(self, repo_name: str = "shellmentor-portfolio") -> tuple[bool, str]:
        """Create repo if it doesn't exist. Returns (success, repo_full_name)."""
        if not self.is_authenticated:
            return False, "Not authenticated"

        username = self.github_username
        try:
            # Check if repo exists
            self._api_get(f"/repos/{username}/{repo_name}")
            self._status(f"Repository {repo_name} already exists")
            return True, f"{username}/{repo_name}"
        except RuntimeError:
            pass  # Repo doesn't exist, create it

        try:
            self._status(f"Creating repository {repo_name}...")
            self._api_post("/user/repos", {
                "name":        repo_name,
                "description": "ShellMentor Learning Portfolio — Linux Command-Line Mastery",
                "private":     False,
                "auto_init":   True,
            })
            self._status(f"✓ Repository created: {username}/{repo_name}")
            return True, f"{username}/{repo_name}"
        except RuntimeError as e:
            return False, str(e)

    def push_file(self, repo_full: str, path: str,
                  content: str, message: str) -> bool:
        """Push a single file to GitHub repository."""
        import base64
        username, repo_name = repo_full.split("/", 1)

        # Get existing file SHA (for updates)
        sha = None
        try:
            existing = self._api_get(f"/repos/{repo_full}/contents/{path}")
            sha = existing.get("sha")
        except RuntimeError:
            pass  # New file

        data: dict = {
            "message": message,
            "content": base64.b64encode(content.encode()).decode(),
        }
        if sha:
            data["sha"] = sha

        try:
            self._api_put(f"/repos/{repo_full}/contents/{path}", data)
            return True
        except RuntimeError as e:
            logger.error(f"Failed to push {path}: {e}")
            return False

    # ── Full Portfolio Push ───────────────────────────────────

    def publish_portfolio(self, portfolio_content: str,
                          extra_files: dict[str, str] | None = None) -> SyncResult:
        """
        Push the full portfolio to GitHub.
        extra_files: {path: content} dict for additional files.
        """
        if not self.is_authenticated:
            return SyncResult(False, "Not authenticated with GitHub", [], error="No token")

        ok, repo_full = self.ensure_repo()
        if not ok:
            return SyncResult(False, f"Could not access repository: {repo_full}",
                              [], error=repo_full)

        username = self.github_username
        pushed_files: list[str] = []

        # Push main README
        self._status("Uploading portfolio README...")
        if self.push_file(repo_full, "README.md", portfolio_content,
                          "Update ShellMentor portfolio"):
            pushed_files.append("README.md")

        # Push extra files
        if extra_files:
            for path, content in extra_files.items():
                self._status(f"Uploading {path}...")
                if self.push_file(repo_full, path, content,
                                  f"Update {path}"):
                    pushed_files.append(path)

        repo_url = f"https://github.com/{repo_full}"
        self._status(f"✓ Portfolio published at {repo_url}")

        return SyncResult(
            success=True,
            message=f"Portfolio published to {repo_url}",
            files_pushed=pushed_files,
            repo_url=repo_url,
        )

    def push_notes(self, notes: list[dict]) -> SyncResult:
        """Push all user notes to GitHub."""
        if not self.is_authenticated:
            return SyncResult(False, "Not authenticated", [])

        ok, repo_full = self.ensure_repo()
        if not ok:
            return SyncResult(False, repo_full, [])

        pushed: list[str] = []
        for note in notes:
            safe_title = note["title"].replace(" ", "_").replace("/", "-")[:40]
            path = f"notes/{safe_title}.md"
            content = f"# {note['title']}\n\n{note['content']}"
            if self.push_file(repo_full, path, content,
                              f"Update note: {note['title']}"):
                pushed.append(path)

        return SyncResult(
            success=True,
            message=f"Pushed {len(pushed)} notes",
            files_pushed=pushed,
            repo_url=f"https://github.com/{repo_full}",
        )

    def get_user_info(self) -> GitHubUser | None:
        """Return cached or freshly fetched GitHub user info."""
        if self._user:
            return self._user
        if not self.is_authenticated:
            return None
        try:
            data = self._api_get("/user")
            self._user = GitHubUser(
                login=data.get("login", ""),
                name=data.get("name", ""),
                avatar_url=data.get("avatar_url", ""),
                public_repos=data.get("public_repos", 0),
                html_url=data.get("html_url", ""),
            )
            return self._user
        except Exception:
            return None
