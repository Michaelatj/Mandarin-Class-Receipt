"""
services/i18n.py — Internationalisation helpers.
"""
import random
from datetime import datetime, timedelta
from flask import session, g

# ── Translation tables ────────────────────────────────────────────────────────

TRANSLATIONS: dict = {
    "en": dict(
        app_title="Chinese Class", app_sub="Attendance & Billing · 中文课堂",
        login="Sign In", username_lbl="Username", password_lbl="Password",
        username_ph="your username", password_ph="your password",
        no_account="Don't have an account?", create_account="Register",
        back_login="Back to Login",
        register_title="Create Account", display_name_lbl="Display Name",
        display_name_ph="e.g. Budi Santoso", phone_lbl="Phone (optional)",
        phone_ph="0812-3456-7890", role_lbl="I am a...",
        role_student="Student", role_teacher="Teacher",
        register_btn="Create Account", logout="Logout",
        student_dash="Student Dashboard", teacher_dash="Teacher Dashboard",
        this_cycle="This Cycle", total_sessions="Total Sessions",
        receipts_lbl="Receipts", mark_attn="Mark Today's Attendance",
        select_teacher="Select Your Teacher", submit_attn="Submit Attendance",
        current_progress="Current Progress", your_receipts="Your Receipts",
        no_teachers="No teachers registered yet.",
        no_progress="No cycle in progress. Mark your first attendance!",
        no_receipts="Complete 8 classes to receive your first receipt.",
        classes_done="Classes Completed", with_teacher="with",
        receipt_lbl="Receipt", teacher_lbl="Teacher", transfer_to="Transfer To",
        total_fee_lbl="Total Fee (8 sessions)",
        payment_settings="Payment Settings", bank_name_lbl="Bank Name",
        bank_name_ph="BCA / Mandiri / BNI", acct_lbl="Account Number",
        acct_ph="1234-5678-9012", default_fee_lbl="Default Fee per 8 Classes (IDR)",
        display_name_t="Display Name (shown to students)",
        save_settings="Save Settings", student_progress="Student Progress",
        all_receipts="All Receipts", student_lbl="Student",
        mark_paid="Mark as Paid", no_students="No active students yet.",
        no_receipts_t="No receipts yet.", students_lbl="Students",
        unpaid_lbl="Unpaid", paid_lbl="Paid",
        add_manual="Add Attendance Manually", manual_student="Select Student",
        manual_date="Class Date and Time", manual_note="Note (optional)",
        manual_note_ph="e.g. make-up class, online session",
        add_btn="Add Attendance", delete_btn="Delete",
        edit_attn="Manage Attendance Records",
        custom_fees="Custom Student Fees",
        custom_fees_info="Override the default fee per student. Leave blank to use default.",
        set_fee="Save", fee_ph="e.g. 500000",
        greeting_s="Hello", greeting_t="Welcome, Teacher",
        mon="Monday", tue="Tuesday", wed="Wednesday",
        thu="Thursday", fri="Friday", sat="Saturday", sun="Sunday",
        err_user="Username not found. Please register.",
        err_pw="Incorrect password.",
        err_taken="Username already taken.",
        err_locked="Too many login attempts. Please wait 5 minutes.",
        err_username_fmt="Username must be 3–40 characters: letters, numbers, _ . - only.",
        ok_created="Account created! Please sign in.",
        ok_saved="Settings saved.", ok_attn="Attendance recorded!",
        ok_paid="Marked as paid.", ok_deleted="Record deleted.",
        id_lbl="User ID",
        pw_short="Password must be at least 6 characters.",
        classes_attended="Class Sessions",
        dark_mode="Dark Mode",
        delete_account="Delete Account",
        delete_account_warn="This will permanently delete your account and all your data. This cannot be undone.",
        delete_confirm_pw="Enter your password to confirm",
        ok_deleted_account="Your account has been deleted.",
        manage_students="Manage Student Accounts",
        manage_students_info="As the teacher, you have authority to remove student accounts and all their data.",
        danger_zone="Danger Zone",
        delete_confirm_msg="Are you sure? This will permanently delete your account and all data.",
        confirm_pw_lbl="Enter your password to confirm",
        err_delete_pw="Incorrect password. Account not deleted.",
        jan="January", feb="February", mar="March", apr="April",
        may_m="May", jun="June", jul="July", aug="August",
        sep="September", oct_m="October", nov="November", dec="December",
        # NEW: Tuition Packet System
        tuition_rules_title="Tuition Payment Rules",
        packet_session="Session Packet",
        packet_monthly="Monthly Packet",
        packet_session_desc="Pay per class attended (Rp 75,000/session). Flexible for irregular schedules.",
        packet_monthly_desc="Fixed monthly fee (Rp 500,000/month). Payment is due every month regardless of attendance or rescheduling.",
        warning_monthly_policy="⚠️ Monthly Policy: For students on the Monthly Packet, payment is required every month even if classes are missed or rescheduled. This ensures stable income for the teacher.",
        select_packet_type="Select Packet Type",
        current_fee="Current Fee",
        remember_me="Remember me on this device",
        nav_classes="Classes",
        nav_attendance="Attendance",
        nav_attend_short="Attend",
        nav_students="Students",
        nav_receipts="Receipts",
        nav_progress="Progress",
        nav_settings="Settings",
        nav_quiz="Quiz",
        teacher_tag="Teacher Dashboard",
        student_tag="Student Dashboard",
        page_classes_sub_teacher="Schedule and manage your class sessions",
        page_classes_sub_student="Upcoming sessions scheduled by your teacher",
        page_attendance_sub="Add sessions manually and track student progress",
        progress_sub_student="Your current billing cycle",
        settings_sub_teacher="Manage your account and payment preferences",
        settings_sub_student="Manage your account",
        student_count_one="{n} student registered",
        student_count_many="{n} students registered",
        receipts_summary="{total} total · {unpaid} unpaid",
        receipts_total_student="{n} total receipts",
        language_lbl="Language",
        show_password="Show password",
        hide_password="Hide password",
        monthly_policy="Monthly Policy",
        monthly_policy_desc="For monthly packet students, payment is due every month regardless of rescheduling or absences. This ensures stable income for the teacher.",
        per_session="Per Session",
        per_month="Per Month",
        quiz_soon_badge="Coming soon",
        quiz_teacher_head="Give quizzes to your students",
        quiz_teacher_desc="Soon you will be able to create Mandarin quizzes here, assign them to your students, and see their scores.",
        quiz_student_head="Quizzes from your teacher",
        quiz_student_desc="Soon your teacher will send you Mandarin quizzes here. You answer them and see your score right away.",
        quiz_planned="Planned features",
        quiz_f_types="Several question types: fill in the blank, hanzi and pinyin, sentence ordering",
        quiz_f_assign="Assign a quiz to chosen students",
        quiz_f_scores="See each student's score",
        quiz_f_timer="One total time limit for the whole quiz",
        quiz_f_streak="Streak feedback when you answer correctly in a row",
        quiz_back="Back to dashboard",
    ),
    "zh": dict(
        app_title="中文课堂", app_sub="考勤与账单系统 · Chinese Class",
        login="登录", username_lbl="用户名", password_lbl="密码",
        username_ph="请输入用户名", password_ph="请输入密码",
        no_account="还没有账号？", create_account="注册",
        back_login="返回登录",
        register_title="注册账号", display_name_lbl="显示名称",
        display_name_ph="例如：张伟", phone_lbl="电话（选填）",
        phone_ph="0812-3456-7890", role_lbl="我是...",
        role_student="学生", role_teacher="老师",
        register_btn="注册账号", logout="退出",
        student_dash="学生仪表板", teacher_dash="教师仪表板",
        this_cycle="本周期", total_sessions="总课时",
        receipts_lbl="收据", mark_attn="标记今日出勤",
        select_teacher="选择您的老师", submit_attn="提交出勤",
        current_progress="当前进度", your_receipts="我的收据",
        no_teachers="暂无老师注册。",
        no_progress="暂无进行中的周期，请在上方标记出勤！",
        no_receipts="完成8节课后将自动生成收据。",
        classes_done="已完成课时", with_teacher="老师：",
        receipt_lbl="收据", teacher_lbl="老师", transfer_to="转账至",
        total_fee_lbl="费用合计（8节课）",
        payment_settings="收款设置", bank_name_lbl="银行名称",
        bank_name_ph="BCA / Mandiri / BNI", acct_lbl="账户号码",
        acct_ph="1234-5678-9012", default_fee_lbl="每8节课默认学费（印尼盾）",
        display_name_t="显示名称（学生可见）",
        save_settings="保存设置", student_progress="学生进度",
        all_receipts="全部收据", student_lbl="学生",
        mark_paid="标记已付款", no_students="暂无活跃学生。",
        no_receipts_t="暂无收据。", students_lbl="学生",
        unpaid_lbl="未付款", paid_lbl="已付款",
        add_manual="手动添加出勤", manual_student="选择学生",
        manual_date="上课日期与时间", manual_note="备注（选填）",
        manual_note_ph="例如：补课、线上课",
        add_btn="添加出勤", delete_btn="删除",
        edit_attn="管理出勤记录",
        custom_fees="学生个性化学费",
        custom_fees_info="可为每位学生单独设置学费，留空则使用默认学费。",
        set_fee="保存", fee_ph="例如：500000",
        greeting_s="你好", greeting_t="老师好",
        mon="星期一", tue="星期二", wed="星期三",
        thu="星期四", fri="星期五", sat="星期六", sun="星期日",
        err_user="用户名不存在，请先注册。",
        err_pw="密码错误。",
        err_taken="用户名已被使用，请重新选择。",
        err_locked="登录尝试次数过多，请等待5分钟后重试。",
        err_username_fmt="用户名须为3-40个字符，仅限字母、数字、_ . -",
        ok_created="账号创建成功！请登录。",
        ok_saved="设置已保存。", ok_attn="出勤已记录！",
        ok_paid="已标记为已付款。", ok_deleted="记录已删除。",
        id_lbl="用户ID",
        pw_short="密码至少需要6个字符。",
        classes_attended="上课记录",
        dark_mode="深色模式",
        delete_account="删除账号",
        delete_account_warn="此操作将永久删除您的账号及所有相关数据，无法撤销。",
        delete_confirm_pw="请输入密码以确认",
        ok_deleted_account="您的账号已成功删除。",
        manage_students="管理学生账号",
        manage_students_info="作为老师，您有权限删除学生账号及其所有数据。",
        danger_zone="危险操作",
        delete_confirm_msg="确定吗？此操作将永久删除您的账号及所有数据。",
        confirm_pw_lbl="请输入密码以确认",
        err_delete_pw="密码错误，账号未删除。",
        jan="一月", feb="二月", mar="三月", apr="四月",
        may_m="五月", jun="六月", jul="七月", aug="八月",
        sep="九月", oct_m="十月", nov="十一月", dec="十二月",
        # NEW: Tuition Packet System
        tuition_rules_title="学费支付规则",
        packet_session="次付套餐",
        packet_monthly="月付套餐",
        packet_session_desc="按上课次数付费 (75,000 印尼盾/节)。适合时间不固定的学生。",
        packet_monthly_desc="固定月费 (500,000 印尼盾/月)。无论是否缺课或调课，每月均需支付全额学费。",
        warning_monthly_policy="⚠️ 月付政策：选择月付套餐的学生，即使缺课或调课，每月仍需支付全额学费。这是为了保障老师的稳定收入。",
        select_packet_type="选择套餐类型",
        current_fee="当前费用",
        remember_me="在此设备上记住我",
        nav_classes="课程",
        nav_attendance="出勤",
        nav_attend_short="出勤",
        nav_students="学生",
        nav_receipts="收据",
        nav_progress="进度",
        nav_settings="设置",
        nav_quiz="测验",
        teacher_tag="教师面板",
        student_tag="学生面板",
        page_classes_sub_teacher="安排并管理你的课程",
        page_classes_sub_student="老师安排的即将开始的课程",
        page_attendance_sub="手动添加课时，并追踪学生进度",
        progress_sub_student="你当前的计费周期",
        settings_sub_teacher="管理你的账户和付款设置",
        settings_sub_student="管理你的账户",
        student_count_one="已注册 {n} 位学生",
        student_count_many="已注册 {n} 位学生",
        receipts_summary="共 {total} 张 · 未付 {unpaid} 张",
        receipts_total_student="共 {n} 张收据",
        language_lbl="语言",
        show_password="显示密码",
        hide_password="隐藏密码",
        monthly_policy="月付政策",
        monthly_policy_desc="月付套餐的学生，无论是否改期或缺课，每月都需付款。这样可以保证老师的收入稳定。",
        per_session="按课时",
        per_month="按月",
        quiz_soon_badge="即将推出",
        quiz_teacher_head="给学生布置测验",
        quiz_teacher_desc="很快你就能在这里创建中文测验，分配给你的学生，并查看他们的成绩。",
        quiz_student_head="老师布置的测验",
        quiz_student_desc="很快老师会在这里给你发送中文测验，你可以作答并立即看到成绩。",
        quiz_planned="计划中的功能",
        quiz_f_types="多种题型：填空、汉字与拼音互转、句子排序",
        quiz_f_assign="把测验分配给指定的学生",
        quiz_f_scores="查看每位学生的成绩",
        quiz_f_timer="整份测验共用一个总时间",
        quiz_f_streak="连续答对时有连击反馈",
        quiz_back="返回面板",
    ),
}

QUOTES: list[dict] = [
    {"zh": "千里之行，始于足下。", "py": "Qiānlǐ zhī xíng, shǐ yú zú xià.", "en": "A journey of a thousand miles begins with a single step."},
    {"zh": "学而不思则罔，思而不学则殆。", "py": "Xué ér bù sī zé wǎng, sī ér bù xué zé dài.", "en": "Learning without thought is wasted; thought without learning is dangerous."},
    {"zh": "不积跬步，无以至千里。", "py": "Bù jī kuǐbù, wúyǐ zhì qiānlǐ.", "en": "Without small steps, one cannot travel a thousand miles."},
    {"zh": "温故而知新。", "py": "Wēn gù ér zhī xīn.", "en": "Review the old and you will discover something new."},
    {"zh": "知之者不如好之者，好之者不如乐之者。", "py": "Zhī zhī zhě bù rú hào zhī zhě.", "en": "To know is not as good as to love; to love is not as good as to delight in."},
    {"zh": "三人行，必有我师焉。", "py": "Sān rén xíng, bì yǒu wǒ shī yān.", "en": "Among three people, one is always my teacher."},
    {"zh": "书山有路勤为径，学海无涯苦作舟。", "py": "Shū shān yǒu lù qín wéi jìng.", "en": "Diligence is the path up the mountain of books."},
    {"zh": "敏而好学，不耻下问。", "py": "Mǐn ér hào xué, bù chǐ xià wèn.", "en": "Be eager to learn and unashamed to ask questions."},
    {"zh": "学无止境。", "py": "Xué wú zhǐ jìng.", "en": "There is no end to learning."},
    {"zh": "勤能补拙。", "py": "Qín néng bǔ zhuō.", "en": "Diligence can make up for lack of talent."},
]

_MONTH_KEYS = ["jan","feb","mar","apr","may_m","jun","jul","aug","sep","oct_m","nov","dec"]
_DAY_KEYS   = ["mon","tue","wed","thu","fri","sat","sun"]

# ── Public helpers ────────────────────────────────────────────────────────────

def get_lang() -> str:
    return session.get("lang", "en")

def get_translations(lang: str) -> dict:
    return TRANSLATIONS.get(lang, TRANSLATIONS["en"])

def tr(key, default=None):
    """Translate a key based on the current session language."""
    lang = get_lang()
    translations = get_translations(lang)
    if key in translations:
        return translations[key]
    return default if default is not None else key

def to_wib(dt: datetime) -> datetime:
    return dt + timedelta(hours=7)

def fmt_date(dt: datetime, lang: str | None = None) -> str:
    if lang is None:
        lang = get_lang()
    tbl = TRANSLATIONS[lang]
    day_name = tbl.get(_DAY_KEYS[dt.weekday()], "")
    month_name = tbl.get(_MONTH_KEYS[dt.month - 1], "")
    if lang == "zh":
        return f"{dt.year}年{month_name}{dt.day}日（{day_name}）{dt.hour:02d}:{dt.minute:02d}"
    return f"{day_name}, {dt.day:02d} {month_name} {dt.year}  {dt.hour:02d}:{dt.minute:02d}"

def fmt_idr(amount: int) -> str:
    return f"{amount:,}".replace(",", ".")

def parse_raw_dates(raw: str) -> list[datetime]:
    if not raw:
        return []
    result = []
    for part in raw.split("|"):
        part = part.strip()
        # Clean up 'Z' if present, to be safe
        if part.endswith("Z"):
            part = part[:-1] + "+00:00"
        if part:
            try:
                # FIX: Use fromisoformat which handles microseconds automatically! 🎯
                result.append(datetime.fromisoformat(part))
            except ValueError:
                pass
    return result

def random_quote() -> dict:
    return random.choice(QUOTES)
