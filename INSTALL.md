# Update v24 (includes v15 to v23)

1. Extract and replace the files.
2. NEW TABLE `notification` (the bell). On Vercel, api/index.py creates it by itself on the next start. Locally run once: `python migrate_new_tables.py`.

What is new
- Notification bell (top bar, students and teachers): new class / class moved / class cancelled, new quiz, new receipt, HSK unlocked (students); a student finished a quiz, a new student registered (teachers). Opening the bell marks them read. No polling, so almost no Vercel usage.
- Our own dialogs everywhere instead of the browser's alert/confirm/prompt, and our own date and time picker (calendar + time lists, bottom sheet on phones). Old scripts keep working.
- Riddles for HSK 1 (137), HSK 2 (107) and HSK 3 (209).
- HSK 1, 2 and 3 content audited: wrong or strange memory tricks rewritten, forced example words removed, a few wrong component notes fixed, more notes for confusing words.
- Badges: Ruby click = earthquake (the card shakes, cracks, debris). Dragon = deep violet and gold, no rainbow; clicking it sends out rays of golden light. Jade = calmer and cozier (breathing glow, soft lights, leaves).
