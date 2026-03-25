"""
GitHub Gist Publisher — uploads a notebook as a public Gist and returns
a colab.research.google.com URL so the user can open it directly.
Implemented fully in Task 4.
"""
from __future__ import annotations


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
    raise NotImplementedError("Implemented in Task 4")
