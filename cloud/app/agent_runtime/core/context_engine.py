"""上下文分页管理 — MemGPT 式虚拟内存，按需 page_in/page_out。"""

from __future__ import annotations

from collections import OrderedDict


def estimate_tokens(text: str) -> int:
    """Roughly estimate the token count of a text string."""
    return len(text) // 4


PRIORITY_ORDER = {
    "system_prompt": 0,
    "current_task": 1,
    "recent_dialogue": 2,
    "history": 3,
    "long_term_knowledge": 4,
}


class ContextPager:
    def __init__(self, max_budget: int = 4096):
        self._max_budget = max_budget
        self._working: OrderedDict[str, str] = OrderedDict()
        self._long_term: OrderedDict[str, str] = OrderedDict()
        self._sections: dict[str, str] = {}
        self._priorities: dict[str, int] = {}

    def register_section(self, name: str, content: str, priority_label: str = "history") -> None:
        """Register a content section with a priority label."""
        self._sections[name] = content
        self._priorities[name] = PRIORITY_ORDER.get(priority_label, 3)
        self._working[name] = content

    def page_in(self, section_name: str) -> str | None:
        """Bring a section from long-term storage into working memory."""
        if section_name in self._long_term:
            content = self._long_term.pop(section_name)
            self._working[section_name] = content
            return content
        return self._sections.get(section_name)

    def page_out(self, section_name: str) -> None:
        """Move a section from working memory to long-term storage."""
        if section_name in self._working:
            content = self._working.pop(section_name)
            self._long_term[section_name] = content

    def auto_manage(self, current_tokens: int | None = None) -> list[str]:
        """Evict low-priority sections if working memory exceeds 80% of budget."""
        tokens = current_tokens if current_tokens is not None else self._estimate_working_tokens()
        budget_80pct = self._max_budget * 0.8
        evicted = []

        if tokens <= budget_80pct:
            return evicted

        sorted_sections = sorted(
            self._working.items(),
            key=lambda item: (self._priorities.get(item[0], 3), -len(item[1])),
        )

        while tokens > budget_80pct and sorted_sections:
            name, content = sorted_sections.pop()
            if self._priorities.get(name, 3) == 0:
                break
            self.page_out(name)
            evicted.append(name)
            tokens -= estimate_tokens(content)

        return evicted

    def _estimate_working_tokens(self) -> int:
        return sum(estimate_tokens(c) for c in self._working.values())

    def get_working_context(self) -> str:
        """Return the assembled working context as a string."""
        sorted_sections = sorted(
            self._working.items(),
            key=lambda item: self._priorities.get(item[0], 3),
        )
        return "\n\n".join(f"[{name}]\n{content}" for name, content in sorted_sections)

    def set_max_budget(self, budget: int) -> None:
        """Update the maximum token budget."""
        self._max_budget = budget


class ContextEngine:
    def __init__(self, pager: ContextPager | None = None):
        self._pager = pager or ContextPager()

    @property
    def pager(self) -> ContextPager:
        """Return the underlying ContextPager instance."""
        return self._pager

    def assemble(self, system_prompt: str, task: str, dialogue: list[dict], knowledge: list[dict]) -> list[dict]:
        """Build a system message from prompt, task, dialogue, and knowledge."""
        self._pager.register_section("system_prompt", system_prompt, "system_prompt")
        self._pager.register_section("current_task", task, "current_task")

        dialogue_text = "\n".join(f"{m.get('role', 'user')}: {m.get('content', '')}" for m in dialogue[-10:])
        self._pager.register_section("recent_dialogue", dialogue_text, "recent_dialogue")

        knowledge_text = "\n".join(k.get("content", "") for k in knowledge)
        if knowledge_text:
            self._pager.register_section("long_term_knowledge", knowledge_text, "long_term_knowledge")

        total = estimate_tokens(system_prompt) + estimate_tokens(task) + estimate_tokens(dialogue_text) + estimate_tokens(knowledge_text)
        self._pager.auto_manage(total)

        working = self._pager.get_working_context()
        return [{"role": "system", "content": working}]
