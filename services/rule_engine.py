"""
Categorization Rule Engine for evaluating applications against dynamic database rules.
"""

from __future__ import annotations

import fnmatch
import logging
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Union

from sqlalchemy.orm import Session

from core.models import CategorizationRule

logger = logging.getLogger("JP001.RuleEngine")


def matches_keyword(keyword: str, text: str) -> bool:
    """
    Check if a keyword matches as a distinct token or delimited word in text.
    Prevents false substring positives (e.g. 'code' matching inside 'encoder').
    """
    kw = keyword.strip().lower()
    if not kw:
        return False
    pattern = rf"(?:^|[\W_]){re.escape(kw)}(?:$|[\W_])"
    if re.search(pattern, text, re.IGNORECASE):
        return True
    if len(kw) >= 6 and (text.lower().startswith(kw) or text.lower().endswith(kw)):
        return True
    return False


class RuleEvaluator:
    """Evaluates applications against categorization rules loaded from database."""

    def __init__(self, db: Session) -> None:
        self.rules: List[CategorizationRule] = (
            db.query(CategorizationRule)
            .filter(CategorizationRule.enabled == True)  # noqa: E712
            .order_by(CategorizationRule.priority.asc())
            .all()
        )

    def categorize_application(
        self,
        name: str,
        path: Union[str, Path],
        files: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """
        Categorize an application based on its name, path, and constituent file extensions.
        Returns matched category name, or 'Uncategorized' if no rule matches.
        """
        p = Path(path).resolve()
        name_lower = name.lower()
        stem_lower = p.stem.lower()
        ext_lower = p.suffix.lower()

        full_path_norm = str(p).replace("\\", "/").lower()
        parent_dir_norm = str(p.parent).replace("\\", "/").lower()

        # Collect all file extensions in the application
        all_exts = {ext_lower} if ext_lower else set()
        if files:
            for f in files:
                rel = f.get("relative_path", "")
                suffix = Path(rel).suffix.lower()
                if suffix:
                    all_exts.add(suffix)

        for rule in self.rules:
            conds = rule.conditions or {}

            # 1. Match File Extensions
            rule_exts = [
                str(e).strip().lower() if str(e).startswith(".") else f".{str(e).strip().lower()}"
                for e in conds.get("extensions", [])
                if str(e).strip()
            ]
            if any(ext in rule_exts for ext in all_exts if ext):
                logger.debug("App '%s' matched category '%s' via extension", name, rule.category)
                return rule.category

            # 2. Match Keywords in App Name / Stem
            rule_keywords = [str(k).strip().lower() for k in conds.get("keywords", []) if str(k).strip()]
            for kw in rule_keywords:
                if matches_keyword(kw, name_lower) or matches_keyword(kw, stem_lower):
                    logger.debug("App '%s' matched category '%s' via keyword '%s'", name, rule.category, kw)
                    return rule.category

            # 3. Match Path Patterns
            rule_patterns = [
                str(pat).strip().replace("\\", "/").lower()
                for pat in conds.get("path_patterns", [])
                if str(pat).strip()
            ]
            for pattern in rule_patterns:
                clean_core = pattern.strip("*").strip("/")
                if (
                    fnmatch.fnmatch(parent_dir_norm, pattern)
                    or (clean_core and clean_core in parent_dir_norm)
                    or fnmatch.fnmatch(full_path_norm, pattern)
                ):
                    logger.debug("App '%s' matched category '%s' via path pattern '%s'", name, rule.category, pattern)
                    return rule.category

        return "Uncategorized"
