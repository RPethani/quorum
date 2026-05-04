"""Transport layer — only `doctor` remains after the protocol retirement.

The protocol-era invoker / runner / locks have been retired. The canvas
dispatcher's invocation path lives in `canvas.transport_adapter`.
"""

from .doctor import HandleHealth, doctor_check, render_doctor_report

__all__ = ["HandleHealth", "doctor_check", "render_doctor_report"]
