import re
import secrets

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import get_password_hash
from app.models import BusinessPartner, Employee, User


PINYIN_FALLBACK = {
    "吴": "wu", "臻": "zhen", "清": "qing", "张": "zhang", "張": "zhang", "王": "wang", "李": "li", "赵": "zhao",
    "趙": "zhao", "陈": "chen", "陳": "chen", "刘": "liu", "劉": "liu", "杨": "yang", "楊": "yang", "黄": "huang",
    "周": "zhou", "徐": "xu", "孙": "sun", "孫": "sun", "马": "ma", "馬": "ma", "朱": "zhu", "胡": "hu",
    "郭": "guo", "何": "he", "高": "gao", "林": "lin", "罗": "luo", "羅": "luo", "郑": "zheng", "鄭": "zheng",
    "梁": "liang", "谢": "xie", "謝": "xie", "宋": "song", "唐": "tang", "许": "xu", "許": "xu", "韩": "han",
    "韓": "han", "冯": "feng", "馮": "feng", "邓": "deng", "鄧": "deng", "曹": "cao", "彭": "peng", "曾": "zeng",
    "肖": "xiao", "田": "tian", "董": "dong", "袁": "yuan", "潘": "pan", "于": "yu", "蒋": "jiang", "蔣": "jiang",
    "蔡": "cai", "余": "yu", "杜": "du", "叶": "ye", "葉": "ye", "程": "cheng", "魏": "wei", "苏": "su",
    "蘇": "su", "吕": "lv", "呂": "lv", "丁": "ding", "任": "ren", "沈": "shen", "姚": "yao", "卢": "lu",
    "盧": "lu", "姜": "jiang", "崔": "cui", "钟": "zhong", "鍾": "zhong", "谭": "tan", "譚": "tan", "陆": "lu",
    "陸": "lu", "汪": "wang", "范": "fan", "金": "jin", "石": "shi", "廖": "liao", "贾": "jia", "賈": "jia",
    "夏": "xia", "韦": "wei", "韋": "wei", "付": "fu", "方": "fang", "白": "bai", "邹": "zou", "鄒": "zou",
    "孟": "meng", "秦": "qin", "邱": "qiu", "江": "jiang", "尹": "yin", "薛": "xue", "闫": "yan", "閆": "yan",
    "段": "duan", "雷": "lei", "侯": "hou", "龙": "long", "龍": "long", "史": "shi", "陶": "tao", "黎": "li",
    "贺": "he", "賀": "he", "顾": "gu", "顧": "gu", "毛": "mao", "郝": "hao", "龚": "gong", "龔": "gong",
    "邵": "shao", "万": "wan", "萬": "wan", "钱": "qian", "錢": "qian", "严": "yan", "嚴": "yan", "覃": "qin",
    "武": "wu", "戴": "dai", "莫": "mo", "孔": "kong", "向": "xiang", "汤": "tang", "湯": "tang",
    "子": "zi", "豪": "hao", "明": "ming", "华": "hua", "華": "hua", "伟": "wei", "偉": "wei", "芳": "fang",
    "娜": "na", "敏": "min", "静": "jing", "麗": "li", "丽": "li", "强": "qiang", "強": "qiang", "磊": "lei",
    "军": "jun", "軍": "jun", "洋": "yang", "勇": "yong", "艳": "yan", "艷": "yan", "杰": "jie", "傑": "jie",
}

COMPOUND_SURNAMES = ["欧阳", "歐陽", "司马", "司馬", "上官", "诸葛", "諸葛", "东方", "東方", "夏侯", "皇甫", "尉迟", "尉遲"]


def pinyin_parts(text: str) -> list[str]:
    try:
        from pypinyin import Style, lazy_pinyin

        return [part for part in lazy_pinyin(text, style=Style.NORMAL, errors="ignore") if part]
    except Exception:
        parts: list[str] = []
        for char in text:
            if char in PINYIN_FALLBACK:
                parts.append(PINYIN_FALLBACK[char])
            elif char.isascii() and char.isalnum():
                parts.append(char.lower())
        return parts


def normalize_ascii(value: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "", value.lower())
    return text


def split_chinese_name(full_name: str) -> tuple[str, str]:
    compact = re.sub(r"[\s\u3000]+", "", full_name)
    for surname in COMPOUND_SURNAMES:
        if compact.startswith(surname) and len(compact) > len(surname):
            return surname, compact[len(surname):]
    if len(compact) >= 2:
        return compact[0], compact[1:]
    return compact, "user"


def platform_account_base(full_name: str, employee_id: int | None = None) -> str:
    surname, given = split_chinese_name(full_name)
    surname_part = normalize_ascii("".join(pinyin_parts(surname)))
    given_part = normalize_ascii("".join(pinyin_parts(given)))
    if not surname_part:
        surname_part = "employee"
    if not given_part:
        given_part = str(employee_id or "user")
    return f"{surname_part}_{given_part}"


def unique_platform_email(db: Session, full_name: str, employee_id: int | None = None) -> str:
    base = platform_account_base(full_name, employee_id)
    domain = "nit-g.co.jp"
    candidate = f"{base}@{domain}"
    suffix = 2
    while db.scalar(select(User).where(User.email == candidate)):
        candidate = f"{base}{suffix}@{domain}"
        suffix += 1
    return candidate


def reusable_platform_user(db: Session, full_name: str, employee_id: int | None = None) -> User | None:
    base = platform_account_base(full_name, employee_id)
    email = f"{base}@nit-g.co.jp"
    return db.scalar(
        select(User).where(
            User.email == email,
            User.role == "employee",
            User.employee_id.is_(None),
            User.is_active.is_(False),
        )
    )


def ensure_employee_user(db: Session, employee: Employee, must_reset_password: bool = True) -> User:
    settings = get_settings()
    user = db.scalar(select(User).where(User.employee_id == employee.id))
    if user:
        was_inactive = not user.is_active
        user.full_name = employee.full_name
        user.is_active = True
        if must_reset_password and was_inactive:
            user.password_hash = get_password_hash(settings.default_employee_password)
            user.must_reset_password = True
        return user

    reusable_user = reusable_platform_user(db, employee.full_name, employee.id)
    if reusable_user:
        reusable_user.full_name = employee.full_name
        reusable_user.employee_id = employee.id
        reusable_user.is_active = True
        reusable_user.password_hash = get_password_hash(settings.default_employee_password)
        reusable_user.must_reset_password = must_reset_password
        return reusable_user

    email = unique_platform_email(db, employee.full_name, employee.id)
    user = User(
        email=email,
        full_name=employee.full_name,
        role="employee",
        password_hash=get_password_hash(settings.default_employee_password),
        must_reset_password=must_reset_password,
        employee_id=employee.id,
    )
    db.add(user)
    return user


KANA_ROMAJI = {
    "ア": "a", "イ": "i", "ウ": "u", "エ": "e", "オ": "o",
    "カ": "ka", "キ": "ki", "ク": "ku", "ケ": "ke", "コ": "ko",
    "サ": "sa", "シ": "shi", "ス": "su", "セ": "se", "ソ": "so",
    "タ": "ta", "チ": "chi", "ツ": "tsu", "テ": "te", "ト": "to",
    "ナ": "na", "ニ": "ni", "ヌ": "nu", "ネ": "ne", "ノ": "no",
    "ハ": "ha", "ヒ": "hi", "フ": "fu", "ヘ": "he", "ホ": "ho",
    "マ": "ma", "ミ": "mi", "ム": "mu", "メ": "me", "モ": "mo",
    "ヤ": "ya", "ユ": "yu", "ヨ": "yo",
    "ラ": "ra", "リ": "ri", "ル": "ru", "レ": "re", "ロ": "ro",
    "ワ": "wa", "ヲ": "wo", "ン": "n",
    "ガ": "ga", "ギ": "gi", "グ": "gu", "ゲ": "ge", "ゴ": "go",
    "ザ": "za", "ジ": "ji", "ズ": "zu", "ゼ": "ze", "ゾ": "zo",
    "ダ": "da", "ヂ": "ji", "ヅ": "zu", "デ": "de", "ド": "do",
    "バ": "ba", "ビ": "bi", "ブ": "bu", "ベ": "be", "ボ": "bo",
    "パ": "pa", "ピ": "pi", "プ": "pu", "ペ": "pe", "ポ": "po",
    "ャ": "ya", "ュ": "yu", "ョ": "yo", "ッ": "", "ー": "",
}


def kana_to_romaji(value: str) -> str:
    text = "".join(chr(ord(char) + 0x60) if "ぁ" <= char <= "ゖ" else char for char in value)
    result: list[str] = []
    for index, char in enumerate(text):
        if char == "ッ" and index + 1 < len(text):
            next_part = KANA_ROMAJI.get(text[index + 1], "")
            if next_part:
                result.append(next_part[0])
            continue
        if char in {"ャ", "ュ", "ョ"} and result:
            result[-1] = result[-1].rstrip("i") + KANA_ROMAJI[char]
            continue
        result.append(KANA_ROMAJI.get(char, char if char.isascii() else ""))
    return "".join(result)


def partner_login_base(partner: BusinessPartner) -> str:
    attrs = partner.attributes or {}
    source = attrs.get("company_kana") or partner.company_name
    romanized = kana_to_romaji(str(source))
    if not normalize_ascii(romanized):
        romanized = "".join(pinyin_parts(str(source)))
    slug = normalize_ascii(romanized)
    if not slug:
        slug = f"company{partner.id or 'partner'}"
    return f"NIT_PARTNER_{slug.upper()}"


def unique_partner_login_id(db: Session, partner: BusinessPartner) -> str:
    base = partner_login_base(partner)
    candidate = base
    suffix = 2
    while db.scalar(select(User).where(User.login_id == candidate)):
        candidate = f"{base}_{suffix}"
        suffix += 1
    return candidate


def ensure_partner_user(db: Session, partner: BusinessPartner, must_reset_password: bool = True) -> tuple[User, str | None]:
    user = db.scalar(select(User).where(User.partner_id == partner.id, User.role == "partner"))
    if user:
        user.full_name = partner.company_name
        user.is_active = True
        if not user.login_id:
            user.login_id = unique_partner_login_id(db, partner)
        return user, None

    login_id = unique_partner_login_id(db, partner)
    temporary_password = secrets.token_urlsafe(12)
    user = User(
        email=f"{login_id.lower()}@partner.nit-g.co.jp",
        login_id=login_id,
        full_name=partner.company_name,
        role="partner",
        password_hash=get_password_hash(temporary_password),
        must_reset_password=must_reset_password,
        partner_id=partner.id,
    )
    db.add(user)
    return user, temporary_password
