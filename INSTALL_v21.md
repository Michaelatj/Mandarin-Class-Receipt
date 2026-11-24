# Update v21 (includes v15 to v20)

Extract and replace the files. Deleted from the project: app/templates/quiz/cards.html and app/static/js/flashcards.js (preview cards are gone; you can delete both files by hand, leaving them does no harm).
Database: table `hsk_game` (Vercel creates it; local SQLite: `python migrate_new_tables.py`).

- Games: switches for pinyin (all games) and for meaning + clue (Character riddle).
- Quiz and Bonus Courses pages are centred. Preview cards removed.
- Story quiz: teacher chooses how many questions are about the story; the rest are separate. Teacher review shows the story and every question with its options.
- 7 badges: Bronze 0, Silver 5, Gold 10, Jade 15, Diamond 20, Ruby 25, Dragon 30+ (white rainbow). New effects and music, lighter on weak phones.
- Titles and badge names show hanzi, pinyin and meaning on hover or tap. Nameplate colours follow the badge.
- New theme: Forest and Forest (dark).
- Insights: new Bonus Courses activity card.
- data.json is cached by the browser for one hour (fewer Vercel function calls).
