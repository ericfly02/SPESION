"""Agents module - Los 8 agentes especializados del Octágono."""

from .base_agent import BaseAgent
from .scholar import ScholarAgent
from .coach import CoachAgent
from .tycoon import TycoonAgent
from .companion import CompanionAgent
from .techlead import TechLeadAgent
from .connector import ConnectorAgent
from .executive import ExecutiveAgent
from .sentinel import SentinelAgent

__all__ = [
    "BaseAgent",
    "ScholarAgent",
    "CoachAgent",
    "TycoonAgent",
    "CompanionAgent",
    "TechLeadAgent",
    "ConnectorAgent",
    "ExecutiveAgent",
    "SentinelAgent",
]

