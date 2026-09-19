"""
personal — Kora Personal Knowledge & Goal Intelligence (V17)

Exports:
  - GoalManager, GoalNotFoundError, GoalActionError
  - DecisionJournal, DecisionNotFoundError
  - PersonalKnowledgeBridge
  - PersonalContextResolver
  - PersonalProactiveDetector
  - Goal, Milestone, DecisionRecord, PersonalContextPackage, GoalState, GoalPriority
"""

from personal.context_resolver import PersonalContextResolver
from personal.graph_bridge import PersonalKnowledgeBridge
from personal.journal import DecisionJournal, DecisionNotFoundError
from personal.manager import GoalActionError, GoalManager, GoalNotFoundError
from personal.proactive_hooks import PersonalProactiveDetector
from personal.types import (
    DecisionRecord,
    Goal,
    GoalPriority,
    GoalState,
    Milestone,
    PersonalContextPackage,
)

__all__ = [
    "GoalManager",
    "GoalNotFoundError",
    "GoalActionError",
    "DecisionJournal",
    "DecisionNotFoundError",
    "PersonalKnowledgeBridge",
    "PersonalContextResolver",
    "PersonalProactiveDetector",
    "Goal",
    "Milestone",
    "DecisionRecord",
    "PersonalContextPackage",
    "GoalState",
    "GoalPriority",
]
