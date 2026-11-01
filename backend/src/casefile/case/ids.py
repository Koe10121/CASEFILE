"""Typed IDs for every entity in a case.

Each ID is a ``NewType`` over ``str`` (so mypy refuses to pass an evidence ID where a
fact ID is expected) wrapped in ``Annotated`` with a pattern (so Pydantic rejects a
malformed ID at load time). The prefixes are the ones in ``docs/design/case-schema.md``.
"""

from typing import Annotated, NewType

from pydantic import StringConstraints

_FactId = NewType("_FactId", str)
_GuardedFactId = NewType("_GuardedFactId", str)
_CharacterId = NewType("_CharacterId", str)
_EvidenceId = NewType("_EvidenceId", str)
_LocationId = NewType("_LocationId", str)
_LieId = NewType("_LieId", str)
_MotiveId = NewType("_MotiveId", str)
_MethodId = NewType("_MethodId", str)

_SUFFIX = r"[A-Z0-9]+(?:_[A-Z0-9]+)*"

FactId = Annotated[_FactId, StringConstraints(pattern=rf"^F_{_SUFFIX}$")]
GuardedFactId = Annotated[_GuardedFactId, StringConstraints(pattern=r"^G_\d{2}$")]
CharacterId = Annotated[_CharacterId, StringConstraints(pattern=rf"^S_{_SUFFIX}$")]
EvidenceId = Annotated[_EvidenceId, StringConstraints(pattern=r"^E\d{2}$")]
LocationId = Annotated[_LocationId, StringConstraints(pattern=rf"^LOC_{_SUFFIX}$")]
LieId = Annotated[_LieId, StringConstraints(pattern=rf"^LIE_{_SUFFIX}$")]
MotiveId = Annotated[_MotiveId, StringConstraints(pattern=rf"^MOT_{_SUFFIX}$")]
MethodId = Annotated[_MethodId, StringConstraints(pattern=rf"^MTH_{_SUFFIX}$")]

CaseId = Annotated[str, StringConstraints(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")]
