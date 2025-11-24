"""Helper tools for Playbook operations."""

async def recordfailure(
    failure_reason: str,
    experiment_id: str
):
    """Record experiment failure."""
    return {
        "status": "recorded",
        "experiment_id": experiment_id,
        "failure_reason": failure_reason
    }
