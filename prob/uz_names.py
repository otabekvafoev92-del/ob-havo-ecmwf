"""Official Uzbek (Latin) names of Uzbekistan's districts and towns, and a Cyrillic → Uzbek Latin transliteration for everything else.
O‘ and g‘ are written with U+2018 (‘), the tutuq belgisi with U+2019 (’): every font of the bot and the videos has both."""
import re

# the Russian district / town stem → the Uzbek name
UZ = {
 'Термез': 'Termiz', 'Нурата': 'Nurota', 'Навои': 'Navoiy', 'Джондор': 'Jondor', 'Бухара': 'Buxoro', 'Алат': 'Olot', 'Каракул': 'Qorako‘l',
 'Касби': 'Kasbi', 'Миришкар': 'Mirishkor', 'Нишан': 'Nishon', 'Мубарек': 'Muborak', 'Караулбазар': 'Qorovulbozor', 'Нурабад': 'Nurobod',
 'Шафиркан': 'Shofirkon', 'Рамитан': 'Romitan', 'Пешку': 'Peshku', 'Каган': 'Kogon', 'Кизилтепа': 'Qiziltepa', 'Пахтачи': 'Paxtachi',
 'Гидждуван': 'G‘ijduvon', 'Вабкент': 'Vobkent', 'Кармана': 'Karmana', 'Навбахор': 'Navbahor', 'Китаб': 'Kitob', 'Камаши': 'Qamashi',
 'Карши': 'Qarshi', 'Гузар': 'G‘uzor', 'Дехканабад': 'Dehqonobod', 'Касан': 'Koson', 'Чиракчи': 'Chiroqchi', 'Байсун': 'Boysun',
 'Музрабад': 'Muzrabot', 'Шерабад': 'Sherobod', 'Ангор': 'Angor', 'Яккабаг': 'Yakkabog‘', 'Шахрисабз': 'Shahrisabz', 'Пастдаргом': 'Pastdarg‘om',
 'Иштихан': 'Ishtixon', 'Нарпай': 'Narpay', 'Каттакурган': 'Kattaqo‘rg‘on', 'Хатирчи': 'Xatirchi', 'Кошрабад': 'Qo‘shrabot', 'Самарканд': 'Samarqand',
 'Ургут': 'Urgut', 'Тайлак': 'Tayloq', 'Джамбай': 'Jomboy', 'Паярик': 'Payariq', 'Акдаря': 'Oqdaryo', 'Фариш': 'Forish', 'Галляарал': 'G‘allaorol',
 'Хива': 'Xiva', 'Караузяк': 'Qorao‘zak', 'Кунград': 'Qo‘ng‘irot', 'Шават': 'Shovot', 'Кошкупир': 'Qo‘shko‘pir', 'Амударя': 'Amudaryo',
 'Гурлен': 'Gurlan', 'Чимбай': 'Chimboy', 'Канликул': 'Qanliko‘l', 'Шуманай': 'Shumanay', 'Ходжейли': 'Xo‘jayli', 'Кегейли': 'Kegeyli',
 'Муйнак': 'Mo‘ynoq', 'Нукус': 'Nukus', 'Тахтакупир': 'Taxtako‘pir', 'Турткул': 'To‘rtko‘l', 'Учкудук': 'Uchquduq', 'Хазарасп': 'Hazorasp',
 'Канимех': 'Konimex', 'Тамди': 'Tomdi', 'Елликкала': 'Ellikqal’a', 'Ханка': 'Xonqa', 'Янгиарик': 'Yangiariq', 'Багат': 'Bog‘ot',
 'Ургенч': 'Urganch', 'Беруний': 'Beruniy', 'Янгибазар': 'Yangibozor', 'Зарафшан': 'Zarafshon', 'Багдад': 'Bag‘dod', 'Янгиабад': 'Yangiobod',
 'Сариасийа': 'Sariosiyo', 'Сариасия': 'Sariosiyo', 'Джаркурган': 'Jarqo‘rg‘on', 'Кизирик': 'Qiziriq', 'Шурчи': 'Sho‘rchi', 'Кумкурган': 'Qumqo‘rg‘on',
 'Узун': 'Uzun', 'Алтинсай': 'Oltinsoy', 'Денау': 'Denov', 'Джизак': 'Jizzax', 'Бахмал': 'Baxmal', 'Булунгур': 'Bulung‘ur',
 'Шароф Рашидов': 'Sharof Rashidov', 'Зафарабад': 'Zafarobod', 'Зарбдар': 'Zarbdor', 'Заамин': 'Zomin', 'Сардоба': 'Sardoba', 'Пахтакор': 'Paxtakor',
 'Дустлик': 'Do‘stlik', 'Хавас': 'Xovos', 'Мирзаабад': 'Mirzaobod', 'Бекабад': 'Bekobod', 'Узбекистан': 'O‘zbekiston', 'Бешарик': 'Beshariq',
 'Сох': 'So‘x', 'Фергана': 'Farg‘ona', 'Баяут': 'Boyovut', 'Ширин': 'Shirin', 'Янгийер': 'Yangiyer', 'Риштан': 'Rishton', 'Алтиарик': 'Oltiariq',
 'Учкуприк': 'Uchko‘prik', 'Кувасай': 'Quvasoy', 'Пап': 'Pop', 'Уртачирчик': 'O‘rtachirchiq', 'Гулистан': 'Guliston', 'Сайхунабад': 'Sayxunobod',
 'Мирзачул': 'Mirzacho‘l', 'Арнасай': 'Arnasoy', 'Акалтин': 'Oqoltin', 'Сирдаря': 'Sirdaryo', 'Сырдарья': 'Sirdaryo', 'Куйичирчик': 'Quyichirchiq', 'Чиназ': 'Chinoz',
 'Ахангаран': 'Ohangaron', 'Бука': 'Bo‘ka', 'Аккурган': 'Oqqo‘rg‘on', 'Пскент': 'Piskent', 'Алмалик': 'Olmaliq', 'Алмалык': 'Olmaliq', 'Бектемир': 'Bektemir',
 'Сергели': 'Sergeli', 'Янгийул': 'Yangiyo‘l', 'Янгиюль': 'Yangiyo‘l', 'Зангиата': 'Zangiota', 'Чиланзар': 'Chilonzor', 'Учтепа': 'Uchtepa', 'Ташкент': 'Toshkent',
 'Яккасарай': 'Yakkasaroy', 'Алмазар': 'Olmazor', 'Шайхантохур': 'Shayxontohur', 'Юнусабад': 'Yunusobod', 'Юкаричирчик': 'Yuqorichirchiq',
 'Паркент': 'Parkent', 'Ангрен': 'Angren', 'Кибрай': 'Qibray', 'Яшнобод': 'Yashnobod', 'Мирабад': 'Mirobod', 'Мирзо Улугбек': 'Mirzo Ulug‘bek',
 'Бостанлик': 'Bo‘stonliq', 'Чирчик': 'Chirchiq', 'Андиджан': 'Andijon', 'Андижан': 'Andijon', 'Улугнар': 'Ulug‘nor', 'Коканд': 'Qo‘qon', 'Фуркат': 'Furqat',
 'Куштепа': 'Qo‘shtepa', 'Бувайда': 'Buvayda', 'Дангара': 'Dang‘ara', 'Язяван': 'Yozyovon', 'Мингбулак': 'Mingbuloq', 'Хадджаабад': 'Xo‘jaobod',
 'Ходжаабад': 'Xo‘jaobod', 'Кува': 'Quva', 'Ташлак': 'Toshloq', 'Маргилан': 'Marg‘ilon', 'Мархамат': 'Marhamat', 'Асака': 'Asaka', 'Шахрихан': 'Shahrixon',
 'Боз': 'Bo‘z', 'Дджалалкудук': 'Jalaquduq', 'Джалалкудук': 'Jalaquduq', 'Булакбаши': 'Buloqboshi', 'Кургантепа': 'Qo‘rg‘ontepa', 'Нарин': 'Norin',
 'Чуст': 'Chust', 'Наманган': 'Namangan', 'Туракурган': 'To‘raqo‘rg‘on', 'Баликчи': 'Baliqchi', 'Янгикурган': 'Yangiqo‘rg‘on', 'Касансай': 'Kosonsoy',
 'Уйчи': 'Uychi', 'Чартак': 'Chortoq', 'Ханабад': 'Xonobod', 'Алтинкул': 'Oltinko‘l', 'Учкурган': 'Uchqo‘rg‘on', 'Избоскан': 'Izboskan',
 'Пахтаабад': 'Paxtaobod', 'Нурафшон': 'Nurafshon', 'Хорезм': 'Xorazm', 'Каракалпакстан': 'Qoraqalpog‘iston', 'Сурхандарья': 'Surxondaryo',
 'Кашкадарья': 'Qashqadaryo', 'Искандер': 'Iskandar', 'Газалкент': 'G‘azalkent', 'Карасу': 'Qorasuv', 'Шурчи ': 'Sho‘rchi', 'Галаба': 'G‘alaba',
 'Хаккулабад': 'Haqqulobod', 'Пайтуг': 'Paytug‘', 'Тойтепа': 'To‘ytepa', 'Келес': 'Keles', 'Гиждуван': 'G‘ijduvon', 'Амирсой': 'Amirsoy', 'Чимган': 'Chimyon',
 'Чарвак': 'Chorvoq', 'Бричмулла': 'Burchmulla', 'Бештерек': 'Beshterak', 'Нукус ': 'Nukus', 'Тахиаташ': 'Taxiatosh', 'Бустан': 'Bo‘ston', 'Мангит': 'Mang‘it',
}

C2L = {'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo', 'ж': 'j', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm', 'н': 'n',
       'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u', 'ф': 'f', 'х': 'x', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sh', 'ъ': '’', 'ы': 'i', 'ь': '',
       'э': 'e', 'ю': 'yu', 'я': 'ya', 'ў': 'o‘', 'қ': 'q', 'ғ': 'g‘', 'ҳ': 'h', 'ә': 'a', 'ө': 'o‘', 'ү': 'u', 'ң': 'ng', 'і': 'i', 'һ': 'h', 'ұ': 'u'}


def translit(s):
    """Cyrillic (Russian, Uzbek, Kazakh) → Uzbek Latin; дж → j, е at a word's start → ye."""
    s = re.sub(r'(?i)дж', lambda m: 'Ж' if m.group()[0].isupper() else 'ж', s)
    out, prev = [], ' '
    for ch in s:
        lo = ch.lower(); r = C2L.get(lo)
        if r is None: out.append(ch); prev = ch; continue
        if lo == 'е' and not prev.isalpha(): r = 'ye'
        if ch.isupper() and r: r = r[0].upper() + r[1:]
        out.append(r); prev = ch
    return ''.join(out)


def fix_apos(s):
    """o' g' o` oʻ … → o‘ g‘; the other apostrophes → ’"""
    s = re.sub(r"([OoGg])['`’ʻʼ´]", r'\1‘', s)
    return re.sub(r"(?<=\w)['`ʻʼ´](?=\w)", '’', s)


def district(ru):
    """'Каттакурган р-н' → 'Kattaqo‘rg‘on tumani', 'г. Джизак' → 'Jizzax shahri', 'Балхашский район' → 'Balxash tumani'"""
    t = ru.strip()
    city = t.startswith('г.') or t.startswith('город ')
    t = re.sub(r'^(г\.|город)\s*', '', t)
    t = re.sub(r'\s*(р-н|район|р\.)\.?$', '', t).strip()
    t = re.sub(r'(ский|ской|ский)$', '', t).replace('ская обл.', '').strip()
    base = UZ.get(t) or fix_apos(translit(t))
    return f"{base} {'shahri' if city else 'tumani'}"


def uz_name(p):
    """A place of geo_*.json in Uzbek: the bot's own list, the official Uzbek name of a town in Uzbekistan, else the Russian name in Uzbek letters."""
    try:
        from regions import UZ_CITY
    except Exception:
        UZ_CITY = {}
    en, ru = p.get('en') or '', p.get('ru') or ''
    if en in UZ_CITY: return fix_apos(UZ_CITY[en])
    if ru in UZ: return UZ[ru]
    return fix_apos(translit(ru)) if ru else fix_apos(en)
