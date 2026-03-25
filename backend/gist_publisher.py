"""
GitHub Gist Publisher — uploads a notebook as a public Gist and returns
a colab.research.google.com URL so the user can open it directly.
"""
from __future__ import annotations

import os

import httpx


def publish_to_gist(notebook_json: str, title: str) -> str | None:
    """
    Create a public GitHub Gist containing the notebook and return a Colab URL.

    Args:
        notebook_json: Serialized .ipynb content (JSON string)
        title:         Human-readable title used as the Gist description + filename

    Returns:
        "https://colab.research.google.com/gist/<username>/<gist_id>"
        or None if GITHUB_TOKEN is not configured (graceful fallback to download-only)
    """
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        return None

    # Sanitize filename — keep alphanumerics, spaces, hyphens, underscores
    safe_title = "".join(c if c.isalnum() or c in " -_" else "_" for c in title)[:80]
    filename = f"{safe_title}.ipynb"

    payload = {
        "description": f"Research Paper Notebook: {title}",
        "public": True,
        "files": {
            filename: {"content": notebook_json},
        },
    }

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    response = httpx.post(
        "https://api.github.com/gists",
        json=payload,
        headers=headers,
        timeout=30.0,
    )
    response.raise_for_status()

    data = response.json()
    gist_id = data["id"]
    owner_login = data["owner"]["login"]

    return f"https://colab.research.google.com/gist/{owner_login}/{gist_id}"
