import os


def print_stopped() -> None:
    """Print the stopped line; a closed or broken stdout is swallowed and replaced by /dev/null for the exit flush."""
    try:
        print("SceneVoice has stopped.", flush=True)
    except (OSError, ValueError):
        try:
            null = os.open(os.devnull, os.O_WRONLY)
            if null != 1:
                os.dup2(null, 1)
                os.close(null)
        except OSError:
            return
