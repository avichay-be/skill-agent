"""Async GitHub REST API client for CI/CD operations."""

import logging
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

GITHUB_API_BASE = "https://api.github.com"


class GitHubClientError(Exception):
    """Error from GitHub API operations."""


class GitHubClient:
    """Async client for GitHub REST API operations.

    Supports fetching diffs, file contents, creating branches, commits, and PRs.
    """

    def __init__(self, token: str, repo_full_name: str) -> None:
        self.token = token
        self.repo = repo_full_name
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    async def get_compare(self, base: str, head: str) -> Dict[str, Any]:
        """Get comparison between two commits.

        Args:
            base: Base commit SHA.
            head: Head commit SHA.

        Returns:
            GitHub compare response with files and commits.
        """
        url = f"{GITHUB_API_BASE}/repos/{self.repo}/compare/{base}...{head}"
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=self._headers, timeout=30.0)
            if resp.status_code != 200:
                raise GitHubClientError(
                    f"Failed to get compare: {resp.status_code} {resp.text}"
                )
            return resp.json()  # type: ignore[no-any-return]

    async def get_file_content(self, path: str, ref: str = "main") -> Optional[str]:
        """Get file content from the repository.

        Args:
            path: File path in the repo.
            ref: Branch or commit ref.

        Returns:
            File content as string, or None if file doesn't exist.
        """
        url = f"{GITHUB_API_BASE}/repos/{self.repo}/contents/{path}"
        params = {"ref": ref}
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=self._headers, params=params, timeout=30.0)
            if resp.status_code == 404:
                return None
            if resp.status_code != 200:
                raise GitHubClientError(
                    f"Failed to get file {path}: {resp.status_code} {resp.text}"
                )
            data = resp.json()
            if data.get("encoding") == "base64":
                import base64

                return base64.b64decode(data["content"]).decode("utf-8")
            return data.get("content", "")  # type: ignore[no-any-return]

    async def get_existing_pipeline_files(self, ref: str = "main") -> Dict[str, Optional[str]]:
        """Fetch existing CI/CD pipeline files from the repo.

        Args:
            ref: Branch or commit ref.

        Returns:
            Dict mapping file path to content (None if not found).
        """
        pipeline_paths = [
            ".github/workflows/ci.yml",
            ".github/workflows/deploy.yml",
            "Dockerfile",
            "infra/main.bicep",
        ]
        results: Dict[str, Optional[str]] = {}
        for path in pipeline_paths:
            try:
                content = await self.get_file_content(path, ref)
                results[path] = content
            except GitHubClientError:
                results[path] = None
        return results

    async def create_branch(self, branch_name: str, from_sha: str) -> None:
        """Create a new branch from a commit SHA.

        Args:
            branch_name: Name for the new branch.
            from_sha: Commit SHA to branch from.
        """
        url = f"{GITHUB_API_BASE}/repos/{self.repo}/git/refs"
        payload = {"ref": f"refs/heads/{branch_name}", "sha": from_sha}
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url, headers=self._headers, json=payload, timeout=30.0
            )
            if resp.status_code not in (201, 422):
                # 422 means ref already exists, which is acceptable
                raise GitHubClientError(
                    f"Failed to create branch: {resp.status_code} {resp.text}"
                )

    async def create_or_update_file(
        self,
        path: str,
        content: str,
        message: str,
        branch: str,
        sha: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create or update a file in the repository.

        Args:
            path: File path in the repo.
            content: File content.
            message: Commit message.
            branch: Target branch.
            sha: Current file SHA (required for updates).

        Returns:
            GitHub API response.
        """
        import base64

        url = f"{GITHUB_API_BASE}/repos/{self.repo}/contents/{path}"
        payload: Dict[str, Any] = {
            "message": message,
            "content": base64.b64encode(content.encode("utf-8")).decode("utf-8"),
            "branch": branch,
        }
        if sha:
            payload["sha"] = sha

        async with httpx.AsyncClient() as client:
            resp = await client.put(
                url, headers=self._headers, json=payload, timeout=30.0
            )
            if resp.status_code not in (200, 201):
                raise GitHubClientError(
                    f"Failed to create/update file {path}: {resp.status_code} {resp.text}"
                )
            return resp.json()  # type: ignore[no-any-return]

    async def get_file_sha(self, path: str, branch: str) -> Optional[str]:
        """Get the SHA of an existing file (needed for updates).

        Args:
            path: File path in the repo.
            branch: Branch to check.

        Returns:
            File SHA or None if file doesn't exist.
        """
        url = f"{GITHUB_API_BASE}/repos/{self.repo}/contents/{path}"
        params = {"ref": branch}
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=self._headers, params=params, timeout=30.0)
            if resp.status_code == 404:
                return None
            if resp.status_code != 200:
                raise GitHubClientError(
                    f"Failed to get file SHA for {path}: {resp.status_code} {resp.text}"
                )
            return resp.json().get("sha")  # type: ignore[no-any-return]

    async def create_pull_request(
        self,
        title: str,
        body: str,
        head: str,
        base: str = "main",
    ) -> Dict[str, Any]:
        """Create a pull request.

        Args:
            title: PR title.
            body: PR description.
            head: Head branch name.
            base: Base branch name.

        Returns:
            GitHub PR response including html_url.
        """
        url = f"{GITHUB_API_BASE}/repos/{self.repo}/pulls"
        payload = {
            "title": title,
            "body": body,
            "head": head,
            "base": base,
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url, headers=self._headers, json=payload, timeout=30.0
            )
            if resp.status_code != 201:
                raise GitHubClientError(
                    f"Failed to create PR: {resp.status_code} {resp.text}"
                )
            return resp.json()  # type: ignore[no-any-return]
