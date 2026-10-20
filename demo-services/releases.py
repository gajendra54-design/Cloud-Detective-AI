"""Two bundled demo release behaviors, not arbitrary images or downloaded code."""

from fastapi import HTTPException


def stable_release():
    return None


def regression_release():
    raise HTTPException(503, "Controlled regression in demo-v2")


RELEASES = {"demo-v1": stable_release, "demo-v2": regression_release}
