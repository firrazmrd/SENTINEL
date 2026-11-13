"""Keeps an authenticated session honest about the USB factor.

Policy: if the logged-in account requires the USB dongle (Settings), the registered dongle must stay connected for the
whole session. The service only decides; the UI shows the warning, counts down, and closes the application."""
from __future__ import annotations

import logging

from sentinel.database.repositories import UserRepo
from sentinel.services.audit_service import AuditService
from sentinel.services.permission_service import CurrentUser
from sentinel.services.usb_service import UsbCheck, UsbService

log = logging.getLogger("sentinel.session")
OK, NOT_REQUIRED, DISCONNECTED, UNKNOWN = "OK", "NOT_REQUIRED", "DISCONNECTED", "UNKNOWN"


class SessionGuard:
    def __init__(self, users: UserRepo, usb: UsbService, audit: AuditService) -> None:
        self._users, self._usb, self._audit = users, usb, audit

    def poll(self, user: CurrentUser) -> tuple[str, UsbCheck | None]:
        """Re-reads the account policy each time, so changing the USB requirement in Settings applies immediately.
        A drive only counts if it is THE registered dongle (volume id + token verified by UsbService.check)."""
        row = self._users.get(user.id)
        if row is None or not row["require_usb"]:
            return NOT_REQUIRED, None
        try:
            check = self._usb.check()
        except Exception as exc:  # noqa: BLE001 - a flaky drive query must not close the app
            log.warning("USB poll failed: %s", exc)
            return UNKNOWN, None
        return (OK if check.state == "VALID" else DISCONNECTED), check

    def record(self, event: str, user: CurrentUser, **details: object) -> None:
        self._audit.record(event, actor_id=user.id, details=details or None)
