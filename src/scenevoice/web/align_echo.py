from .listen_scenes import listen_scenes
from .project_facts import ProjectFacts
from .script_revision import script_revision


def align_echo(facts: ProjectFacts, data: bytes) -> dict[str, object]:
    """What the server counts for an align start (J1): the scenes it would send to transcription (0 for a free run) and the script revision."""
    return {"scenes": listen_scenes(facts.scenes, facts.record, facts.audio.hashes), "revision": script_revision(data)}
