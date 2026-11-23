# Update v18 (includes v15 to v17)

Extract and replace the files.

New badge ladder, one level every 5 classes in a row:
Bronze 0, Silver 5, Gold 10, Jade 15, Diamond 20, Dragon 25+ (rainbow).
Each badge has its own animation and its own music (WebAudio, no sound files). The teacher gallery (Badges & animations) shows all 6.
Students' current badge is recalculated automatically from their streak; no database change.
Database: table `hsk_game` (Vercel creates it; local SQLite: `python migrate_new_tables.py`).
