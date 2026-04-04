from app.adk.workflow_runner import run_goal_workflow_adk


class _Workflow:
    def invoke(self, state: dict) -> dict:
        return run_goal_workflow_adk(state)


def build_graph():
    return _Workflow()