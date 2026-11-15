# Update HSK v3 (bug fix + new UI + English buttons)

1. Extract this zip into the project root (the folder that contains `app/`). Choose Merge and Replace.
2. No database migration, no new libraries. Restart the app as usual.
3. Hard-refresh the browser once (Ctrl+Shift+R) so the new CSS/JS load.

What changed
- BUG FIX (student/dashboard.html): the dashboard script tried to hide `#langBar`, which does not exist in base.html. That raised an error and left every tab (Classes, Schedule, ...) hidden. The code is now null-safe, so Classes shows again right after login.
- New flashcard UI: equal-height pill buttons, one centred control row, a 3D flip card, SVG icons, a segmented mode switch.
- All HSK buttons and labels are English. Lesson material (meanings, memory tricks, notes, translations) stays Indonesian.
- New file: app/templates/hsk/_sprite.html (icon set).
