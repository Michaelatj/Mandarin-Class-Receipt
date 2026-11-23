# Update v19 (includes v15 to v18)

Extract and replace the files. No database change beyond v15 (table `hsk_game`; local SQLite: `python migrate_new_tables.py`).

- Flashcards for all words now live on the HSK level page (first page). The "All words" page no longer has its own Flashcards tab. Each topic keeps its tab.
- Quiz: a run of right answers (3, 5, 8, 10, 15...) plays the student's own badge show and music.
- Memory match: all cards are shown first, then closed. Tap a card to open, tap again to close. Two matching open cards score.
