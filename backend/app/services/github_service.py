import base64
import hashlib
import logging
from typing import List

import httpx

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"


class GitHubPushError(Exception):
    pass


def obfuscate_token(token: str, secret: str) -> str:
    """XOR-based obfuscation using JWT secret as key. Not cryptographic — prevents plaintext storage."""
    key = hashlib.sha256(secret.encode()).digest()
    xored = bytes(b ^ key[i % len(key)] for i, b in enumerate(token.encode()))
    return base64.urlsafe_b64encode(xored).decode()


def deobfuscate_token(encoded: str, secret: str) -> str:
    key = hashlib.sha256(secret.encode()).digest()
    xored = base64.urlsafe_b64decode(encoded)
    return bytes(b ^ key[i % len(key)] for i, b in enumerate(xored)).decode()


class GitHubService:
    def __init__(self, token: str):
        self.token = token
        self.headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    async def validate_token(self) -> dict:
        async with httpx.AsyncClient(timeout=15) as client:
            res = await client.get(f"{GITHUB_API}/user", headers=self.headers)
            if res.status_code == 401:
                raise GitHubPushError("Invalid GitHub token. Please check your Personal Access Token.")
            if res.status_code != 200:
                raise GitHubPushError(f"GitHub API error: {res.status_code}")
            return res.json()

    async def create_repo(self, name: str, description: str = "", private: bool = False) -> dict:
        async with httpx.AsyncClient(timeout=15) as client:
            res = await client.post(
                f"{GITHUB_API}/user/repos",
                headers=self.headers,
                json={"name": name, "description": description, "private": private, "auto_init": False},
            )
            if res.status_code == 422:
                data = res.json()
                errors = data.get("errors", [])
                if any(e.get("message") == "name already exists on this account" for e in errors):
                    raise GitHubPushError(f"Repository '{name}' already exists on your GitHub account.")
                raise GitHubPushError(f"GitHub validation error: {data.get('message', 'Unknown error')}")
            if res.status_code not in (200, 201):
                raise GitHubPushError(f"Failed to create repo: {res.status_code}")
            return res.json()

    async def push_files(self, owner: str, repo: str, files: List[dict], commit_message: str = "Initial commit from AI Software Company") -> str:
        async with httpx.AsyncClient(timeout=60) as client:
            tree_items = []
            for f in files:
                path = f["path"]
                content = f["content"]
                blob_res = await client.post(
                    f"{GITHUB_API}/repos/{owner}/{repo}/git/blobs",
                    headers=self.headers,
                    json={"content": content, "encoding": "utf-8"},
                )
                if blob_res.status_code != 201:
                    raise GitHubPushError(f"Failed to create blob for {path}: {blob_res.status_code}")
                blob_sha = blob_res.json()["sha"]
                tree_items.append({
                    "path": path,
                    "mode": "100644",
                    "type": "blob",
                    "sha": blob_sha,
                })

            tree_res = await client.post(
                f"{GITHUB_API}/repos/{owner}/{repo}/git/trees",
                headers=self.headers,
                json={"tree": tree_items},
            )
            if tree_res.status_code != 201:
                raise GitHubPushError(f"Failed to create tree: {tree_res.status_code}")
            tree_sha = tree_res.json()["sha"]

            commit_res = await client.post(
                f"{GITHUB_API}/repos/{owner}/{repo}/git/commits",
                headers=self.headers,
                json={"message": commit_message, "tree": tree_sha},
            )
            if commit_res.status_code != 201:
                raise GitHubPushError(f"Failed to create commit: {commit_res.status_code}")
            commit_sha = commit_res.json()["sha"]

            ref_res = await client.post(
                f"{GITHUB_API}/repos/{owner}/{repo}/git/refs",
                headers=self.headers,
                json={"ref": "refs/heads/main", "sha": commit_sha},
            )
            if ref_res.status_code not in (200, 201):
                await client.patch(
                    f"{GITHUB_API}/repos/{owner}/{repo}/git/refs/heads/main",
                    headers=self.headers,
                    json={"sha": commit_sha, "force": True},
                )

            return commit_sha
