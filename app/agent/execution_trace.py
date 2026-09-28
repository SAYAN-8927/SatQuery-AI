from datetime import datetime


class ExecutionTrace:

    def __init__(self, query: str):

        self.query = query
        self.steps = []
        self.started_at = datetime.utcnow().isoformat()

    def add_step(
        self,
        step: str,
        status: str,
        details: dict | None = None
    ):

        self.steps.append({
            "step": step,
            "status": status,
            "timestamp": datetime.utcnow().isoformat(),
            "details": details or {}
        })

    def complete(self):

        self.completed_at = datetime.utcnow().isoformat()

    def to_dict(self):

        return {
            "query": self.query,
            "started_at": self.started_at,
            "completed_at": getattr(
                self,
                "completed_at",
                None
            ),
            "steps": self.steps
        }