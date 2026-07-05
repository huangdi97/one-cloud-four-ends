"""Agent 注册中心 — 扫描 agents/*/identity.yaml 并缓存 Agent 实例。"""

import logging
from pathlib import Path

from cloud.app.agent_runtime.core.agent import Agent

logger = logging.getLogger(__name__)

_AGENTS_DIR = Path("agents")


class AgentRegistry:
    _agents: dict[str, Agent] = {}
    _loaded = False

    @classmethod
    def load(cls, agents_dir: str | Path | None = None) -> None:
        """Scan agents_dir for identity.yaml files and populate the registry."""
        cls._agents.clear()
        base = Path(agents_dir) if agents_dir else _AGENTS_DIR
        if not base.is_dir():
            logger.warning("Agent directory not found: %s", base)
            cls._loaded = True
            return
        for yaml_path in sorted(base.rglob("identity.yaml")):
            try:
                agent = Agent.from_yaml(str(yaml_path))
                cls._agents[agent.identity.key] = agent
                logger.info("Loaded agent %s from %s", agent.identity.key, yaml_path)
            except (OSError, KeyError, TypeError):
                logger.exception("Failed to load agent from %s", yaml_path)
        cls._loaded = True
        logger.info("AgentRegistry loaded %d agents", len(cls._agents))

    @classmethod
    def get(cls, key: str) -> Agent | None:
        """Return the agent identified by key, loading on demand if needed."""
        if not cls._loaded:
            cls.load()
        return cls._agents.get(key)

    @classmethod
    def list(cls) -> list[Agent]:
        """Return all registered agents, loading on demand if needed."""
        if not cls._loaded:
            cls.load()
        return list(cls._agents.values())

    @classmethod
    def find_failover_agent(cls, agent_key: str) -> str | None:
        """Find another agent with the same role/tags for failover."""
        failed = cls._agents.get(agent_key)
        if failed is None:
            return None
        failed_tags = set(failed.identity.tags or [])
        if not failed_tags:
            return None
        best = None
        best_score = 0
        for key, agent in cls._agents.items():
            if key == agent_key:
                continue
            agent_tags = set(agent.identity.tags or [])
            score = len(failed_tags & agent_tags)
            if score > best_score:
                best = key
                best_score = score
        return best

    @classmethod
    def reload(cls) -> None:
        """Clear the cache and re-load all agents from disk."""
        cls._loaded = False
        cls.load()
