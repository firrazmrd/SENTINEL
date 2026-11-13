# Perubahan pada revisi redesign v1.3

Dependensi baru: **tidak ada** paket pip baru. Aset baru: `assets/fonts/IBMPlexSans-{Regular,Bold}.ttf` + lisensi OFL (diambil dari paket npm `@ibm/plex-sans`, dikonversi woff → ttf).

## File ditambahkan
`assets/fonts/*` · `sentinel/ui/camera_widget.py` · `sentinel/services/session_guard.py` · `tests/integration/test_session_and_stages.py` ·
`docs/test_report.md` · `docs/CHANGELOG_v1_3.md`

## File diubah (ringkas)
- **UI**: `ui/common.py` (design tokens, font loader, StatusDot/StatusPill/Panel, DataTable empty/loading state), `ui/app.py` (shell baru, loading bar, guard USB),
  `ui/login_view.py` (split-screen + kamera live), `ui/dashboard_view.py` (padat informasi), `ui/dialogs.py` (kode pemulihan + checkbox konfirmasi, dialog wajah memakai CameraPanel),
  `ui/settings_view.py`, `ui/setup_view.py` (token + konfirmasi kode), `ui/async_utils.py` (penghitung job).
- **Service**: `biometric_service.py` (verify bertahap pada stream, pelepasan kamera terjamin), `auth_service.py` (callback tahap/stream), `dashboard_service.py` (`security_overview`),
  `bootstrap.py` (SessionGuard), `repositories.py` (`status_counts`), `devices/camera.py` (warm-up exposure).
- **Script/dokumentasi**: `scripts/install_deps.ps1` (fallback drive, `-Biometric`), `scripts/run_app.ps1` (fallback drive), `README.md`, `docs/demo_guide.md`.
- **Test**: `tests/conftest.py`, `tests/gui/test_gui_flow.py` (+3 test), 7 test baru service.

## Perilaku yang berubah / disengaja berbeda dari brief
- Kamera login menyala setelah password (dan USB) lolos, bukan saat halaman dibuka — alasan di README §10.
- Medium weight IBM Plex tidak dibundel (hanya Regular & Bold).
