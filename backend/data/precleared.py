"""Internal rights/release repository.

A real production keeps this in a document store or database; for the
hackathon demo it's a static lookup so the pipeline has something concrete
to check before it ever spends a Parallel call. Keys are matched against
extracted entity names, case-insensitively, after stripping punctuation.
"""

PRECLEARED: dict[str, dict] = {
    "eye of the tiger": {
        "status": "cleared",
        "license_ref": "SYNC-2024-0417",
        "note": (
            "Needle-drop sync license on file with the music supervisor, "
            "signed 2024-11-02, covers worldwide theatrical and streaming use."
        ),
    },
}


def lookup(entity_name: str) -> dict | None:
    key = entity_name.strip().lower().strip("\"'")
    return PRECLEARED.get(key)
