# Update v25 (includes v15 to v24)

Extract and replace the files. Needs the `notification` table from v24 (`python migrate_new_tables.py` locally; Vercel creates it itself). config.py is NOT included: keep yours (see the note about the duplicate SQLALCHEMY_DATABASE_URI line).

- Classes and Attendance are one page: three columns on wide screens, two buttons (Classes | Attendance) on phones. The Attendance menu item is gone. The confusing X next to the date field is removed (the picker has a Today button).
- Dragon badge: pearl white like before, no rainbow; click = white light rays; every badge now plays its own sound when a student clicks it.
- Quiz: the timer floats at the top while scrolling; single-choice questions are checked the moment you tap (in a story quiz: the questions that are not about the story), with streak effects and sound.
- Racing: first to the finish line (1500 m) against three bots; leaderboard (top 10 per game) at the bottom of the Games page.
