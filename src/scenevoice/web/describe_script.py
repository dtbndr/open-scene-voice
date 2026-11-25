from .plan_problem import PlanProblem
from .plan_run import PlanRun
from .script_bytes import ScriptBytes
from .script_revision import script_revision


def describe_script(script: ScriptBytes, plan: PlanRun | PlanProblem | None) -> dict[str, object]:
    """The `script` object of the project detail; `plan` is None only when no plan was run (absent or unreadable)."""
    problem = plan if isinstance(plan, PlanProblem) else script.problem
    scenes = plan.scenes if isinstance(plan, PlanRun) else ()
    return {
        "present": script.data is not None or script.problem is not None,
        "ok": isinstance(plan, PlanRun),
        "revision": script_revision(script.data) if script.data is not None else None,
        "problem": None if problem is None else {"line": problem.line, "message": problem.message},
        "scenes": [{"ordinal": s.ordinal, "title": s.title, "characters": len(s.body)} for s in scenes],
        "total_characters": sum(len(s.body) for s in scenes),
    }
