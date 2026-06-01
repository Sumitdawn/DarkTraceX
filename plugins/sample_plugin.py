metadata = {
    "name": "sample_tool",
    "version": "0.1.0",
    "description": "Example plugin for DarkTrace X.",
}


def run(target: str) -> dict:
    return {
        "name": "sample_tool",
        "target": target,
        "status": "loaded",
    }
