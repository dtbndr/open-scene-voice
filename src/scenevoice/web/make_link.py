def make_link(port: int, token: str) -> str:
    """The one launch link; the token appears nowhere else."""
    return f"http://127.0.0.1:{port}/?token={token}"
