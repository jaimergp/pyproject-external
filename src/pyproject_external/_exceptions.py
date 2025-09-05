# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2025 Quansight Labs
"""
Exception subclasses for this package.
"""

try:
    ExceptionGroup
except NameError:
    from exceptiongroup import ExceptionGroup


class UnsupportedSpecError(ValueError):
    pass


class ExactVersionNotSupportedError(UnsupportedSpecError):
    pass


class VersionRangesNotSupportedError(UnsupportedSpecError):
    pass


class VersionConstraintNotSupportedError(UnsupportedSpecError):
    pass


class ExternalTableNotFoundError(ValueError):
    pass


class ValidationErrors(ExceptionGroup):
    pass
