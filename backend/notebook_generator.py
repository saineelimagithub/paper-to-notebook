"""
Notebook Generator — uses gpt-4o to analyze a research paper and generates
a production-quality Google Colab notebook via nbformat.
"""
from __future__ import annotations

import asyncio
import json
from typing import Callable, Awaitable

import nbformat
from openai import AsyncOpenAI


# ─────────────────────────────────────────────────────────────────────────────
# System Prompt
# ─────────────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are an expert research engineer at a top AI lab. Your task is to create a production-quality Google Colab tutorial notebook that implements the core algorithms from a research paper.

The notebook MUST follow this exact structure with these 10 sections:

1. **Title & Overview** (markdown cell)
   - Paper title, authors if mentioned, publication venue
   - 3-sentence abstract summary
   - What this notebook demonstrates

2. **Installation & Setup** (code cell)
   - pip install commands for all required packages
   - Import statements with standard aliases
   - Set random seeds for reproducibility
   - Configure matplotlib style

3. **Theoretical Background** (markdown cell)
   - Core mathematical formulation with LaTeX equations (use $...$ inline, $$...$$ display)
   - Key assumptions and when they hold
   - Intuition behind the approach

4. **Algorithm — Pseudocode & Design** (markdown cell)
   - Step-by-step pseudocode in a code block
   - Design decisions and why they matter
   - Complexity analysis (time and space)

5. **Core Implementation** (code cell)
   - Full Python implementation with type hints and docstrings
   - Well-structured classes/functions (not a monolithic script)
   - Production-quality code: proper error handling, clear variable names
   - Comments explaining non-obvious steps

6. **Synthetic Dataset Generation** (code cell)
   - Generate realistic synthetic data that matches the paper's domain
   - NOT toy data: use appropriate scale (1000-10000 samples), realistic distributions
   - Include data visualization to verify the synthetic data looks reasonable
   - Document the data generation assumptions

7. **Experiments: Reproducing Key Results** (code cell)
   - Run the implemented algorithm on the synthetic dataset
   - Track and display metrics mentioned in the paper
   - Compare against at least one baseline

8. **Visualization & Analysis** (code cell)
   - Plot results using matplotlib/seaborn with publication-quality styling
   - Multiple subplots showing different aspects
   - Clear labels, titles, legends

9. **Ablation Study** (code cell)
   - Vary 2-3 key hyperparameters or components
   - Show impact on performance
   - Discuss which components matter most

10. **Summary & Next Steps** (markdown cell)
    - What was demonstrated
    - Limitations of the implementation
    - 3-5 concrete next steps for researchers

CRITICAL REQUIREMENTS:
- All code must be runnable end-to-end in Google Colab
- Use only standard libraries available in Colab (numpy, scipy, sklearn, matplotlib, seaborn, torch if needed)
- Synthetic data must be realistic for the paper's domain (not random noise)
- Include actual numerical results and comparisons, not placeholders
- LaTeX equations must be correct and render in Jupyter
- Code must have type hints, docstrings, and be PEP 8 compliant

Return your response as a JSON object with this structure:
{
  "summary_bullets": ["bullet 1", "bullet 2", "bullet 3"],
  "cells": [
    {"type": "markdown", "source": "# markdown content here"},
    {"type": "code", "source": "# python code here"},
    ...
  ]
}

The "cells" array must have exactly 10 elements following the structure above (some sections may have multiple cells, but aim for one per section unless it significantly improves clarity)."""


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────


async def generate_notebook(
    paper: dict,
    api_key: str,
    progress: Callable[[str], Awaitable[None]],
) -> tuple:
    """
    Analyze the paper with gpt-4o and build a research-grade .ipynb notebook.

    Args:
        paper:    Parsed paper dict from pdf_parser.parse_pdf()
        api_key:  User's OpenAI API key (forwarded per-request, never stored)
        progress: Async callback to push progress messages to the SSE stream

    Returns:
        (NotebookNode, summary_bullets: list[str])
    """
    client = AsyncOpenAI(api_key=api_key)

    await progress("Analyzing core algorithms and theoretical contributions...")
    await asyncio.sleep(0)  # yield to event loop

    # Build user message with paper content
    user_content = f"""
Paper Title: {paper.get('title', 'Unknown')}

Abstract:
{paper.get('abstract', 'Not found')}

Full Paper Text (first 12000 chars):
{paper.get('full_text', '')[:12000]}
"""

    await progress("Mapping methodology to implementable components...")

    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        response_format={"type": "json_object"},
        max_tokens=8000,
        temperature=0.2,
    )

    await progress("Assembling notebook cells...")

    result = json.loads(response.choices[0].message.content)
    notebook = build_notebook(result["cells"])
    summary_bullets = result.get("summary_bullets", [])

    return notebook, summary_bullets


# ─────────────────────────────────────────────────────────────────────────────
# Notebook builder
# ─────────────────────────────────────────────────────────────────────────────


def build_notebook(cells: list[dict]) -> nbformat.NotebookNode:
    """
    Assemble a valid nbformat v4 NotebookNode from a list of cell dicts.

    Args:
        cells: List of {"type": "markdown"|"code", "source": str}

    Returns:
        NotebookNode ready to be serialized with nbformat.writes()
    """
    nb = nbformat.v4.new_notebook()
    nb.metadata.update(
        {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {
                "name": "python",
                "version": "3.10.0",
            },
            "colab": {
                "provenance": [],
                "toc_visible": True,
            },
        }
    )

    for cell in cells:
        if cell["type"] == "markdown":
            nb.cells.append(nbformat.v4.new_markdown_cell(cell["source"]))
        elif cell["type"] == "code":
            nb.cells.append(nbformat.v4.new_code_cell(cell["source"]))

    nbformat.validate(nb)
    return nb
