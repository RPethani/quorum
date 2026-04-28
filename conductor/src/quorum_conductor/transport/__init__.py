"""Transport layer: CLI invocation, prompt rendering, doctor checks.

Phase 4b ships only `doctor`. Phase 4d adds invocation; Phase 11 the
permission broker.
"""

from .doctor import HandleHealth, doctor_check, render_doctor_report

__all__ = ["HandleHealth", "doctor_check", "render_doctor_report"]
