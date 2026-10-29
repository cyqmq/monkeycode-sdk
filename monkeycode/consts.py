"""枚举常量。"""
from enum import Enum


class TaskType(str, Enum):
    """任务类型。"""

    DEVELOP = "develop"
    DESIGN = "design"
    REVIEW = "review"


class TaskSubType(str, Enum):
    """任务子类型。"""

    GENERATE_DOCS = "generate_docs"
    GENERATE_REQUIREMENT = "generate_requirement"
    GENERATE_DESIGN = "generate_design"
    GENERATE_TASKLIST = "generate_tasklist"
    EXECUTE_TASK = "execute_task"
    PR_REVIEW = "pr_review"


class CliName(str, Enum):
    """CLI 名称。"""

    CODEX = "codex"
    CLAUDE = "claude"
    OPENCODE = "opencode"