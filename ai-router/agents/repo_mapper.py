"""
HELIOS — RepoMapper Agent
Performs fast, deterministic codebase inspection (AST, symbols, imports, tests)
and uses LLM only for high-level relevance interpretation.
"""

from __future__ import annotations

import ast
import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from pydantic import BaseModel, Field

from agents.base import AgentResult, AgentStatus, BaseAgent
from core.model_router import model_router
from providers.base import BaseProvider

logger = logging.getLogger("helios.agents.repo_mapper")


class RepoMapOutput(BaseModel):
    """Structured output of repository analysis."""
    relevant_files: List[str] = Field(default_factory=list)
    symbols: List[Dict[str, Any]] = Field(default_factory=list)
    test_files: List[str] = Field(default_factory=list)
    dependent_files: List[str] = Field(default_factory=list)
    summary: str = ""


class RepoMapperAgent(BaseAgent):
    """
    Deterministically maps files, AST symbols, dependencies, and tests.
    Uses LLM only for final ranking and interpretation.
    """

    def __init__(self, provider: BaseProvider, agent_id: Optional[str] = None):
        super().__init__(agent_id)
        self.provider = provider
        self.skip_dirs = {
            "__pycache__", ".git", ".pytest_cache", "venv", ".venv",
            "node_modules", ".helios_worktrees", "static", ".models"
        }

    @property
    def agent_type(self) -> str:
        return "repo_mapper"

    def deterministic_symbol_search(self, root_dir: str, query: str) -> List[Dict[str, Any]]:
        """Scans Python AST for classes and functions matching query."""
        results = []
        q_lower = query.lower()

        for dirpath, dirs, files in os.walk(root_dir):
            dirs[:] = [d for d in dirs if d not in self.skip_dirs]
            for file in files:
                if not file.endswith(".py"):
                    continue
                full_path = os.path.join(dirpath, file)
                rel_path = os.path.relpath(full_path, root_dir)

                try:
                    with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                        source = f.read()
                    tree = ast.parse(source, filename=rel_path)

                    for node in ast.walk(tree):
                        if isinstance(node, ast.ClassDef):
                            if q_lower in node.name.lower() or any(term in node.name.lower() for term in q_lower.split()):
                                results.append({
                                    "file": rel_path,
                                    "symbol": node.name,
                                    "type": "class",
                                    "line": getattr(node, "lineno", 0),
                                })
                        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            if q_lower in node.name.lower() or any(term in node.name.lower() for term in q_lower.split()):
                                results.append({
                                    "file": rel_path,
                                    "symbol": node.name,
                                    "type": "function",
                                    "line": getattr(node, "lineno", 0),
                                })
                except Exception:
                    continue

        return results[:40]

    def deterministic_text_search(self, root_dir: str, terms: List[str], max_results: int = 30) -> List[str]:
        """Fast keyword search across source files."""
        matched_files: Set[str] = set()

        for dirpath, dirs, files in os.walk(root_dir):
            dirs[:] = [d for d in dirs if d not in self.skip_dirs]
            for file in files:
                if not (file.endswith((".py", ".json", ".yaml", ".yml", ".md", ".sh", ".bat", ".ts", ".js"))):
                    continue
                full_path = os.path.join(dirpath, file)
                rel_path = os.path.relpath(full_path, root_dir)

                # Check filename match
                for term in terms:
                    if term.lower() in file.lower():
                        matched_files.add(rel_path)

                try:
                    with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read(50000)  # Read up to 50KB
                    for term in terms:
                        if term.lower() in content.lower():
                            matched_files.add(rel_path)
                            break
                except Exception:
                    continue

                if len(matched_files) >= max_results:
                    break
            if len(matched_files) >= max_results:
                break

        return sorted(list(matched_files))

    def find_associated_tests(self, root_dir: str, candidate_files: List[str]) -> List[str]:
        """Identifies test files corresponding to candidates."""
        test_files = set()
        for cand in candidate_files:
            base_name = os.path.basename(cand)
            stem = os.path.splitext(base_name)[0]
            test_candidates = [
                f"test_{stem}.py",
                f"{stem}_test.py",
                f"tests/test_{stem}.py",
            ]
            for tc in test_candidates:
                full_tc = os.path.join(root_dir, tc)
                if os.path.exists(full_tc):
                    test_files.add(os.path.relpath(full_tc, root_dir))

        # Also scan tests/ directory directly
        tests_dir = os.path.join(root_dir, "tests")
        if os.path.exists(tests_dir):
            for f in os.listdir(tests_dir):
                if f.startswith("test_") and f.endswith(".py"):
                    test_files.add(f"tests/{f}")

        return sorted(list(test_files))[:20]

    async def execute(self, objective: str, context: Optional[Dict[str, Any]] = None) -> AgentResult:
        started_at = datetime.now(timezone.utc)
        context = context or {}

        repo_root = context.get("repository_root") or os.getcwd()
        if "coding_context" in context and hasattr(context["coding_context"], "worktree"):
            repo_root = context["coding_context"].worktree or context["coding_context"].repository_root

        # 1. Deterministic Analysis
        terms = [t for t in re.split(r"[\s_,\.:/]+", objective) if len(t) > 3 and not t.isdigit()]
        matched_files = self.deterministic_text_search(repo_root, terms)
        symbols = self.deterministic_symbol_search(repo_root, objective)
        tests = self.find_associated_tests(repo_root, matched_files)

        for sym in symbols:
            if sym["file"] not in matched_files:
                matched_files.append(sym["file"])

        # 2. LLM Interpretation (Rank and filter)
        model_name, options = await model_router.prepare_model_for_agent("repo_mapper", self.provider)

        prompt = f"""You are the HELIOS Repository Mapping Specialist.
Objective: {objective}

Deterministic Search Results:
- Found Files: {json.dumps(matched_files[:25])}
- Found Symbols: {json.dumps(symbols[:15])}
- Associated Tests: {json.dumps(tests[:10])}

Select and rank the most relevant files (maximum 10) needed to accomplish the objective.
Output strict JSON with format:
{{
  "relevant_files": ["path/to/file1.py"],
  "test_files": ["tests/test_file1.py"],
  "summary": "Brief explanation of how the files relate to the objective"
}}
"""

        try:
            response = await self.provider.generate(
                model=model_name,
                prompt=prompt,
                options=options,
                stream=False,
                format="json",
            )
            raw = response.get("response", "").strip()
            parsed = {}
            try:
                # Direct JSON or regex match
                parsed = json.loads(raw)
            except Exception:
                m = re.search(r"(\{[\s\S]*\})", raw)
                if m:
                    parsed = json.loads(m.group(1))

            final_relevant = parsed.get("relevant_files", matched_files[:8])
            final_tests = parsed.get("test_files", tests[:5])
            summary = parsed.get("summary", f"Located {len(final_relevant)} relevant files.")

        except Exception as ex:
            self.logger.warning(f"RepoMapper LLM interpretation skipped: {ex}")
            final_relevant = matched_files[:8]
            final_tests = tests[:5]
            summary = f"Deterministically identified {len(final_relevant)} files."

        output = RepoMapOutput(
            relevant_files=final_relevant,
            symbols=symbols,
            test_files=final_tests,
            summary=summary,
        )

        # Update CodingContext
        if "coding_context" in context:
            ctx = context["coding_context"]
            ctx.relevant_files = sorted(list(set(ctx.relevant_files + final_relevant)))
            if final_tests and not ctx.test_command:
                ctx.test_command = f"pytest {' '.join(final_tests[:3])}"

        return self._make_result(
            status=AgentStatus.SUCCESS,
            summary=summary,
            detail=output.model_dump_json(indent=2),
            evidence=output.model_dump(),
            started_at=started_at,
            confidence=0.9,
        )
