"""Reasoning chain implementations for meta-cognitive planning."""

import re


class ReasoningChain:
    """Rule-based reasoning chains for goal decomposition and exploration."""

    def chain_of_thought(self, goal: str, context: dict | None = None) -> list[dict]:
        """Decompose a goal into sequential reasoning steps via sentence splitting or decomposition."""
        steps = []
        sentences = [s.strip() for s in re.split(r"[.?!]\s+", goal) if s.strip()]
        num_sentences = len(sentences)

        if num_sentences <= 1:
            parts = self._decompose_goal(goal)
            for i, part in enumerate(parts, 1):
                steps.append(
                    {
                        "step_id": f"cot_{i}",
                        "description": part,
                        "rationale": self._rationale_for_step(part, goal, i, len(parts)),
                    }
                )
        else:
            for i, sent in enumerate(sentences, 1):
                steps.append(
                    {
                        "step_id": f"cot_{i}",
                        "description": f"Address sub-goal: {sent}",
                        "rationale": (
                            "This sentence is an independent objective within the overall goal. "
                            "Processing it sequentially ensures focused attention on each sub-goal."
                        ),
                    }
                )

        if len(steps) < 3:
            steps = self._fill_steps(goal, steps)
        elif len(steps) > 7:
            steps = self._merge_steps(steps, 7)

        return steps

    def tree_of_thought(self, goal: str, context: dict | None = None, branches: int = 3) -> list[dict]:
        """Explore multiple reasoning branches and return the highest-scoring path."""
        root_steps = self.chain_of_thought(goal, context)
        if not root_steps:
            return []

        best_path = None
        best_score = -1.0

        for _ in range(branches):
            path = []
            for step in root_steps:
                variants = self._generate_variants(step, goal, branches)
                scored = [(v, self._score_step(v, goal)) for v in variants]
                scored.sort(key=lambda x: x[1], reverse=True)
                path.append(scored[0][0])

            score = sum(self._score_step(s, goal) for s in path) / len(path)
            if score > best_score:
                best_score = score
                best_path = path

        return best_path or root_steps[:3]

    def react_loop(self, goal: str, tools: list[str], max_steps: int = 10) -> list[dict]:
        """Simulate a ReAct-style thought-action-observation loop up to max_steps steps."""
        history = []
        observation = f"Starting goal: {goal}"

        for step in range(max_steps):
            thought = f"Analyze current state for step {step + 1}. {observation[:100]}"
            action = self._select_action(thought, tools, step)
            observation = self._simulate_observation(action, goal, step, max_steps)

            history.append(
                {
                    "thought": thought,
                    "action": action,
                    "observation": observation,
                }
            )

            if self._is_goal_achieved(observation):
                break

        return history

    def _decompose_goal(self, goal: str) -> list[str]:
        connectors = [
            r"\band\b",
            r"\bthen\b",
            r"\bfirst\b",
            r"\bnext\b",
            r"\bfinally\b",
            r"\bmoreover\b",
            r"\badditionally\b",
            r"\bsubsequently\b",
            r"\bthereafter\b",
        ]
        pattern = "|".join(connectors)
        parts = re.split(pattern, goal, flags=re.IGNORECASE)
        parts = [p.strip().strip(",").strip() for p in parts if p.strip()]
        if len(parts) < 2:
            words = goal.split()
            mid = max(1, len(words) // 2)
            parts = [" ".join(words[:mid]), " ".join(words[mid:])]
        return parts

    def _rationale_for_step(self, part: str, goal: str, idx: int, total: int) -> str:
        return f"Step {idx} of {total}: this partial objective advances toward the overall goal by addressing '{part[:60]}'."

    def _fill_steps(self, goal: str, steps: list[dict]) -> list[dict]:
        while len(steps) < 3:
            idx = len(steps) + 1
            steps.append(
                {
                    "step_id": f"cot_{idx}",
                    "description": f"Review and validate outcome of previous steps for: {goal[:50]}",
                    "rationale": f"Step {idx}: consolidation phase to ensure coherence across all sub-goals before completion.",
                }
            )
        return steps

    def _merge_steps(self, steps: list[dict], max_n: int) -> list[dict]:
        merged = []
        group_size = max(1, len(steps) // max_n)
        for i in range(0, len(steps), group_size):
            group = steps[i : i + group_size]
            if not merged or len(merged) >= max_n:
                merged.append(
                    {
                        "step_id": f"cot_{len(merged) + 1}",
                        "description": f"Combined: {'; '.join(s['description'][:40] for s in group)}",
                        "rationale": f"Merged {len(group)} related sub-steps into one consolidated step for efficiency.",
                    }
                )
            else:
                merged.append(group[0])
        return merged[:max_n]

    def _generate_variants(self, step: dict, goal: str, branches: int) -> list[dict]:
        variants = [step]
        for b in range(1, branches):
            variants.append(
                {
                    "step_id": f"tot_{step['step_id']}_v{b}",
                    "description": f"Alternate: {step['description'][:50]} (variant {b})",
                    "rationale": f"Alternative approach #{b} for this step, exploring different decomposition strategy.",
                }
            )
        return variants

    def _score_step(self, step: dict, goal: str) -> float:
        score = 0.5
        goal_words = set(re.findall(r"\w+", goal.lower()))
        step_words = set(re.findall(r"\w+", step.get("description", "").lower()))
        overlap = goal_words & step_words
        if overlap:
            score += len(overlap) * 0.05
        if step.get("rationale"):
            score += 0.1
        if len(step.get("description", "")) > 10:
            score += 0.1
        return min(score, 1.0)

    def _select_action(self, thought: str, tools: list[str], step: int) -> str:
        if not tools:
            return f"analyze(step={step + 1})"
        tool = tools[step % len(tools)]
        return f"{tool}(step={step + 1})"

    def _simulate_observation(self, action: str, goal: str, step: int, max_steps: int) -> str:
        return f"Executed {action}. Progress: step {step + 1}/{max_steps} toward '{goal[:60]}'."

    def _is_goal_achieved(self, observation: str) -> bool:
        return False
