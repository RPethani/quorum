"""Canvas module — the brainstorming conversation, persisted to disk.

See `docs-specs/canvas-redesign.md` (S1, S2, S3) for the on-disk
contract this module implements.

Public surface:
    Message, parse_canvas, append_message               # canvas IO
    extract_mentions                                    # @-routing
    ArtifactEmit, ParsedReply, extract_artifacts        # artifact parsing
    ArtifactWriteResult, write_artifact                 # artifact writing
    WorkspaceState, CostState,
    load_state, save_state, next_message_id             # state.yaml
    scaffold, ScaffoldError                             # workspace setup
    dispatch, DispatchResult, AgentTurn,
    InvocationRequest, InvocationResult, InvokeFn       # dispatcher
"""

from .artifact_writer import ArtifactWriteResult, write_artifact
from .artifacts import ArtifactEmit, ParsedReply, extract_artifacts
from .dispatcher import (
    AgentTurn,
    DispatchResult,
    InvocationRequest,
    InvocationResult,
    InvokeFn,
    dispatch,
)
from .io import append_message, parse_canvas
from .mentions import extract_mentions
from .message import Message
from .state import (
    CostState,
    StateError,
    WorkspaceState,
    load_state,
    next_message_id,
    save_state,
)
from .workspace import ScaffoldError, scaffold

__all__ = [
    "AgentTurn",
    "ArtifactEmit",
    "ArtifactWriteResult",
    "CostState",
    "DispatchResult",
    "InvocationRequest",
    "InvocationResult",
    "InvokeFn",
    "Message",
    "ParsedReply",
    "ScaffoldError",
    "StateError",
    "WorkspaceState",
    "append_message",
    "dispatch",
    "extract_artifacts",
    "extract_mentions",
    "load_state",
    "next_message_id",
    "parse_canvas",
    "save_state",
    "scaffold",
    "write_artifact",
]
