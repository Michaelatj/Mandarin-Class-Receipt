"""
services/quiz_logic.py - quiz rules shared by the quiz routes.

Ported from the Mandarin-Quiz-Assessment Node app (server.js, titles.js):
validation of the JSON a chatbot produces, per-student shuffling, grading,
the two scores (accuracy and XP) and the fun title for each attempt.
"""
import re
import random
import secrets

MAX_QUESTIONS = 60
MAX_TEXT = 400          # longest question / option / chunk we store
MAX_OPTIONS = 10
MAX_CHUNKS = 12

# A fun label for how ONE attempt went, from its accuracy and streak.
# Keep ascending by min_accuracy. Only the top tier needs a flawless run.
TITLES = [
    {"name": "童生", "pinyin": "tóngshēng", "meaning": "Beginner",       "icon": "🌱", "min_accuracy": 0},
    {"name": "秀才", "pinyin": "xiùcái",    "meaning": "Apprentice",     "icon": "📖", "min_accuracy": 50},
    {"name": "举人", "pinyin": "jǔrén",     "meaning": "Rising Talent",  "icon": "⭐", "min_accuracy": 75},
    {"name": "探花", "pinyin": "tànhuā",    "meaning": "Star Student",   "icon": "🏅", "min_accuracy": 90},
    {"name": "状元", "pinyin": "zhuàngyuán", "meaning": "Grand Champion", "icon": "👑", "min_accuracy": 100,
     "requires_flawless": True},
]


def compute_title(accuracy, longest_streak, total_questions):
    title = TITLES[0]
    for t in TITLES:
        if accuracy < t["min_accuracy"]:
            continue
        if t.get("requires_flawless") and longest_streak < total_questions:
            continue
        title = t
    return title


def title_by_name(name):
    for t in TITLES:
        if t["name"] == name:
            return t
    return None


def new_id():
    return secrets.token_urlsafe(6)


def _clean(value, limit=MAX_TEXT):
    return str(value).strip()[:limit]


# ---------------------------------------------------------------------
# Validation + normalising what the teacher pasted
# ---------------------------------------------------------------------
def validate_quiz_payload(payload):
    """Return a list of human readable problems (empty list = valid)."""
    errors = []
    if not isinstance(payload, dict):
        return ["The quiz must be a JSON object."]
    if not isinstance(payload.get("title"), str) or not payload["title"].strip():
        errors.append('Missing a "title" (text).')
    questions = payload.get("questions")
    if not isinstance(questions, list) or not questions:
        errors.append('Missing a "questions" list.')
        return errors
    if len(questions) > MAX_QUESTIONS:
        errors.append(f"A quiz can have at most {MAX_QUESTIONS} questions.")
        return errors

    for i, q in enumerate(questions, start=1):
        label = f"Question {i}"
        if not isinstance(q, dict):
            errors.append(f"{label}: must be an object.")
            continue
        if not isinstance(q.get("question"), str) or not q["question"].strip():
            errors.append(f'{label}: missing the "question" text.')
        qtype = q.get("type", "multiple_choice")
        if qtype == "sentence_reorder":
            chunks = q.get("chunks")
            if not isinstance(chunks, list) or not (2 <= len(chunks) <= MAX_CHUNKS) \
                    or not all(isinstance(c, str) and c.strip() for c in chunks):
                errors.append(f"{label}: needs between 2 and {MAX_CHUNKS} text chunks.")
        elif qtype in ("multiple_choice", "multiple_select"):
            options = q.get("options")
            if not isinstance(options, list) or not (2 <= len(options) <= MAX_OPTIONS) \
                    or not all(isinstance(o, str) and o.strip() for o in options):
                errors.append(f"{label}: needs between 2 and {MAX_OPTIONS} text options.")
                continue
            if len({o.strip() for o in options}) != len(options):
                errors.append(f"{label}: the options must all be different.")
            if qtype == "multiple_choice":
                if q.get("answer") not in options:
                    errors.append(f"{label}: the answer must match one of the options exactly.")
            else:
                answers = q.get("answers")
                if not isinstance(answers, list) or not answers \
                        or not all(a in options for a in answers) or len(set(answers)) != len(answers):
                    errors.append(f"{label}: answers must list correct options, each copied exactly from the options.")
                elif len(answers) >= len(options):
                    errors.append(f"{label}: at least one option must be wrong.")
            meanings = q.get("optionMeanings")
            if meanings is not None and (not isinstance(meanings, list) or len(meanings) != len(options)):
                errors.append(f"{label}: optionMeanings must have the same length as options.")
        else:
            errors.append(f'{label}: unsupported type "{qtype}".')
    return errors


def _alt_orders(chunks, raw):
    """Alternative correct orders as index lists.

    Each order may be given as chunk indexes (the editor) or as chunk text
    (what a chatbot writes). Orders that are not a full rearrangement of the
    chunks, equal the main order, or repeat another one are dropped.
    """
    result, seen = [], {tuple(range(len(chunks)))}
    if not isinstance(raw, list):
        return []
    for order in raw:
        if not isinstance(order, list) or len(order) != len(chunks):
            continue
        indices = None
        if all(isinstance(v, int) and not isinstance(v, bool) for v in order):
            if sorted(order) == list(range(len(chunks))):
                indices = list(order)
        else:
            remaining = list(enumerate(chunks))
            found = []
            for text in order:
                text = str(text).strip()
                hit = next((k for k, (_, c) in enumerate(remaining) if c == text), None)
                if hit is None:
                    break
                found.append(remaining.pop(hit)[0])
            if len(found) == len(chunks):
                indices = found
        if indices is not None and tuple(indices) not in seen:
            seen.add(tuple(indices))
            result.append(indices)
    return result


def normalize_quiz(payload, existing_ids=None):
    """Build the stored question list from a validated payload.

    When a teacher edits a quiz, questions keep their id (so saved answers still
    belong to them). Only ids that already exist on this quiz are accepted.
    """
    allowed = set(existing_ids or [])
    used = set()
    questions = []
    for q in payload["questions"]:
        qid = q.get("id")
        if not (isinstance(qid, str) and qid in allowed and qid not in used):
            qid = new_id()
        used.add(qid)
        qtype = q.get("type") if q.get("type") in ("sentence_reorder", "multiple_select") else "multiple_choice"
        base = {
            "id": qid,
            "type": qtype,
            "question": _clean(q["question"]),
            "questionMeaning": _clean(q["questionMeaning"]) if q.get("questionMeaning") else None,
            "explanation": _clean(q["explanation"], 600) if q.get("explanation") else None,
            "points": q["points"] if isinstance(q.get("points"), (int, float)) and 0 < q["points"] <= 10 else 1,
        }
        if base["type"] == "sentence_reorder":
            chunks = [_clean(c) for c in q["chunks"]]
            base["chunks"] = chunks
            base["altOrders"] = _alt_orders(chunks, q.get("altOrders"))
        else:
            base["options"] = [_clean(o) for o in q["options"]]
            meanings = q.get("optionMeanings")
            base["optionMeanings"] = [_clean(m) for m in meanings] if isinstance(meanings, list) else None
            if qtype == "multiple_select":
                wanted = {_clean(a) for a in q["answers"]}
                base["answers"] = [o for o in base["options"] if o in wanted]   # keep the options' order
            else:
                base["answer"] = _clean(q["answer"])
        questions.append(base)
    return {
        "title": _clean(payload["title"], 200),
        "description": _clean(payload.get("description") or "", 500),
        "questions": questions,
    }


# ---------------------------------------------------------------------
# What a student is allowed to see
# ---------------------------------------------------------------------
_PINYIN_PAREN = re.compile(r"\s*\([a-zA-Zāáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜü' -]+\)")


def strip_pinyin(text):
    if not isinstance(text, str):
        return text
    return _PINYIN_PAREN.sub("", text).strip()


def _pick_display_options(q, max_count=4):
    """The correct option plus up to 3 random wrong ones, shuffled."""
    meanings = q.get("optionMeanings")
    pairs = [(opt, meanings[i] if meanings else None) for i, opt in enumerate(q["options"])]
    correct = [p for p in pairs if p[0] == q["answer"]]
    wrong = [p for p in pairs if p[0] != q["answer"]]
    random.shuffle(wrong)
    chosen = correct + wrong[:max(0, max_count - 1)]
    random.shuffle(chosen)
    return ([p[0] for p in chosen], [p[1] for p in chosen] if meanings else None)


def to_student_view(quiz):
    """Questions shuffled for one student. Never includes answers."""
    hide = bool(quiz.hide_pinyin)
    fix = strip_pinyin if hide else (lambda t: t)
    questions = list(quiz.questions)
    random.shuffle(questions)

    out = []
    for q in questions:
        item = {"id": q["id"], "type": q["type"], "question": fix(q["question"]),
                "questionMeaning": q.get("questionMeaning")}
        if q["type"] == "sentence_reorder":
            chunks = [{"id": i, "text": fix(text)} for i, text in enumerate(q["chunks"])]
            random.shuffle(chunks)
            item["chunks"] = chunks
        elif q["type"] == "multiple_select":
            order = list(range(len(q["options"])))
            random.shuffle(order)
            options = [q["options"][i] for i in order]
            meanings = [q["optionMeanings"][i] for i in order] if q.get("optionMeanings") else None
            item["options"] = [fix(o) for o in options]
            item["optionValues"] = options
            item["optionMeanings"] = meanings
        else:
            options, meanings = _pick_display_options(q)
            item["options"] = [fix(o) for o in options]
            # the client sends back the displayed text, so keep a map to the real option
            item["optionValues"] = options
            item["optionMeanings"] = meanings
        out.append(item)

    return {
        "id": quiz.id,
        "title": quiz.title,
        "description": quiz.description or "",
        "timeLimitSeconds": quiz.time_limit_seconds or 0,
        "questions": out,
    }


# ---------------------------------------------------------------------
# Grading + scoring
# ---------------------------------------------------------------------
def is_answer_correct(q, value):
    if q["type"] == "sentence_reorder":
        total = len(q["chunks"])
        if not isinstance(value, list) or len(value) != total:
            return False
        if not all(isinstance(v, int) and not isinstance(v, bool) for v in value):
            return False
        if value == list(range(total)):
            return True
        return any(value == order for order in (q.get("altOrders") or []))
    if q["type"] == "multiple_select":
        if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
            return False
        # all-or-nothing: exactly the right set, no more and no fewer
        return len(set(value)) == len(value) and set(value) == set(q["answers"])
    return isinstance(value, str) and value == q["answer"]


def recompute_score(answers, answer_order, questions, time_limit_seconds):
    """Accuracy (0-100), XP (uncapped, playful) and longest streak."""
    by_id = {q["id"]: q for q in questions}
    limit_ms = (time_limit_seconds or 0) * 1000
    correct = 0
    xp = 0.0
    streak = 0
    longest = 0

    order = answer_order or [q["id"] for q in questions]
    for qid in order:
        q = by_id.get(qid)
        given = answers.get(qid)
        if not q or not given:
            streak = 0
            continue
        value = given.get("value")
        used_hint = given.get("usedMeaning") is True
        answered_at = given.get("answeredAtMs")
        if not isinstance(answered_at, (int, float)) or isinstance(answered_at, bool):
            answered_at = None

        if not is_answer_correct(q, value):
            streak = 0
            continue

        correct += 1
        streak += 1
        longest = max(longest, streak)

        base = q["points"] * 0.5 if used_hint else q["points"]
        bonus = 0.0
        if limit_ms > 0 and answered_at is not None:
            remaining = max(0, limit_ms - answered_at)
            bonus += 0.5 * min(1, remaining / limit_ms)
        bonus += min(0.5, max(0, streak - 2) * 0.1)
        xp += base + base * bonus

    total = len(questions)
    return {
        "accuracy": round(correct / total * 100) if total else 0,
        "xp": round(xp, 2),
        "longest_streak": longest,
    }


def display_answer(q, value):
    """Readable text for a stored answer (used on result and review screens)."""
    if value is None:
        return None
    if q["type"] == "sentence_reorder":
        if isinstance(value, list) and all(isinstance(v, int) and 0 <= v < len(q["chunks"]) for v in value):
            return " ".join(q["chunks"][v] for v in value)
        return None
    if q["type"] == "multiple_select":
        if isinstance(value, list) and all(isinstance(v, str) for v in value):
            return " / ".join(value) if value else None
        return None
    return value if isinstance(value, str) else None


def correct_text(q):
    if q["type"] == "sentence_reorder":
        return " ".join(q["chunks"])
    if q["type"] == "multiple_select":
        return " / ".join(q["answers"])
    return q["answer"]


def build_review(questions, answers):
    review = []
    for q in questions:
        given = answers.get(q["id"]) or {}
        value = given.get("value")
        review.append({
            "id": q["id"],
            "type": q["type"],
            "question": q["question"],
            "questionMeaning": q.get("questionMeaning"),
            "explanation": q.get("explanation"),
            "given": display_answer(q, value),
            "correctAnswer": correct_text(q),
            "otherOrders": [" ".join(q["chunks"][i] for i in order) for order in (q.get("altOrders") or [])]
                           if q["type"] == "sentence_reorder" else [],
            "correct": is_answer_correct(q, value),
        })
    return review


def regrade_attempt(attempt, questions, time_limit_seconds):
    """Score a finished attempt again against the current questions."""
    scored = recompute_score(attempt.answers or {}, attempt.answer_order or [], questions, time_limit_seconds)
    title = compute_title(scored["accuracy"], scored["longest_streak"], len(questions))
    attempt.accuracy_score = scored["accuracy"]
    attempt.xp_score = scored["xp"]
    attempt.longest_streak = scored["longest_streak"]
    attempt.title = title["name"]
