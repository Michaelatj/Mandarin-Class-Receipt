"""
services/i18n.py — Internationalisation helpers.

Translations, date formatting, and quote data all live here so
routes and templates stay clean.
"""
import random
from datetime import datetime
from flask import session

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
    ),
}

QUOTES: list[dict] = [
    {"zh": "千里之行，始于足下。",
     "py": "Qiānlǐ zhī xíng, shǐ yú zú xià.",
     "en": "A journey of a thousand miles begins with a single step."},
    {"zh": "学而不思则罔，思而不学则殆。",
     "py": "Xué ér bù sī zé wǎng, sī ér bù xué zé dài.",
     "en": "Learning without thought is wasted; thought without learning is dangerous."},
    {"zh": "不积跬步，无以至千里。",
     "py": "Bù jī kuǐbù, wúyǐ zhì qiānlǐ.",
     "en": "Without small steps, one cannot travel a thousand miles."},
    {"zh": "温故而知新。",
     "py": "Wēn gù ér zhī xīn.",
     "en": "Review the old and you will discover something new."},
    {"zh": "知之者不如好之者，好之者不如乐之者。",
     "py": "Zhī zhī zhě bù rú hào zhī zhě.",
     "en": "To know is not as good as to love; to love is not as good as to delight in."},
    {"zh": "三人行，必有我师焉。",
     "py": "Sān rén xíng, bì yǒu wǒ shī yān.",
     "en": "Among three people, one is always my teacher."},
    {"zh": "书山有路勤为径，学海无涯苦作舟。",
     "py": "Shū shān yǒu lù qín wéi jìng.",
     "en": "Diligence is the path up the mountain of books."},
    {"zh": "敏而好学，不耻下问。",
     "py": "Mǐn ér hào xué, bù chǐ xià wèn.",
     "en": "Be eager to learn and unashamed to ask questions."},
    {"zh": "学无止境。", "py": "Xué wú zhǐ jìng.", "en": "There is no end to learning."},
    {"zh": "勤能补拙。", "py": "Qín néng bǔ zhuō.",
     "en": "Diligence can make up for lack of talent."},
]

_MONTH_KEYS = ["jan","feb","mar","apr","may_m","jun",
               "jul","aug","sep","oct_m","nov","dec"]
_DAY_KEYS   = ["mon","tue","wed","thu","fri","sat","sun"]


# ── Public helpers ────────────────────────────────────────────────────────────

def get_lang() -> str:
    return session.get("lang", "en")


def tr(key: str) -> str:
    """Return the translated string for key in the current session language."""
    lang = get_lang()
    return TRANSLATIONS[lang].get(key, TRANSLATIONS["en"].get(key, key))


def to_wib(dt: datetime) -> datetime:
    """Convert a UTC datetime to WIB (UTC+7). All display should go through this."""
    from datetime import timedelta
    return dt + timedelta(hours=7)


def fmt_date(dt: datetime, lang: str | None = None) -> str:
    """
    Format a datetime with localised day name, e.g.:
      EN → "Monday, 15 January 2025  14:30"
      ZH → "2025年一月15日（星期一）14:30"
    """
    if lang is None:
        lang = get_lang()
    tbl        = TRANSLATIONS[lang]
    day_name   = tbl.get(_DAY_KEYS[dt.weekday()], "")
    month_name = tbl.get(_MONTH_KEYS[dt.month - 1], "")
    if lang == "zh":
        return f"{dt.year}年{month_name}{dt.day}日（{day_name}）{dt.hour:02d}:{dt.minute:02d}"
    return f"{day_name}, {dt.day:02d} {month_name} {dt.year}  {dt.hour:02d}:{dt.minute:02d}"


def fmt_idr(amount: int) -> str:
    """Format an integer as Indonesian Rupiah, e.g. 500000 → '500.000'."""
    return f"{amount:,}".replace(",", ".")


def parse_raw_dates(raw: str) -> list[datetime]:
    """Parse a pipe-separated string of ISO-8601 timestamps into datetime objects."""
    if not raw:
        return []
    result = []
    for part in raw.split("|"):
        part = part.strip()
        if part:
            try:
                result.append(datetime.strptime(part, "%Y-%m-%dT%H:%M:%S"))
            except ValueError:
                pass
    return result


def random_quote() -> dict:
    """Return a random motivational Chinese quote."""
    return random.choice(QUOTES)
