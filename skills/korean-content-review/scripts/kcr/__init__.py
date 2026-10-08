"""원문을 보호하는 한국어 텍스트 검수 엔진 (MIT)."""

from .findings import Finding, SuppressedCounter
from .protect import Span, find_protected

__all__ = ["Finding", "SuppressedCounter", "Span", "find_protected"]
