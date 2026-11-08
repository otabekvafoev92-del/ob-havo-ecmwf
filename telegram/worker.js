// Osmon Telegram bot (Cloudflare Workers, free plan).
//  • Private chat: /start → language → country/continent → today & tomorrow, by days, 15-day videos, the site as a Mini App.
//  • Groups and channels: add the bot (as admin in a channel) and it posts the forecast by itself after every update
//    every day at the hour the group picked (default 07:00 Tashkent). An admin picks the language, one or several
//    countries and the hour with /sozla (/settings). Each post: 3 videos + today/tomorrow/next days + weather by city.
//  • /help: instructions in Uzbek, Russian and Turkish.
//  • /hit and /stats: anonymous visit counter for the website (daily totals per country and city).
// Everything is read from the website built by GitHub Actions (SITE_URL/prob/manifest.json and the .mp4 files).
// Settings (Workers → Settings): BOT_TOKEN (secret), SITE_URL (variable), D1 database bound as DB,
// cron trigger (e.g. every 20 minutes) for the automatic group posts.
// Connect once: open <worker URL>/setup in a browser (webhook, command menus, bot description).

const NAMES = {
  world: { uz: 'Butun dunyo', ru: 'Весь мир', tr: 'Tüm dünya' }, EU: { uz: 'Yevropa', ru: 'Европа', tr: 'Avrupa' }, AS: { uz: 'Osiyo', ru: 'Азия', tr: 'Asya' },
  AF: { uz: 'Afrika', ru: 'Африка', tr: 'Afrika' }, NA: { uz: 'Shimoliy Amerika', ru: 'Северная Америка', tr: 'Kuzey Amerika' },
  SA: { uz: 'Janubiy Amerika', ru: 'Южная Америка', tr: 'Güney Amerika' }, OC: { uz: 'Okeaniya', ru: 'Океания', tr: 'Okyanusya' },
  cis: { uz: 'MDH va Turkiya', ru: 'СНГ и Турция', tr: 'BDT ve Türkiye' }, UZ: { uz: 'O‘zbekiston', ru: 'Узбекистан', tr: 'Özbekistan' },
  KZ: { uz: 'Qozog‘iston', ru: 'Казахстан', tr: 'Kazakistan' }, KG: { uz: 'Qirg‘iziston', ru: 'Кыргызстан', tr: 'Kırgızistan' },
  TJ: { uz: 'Tojikiston', ru: 'Таджикистан', tr: 'Tacikistan' }, TM: { uz: 'Turkmaniston', ru: 'Туркменистан', tr: 'Türkmenistan' },
  AZ: { uz: 'Ozarbayjon', ru: 'Азербайджан', tr: 'Azerbaycan' }, AM: { uz: 'Armaniston', ru: 'Армения', tr: 'Ermenistan' },
  BY: { uz: 'Belarus', ru: 'Беларусь', tr: 'Belarus' }, MD: { uz: 'Moldova', ru: 'Молдова', tr: 'Moldova' },
  RU: { uz: 'Rossiya', ru: 'Россия', tr: 'Rusya' }, TR: { uz: 'Turkiya', ru: 'Турция', tr: 'Türkiye' },
};
const FLAG = { world: '🌍', EU: '🌍', AF: '🌍', AS: '🌏', OC: '🌏', NA: '🌎', SA: '🌎', cis: '🗺', UZ: '🇺🇿', KZ: '🇰🇿', KG: '🇰🇬', TJ: '🇹🇯', TM: '🇹🇲', AZ: '🇦🇿', AM: '🇦🇲', BY: '🇧🇾', MD: '🇲🇩', RU: '🇷🇺', TR: '🇹🇷' };
const GROUPS = [['UZ', 'KZ', 'KG'], ['TJ', 'TM', 'AZ'], ['AM', 'BY', 'MD'], ['RU', 'TR', 'cis'], ['world', 'EU', 'AS'], ['AF', 'NA', 'SA'], ['OC']];
const T = {
  uz: {
    cities: '🏙 Shaharlar', cPick: '🏙 Shaharni tanlang:', cTitle: '🏙 Bugun shaharlarda', time: '⏰ Guruhga prognoz qaysi vaqtda yuborilsin? (Toshkent vaqti)', help: 'ℹ️ Yordam',
    d15: '15 kunlik prognoz', hi: '☀️ <b>Osmon</b> — ob-havo prognozi\n6 ta model (ECMWF, NOAA) asosida 15 kunga.\n\nTilni tanlang:', pick: '📍 Davlat yoki qit’ani tanlang:',
    menu: 'Nimani ko‘rsatay?', today: '⏱ Bugun va ertaga soatma-soat', all: '🎬 15 kunlik video', days: '🗓 15 kun', site: '🗺 Sayt va globus', rep: '📊 Hisobot', menuHint: '⌨️ Barcha bo‘limlar — pastdagi tugmalarda.\n📍 Joylashuvni yuboring yoki shahar nomini yozing, masalan: Namangan', locAsk: '📍 Pastdagi tugmani bosing — joylashuvingiz yuboriladi.',
    back: '↩️ Davlatlar', none: '⏳ Ma’lumot hali tayyor emas, birozdan keyin urinib ko‘ring.', tdy: 'Bugun', tmw: 'Ertaga', next: 'Keyingi kunlar',
    upd: 'Yangilandi', swipe: '🎬 Videoni suring: 🌧 yog‘in · 🌡 harorat · ☁️ bulutlar · 💨 shamol', bot: '🤖 Bot',
    gHi: '👋 Salom! Men har kuni shu yerga ob-havoni video bilan yuboraman.\nGuruh admini: til, davlat va vaqtni tanlang 👇 (/sozla)',
    gSet: '✅ Tayyor! Har kuni soat {time} da (Toshkent vaqti) bu chatga prognoz yuboriladi: <b>{name}</b> ({lang}).\nO‘zgartirish: /sozla', gMulti: '📍 Davlatlarni tanlang (bir nechtasini ham), so‘ng «Tayyor» tugmasini bosing:', done: '✅ Tayyor', gNone: 'Kamida bitta davlatni tanlang.', gAdm: '⚙️ Guruh sozlamalarini faqat shu guruhning admini o‘zgartira oladi. Undan /sozla yozishini so‘rang.', gLang: 'Tilni tanlang:', lang: 'o‘zbekcha',
    pdf: '📄 Yo‘riqnoma (PDF)', adm: '✉️ Adminga yozish', admAsk: '✍️ Bot adminiga xabaringizni yozing (matn, rasm yoki ovozli xabar) — men uni yetkazaman.\nBekor qilish: /cancel', admSent: '✅ Xabaringiz adminga yuborildi. Javob shu chatga keladi.', admAns: '💬 Admin javobi:', admOff: 'Admin hali ulanmagan, keyinroq urinib ko‘ring.', cancel: 'Bekor qilindi.', guideCap: '📄 Osmon bot — to‘liq yo‘riqnoma',
    sub: '🔔 Har kuni', unsub: '🔕 O‘chirish', subAsk: '🔔 {name} prognozini har kuni soat nechada yuboray? (Toshkent vaqti)', subOk: '✅ Har kuni soat {time} da shu yerga prognoz keladi: {name}.\nO‘chirish: menyudagi 🔔 tugmasi.', subOff: '🔕 Kunlik yuborish o‘chirildi.',
  },
  ru: {
    cities: '🏙 Города', cPick: '🏙 Выберите город:', cTitle: '🏙 Сегодня по городам', time: '⏰ Во сколько присылать прогноз в группу? (по Ташкенту)', help: 'ℹ️ Помощь',
    d15: 'прогноз на 15 дней', hi: '☀️ <b>Osmon</b> — прогноз погоды\nна 15 дней по 6 моделям (ECMWF, NOAA).\n\nВыберите язык:', pick: '📍 Выберите страну или континент:',
    menu: 'Что показать?', today: '⏱ Сегодня и завтра по часам', all: '🎬 Видео на 15 дней', days: '🗓 15 дней', site: '🗺 Сайт и глобус', rep: '📊 Отчёт', menuHint: '⌨️ Все разделы — на кнопках внизу.\n📍 Отправьте геолокацию или напишите город, например: Наманган', locAsk: '📍 Нажмите кнопку внизу — бот получит ваше место.',
    back: '↩️ Страны', none: '⏳ Данные ещё не готовы, попробуйте чуть позже.', tdy: 'Сегодня', tmw: 'Завтра', next: 'Дальше',
    upd: 'Обновлено', swipe: '🎬 Листайте видео: 🌧 осадки · 🌡 температура · ☁️ облака · 💨 ветер', bot: '🤖 Бот',
    gHi: '👋 Привет! Я буду каждый день присылать сюда прогноз погоды с видео.\nАдминистратор группы: выберите язык, страны и время 👇 (/settings)',
    gSet: '✅ Готово! Каждый день в {time} (по Ташкенту) в этот чат будет приходить прогноз: <b>{name}</b> ({lang}).\nИзменить: /settings', gMulti: '📍 Отметьте страны (можно несколько) и нажмите «Готово»:', done: '✅ Готово', gNone: 'Отметьте хотя бы одну страну.', gAdm: '⚙️ Настройки меняет только администратор этой группы. Попросите его написать /settings.', gLang: 'Выберите язык:', lang: 'по-русски',
    pdf: '📄 Инструкция (PDF)', adm: '✉️ Написать админу', admAsk: '✍️ Напишите сообщение администратору бота (текст, фото или голосовое) — я передам.\nОтмена: /cancel', admSent: '✅ Сообщение отправлено администратору. Ответ придёт в этот чат.', admAns: '💬 Ответ администратора:', admOff: 'Администратор бота ещё не подключён, попробуйте позже.', cancel: 'Отменено.', guideCap: '📄 Бот Osmon — полная инструкция',
    sub: '🔔 Каждый день', unsub: '🔕 Отключить', subAsk: '🔔 Во сколько каждый день присылать прогноз: {name}? (по Ташкенту)', subOk: '✅ Каждый день в {time} сюда будет приходить прогноз: {name}.\nОтключить — кнопка 🔔 в меню.', subOff: '🔕 Ежедневная рассылка отключена.',
  },
  tr: {
    cities: '🏙 Şehirler', cPick: '🏙 Şehir seçin:', cTitle: '🏙 Bugün şehirlerde', time: '⏰ Tahmin gruba saat kaçta gönderilsin? (Taşkent saati)', help: 'ℹ️ Yardım',
    d15: '15 günlük tahmin', hi: '☀️ <b>Osmon</b> — hava tahmini\n6 modele göre 15 günlük (ECMWF, NOAA).\n\nDil seçin:', pick: '📍 Ülke veya kıta seçin:',
    menu: 'Ne göstereyim?', today: '⏱ Bugün ve yarın saat saat', all: '🎬 15 günlük video', days: '🗓 15 gün', site: '🗺 Site ve küre', rep: '📊 Rapor', menuHint: '⌨️ Tüm bölümler — alttaki düğmelerde.\n📍 Konum gönderin veya şehir adı yazın, örneğin: Antalya', locAsk: '📍 Alttaki düğmeye basın — konumunuz gönderilir.',
    back: '↩️ Ülkeler', none: '⏳ Veriler henüz hazır değil, biraz sonra deneyin.', tdy: 'Bugün', tmw: 'Yarın', next: 'Sonraki günler',
    upd: 'Güncellendi', swipe: '🎬 Videoları kaydırın: 🌧 yağış · 🌡 sıcaklık · ☁️ bulutlar · 💨 rüzgâr', bot: '🤖 Bot',
    gHi: '👋 Merhaba! Her gün buraya videolu hava tahmini göndereceğim.\nGrup yöneticisi: dil, ülke ve saati seçin 👇 (/settings)',
    gSet: '✅ Hazır! Her gün {time}’da (Taşkent saati) bu sohbete tahmin gönderilecek: <b>{name}</b> ({lang}).\nDeğiştirmek için: /settings', gMulti: '📍 Ülkeleri işaretleyin (birden fazla olabilir) ve «Tamam»a basın:', done: '✅ Tamam', gNone: 'En az bir ülke seçin.', gAdm: '⚙️ Ayarları yalnızca bu grubun yöneticisi değiştirebilir. Ondan /settings yazmasını isteyin.', gLang: 'Dil seçin:', lang: 'Türkçe',
    pdf: '📄 Kılavuz (PDF)', adm: '✉️ Yöneticiye yaz', admAsk: '✍️ Bot yöneticisine mesajınızı yazın (metin, fotoğraf veya sesli mesaj), ileteceğim.\nİptal: /cancel', admSent: '✅ Mesajınız yöneticiye gönderildi. Cevap bu sohbete gelecek.', admAns: '💬 Yönetici cevabı:', admOff: 'Bot yöneticisi henüz bağlanmadı, daha sonra deneyin.', cancel: 'İptal edildi.', guideCap: '📄 Osmon botu — tam kılavuz',
    sub: '🔔 Her gün', unsub: '🔕 Kapat', subAsk: '🔔 {name} tahminini her gün saat kaçta göndereyim? (Taşkent saati)', subOk: '✅ Her gün {time}’da buraya tahmin gelecek: {name}.\nKapatmak için menüdeki 🔔 düğmesi.', subOff: '🔕 Günlük gönderim kapatıldı.',
  },
};
const HELP = {
  uz: `ℹ️ <b>Osmon — qanday foydalanish</b>

<b>Pastdagi tugmalar</b>
⏱ <b>Bugun va ertaga soatma-soat</b> — 48 soatlik ovozli video va «🗺 Interaktiv xarita»: xaritaga bosing — o‘sha joy ob-havosi; pastdagi soatlar chizig‘ini suring; ▶ — ijro, 🔈 — ob-havo ovozi, ⛶ — to‘liq ekran
🗓 <b>15 kunlik prognoz</b> — shaharni tanlang, kunlar bo‘yicha prognoz keladi
🎬 <b>15 kunlik video-prognoz</b> — shahringiz yoki davlat uchun yog‘in va harorat videosi
📅 <b>Haftalar va oylar</b> — davrni tugma bilan tanlang: o‘tgan hafta, keyingi haftalar, oylar, chang
🏔 <b>Tog‘lar: qor va sayohat</b> — 10 kunlik rasm (qor, yomg‘ir, yaxshi kunlar); joy nomli tugma — batafsil; 🔔 — qor haqida xabar
🌡 <b>Hozirgi ob-havo</b> — joyingizda hozir qanday
🌫 <b>Bugungi havo sifati</b> — chang va havo sifati soatma-soat
🏙 <b>Shaharni tanlash</b> · 🌍 <b>Davlatni almashtirish</b>
📍 <b>Joyimni yuborish</b> — aynan sizning nuqtangiz uchun prognoz (yoki shunchaki shahar nomini yozing)
🔔 <b>Har tongi prognoz</b> — kunlik prognoz siz tanlagan vaqtda
⏰ <b>Bildirishnomalarim</b> — nima va soat nechada kelsin: soatma-soat, haftalar, tog‘lar, havo sifati
⚠️ <b>Xavfli ob-havo</b> — kuchli yog‘in, chang
🎯 <b>Prognoz aniqligi</b> — prognozlar haqiqiy ob-havo bilan solishtiriladi
🗺 <b>Xarita-sayt va globus</b> — sayt Telegram ichida ochiladi

<b>Avtomatik yuborish</b>
Bo‘limlar ostida «⏰ Avtomatik yuborish» tugmasi bor: vaqtni tanlang — bo‘lim o‘zi keladi. O‘chirish — o‘sha yerda yoki «⏰ Bildirishnomalarim» da. Vaqt — Toshkent vaqti.

<b>Guruh yoki kanalda</b>
1. Botni guruhga qo‘shing (kanalda — admin qilib, «xabar yuborish» huquqi bilan).
2. Admin /sozla yozadi: til → davlatlar (bir nechta) → «Tayyor» → yuborish vaqti.
3. Har kuni tanlangan vaqtda har bir davlat uchun post keladi.
4. Keyin «⏰ Bu chatga nima yuborilsin» chiqadi: soatma-soat, haftalar, tog‘lar, havo sifati, qor xabari — har biriga vaqt, yoki «✅ Hammasini yoqish». Keyinroq: /notify
/bugun — guruhda hozirgi prognoz.

✉️ Savol yoki taklif — /admin, javob shu yerga keladi
📄 /guide — PDF yo‘riqnoma

Ma’lumot: ECMWF, NOAA, DWD modellari; havo sifati — CAMS. Har 3 soatda yangilanadi.`,
  ru: `ℹ️ <b>Osmon — как пользоваться</b>

<b>Кнопки внизу экрана</b>
⏱ <b>Сегодня и завтра по часам</b> — видео со звуком на 48 часов и «🗺 Интерактивная карта»: нажмите на карту — погода в этой точке; тяните полосу часов внизу; ▶ — проиграть, 🔈 — звук погоды, ⛶ — во весь экран
🗓 <b>Прогноз на 15 дней</b> — выберите город и получите прогноз по дням
🎬 <b>Видео-прогноз 15 дней</b> — видео осадков и температуры для вашего города или страны
📅 <b>Недели и месяцы</b> — выберите период кнопкой: прошедшая неделя, следующие недели, месяцы, пыль
🏔 <b>Горы: снег и поездки</b> — картинка на 10 дней (снег, дождь, хорошие дни); кнопка с названием места — подробно; 🔔 — сигнал о снеге
🌡 <b>Погода сейчас</b> — что сейчас в вашем месте
🌫 <b>Воздух сегодня</b> — пыль и качество воздуха по часам
🏙 <b>Выбрать город</b> · 🌍 <b>Сменить страну</b>
📍 <b>Отправить моё место</b> — прогноз точно для вашей точки (или просто напишите название города)
🔔 <b>Прогноз каждое утро</b> — прогноз на день в выбранное время
⏰ <b>Мои уведомления</b> — что и во сколько присылать: по часам, недели, горы, воздух
⚠️ <b>Опасная погода</b> — сильные осадки, пыль
🎯 <b>Точность прогноза</b> — как прогнозы совпали с фактом
🗺 <b>Карта-сайт и глобус</b> — сайт прямо в Telegram

<b>Автоотправка</b>
Под разделами есть кнопка «⏰ Присылать автоматически»: выберите время — и раздел будет приходить сам. Выключить — там же или в «⏰ Мои уведомления». Время — по Ташкенту.

<b>В группе или канале</b>
1. Добавьте бота в группу (в канал — администратором с правом публикации).
2. Администратор пишет /settings: язык → страны (можно несколько) → «Готово» → время отправки.
3. Каждый день в выбранное время по каждой стране приходит пост.
4. Затем появится «⏰ Что присылать в этот чат»: по часам, недели и месяцы, горы, воздух, сигнал о снеге — у каждого своё время, или «✅ Включить всё». Позже: /notify
/bugun — прогноз в группу прямо сейчас.

✉️ Вопрос или предложение — /admin, ответ придёт сюда
📄 /guide — инструкция в PDF

Данные: модели ECMWF, NOAA, DWD; качество воздуха — CAMS. Обновление каждые 3 часа.`,
  tr: `ℹ️ <b>Osmon — nasıl kullanılır</b>

<b>Alttaki düğmeler</b>
⏱ <b>Bugün ve yarın saat saat</b> — 48 saatlik sesli video ve «🗺 Etkileşimli harita»: haritaya dokunun — o yerin havası; alttaki saat şeridini kaydırın; ▶ — oynat, 🔈 — hava sesi, ⛶ — tam ekran
🗓 <b>15 günlük tahmin</b> — şehri seçin, günlere göre tahmin gelir
🎬 <b>15 günlük video tahmin</b> — şehriniz veya ülke için yağış ve sıcaklık videosu
📅 <b>Haftalar ve aylar</b> — dönemi düğmeyle seçin: geçen hafta, gelecek haftalar, aylar, toz
🏔 <b>Dağlar: kar ve gezi</b> — 10 günlük resim (kar, yağmur, iyi günler); yer adlı düğme — ayrıntı; 🔔 — kar bildirimi
🌡 <b>Şu anki hava</b> — bulunduğunuz yerde şimdi
🌫 <b>Bugün hava kalitesi</b> — toz ve hava kalitesi saat saat
🏙 <b>Şehir seç</b> · 🌍 <b>Ülke değiştir</b>
📍 <b>Konumumu gönder</b> — tam olarak sizin noktanız için tahmin (veya şehir adını yazın)
🔔 <b>Her sabah tahmin</b> — seçtiğiniz saatte günlük tahmin
⏰ <b>Bildirimlerim</b> — ne ve saat kaçta gelsin: saat saat, haftalar, dağlar, hava kalitesi
⚠️ <b>Tehlikeli hava</b> — kuvvetli yağış, toz
🎯 <b>Tahmin doğruluğu</b> — tahminler gerçekle karşılaştırılır
🗺 <b>Harita-site ve küre</b> — site Telegram içinde açılır

<b>Otomatik gönderim</b>
Bölümlerin altında «⏰ Otomatik gönder» düğmesi var: saati seçin — bölüm kendiliğinden gelir. Kapatmak — aynı yerde veya «⏰ Bildirimlerim». Saat — Taşkent saati.

<b>Grupta veya kanalda</b>
1. Botu gruba ekleyin (kanalda yönetici olarak, gönderme izniyle).
2. Yönetici /settings yazar: dil → ülkeler (birden fazla) → «Tamam» → gönderme saati.
3. Her gün seçilen saatte her ülke için gönderi gelir.
4. Ardından «⏰ Bu sohbete ne gönderilsin» çıkar: saat saat, haftalar, dağlar, hava kalitesi, kar bildirimi — her birine saat ya da «✅ Hepsini aç». Sonra: /notify

✉️ Soru veya öneri — /admin, cevap buraya gelir
📄 /guide — PDF kılavuz

Veri: ECMWF, NOAA, DWD modelleri; hava kalitesi — CAMS. Her 3 saatte güncellenir.`,
};
const WD = { uz: ['Yak', 'Dush', 'Sesh', 'Chor', 'Pay', 'Jum', 'Shan'], ru: ['Вс', 'Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб'], tr: ['Paz', 'Pzt', 'Sal', 'Çar', 'Per', 'Cum', 'Cmt'] };
const PER_TICK = 4;      // groups per cron run (Workers free plan: 50 subrequests per run; a group may want several countries)
const POST_HOUR = 7, TZ = 5;  // default daily post at 07:00 Tashkent; each group can pick its hour (hourly cron)
const HOURS = [6, 7, 8, 9, 10, 12, 15, 18, 20, 21];
const hh = h => `${String(h).padStart(2, '0')}:00`;
const timeKb = (lang, cur) => ({ inline_keyboard: [HOURS.slice(0, 5), HOURS.slice(5)].map(row => row.map(h => ({ text: `${h === cur ? '✅ ' : ''}${hh(h)}`, callback_data: `GH:${lang}:${h}` }))) });
// a stored UTC time shown in Tashkent time: "06.11 12:04"
const tkt = iso => { if (!iso) return '—'; const t = new Date(Date.parse(iso) + TZ * 3600e3); return isNaN(t) ? '—' : `${String(t.getUTCDate()).padStart(2, '0')}.${String(t.getUTCMonth() + 1).padStart(2, '0')} ${String(t.getUTCHours()).padStart(2, '0')}:${String(t.getUTCMinutes()).padStart(2, '0')}`; };
const todayTZ = () => new Date(Date.now() + TZ * 3600e3).toISOString().slice(0, 10);
const multiKb = (lang, sel) => ({ inline_keyboard: [...GROUPS.map(row => row.map(id => ({ text: `${sel.includes(id) ? '✅' : FLAG[id]} ${NAMES[id][lang]}`, callback_data: `GT:${lang}:${id}` }))), [{ text: T[lang].done, callback_data: `GD:${lang}` }]] });
const regionsOf = s => (s && s.region ? s.region.split(',').filter(r => NAMES[r]) : []);

export default {
  async fetch(req, env, ctx) {
    const url = new URL(req.url);
    if (req.method === 'GET' && url.pathname === '/setup') return setup(env, url);
    if (url.pathname === '/hit' || url.pathname === '/stats') return visits(req, env, url);
    if (req.method === 'GET' && url.pathname === '/invite') return new Response(JSON.stringify(await invite(env, +(url.searchParams.get('n') || 12))), { headers: { 'content-type': 'application/json' } });
    if (req.method === 'GET' && url.pathname === '/broadcast') { const r = await broadcast(env); return new Response(JSON.stringify(r), { headers: { 'content-type': 'application/json' } }); }
    if (req.method !== 'POST') return new Response('Osmon bot is running. Open /setup once to connect it to Telegram.');
    if (req.headers.get('x-telegram-bot-api-secret-token') !== await secret(env)) return new Response('forbidden', { status: 403 });
    const up = await req.json().catch(() => ({}));
    // answer Telegram at once; sending videos can take longer than its webhook timeout
    ctx.waitUntil(handle(up, env).catch(e => console.log('error', e && e.stack)));
    return new Response('ok');
  },
  async scheduled(ev, env, ctx) {
    // each job on its own, so one failure (or Cloudflare's limit of requests per run) cannot stop the others;
    // the check of the site builds goes first: it is small and it matters most
    const run = (name, f) => f().catch(e => console.log(name, e && e.stack));
    if (ev && ev.cron === WATCH_CRON) return ctx.waitUntil(run('watch', () => watchTick(env)));  // its own runs: the weather at people's places
    ctx.waitUntil((async () => {
      await run('stale', () => staleTick(env));
      const r = await broadcast(env).catch(e => { console.log('broadcast', e && e.stack); return null; });
      if (!r || !r.due) for (const [n, f] of [['alert', alertTick], ['mtn', mtnTick], ['notif', notifTick], ['stats', statsTick], ['backup', backupTick]]) await run(n, () => f(env));
    })());
  },
};

// the admin's own command menu and buttons: /users, /admin, /yt
const ADMIN_BTN = '👤 Пользователи';
const ADMIN_KB = { inline_keyboard: [[{ text: ADMIN_BTN, callback_data: 'AU:ru' }, { text: '📺 YouTube', callback_data: 'AY:ru' }], [{ text: '📈 Динамика', callback_data: 'AD:ru' }, { text: '🆕 Изменения', callback_data: 'AC:ru' }]] };
// admin: day by day — how many people used the bot, how many were new, site visits, and how many have the daily auto-send on
async function dstatSnap(env) {  // today's subscription counts, kept per day (so unsubscribes show in the history too)
  const one = async q => ((await env.DB.prepare(q).first()) || {}).n || 0;
  const prv = await one("SELECT COUNT(*) AS n FROM subs WHERE type = 'private'"), grp = await one("SELECT COUNT(*) AS n FROM subs WHERE type <> 'private'");
  const mtn = await one('SELECT COUNT(*) AS n FROM mtn'), users = await one('SELECT COUNT(*) AS n FROM users');
  await env.DB.prepare('INSERT INTO dstat (day, prv, grp, mtn, users) VALUES (?1, ?2, ?3, ?4, ?5) ON CONFLICT(day) DO UPDATE SET prv = ?2, grp = ?3, mtn = ?4, users = ?5').bind(todayTZ(), prv, grp, mtn, users).run();
  return { prv, grp, mtn, users };
}
async function sendDynamics(env, chat, n = 14) {
  if (!env.DB) return; await db(env);
  const now = await dstatSnap(env), all = async (q, ...a) => (await env.DB.prepare(q).bind(...a).all()).results;
  const days = []; for (let i = n - 1; i >= 0; i--) days.push(new Date(Date.now() + TZ * 3600e3 - i * 864e5).toISOString().slice(0, 10));
  const from = days[0], map = (rows, k = 'n') => Object.fromEntries(rows.map(r => [r.day, r[k]]));
  const act = map(await all('SELECT day, COUNT(*) AS n FROM daily WHERE day >= ?1 GROUP BY day', from));
  const neu = map(await all(`SELECT date(first, '+${TZ} hours') AS day, COUNT(*) AS n FROM users WHERE first IS NOT NULL AND chat_id > 0 GROUP BY day HAVING day >= ?1`, from));
  let site = {}; try { site = map(await all('SELECT day, SUM(n) AS n FROM hits WHERE day >= ?1 GROUP BY day', from)); } catch (e) { /* no site counter yet */ }
  const snap = Object.fromEntries((await all('SELECT * FROM dstat WHERE day >= ?1', from)).map(r => [r.day, r]));
  // days before the snapshots began: today's subscribers counted by the day they subscribed
  const added = await all(`SELECT date(added, '+${TZ} hours') AS day, type FROM subs WHERE added IS NOT NULL`);
  const subsOn = d => snap[d] ? snap[d].prv + snap[d].grp : added.filter(x => x.day <= d).length;
  const newSubs = map(await all(`SELECT date(added, '+${TZ} hours') AS day, COUNT(*) AS n FROM subs GROUP BY day HAVING day >= ?1`, from));
  const top = Math.max(1, ...days.map(d => act[d] || 0)), bar = v => '█'.repeat(Math.round((v || 0) / top * 8)).padEnd(8, '·');
  const pad = (v, w) => String(v ?? 0).padStart(w);
  const rows = days.map(d => `${d.slice(8, 10)}.${d.slice(5, 7)} ${bar(act[d])}${pad(act[d], 4)}${pad(neu[d], 4)}${pad(site[d], 5)}${pad(subsOn(d), 4)}${newSubs[d] ? '+' + newSubs[d] : ''}`);
  const sum = k => days.reduce((a, d) => a + (k[d] || 0), 0), avg = Math.round(sum(act) / Math.max(1, days.filter(d => act[d]).length));
  const text = [`📈 <b>Динамика за ${n} дней</b> (по Ташкенту)`, '',
    `<pre>${esc(`Дата  Заходили    Нов Сайт  🔔\n${rows.join('\n')}`)}</pre>`,
    `👤 Заходили: в среднем <b>${avg}</b> в день · всего уникальных за период: <b>${((await env.DB.prepare('SELECT COUNT(DISTINCT chat_id) AS n FROM daily WHERE day >= ?1').bind(from).first()) || {}).n || 0}</b>`,
    `🆕 Новых за период: <b>${sum(neu)}</b> · всего пользователей: <b>${now.users}</b>`,
    `🔔 Автоотправка погоды включена: <b>${now.prv + now.grp}</b> (👤 личных ${now.prv} · 👥 групп и каналов ${now.grp})`,
    `❄️ Сигнал о снеге в горах: <b>${now.mtn}</b>`,
    `<i>«Заходили» считается с ${(await env.DB.prepare('SELECT MIN(day) AS d FROM daily').first() || {}).d || 'сегодня'}; столбец 🔔 — сколько подписок было в тот день, «+» — новые подписки.</i>`].join('\n');
  return tg(env, 'sendMessage', { chat_id: chat, text: text.slice(0, 4000), parse_mode: 'HTML',
    reply_markup: { inline_keyboard: [[7, 14, 30].map(k => ({ text: `${k === n ? '✅ ' : ''}${k} дней`, callback_data: `AD:ru:${k}` }))] } });
}
// admin: what changed lately (telegram/changes.json in the repository) and how the last site builds went (GitHub Actions)
async function sendChanges(env, chat) {
  const REPO = 'otabekvafoev92-del/ob-havo-ecmwf', H = { 'User-Agent': 'osmon-bot', Accept: 'application/vnd.github+json' };
  const [ch, runs] = await Promise.all([
    fetch(`https://raw.githubusercontent.com/${REPO}/main/telegram/changes.json?t=${Date.now()}`).then(r => r.ok ? r.json() : null).catch(() => null),
    fetch(`https://api.github.com/repos/${REPO}/actions/runs?per_page=6`, { headers: H }).then(r => r.ok ? r.json() : null).catch(() => null)]);
  const st = { success: '✅ готово', failure: '❌ ошибка', cancelled: '⏭ заменена новой', in_progress: '⏳ идёт', queued: '🕓 в очереди', pending: '🕓 в очереди' };
  const out = ['🆕 <b>Последние изменения</b>', ''];
  for (const it of ((ch && ch.items) || []).slice(0, 12)) out.push(`• <b>${esc(it.d.slice(8, 10) + '.' + it.d.slice(5, 7) + ' ' + it.d.slice(11))}</b> — ${esc(it.t)}`);
  if (!ch) out.push('Список изменений сейчас недоступен.');
  if (runs && runs.workflow_runs) {
    out.push('', '🛠 <b>Сборки сайта и видео</b>');
    for (const r of runs.workflow_runs.slice(0, 5)) {
      const s = r.status === 'completed' ? (st[r.conclusion] || r.conclusion) : (st[r.status] || r.status);
      const mins = r.run_started_at ? Math.max(0, Math.round(((r.status === 'completed' ? Date.parse(r.updated_at) : Date.now()) - Date.parse(r.run_started_at)) / 60000)) : 0;
      out.push(`• ${tkt(r.created_at)} — ${s}${r.status !== 'queued' && mins ? ` · ${mins} мин` : ''} · ${r.event === 'schedule' ? 'по расписанию' : r.event === 'push' ? 'после изменений' : 'вручную'}`);
    }
  }
  return tg(env, 'sendMessage', { chat_id: chat, text: out.join('\n').slice(0, 4000), parse_mode: 'HTML', disable_web_page_preview: true });
}
async function adminMenu(env, chat) {
  await tg(env, 'setMyCommands', { scope: { type: 'chat', chat_id: Number(chat) }, commands: [{ command: 'users', description: '👤 Пользователи бота' }, { command: 'searches', description: '🔎 Что ищут (7 дней)' }, { command: 'accuracy', description: '🎯 Точность прогноза' }, { command: 'admin', description: '👑 Статистика' }, { command: 'yt', description: '📺 Видеообзор для YouTube' }, { command: 'changes', description: '🆕 Последние изменения' }, { command: 'dyn', description: '📈 Динамика по дням' }, { command: 'start', description: 'Меню' }] });
}
async function setup(env, url) {
  { const a = await kv(env, 'admin'); if (a) await adminMenu(env, a); }
  const hook = await tg(env, 'setWebhook', { url: `${url.origin}/`, secret_token: await secret(env), allowed_updates: ['message', 'callback_query', 'my_chat_member', 'channel_post'] });
  await tg(env, 'setMyCommands', { commands: [  // ☰ only the basics: everything else is on the keyboard under the input field
    { command: 'home', description: '🏠 Menyu / Меню (klaviatura / клавиатура)' },
    { command: 'help', description: 'ℹ️ Yordam, PDF / Помощь, PDF' },
    { command: 'admin', description: '✉️ Adminga yozish / Написать админу' },
    { command: 'start', description: '🔤 Til / Язык / Dil' }] });
  await tg(env, 'setMyCommands', { scope: { type: 'all_group_chats' }, commands: [{ command: 'sozla', description: 'Davlat va til (adminlar uchun)' }, { command: 'settings', description: 'Страна и язык (для админов)' }, { command: 'bugun', description: 'Bugun va ertaga / Сегодня и завтра' }, { command: 'notify', description: '⏰ Nima yuborilsin / Что присылать (adminlar)' }, { command: 'help', description: 'Yordam / Помощь' }] });
  await tg(env, 'setChatMenuButton', { menu_button: { type: 'commands' } });  // ☰ opens the command menu
  await tg(env, 'setMyShortDescription', { short_description: 'Ob-havo · Погода · Hava — 15 kun, 6 model (ECMWF, NOAA). Guruhlarga avtomatik prognoz.' });
  await tg(env, 'setMyDescription', { description: '☀️ Osmon — ob-havo prognozi 15 kunga\n🌧 Yog‘in ehtimoli, 🌡 harorat, ☁️ bulutlar — 6 ta model asosida (ECMWF IFS/AIFS, NOAA GFS/GEFS).\n🌍 Butun dunyo, qit’alar, MDH va Turkiya.\n👥 Guruh yoki kanalga qo‘shing — prognozni o‘zi yuboradi.\n\nПогода на 15 дней по 6 моделям. Добавьте в группу — бот сам будет присылать прогноз.' });
  if (env.DB) await db(env);
  const me = await tg(env, 'getMe', {});
  return new Response(hook.ok ? `OK: @${me.result && me.result.username} is connected. Open Telegram and send /start.` : `Error: ${JSON.stringify(hook)}`, { headers: { 'content-type': 'text/plain; charset=utf-8' } });
}

// Telegram sends this header with every update (set in /setup): fake updates posted to the worker are refused
async function secret(env) {
  const h = new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode('osmon:' + env.BOT_TOKEN)));
  return [...h].map(b => b.toString(16).padStart(2, '0')).join('').slice(0, 48);
}
async function tg(env, method, body) {
  const r = await fetch(`https://api.telegram.org/bot${env.BOT_TOKEN}/${method}`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) });
  return r.json();
}
async function manifest(env, fresh) {
  const r = await fetch(`${base(env)}/prob/manifest.json${fresh ? '?t=' + Date.now() : ''}`, { cf: { cacheTtl: fresh ? 0 : 600 } });
  return r.ok ? r.json() : null;
}
const base = env => env.SITE_URL.replace(/\/$/, '');
async function cities(env, id, lang) {
  const r = await fetch(`${base(env)}/prob/cities/${id}_${lang}.json`, { cf: { cacheTtl: 600 } });
  return r.ok ? r.json() : null;
}
// one line per city for today: "⛅ Ташкент: +11°…+16°, дождь маловероятен (24 %)"
async function cityLines(env, id, lang, n = 10) {
  const C = await cities(env, id, lang); if (!C) return '';
  const d = localToday(C.off);
  return C.cities.slice(0, n).map(c => c.days[d]).filter(Boolean).map(t => `${icon(t)} ${esc(t.replace(/, (ясно|переменная облачность|облачно|пасмурно|ochiq havo|qisman bulutli|bulutli|qalin bulutli|açık|parçalı bulutlu|bulutlu|kapalı)\.$/, '.'))}`).join('\n');
}
// the website opens inside Telegram (Mini App): ?view= picks the page, country, language and tab
const site = (env, view) => `${base(env)}/?tg=1&view=${encodeURIComponent(view)}`;
const link = (env, view) => `${base(env)}/?view=${encodeURIComponent(view)}`;
const esc = s => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

/* ---------- keyboards ---------- */
const langKb = (p = 'L') => ({ inline_keyboard: [[{ text: '🇺🇿 O‘zbekcha', callback_data: `${p}:uz` }, { text: '🇷🇺 Русский', callback_data: `${p}:ru` }, { text: '🇹🇷 Türkçe', callback_data: `${p}:tr` }]] });
const countryKb = (lang, p = 'C') => ({ inline_keyboard: GROUPS.map(row => row.map(id => ({ text: `${FLAG[id]} ${NAMES[id][lang]}`, callback_data: `${p}:${lang}:${id}` }))) });
const OLK = { uz: '📅 Haftalar va oylar', ru: '📅 Недели и месяцы', tr: '📅 Haftalar ve aylar' };
// Uzbekistan: the past week, the next two weeks, this and next month and the dust (prob/outlook.py), in segments:
// first a menu of periods, then each period's maps on their own with the same buttons under the last one
const OLA = { ru: { pick: 'Выберите период — пришлю его карты:', all: '📤 Все карты сразу', dust: '🌫' },
              uz: { pick: 'Davrni tanlang — xaritalarini yuboraman:', all: '📤 Barcha xaritalar', dust: '🌫' },
              tr: { pick: 'Dönemi seçin — haritalarını göndereyim:', all: '📤 Tüm haritalar', dust: '🌫' } };
const OL_ICON = { past: '⏪', w1: '📆', w2: '📆', m0: '🗓', m1: '🗓', dust: '🌫' };
async function outlookItems(env, lang) {
  const I = await (await fetch(`${base(env)}/prob/outlook/index.json?t=${Date.now()}`)).json().catch(() => null);
  let its = I ? I.items.filter(i => i.lang === lang) : []; if (I && !its.length) its = I.items.filter(i => i.lang === 'ru');
  return { I, its };
}
const ddm = x => `${x.slice(8, 10)}.${x.slice(5, 7)}`;
// the segments as buttons: the past week alone, the two weeks side by side, the two months side by side, the dust, "all at once"
function outlookKb(its, lang, cur) {
  const A = OLA[lang] || OLA.ru, btn = i => ({ text: `${cur === i.key ? '✅' : OL_ICON[i.key] || '📅'} ${i.title}${/^w/.test(i.key) ? ` · ${ddm(i.start)}–${ddm(i.end)}` : ''}`, callback_data: `OP:${lang}:${i.key}` });
  const by = k => its.filter(i => k.includes(i.key)).map(btn), rows = [by(['past']), by(['w1', 'w2']), by(['m0', 'm1']), by(['dust']),
    its.filter(i => !['past', 'w1', 'w2', 'm0', 'm1', 'dust'].includes(i.key)).map(btn)].filter(r => r.length);
  rows.push([{ text: A.all, callback_data: `OA:${lang}` }]);
  rows.push([notifBtn(lang, 'outlook')]);
  return { inline_keyboard: rows };
}
async function sendOutlook(env, chat, lang) {
  const { its } = await outlookItems(env, lang);
  if (!its.length) return tg(env, 'sendMessage', { chat_id: chat, text: T[lang].none });
  return tg(env, 'sendMessage', { chat_id: chat, text: `🇺🇿 <b>${OLK[lang]}</b>\n${(OLA[lang] || OLA.ru).pick}`, parse_mode: 'HTML', reply_markup: outlookKb(its, lang) });
}
// one period (key) or all of them: every map is its own photo with its own caption; the segment buttons go under the last one
async function sendOutlookPart(env, chat, lang, key) {
  const quiet = chat < 0;  // a group or channel: just the maps
  const { I, its } = await outlookItems(env, lang);
  if (!its.length) return tg(env, 'sendMessage', { chat_id: chat, text: T[lang].none });
  const v = encodeURIComponent(I.made || ''), list = key ? its.filter(i => i.key === key) : its;
  if (!list.length) return sendOutlook(env, chat, lang);
  const shots = [];
  for (const i of list) {
    const imgs = i.imgs || [i.img], caps = i.caps || [];
    imgs.forEach((im, k) => shots.push({ im, cap: `<b>${esc(i.title)}</b>${caps[k] ? ` · ${esc(caps[k])}` : ''}\n${ddm(i.start)}–${ddm(i.end)}${k === 0 && i.text ? `\n${esc(i.text)}` : ''}` }));
  }
  let r = null;
  for (let n = 0; n < shots.length; n++) {
    await tg(env, 'sendChatAction', { chat_id: chat, action: 'upload_photo' });
    r = await tg(env, 'sendPhoto', { chat_id: chat, photo: `${base(env)}/prob/${shots[n].im}?v=${v}`, caption: shots[n].cap.slice(0, 1024), parse_mode: 'HTML',
      ...(n === shots.length - 1 && !quiet ? { reply_markup: outlookKb(its, lang, key) } : {}) });
  }
  return r;
}
/* ---------- the weather by regions and districts (Uzbekistan, Kazakhstan, Kyrgyzstan; prob/admin_wx.py) ---------- */
const ADM = new Set(['UZ', 'KZ', 'KG']);
const RGX = {
  ru: { btn: '🗺 Погода по регионам и районам', detail: 'Нажмите район — пришлю подробный прогноз: по часам и на 15 дней.', title: 'Погода по регионам', pick: 'Нажмите регион — покажу погоду по его районам:', today: 'сегодня', tomorrow: 'завтра', none: 'Погода по регионам ещё готовится, попробуйте чуть позже.', back: '⬅️ Все регионы', dists: 'по районам', foot: 'Температура: ночь…день. ☂ — вероятность дождя, ❄ — снега, ☀ — без осадков.' },
  uz: { btn: '🗺 Viloyat va tumanlar bo‘yicha', detail: 'Tumanni bosing — batafsil prognoz yuboraman: soatma-soat va 15 kunga.', title: 'Viloyatlar bo‘yicha ob-havo', pick: 'Viloyatni bosing — tumanlari bo‘yicha ob-havoni ko‘rsataman:', today: 'bugun', tomorrow: 'ertaga', none: 'Viloyatlar bo‘yicha ma’lumot tayyorlanmoqda, birozdan keyin urinib ko‘ring.', back: '⬅️ Barcha viloyatlar', dists: 'tumanlar bo‘yicha', foot: 'Harorat: tun…kun. ☂ — yomg‘ir ehtimoli, ❄ — qor, ☀ — yog‘insiz.' },
  tr: { btn: '🗺 Bölge ve ilçelere göre', detail: 'İlçeye dokunun — ayrıntılı tahmin göndereyim: saat saat ve 15 gün.', title: 'Bölgelere göre hava', pick: 'Bölgeye dokunun — ilçelerine göre havayı göstereyim:', today: 'bugün', tomorrow: 'yarın', none: 'Bölge verileri hazırlanıyor, biraz sonra deneyin.', back: '⬅️ Tüm bölgeler', dists: 'ilçelere göre', foot: 'Sıcaklık: gece…gündüz. ☂ — yağmur olasılığı, ❄ — kar, ☀ — yağışsız.' } };
const t0 = v => v == null ? '—' : `${v > 0.5 ? '+' : ''}${Math.round(v)}°`.replace('+0°', '0°').replace('-0°', '0°');
const admLine = v => !v ? '—' : `${t0(v[0])}…${t0(v[1])} ${v[2] >= 20 ? `${v[3] ? '❄' : '☂'}${v[2]}%` : '☀'}`;
const admName = (a, lang) => (a.name[lang] || a.name.ru);
async function adminData(env, rid) { return fetch(`${base(env)}/prob/hr/${rid}_admin.json?v=${fresh()}`).then(r => r.ok ? r.json() : null).catch(() => null); }
function regionsKb(A, lang, rid, cur) {
  const b = [...A.adm1].sort((x, y) => admName(x, lang).localeCompare(admName(y, lang))).map(a => ({ text: `${cur === a.id ? '✅ ' : ''}${admName(a, lang).replace(/ обл\.$| viloyati$/, '')}`, callback_data: `RD:${lang}:${rid}:${a.id}` }));
  const rows = []; for (let i = 0; i < b.length; i += 2) rows.push(b.slice(i, i + 2));
  return { inline_keyboard: rows };
}
// the two maps (today, tomorrow), then every region in a line with buttons that open its districts
async function sendRegions(env, chat, lang, rid) {
  const X = RGX[lang] || RGX.ru, A = await adminData(env, rid);
  if (!A) return tg(env, 'sendMessage', { chat_id: chat, text: X.none });
  const L = lang === 'tr' ? 'ru' : lang, v = encodeURIComponent(A.run);
  await tg(env, 'sendChatAction', { chat_id: chat, action: 'upload_photo' });
  await tg(env, 'sendMediaGroup', { chat_id: chat, media: [0, 1].map(k => ({ type: 'photo', media: `${base(env)}/prob/hr/${rid}_adm_${L}_${k}.png?v=${v}`, ...(k ? {} : { caption: `${FLAG[rid]} ${NAMES[rid][lang]} · ${X.title}` }) })) });
  return tg(env, 'sendMessage', regionsList(A, lang, rid, chat));
}
function regionsList(A, lang, rid, chat) {
  const X = RGX[lang] || RGX.ru, lines = [...A.adm1].sort((x, y) => admName(x, lang).localeCompare(admName(y, lang)))
    .map(a => `<b>${esc(admName(a, lang))}</b>\n   ${X.today} ${admLine(a.v[0])} · ${X.tomorrow} ${admLine(a.v[1])}`);
  return { chat_id: chat, text: [`${FLAG[rid]} <b>${NAMES[rid][lang]} — ${X.title}</b>`, '', ...lines, '', `<i>${X.foot}</i>`, '', X.pick].join('\n').slice(0, 4000), parse_mode: 'HTML', reply_markup: regionsKb(A, lang, rid) };
}
// one region: its districts, today and tomorrow (the message changes in place when another region is pressed)
async function sendDistricts(env, chat, lang, rid, id, msgId) {
  const X = RGX[lang] || RGX.ru, A = await adminData(env, rid);
  if (!A) return tg(env, 'sendMessage', { chat_id: chat, text: X.none });
  const r = A.adm1.find(a => a.id === id); if (!r) return sendRegions(env, chat, lang, rid);
  const ds = A.adm2.map((d, i) => ({ ...d, i })).filter(d => d.p === id).sort((x, y) => admName(x, lang).localeCompare(admName(y, lang)));
  const text = [`🗺 <b>${esc(admName(r, lang))}</b> — ${X.dists}`, `${X.today} ${admLine(r.v[0])} · ${X.tomorrow} ${admLine(r.v[1])}`, `<i>${X.detail}</i>`, '',
    ...ds.map(d => `• ${esc(admName(d, lang))}: ${admLine(d.v[0])} · ${X.tomorrow} ${admLine(d.v[1])}`), '', `<i>${X.foot}</i>`].join('\n').slice(0, 4000);
  // a button per district: its detailed forecast (by hours, 15 days) at the district's centre
  const btn = ds.map(d => ({ text: admName(d, lang).replace(/ р-н$| tumani$/, ''), callback_data: `RX:${lang}:${rid}:${d.i}` })), rows = [];
  for (let i = 0; i < btn.length; i += 3) rows.push(btn.slice(i, i + 3));
  const kb = { inline_keyboard: [...rows, [{ text: X.back, callback_data: `RB:${lang}:${rid}` }]] };
  const body = { chat_id: chat, text, parse_mode: 'HTML', reply_markup: kb };
  if (msgId) { const e = await tg(env, 'editMessageText', { ...body, message_id: msgId }); if (e.ok || /not modified/.test(e.description || '')) return e; }
  return tg(env, 'sendMessage', body);
}

/* ---------- where the rain and snow come from (prob/trajectory.py: the air's path 2 days back) ---------- */
const TRJ = new Set(['UZ', 'KZ']);
const TJX = { ru: { btn: '🧭 Откуда придут осадки', moist: 'Откуда идёт дождь, 3 дня: серое — тучи, синее — дождь, фиолетовое — снег, красное — циклон, жёлтое — сильный ветер, оранжевый пунктир — путь влаги к городу (ECMWF)', m15: '📅 Видео на 15 дней', moist15: 'Дождь, снег и ветер на 15 дней (ECMWF; после 10-го дня — контрольный прогноз ансамбля, это ориентир)', m15none: 'Видео на 15 дней ещё готовится — загляните чуть позже.', title: 'Откуда придут осадки', none: 'В ближайшие 3 дня осадков в крупных городах не ожидается — показывать нечего. ☀️', foot: 'Линия — путь воздуха (на высоте ~3 км), который принесёт осадки, за 2 суток до их начала. Модель ECMWF.' },
              uz: { btn: '🧭 Yog‘in qayerdan keladi', moist: 'Yomg‘ir qayerdan keladi, 3 kun: kulrang — bulut, ko‘k — yomg‘ir, binafsha — qor, qizil — siklon, sariq — kuchli shamol, to‘q sariq punktir — namlikning shaharga yo‘li (ECMWF)', m15: '📅 15 kunlik video', moist15: 'Yomg‘ir, qor va shamol 15 kunga (ECMWF; 10-kundan keyin — ansambl nazorat prognozi, taxminiy)', m15none: '15 kunlik video hali tayyorlanmoqda — birozdan keyin qarang.', title: 'Yog‘in qayerdan keladi', none: 'Yaqin 3 kunda yirik shaharlarda yog‘in kutilmaydi — ko‘rsatadigan narsa yo‘q. ☀️', foot: 'Chiziq — yog‘in olib keladigan havoning (~3 km balandlikda) boshlanishidan 2 kun oldingi yo‘li. ECMWF modeli.' },
              tr: { btn: '🧭 Yağış nereden gelecek', moist: 'Yağmur nereden geliyor, 3 gün: gri — bulut, mavi — yağmur, mor — kar, kırmızı — siklon, sarı — kuvvetli rüzgâr, turuncu kesikli — nemin şehre yolu (ECMWF)', m15: '📅 15 günlük video', moist15: 'Yağmur, kar ve rüzgâr 15 gün (ECMWF; 10. günden sonra ensemble kontrol tahmini, yaklaşık)', m15none: '15 günlük video henüz hazırlanıyor — biraz sonra bakın.', title: 'Yağış nereden gelecek', none: 'Önümüzdeki 3 günde büyük şehirlerde yağış beklenmiyor. ☀️', foot: 'Çizgi — yağışı getirecek havanın (~3 km yükseklikte) başlamadan önceki 2 günlük yolu. ECMWF modeli.' } };
async function trajData(env, rid) { return fetch(`${base(env)}/prob/hr/${rid}_traj.json?v=${fresh()}`).then(r => r.ok ? r.json() : null).catch(() => null); }
async function sendMoist15(env, chat, lang, rid) {  // the long video: 15 days of rain, snow and wind (prob/moisture.py --days 15)
  const X = TJX[lang] || TJX.ru, L = lang === 'tr' ? 'ru' : lang, url = `${base(env)}/prob/hr/${rid}_moist15_${L}.mp4`;
  const ok = await fetch(url, { method: 'HEAD' }).then(r => r.ok).catch(() => false);
  if (!ok) return tg(env, 'sendMessage', { chat_id: chat, text: X.m15none });
  await tg(env, 'sendChatAction', { chat_id: chat, action: 'upload_video' });
  return tg(env, 'sendVideo', { chat_id: chat, video: `${url}?v=${fresh()}`, caption: `📅 ${FLAG[rid]} ${NAMES[rid][lang]} · ${X.moist15}`, supports_streaming: true });
}
async function sendTraj(env, chat, lang, rid) {
  const X = TJX[lang] || TJX.ru, J = await trajData(env, rid);
  if (!J || !J.items.length) return tg(env, 'sendMessage', { chat_id: chat, text: X.none });
  await tg(env, 'sendChatAction', { chat_id: chat, action: 'upload_photo' });
  // first the moving picture of the moisture coming in (prob/moisture.py), then the map of the air's paths
  const L = lang === 'tr' ? 'ru' : lang, v = encodeURIComponent(J.run), cap = `🧭 ${FLAG[rid]} ${NAMES[rid][lang]} · ${X.title}`;
  await tg(env, 'sendVideo', { chat_id: chat, video: `${base(env)}/prob/hr/${rid}_moist_${L}.mp4?v=${v}`, caption: `💧 ${FLAG[rid]} ${NAMES[rid][lang]} · ${X.moist}`, supports_streaming: true,
    reply_markup: { inline_keyboard: [[{ text: X.m15, callback_data: `MV:${lang}:${rid}` }]] } });
  await tg(env, 'sendPhoto', { chat_id: chat, photo: `${base(env)}/prob/hr/${rid}_traj_${L}.png?v=${v}`, caption: cap });
  const seen = new Set(), lines = [...J.items].sort((a, b) => a.k - b.k || b.p - a.p).filter(it => !seen.has(it.city.ru + it.day) && seen.add(it.city.ru + it.day)).slice(0, 10)
    .map(it => `<b>${esc(it.city[lang] || it.city.ru)} · ${dayLabel(it.day, lang)} · ${it.snow ? '❄' : '☂'} ${it.p}%</b>\n🧭 ${esc(it.text[lang] || it.text.ru)}`);
  return tg(env, 'sendMessage', { chat_id: chat, text: [`🧭 <b>${X.title}</b>`, '', lines.join('\n\n'), '', `<i>${X.foot}</i>`].join('\n').slice(0, 4000), parse_mode: 'HTML' });
}

/* ---------- the weather at the person's place: a word only when it matters ----------
   At each entry (/start, or the first message of the day) the bot asks where the person is; the place they send is
   watched until the next time: rain or snow starting (or within the hour), a thunderstorm, great heat, hard frost,
   strong wind. Normal weather: silence. Night (23:00–07:00): silence. Open-Meteo, checked every 20 minutes. */
const WATCH_CRON = '10,30,50 * * * *';
const WX = {
  ru: { ask: '📍 <b>Где вы сейчас?</b>\nОтправьте своё место — я сообщу, если начнётся дождь или снег, будет гроза, сильная жара, мороз или ветер. В обычную погоду писать не буду.', send: '📍 Отправить моё место', sameP: '✅ Я там же: ', off: '🔕 Не предупреждать',
    onOk: '🔔 Слежу за погодой: <b>{p}</b>\nСообщу, если начнётся дождь или снег, будет гроза, сильная жара, мороз или сильный ветер. В обычную погоду — тишина, ночью тоже.', offOk: '🔕 Хорошо, предупреждать не буду. Включить снова — отправьте 📍 своё место.', here: 'ваше место',
    rainSoon: '🌧 <b>{p}</b>: примерно через {m} мин начнётся дождь', snowSoon: '🌨 <b>{p}</b>: примерно через {m} мин начнётся снег', rainNow: '🌧 <b>{p}</b>: у вас начался дождь', snowNow: '🌨 <b>{p}</b>: у вас пошёл снег',
    storm: '⛈ <b>{p}</b>: гроза в ближайший час — лучше быть в помещении', heat: '🥵 <b>{p}</b>: очень жарко — {t}, ощущается как {f}. Пейте воду, в полдень лучше в тень', cold: '🥶 <b>{p}</b>: сильный мороз — {t}, ощущается как {f}. Одевайтесь теплее', wind: '💨 <b>{p}</b>: сильный ветер, порывы до {w} м/с' },
  uz: { ask: '📍 <b>Hozir qayerdasiz?</b>\nJoyingizni yuboring — yomg‘ir yoki qor boshlansa, momaqaldiroq, kuchli issiq, sovuq yoki shamol bo‘lsa xabar beraman. Oddiy ob-havoda yozmayman.', send: '📍 Joyimni yuborish', sameP: '✅ O‘sha joydaman: ', off: '🔕 Ogohlantirmaslik',
    onOk: '🔔 Ob-havoni kuzataman: <b>{p}</b>\nYomg‘ir yoki qor boshlansa, momaqaldiroq, kuchli issiq, sovuq yoki kuchli shamol bo‘lsa xabar beraman. Oddiy ob-havoda va kechasi — jimlik.', offOk: '🔕 Yaxshi, ogohlantirmayman. Qayta yoqish — 📍 joyingizni yuboring.', here: 'joyingiz',
    rainSoon: '🌧 <b>{p}</b>: taxminan {m} daqiqadan keyin yomg‘ir boshlanadi', snowSoon: '🌨 <b>{p}</b>: taxminan {m} daqiqadan keyin qor boshlanadi', rainNow: '🌧 <b>{p}</b>: yomg‘ir boshlandi', snowNow: '🌨 <b>{p}</b>: qor yog‘a boshladi',
    storm: '⛈ <b>{p}</b>: yaqin bir soatda momaqaldiroq — xonada bo‘lgan ma’qul', heat: '🥵 <b>{p}</b>: juda issiq — {t}, {f} kabi seziladi. Suv iching, tushda soyada bo‘ling', cold: '🥶 <b>{p}</b>: qattiq sovuq — {t}, {f} kabi seziladi. Issiq kiyining', wind: '💨 <b>{p}</b>: kuchli shamol, {w} m/s gacha' },
  tr: { ask: '📍 <b>Şu an neredesiniz?</b>\nKonumunuzu gönderin — yağmur veya kar başlarsa, fırtına, aşırı sıcak, don veya rüzgâr olursa haber veririm. Normal havada yazmam.', send: '📍 Konumumu gönder', sameP: '✅ Aynı yerdeyim: ', off: '🔕 Uyarma',
    onOk: '🔔 Havayı izliyorum: <b>{p}</b>\nYağmur veya kar başlarsa, fırtına, aşırı sıcak, don veya kuvvetli rüzgâr olursa haber veririm. Normal havada ve gece — sessizlik.', offOk: '🔕 Tamam, uyarmayacağım. Tekrar açmak için 📍 konumunuzu gönderin.', here: 'konumunuz',
    rainSoon: '🌧 <b>{p}</b>: yaklaşık {m} dk sonra yağmur başlayacak', snowSoon: '🌨 <b>{p}</b>: yaklaşık {m} dk sonra kar başlayacak', rainNow: '🌧 <b>{p}</b>: yağmur başladı', snowNow: '🌨 <b>{p}</b>: kar yağmaya başladı',
    storm: '⛈ <b>{p}</b>: bir saat içinde gök gürültülü fırtına — içeride olun', heat: '🥵 <b>{p}</b>: çok sıcak — {t}, hissedilen {f}. Su için, öğlen gölgede kalın', cold: '🥶 <b>{p}</b>: sert ayaz — {t}, hissedilen {f}. Sıkı giyinin', wind: '💨 <b>{p}</b>: kuvvetli rüzgâr, {w} m/s’ye kadar' } };
async function watchGet(env, chat) { if (!env.DB) return null; await db(env); return env.DB.prepare('SELECT * FROM watch WHERE chat_id = ?1').bind(chat).first(); }
async function watchSet(env, chat, f) {
  if (!env.DB) return; await db(env);
  const w = (await watchGet(env, chat)) || {}, n = { ...w, ...f };
  await env.DB.prepare('INSERT OR REPLACE INTO watch (chat_id, lat, lon, name, lang, on_, asked, st, checked) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9)')
    .bind(chat, n.lat ?? null, n.lon ?? null, n.name ?? null, n.lang ?? null, n.on_ ?? 0, n.asked ?? null, n.st ?? '{}', n.checked ?? null).run();
}
// "where are you now?" — once a day at most; not after the person said no
async function watchAsk(env, chat, lang) {
  const W = WX[lang] || WX.ru, w = await watchGet(env, chat);
  if (w && (w.asked === todayTZ() || (w.on_ === 0 && w.asked))) return;
  await watchSet(env, chat, { asked: todayTZ(), lang });
  const kb = [[{ text: W.send, request_location: true }], ...(w && w.lat != null ? [[{ text: W.sameP + (w.name || '📍') }]] : []), [{ text: W.off }]];
  return tg(env, 'sendMessage', { chat_id: chat, text: W.ask, parse_mode: 'HTML', reply_markup: { keyboard: kb, resize_keyboard: true, one_time_keyboard: true } });
}
async function watchTick(env) {
  if (!env.DB) return; await db(env);
  const rows = (await env.DB.prepare("SELECT * FROM watch WHERE on_ = 1 AND lat IS NOT NULL ORDER BY COALESCE(checked, '') LIMIT 22").all()).results;
  for (const w of rows) {
    const now = Date.now(); await env.DB.prepare('UPDATE watch SET checked = ?2 WHERE chat_id = ?1').bind(w.chat_id, new Date(now).toISOString()).run();
    const j = await fetch(`https://api.open-meteo.com/v1/forecast?latitude=${(+w.lat).toFixed(3)}&longitude=${(+w.lon).toFixed(3)}&current=temperature_2m,apparent_temperature,precipitation,rain,snowfall,weather_code,wind_gusts_10m&minutely_15=precipitation,snowfall,weather_code&forecast_minutely_15=6&wind_speed_unit=ms&timezone=auto`).then(r => r.ok ? r.json() : null).catch(() => null);
    if (!j || !j.current) continue;
    const hourL = new Date(now + (j.utc_offset_seconds || 0) * 1000).getUTCHours();
    if (hourL >= 23 || hourL < 7) continue;  // night: silence
    const st = JSON.parse(w.st || '{}'), c = j.current, m = j.minutely_15 || {}, lang = WX[w.lang] ? w.lang : 'ru', X = WX[lang], p = esc(w.name || X.here), day = todayTZ();
    const ago = k => now - (st[k] || 0), out = [];
    const snowy = (c.snowfall || 0) > 0 || (c.temperature_2m ?? 9) <= 0.5;
    const wetNow = (c.precipitation || 0) >= 0.1, soonI = (m.precipitation || []).slice(1, 5).findIndex(v => v >= 0.15);  // 15-min steps: within the hour
    if ((wetNow || soonI >= 0) && ago('rain') > 3 * 3600e3 && !st.wet) {
      out.push(wetNow ? (snowy ? X.snowNow : X.rainNow).replace('{p}', p) : (snowy ? X.snowSoon : X.rainSoon).replace('{p}', p).replace('{m}', String((soonI + 1) * 15)));
      st.rain = now;
    }
    st.wet = wetNow || soonI >= 0 ? 1 : (st.wet && ago('rain') < 2 * 3600e3 ? 1 : 0);  // dry again for a while: the next rain is news again
    const code = Math.max(c.weather_code || 0, ...(m.weather_code || []).slice(0, 4));
    if (code >= 95 && ago('storm') > 3 * 3600e3) { out.push(X.storm.replace('{p}', p)); st.storm = now; }
    const t = c.temperature_2m, f = c.apparent_temperature, ft = v => `${v > 0 ? '+' : ''}${Math.round(v)}°`;
    if ((t >= 38 || f >= 40) && st.heat !== day) { out.push(X.heat.replace('{p}', p).replace('{t}', ft(t)).replace('{f}', ft(f))); st.heat = day; }
    if ((t <= -15 || f <= -20) && st.cold !== day) { out.push(X.cold.replace('{p}', p).replace('{t}', ft(t)).replace('{f}', ft(f))); st.cold = day; }
    if ((c.wind_gusts_10m || 0) >= 15 && ago('wind') > 6 * 3600e3) { out.push(X.wind.replace('{p}', p).replace('{w}', String(Math.round(c.wind_gusts_10m)))); st.wind = now; }
    await env.DB.prepare('UPDATE watch SET st = ?2 WHERE chat_id = ?1').bind(w.chat_id, JSON.stringify(st)).run();
    if (!out.length) continue;  // normal weather: nothing
    const r = await tg(env, 'sendMessage', { chat_id: w.chat_id, text: out.join('\n\n'), parse_mode: 'HTML' });
    if (!r.ok && /blocked|deactivated|chat not found/i.test(r.description || '')) await env.DB.prepare('UPDATE watch SET on_ = 0 WHERE chat_id = ?1').bind(w.chat_id).run();
  }
}

/* ---------- automatic sending of one section at the hour the person picked (⏰) ---------- */
const NX_ = {
  ru: { btn: '⏰ Присылать автоматически', ask: '⏰ Во сколько присылать «{s}»? Время — по Ташкенту.', weekly: ' (по понедельникам)', off: '🔕 Не присылать', on: '✅ «{s}» будет приходить каждый день в {h}.', onW: '✅ «{s}» будет приходить по понедельникам в {h}.', offT: '🔕 «{s}» больше не присылаю.', list: '⏰ <b>Мои уведомления</b>', none: 'Пока ничего не приходит автоматически. Нажмите раздел ниже и выберите время:', at: 'в', edit: 'Нажмите раздел, чтобы поменять время или выключить:', daily: '🔔 Прогноз каждое утро — включается кнопкой «🔔 Прогноз каждое утро»' },
  uz: { btn: '⏰ Avtomatik yuborish', ask: '⏰ «{s}» soat nechada kelsin? Vaqt — Toshkent bo‘yicha.', weekly: ' (dushanba kunlari)', off: '🔕 Yubormaslik', on: '✅ «{s}» har kuni soat {h} da keladi.', onW: '✅ «{s}» har dushanba soat {h} da keladi.', offT: '🔕 «{s}» endi yuborilmaydi.', list: '⏰ <b>Bildirishnomalarim</b>', none: 'Hozircha hech narsa avtomatik kelmaydi. Quyidagi bo‘limni bosing va vaqtni tanlang:', at: 'soat', edit: 'Vaqtni o‘zgartirish yoki o‘chirish uchun bo‘limni bosing:', daily: '🔔 Har tongi prognoz — «🔔 Har tongi prognoz» tugmasi bilan yoqiladi' },
  tr: { btn: '⏰ Otomatik gönder', ask: '⏰ «{s}» saat kaçta gelsin? Saat — Taşkent saati.', weekly: ' (pazartesi günleri)', off: '🔕 Gönderme', on: '✅ «{s}» her gün saat {h} gelecek.', onW: '✅ «{s}» her pazartesi saat {h} gelecek.', offT: '🔕 «{s}» artık gönderilmeyecek.', list: '⏰ <b>Bildirimlerim</b>', none: 'Şu anda otomatik bir şey gelmiyor. Aşağıdan bölüm seçip saati belirleyin:', at: 'saat', edit: 'Saati değiştirmek veya kapatmak için bölüme dokunun:', daily: '🔔 Her sabah tahmin — «🔔 Her sabah tahmin» düğmesiyle açılır' } };
const NSEC = ['hourly', 'outlook', 'mtn', 'air'];  // sections that can come by themselves (the 15 days already have 🔔 Прогноз каждое утро)
const NWEEKLY = { outlook: true };                   // the weeks and months change slowly: once a week is enough
const secName = (sec, lang) => ((RKL[lang] || RKL.ru)[sec] || sec).replace(/^\S+\s/, '');
const notifBtn = (lang, sec) => ({ text: (NX_[lang] || NX_.ru).btn, callback_data: `NS:${lang}:${sec}` });
async function notifGet(env, chat, sec) { if (!env.DB) return null; await db(env); return env.DB.prepare('SELECT * FROM notif WHERE chat_id = ?1 AND sec = ?2').bind(chat, sec).first(); }
async function notifAsk(env, chat, lang, sec) {
  const N = NX_[lang] || NX_.ru, cur = await notifGet(env, chat, sec), hrs = HOURS;
  const rows = [hrs.slice(0, 5), hrs.slice(5)].map(r => r.map(h => ({ text: `${cur && cur.hour === h ? '✅ ' : ''}${hh(h)}`, callback_data: `NT:${lang}:${sec}:${h}` })));
  if (cur) rows.push([{ text: N.off, callback_data: `NO:${lang}:${sec}` }]);
  return tg(env, 'sendMessage', { chat_id: chat, text: N.ask.replace('{s}', secName(sec, lang)) + (NWEEKLY[sec] ? N.weekly : ''), reply_markup: { inline_keyboard: rows } });
}
async function notifSet(env, chat, lang, sec, hour, msgId) {
  const N = NX_[lang] || NX_.ru, now = new Date(Date.now() + TZ * 3600e3), u = chat > 0 ? await getUser(env, chat) : { region: regionsOf(await sub(env, chat))[0] };
  // an hour already past today: the first one comes tomorrow
  const last = hour <= now.getUTCHours() ? todayTZ() : '';
  await env.DB.prepare('INSERT INTO notif (chat_id, sec, hour, lang, region, last_day, added) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7) ON CONFLICT(chat_id, sec) DO UPDATE SET hour = ?3, lang = ?4, region = ?5, last_day = ?6')
    .bind(chat, sec, hour, lang, (u && u.region) || 'UZ', last, new Date().toISOString()).run();
  const text = (NWEEKLY[sec] ? N.onW : N.on).replace('{s}', secName(sec, lang)).replace('{h}', hh(hour));
  if (chat < 0) { if (msgId) await tg(env, 'deleteMessage', { chat_id: chat, message_id: msgId }); return groupNotif(env, chat, lang, null, text); }  // a group: back to its menu
  return msgId ? tg(env, 'editMessageText', { chat_id: chat, message_id: msgId, text }) : tg(env, 'sendMessage', { chat_id: chat, text });
}
async function notifList(env, chat, lang) {
  const N = NX_[lang] || NX_.ru; if (!env.DB) return; await db(env);
  const rows = (await env.DB.prepare('SELECT * FROM notif WHERE chat_id = ?1').bind(chat).all()).results, by = Object.fromEntries(rows.map(r => [r.sec, r]));
  const d = await sub(env, chat), lines = [N.list, ''];
  for (const sec of NSEC) if (by[sec]) lines.push(`✅ ${secName(sec, lang)} — ${N.at} ${hh(by[sec].hour)}${NWEEKLY[sec] ? N.weekly : ''}`);
  if (d) lines.push(`✅ ${secName('daily', lang)} — ${N.at} ${hh(d.post_hour ?? POST_HOUR)}`);
  lines.push('', rows.length || d ? N.edit : N.none);
  const kb = NSEC.map(sec => [{ text: `${by[sec] ? '✅' : '➕'} ${(RKL[lang] || RKL.ru)[sec]}${by[sec] ? ` · ${hh(by[sec].hour)}` : ''}`, callback_data: `NS:${lang}:${sec}` }]);
  return tg(env, 'sendMessage', { chat_id: chat, text: lines.join('\n') + (d ? '' : `\n\n<i>${N.daily}</i>`), parse_mode: 'HTML', reply_markup: { inline_keyboard: kb } });
}
// a group or channel: one message with every section that can come by itself, its hour, and "turn everything on / off"
const GNX = {
  ru: { head: '⏰ <b>Что присылать в этот чат</b>', main: '🗓 Ежедневный прогноз (главный пост) — в {h}, страны: {c}. Изменить: /settings', snow: '❄️ Сигнал о снеге в горах', tip: 'Нажмите раздел, чтобы выбрать время или выключить. Время — по Ташкенту. Менять могут только администраторы.', all: '✅ Включить всё', allOff: '🔕 Выключить всё', allOn: '✅ Включено всё: разделы будут приходить в {h} (недели и месяцы — по понедельникам).', offAll: '🔕 Дополнительные разделы выключены. Ежедневный прогноз остаётся.' },
  uz: { head: '⏰ <b>Bu chatga nima yuborilsin</b>', main: '🗓 Kunlik prognoz (asosiy post) — soat {h}, davlatlar: {c}. O‘zgartirish: /sozla', snow: '❄️ Tog‘larda qor haqida xabar', tip: 'Vaqtni tanlash yoki o‘chirish uchun bo‘limni bosing. Vaqt — Toshkent bo‘yicha. Faqat adminlar o‘zgartira oladi.', all: '✅ Hammasini yoqish', allOff: '🔕 Hammasini o‘chirish', allOn: '✅ Hammasi yoqildi: bo‘limlar soat {h} da keladi (haftalar va oylar — dushanba kunlari).', offAll: '🔕 Qo‘shimcha bo‘limlar o‘chirildi. Kunlik prognoz qoladi.' },
  tr: { head: '⏰ <b>Bu sohbete ne gönderilsin</b>', main: '🗓 Günlük tahmin (ana gönderi) — saat {h}, ülkeler: {c}. Değiştirmek: /settings', snow: '❄️ Dağlarda kar bildirimi', tip: 'Saati seçmek veya kapatmak için bölüme dokunun. Saat — Taşkent saati. Yalnızca yöneticiler değiştirebilir.', all: '✅ Hepsini aç', allOff: '🔕 Hepsini kapat', allOn: '✅ Hepsi açıldı: bölümler saat {h} gelecek (haftalar ve aylar — pazartesi günleri).', offAll: '🔕 Ek bölümler kapatıldı. Günlük tahmin devam ediyor.' } };
async function groupNotif(env, chat, lang, msgId, note) {
  if (!env.DB) return; await db(env);
  const G = GNX[lang] || GNX.ru, s0 = await sub(env, chat), regs = regionsOf(s0), uz = !regs.length || regs.includes('UZ');
  const rows = (await env.DB.prepare('SELECT * FROM notif WHERE chat_id = ?1').bind(chat).all()).results, by = Object.fromEntries(rows.map(r => [r.sec, r]));
  const snow = await mtnSub(env, chat), secs = NSEC.filter(x => uz || !['outlook', 'mtn'].includes(x));  // weeks/months and the mountains are about Uzbekistan
  const text = [...(note ? [note, ''] : []), G.head, '', G.main.replace('{h}', hh(s0 && s0.post_hour != null ? s0.post_hour : POST_HOUR)).replace('{c}', (regs.length ? regs : ['UZ']).map(r => `${FLAG[r] || ''} ${NAMES[r] ? NAMES[r][lang] : r}`).join(', ')), '', G.tip].join('\n');
  const kb = [...secs.map(sec => [{ text: `${by[sec] ? '✅' : '➕'} ${(RKL[lang] || RKL.ru)[sec]}${by[sec] ? ` · ${hh(by[sec].hour)}` : ''}`, callback_data: `NS:${lang}:${sec}` }]),
    ...(uz ? [[{ text: `${snow ? '✅' : '➕'} ${G.snow}`, callback_data: `WS:${lang}` }]] : []),
    [{ text: G.all, callback_data: `WA:${lang}` }, { text: G.allOff, callback_data: `WX:${lang}` }]];
  const body = { chat_id: chat, text, parse_mode: 'HTML', reply_markup: { inline_keyboard: kb } };
  if (msgId) { const r = await tg(env, 'editMessageText', { ...body, message_id: msgId }); if (r.ok || /not modified/.test(r.description || '')) return r; }
  return tg(env, 'sendMessage', body);
}
async function groupAll(env, chat, lang, on) {  // every section at the group's post hour (and the snow signal), or all of them off
  const s0 = await sub(env, chat), h = s0 && s0.post_hour != null ? s0.post_hour : POST_HOUR, regs = regionsOf(s0), uz = !regs.length || regs.includes('UZ');
  if (!on) { await env.DB.prepare('DELETE FROM notif WHERE chat_id = ?1').bind(chat).run(); await env.DB.prepare('DELETE FROM mtn WHERE chat_id = ?1').bind(chat).run(); return; }
  const last = h <= new Date(Date.now() + TZ * 3600e3).getUTCHours() ? todayTZ() : '';
  for (const sec of NSEC.filter(x => uz || !['outlook', 'mtn'].includes(x)))
    await env.DB.prepare('INSERT INTO notif (chat_id, sec, hour, lang, region, last_day, added) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7) ON CONFLICT(chat_id, sec) DO UPDATE SET hour = ?3, lang = ?4, region = ?5')
      .bind(chat, sec, h, lang, regs[0] || 'UZ', last, new Date().toISOString()).run();
  if (uz) await env.DB.prepare('INSERT OR REPLACE INTO mtn (chat_id, lang, ver, added) VALUES (?1, ?2, ?3, ?4)').bind(chat, lang, (await kv(env, 'mtn_ver')) || '', new Date().toISOString()).run();
}

// each cron run: the sections that are due now (a few per run: videos and pictures take time)
async function notifTick(env) {
  if (!env.DB) return; await db(env);
  const now = new Date(Date.now() + TZ * 3600e3), day = todayTZ(), hour = now.getUTCHours(), monday = now.getUTCDay() === 1;
  let due = (await env.DB.prepare("SELECT * FROM notif WHERE hour <= ?1 AND COALESCE(last_day, '') <> ?2 ORDER BY hour LIMIT 18").bind(hour, day).all()).results;
  if (due.some(n => n.sec !== 'air')) { const F = await siteFresh(env); if (!F.fresh) due = due.filter(n => n.sec === 'air' || hour - n.hour >= HOLD_MAX_H); }
  for (const n of due.slice(0, 6)) {
    await env.DB.prepare('UPDATE notif SET last_day = ?3 WHERE chat_id = ?1 AND sec = ?2').bind(n.chat_id, n.sec, day).run();
    if (NWEEKLY[n.sec] && !monday) continue;
    const lang = RKL[n.lang] ? n.lang : 'ru', rid = NAMES[n.region] ? n.region : 'UZ';  // (groups: saved from their settings)
    let r = null;
    try {
      if (n.sec === 'hourly') r = await sendHourly(env, n.chat_id, lang, rid);
      else if (n.sec === 'outlook') r = await sendOutlookPart(env, n.chat_id, lang, 'w1');
      else if (n.sec === 'mtn') r = await sendMountains(env, n.chat_id, lang);
      else if (n.sec === 'air') r = await sendAir(env, n.chat_id, lang, rid);
    } catch (e) { console.log('notif', n.sec, e && e.stack); }
    if (r && !r.ok && /blocked|deactivated|chat not found|kicked|not a member|was deleted|not enough rights/i.test(r.description || '')) await env.DB.prepare('DELETE FROM notif WHERE chat_id = ?1').bind(n.chat_id).run();
  }
}

/* ---------- the air today: dust and air quality hour by hour at the person's place (CAMS via Open-Meteo) ---------- */
const AQX = {
  ru: { title: '🌫 <b>Воздух сегодня</b>', now: 'Сейчас', max: 'Хуже всего сегодня', hours: 'По часам (индекс AQI)', pm: 'PM10 {a} · PM2.5 {b} мкг/м³', dust: 'пыль {d} мкг/м³',
    bands: ['хорошо', 'умеренно', 'вредно для чувствительных', 'вредно', 'очень вредно', 'опасно'],
    tips: ['', '', '🙂 Людям с астмой и детям лучше меньше быть на улице', '😷 Сократите время на улице, закройте окна', '😷 Маска N95, без нужды не выходите', '⛔ Оставайтесь дома, закройте окна'],
    src: 'Прогноз CAMS (ECMWF Copernicus) · Open-Meteo', none: 'Не удалось получить данные о воздухе, попробуйте позже.', map: 'Карта пыли по Узбекистану' },
  uz: { title: '🌫 <b>Bugungi havo sifati</b>', now: 'Hozir', max: 'Bugun eng yomoni', hours: 'Soatma-soat (AQI indeksi)', pm: 'PM10 {a} · PM2.5 {b} mkg/m³', dust: 'chang {d} mkg/m³',
    bands: ['yaxshi', 'o‘rtacha', 'sezgirlar uchun zararli', 'zararli', 'juda zararli', 'xavfli'],
    tips: ['', '', '🙂 Astmasi borlar va bolalar ko‘chada kamroq bo‘lgani yaxshi', '😷 Ko‘chada kamroq bo‘ling, derazalarni yoping', '😷 N95 niqob, keraksiz chiqmang', '⛔ Uyda qoling, derazalarni yoping'],
    src: 'CAMS prognozi (ECMWF Copernicus) · Open-Meteo', none: 'Havo ma’lumotlarini olib bo‘lmadi, keyinroq urinib ko‘ring.', map: 'O‘zbekiston bo‘yicha chang xaritasi' },
  tr: { title: '🌫 <b>Bugün hava kalitesi</b>', now: 'Şimdi', max: 'Bugün en kötü', hours: 'Saat saat (AQI endeksi)', pm: 'PM10 {a} · PM2.5 {b} µg/m³', dust: 'toz {d} µg/m³',
    bands: ['iyi', 'orta', 'hassaslar için zararlı', 'zararlı', 'çok zararlı', 'tehlikeli'],
    tips: ['', '', '🙂 Astımlılar ve çocuklar dışarıda daha az kalsın', '😷 Dışarıda daha az kalın, pencereleri kapatın', '😷 N95 maske, gereksiz çıkmayın', '⛔ Evde kalın, pencereleri kapatın'],
    src: 'CAMS tahmini (ECMWF Copernicus) · Open-Meteo', none: 'Hava verisi alınamadı, sonra tekrar deneyin.', map: 'Özbekistan toz haritası' } };
const aqBand = v => v == null ? 0 : v <= 50 ? 0 : v <= 100 ? 1 : v <= 150 ? 2 : v <= 200 ? 3 : v <= 300 ? 4 : 5;
const AQ_DOT = ['🟢', '🟡', '🟠', '🔴', '🟣', '🟤'];
async function sendAir(env, chat, lang, rid) {
  const X = AQX[lang] || AQX.ru, u = chat > 0 ? await getUser(env, chat) : null, pl = u && u.place ? JSON.parse(u.place) : null;
  let lat, lon, name;
  if (pl) { lat = +pl[0]; lon = +pl[1]; const np = await nearestPlace(env, lat, lon); name = np ? `${FLAG[np[4]] || '📍'} ${pname(np, lang)}` : `📍 ${lat.toFixed(2)}, ${lon.toFixed(2)}`; }
  else { const C = (await cities(env, rid, lang)) || (await cities(env, rid, 'ru')), c = C && C.cities.find(c => c.lat != null);
    if (c) { lat = c.lat; lon = c.lon; name = `${FLAG[rid] || ''} ${c.name}`; } else { lat = 41.31; lon = 69.28; name = '🇺🇿 Toshkent'; } }
  const j = await fetch(`https://air-quality-api.open-meteo.com/v1/air-quality?latitude=${lat.toFixed(3)}&longitude=${lon.toFixed(3)}&hourly=us_aqi,pm10,pm2_5,dust&current=us_aqi,pm10,pm2_5,dust&timezone=auto&forecast_days=1`).then(r => r.ok ? r.json() : null).catch(() => null);
  if (!j || !j.hourly) return tg(env, 'sendMessage', { chat_id: chat, text: X.none, ...(chat > 0 ? { reply_markup: { inline_keyboard: [[notifBtn(lang, 'air')]] } } : {}) });
  const Hh = j.hourly, c = j.current || {}, b = aqBand(c.us_aqi), r0 = v => v == null ? '—' : Math.round(v);
  let mi = 0; Hh.us_aqi.forEach((v, i) => { if (v != null && v > (Hh.us_aqi[mi] ?? -1)) mi = i; });
  const hrs = []; for (let i = 0; i < Hh.time.length; i += 3) { const v = Hh.us_aqi[i]; hrs.push(`${Hh.time[i].slice(11, 13)}:00 ${AQ_DOT[aqBand(v)]} ${r0(v)}`); }
  const out = [`${X.title} · <b>${esc(name)}</b>`, '',
    `${X.now}: ${AQ_DOT[b]} <b>${r0(c.us_aqi)}</b> — ${X.bands[b]}`, `   ${X.pm.replace('{a}', r0(c.pm10)).replace('{b}', r0(c.pm2_5))}${c.dust >= 20 ? ` · ${X.dust.replace('{d}', r0(c.dust))}` : ''}`,
    `${X.max}: ${AQ_DOT[aqBand(Hh.us_aqi[mi])]} <b>${r0(Hh.us_aqi[mi])}</b> ${X.bands[aqBand(Hh.us_aqi[mi])]} · ${Hh.time[mi].slice(11, 16)}`,
    ...(X.tips[Math.max(b, aqBand(Hh.us_aqi[mi]))] ? ['', X.tips[Math.max(b, aqBand(Hh.us_aqi[mi]))]] : []),
    '', `<b>${X.hours}</b>`, `<pre>${hrs.reduce((a, x, i) => a + x.padEnd(14) + (i % 2 ? '\n' : ''), '')}</pre>`,
    `🟢 ≤50 · 🟡 ≤100 · 🟠 ≤150 · 🔴 ≤200 · 🟣 ≤300 · 🟤 >300`, `<i>${X.src}</i>`];
  const kb = chat > 0 ? { inline_keyboard: [[notifBtn(lang, 'air')]] } : undefined;
  // in Uzbekistan the dust map of today goes first (prob/outlook.py, dust0)
  if (rid === 'UZ') {
    const I = await (await fetch(`${base(env)}/prob/outlook/index.json?t=${fresh()}`)).json().catch(() => null), it = I && (I.items.find(i => i.key === 'dust' && i.lang === lang) || I.items.find(i => i.key === 'dust'));
    if (it) await tg(env, 'sendPhoto', { chat_id: chat, photo: `${base(env)}/prob/${(it.imgs || [it.img])[0]}?v=${encodeURIComponent(I.made || '')}`, caption: `🌫 ${X.map}` });
  }
  return tg(env, 'sendMessage', { chat_id: chat, text: out.join('\n'), parse_mode: 'HTML', ...(kb ? { reply_markup: kb } : {}) });
}

/* ---------- mountains of Uzbekistan: fresh snow and good days for a trip (site/prob/mountains.json, prob/mountains.py) ---------- */
const MTX = {
  ru: { title: '🏔 <b>Горы Узбекистана: снег и поездки</b>', rain: '🌧 Дождь', mm: 'мм', m: 'м', snow: '❄️ Ожидается снег', noSnow: '❄️ Снегопадов в ближайшие 16 дней не видно', cm: 'см', cover: '⛄ Снег лежит', go: '🥾 Когда ехать', noGo: '🥾 Хороших дней для поездки пока не видно', after: '👉 После снега лучше всего', wind: 'ветер до', ms: 'м/с',
    foot: 'Прогноз на 16 дней с поправкой на высоту · ECMWF, DWD, NOAA (Open-Meteo). Снегопад — от 2 см за сутки; хороший день — сухо, солнечно, без сильного ветра.', sub: '🔔 Сигнал о снеге в горах', unsub: '🔕 Выключить сигнал о снеге', on: '🔔 Сигнал включён: напишу, как только в горах ожидается снег, и подскажу, в какой день лучше ехать.', off: '🔕 Сигнал о снеге выключен.', alert: '❄️ <b>В горах ожидается снег!</b>', fresh: (n, cm) => `ожидается ~${n} ${cm} снега`, all: '🏔 Все горы', none: 'Данные по горам ещё готовятся, попробуйте чуть позже.' },
  uz: { title: '🏔 <b>O‘zbekiston tog‘lari: qor va sayohat</b>', rain: '🌧 Yomg‘ir', mm: 'mm', m: 'm', snow: '❄️ Qor kutilmoqda', noSnow: '❄️ Yaqin 16 kunda qor yog‘ishi kutilmayapti', cm: 'sm', cover: '⛄ Qor qoplami', go: '🥾 Qachon borish kerak', noGo: '🥾 Hozircha sayohat uchun yaxshi kun ko‘rinmayapti', after: '👉 Qordan keyin eng yaxshi kun', wind: 'shamol', ms: 'm/s',
    foot: '16 kunlik prognoz, balandlikka moslangan · ECMWF, DWD, NOAA (Open-Meteo). Qor yog‘ishi — sutkada 2 sm dan; yaxshi kun — quruq, quyoshli, kuchli shamolsiz.', sub: '🔔 Tog‘da qor haqida xabar', unsub: '🔕 Qor xabarini o‘chirish', on: '🔔 Xabar yoqildi: tog‘larda qor kutilishi bilan yozaman va qaysi kuni borish yaxshiligini aytaman.', off: '🔕 Qor xabari o‘chirildi.', alert: '❄️ <b>Tog‘larda qor kutilmoqda!</b>', fresh: (n, cm) => `~${n} ${cm} qor kutilmoqda`, all: '🏔 Barcha tog‘lar', none: 'Tog‘lar ma’lumoti hali tayyorlanmoqda, birozdan keyin urinib ko‘ring.' },
  tr: { title: '🏔 <b>Özbekistan dağları: kar ve gezi</b>', rain: '🌧 Yağmur', mm: 'mm', m: 'm', snow: '❄️ Kar bekleniyor', noSnow: '❄️ Önümüzdeki 16 günde kar yağışı görünmüyor', cm: 'cm', cover: '⛄ Kar örtüsü', go: '🥾 Ne zaman gidilir', noGo: '🥾 Şimdilik gezi için iyi gün görünmüyor', after: '👉 Kardan sonra en iyi gün', wind: 'rüzgâr', ms: 'm/s',
    foot: 'Yüksekliğe göre düzeltilmiş 16 günlük tahmin · ECMWF, DWD, NOAA (Open-Meteo). Kar yağışı — günde 2 cm’den; iyi gün — kuru, güneşli, sert rüzgârsız.', sub: '🔔 Dağlarda kar bildirimi', unsub: '🔕 Kar bildirimini kapat', on: '🔔 Bildirim açık: dağlarda kar beklendiğinde yazacağım ve hangi gün gitmenin iyi olduğunu söyleyeceğim.', off: '🔕 Kar bildirimi kapatıldı.', alert: '❄️ <b>Dağlarda kar bekleniyor!</b>', fresh: (n, cm) => `~${n} ${cm} kar bekleniyor`, all: '🏔 Tüm dağlar', none: 'Dağ verileri henüz hazırlanıyor, biraz sonra deneyin.' },
};
const wIcon = c => c == null ? '' : c <= 1 ? '☀️' : c === 2 ? '🌤' : c === 3 ? '☁️' : c <= 48 ? '🌫' : c <= 67 ? '🌧' : c <= 77 ? '🌨' : c <= 82 ? '🌦' : c <= 86 ? '🌨' : '⛈';
const sgn = t => `${t > 0 ? '+' : t < 0 ? '−' : ''}${Math.abs(Math.round(t))}°`;
async function mountainsData(env) {
  const r = await fetch(`${base(env)}/prob/mountains.json?t=${Date.now()}`, { cf: { cacheTtl: 0 } });
  return r.ok ? r.json().catch(() => null) : null;
}
const dayW = (d, lang) => { const X = MTX[lang] || MTX.ru; return `${dayLabel(d.d, lang)} ${wIcon(d.code)} ${sgn(d.tmin)}…${sgn(d.tmax)}, ${X.wind} ${Math.round(d.gust)} ${X.ms}`; };
// the first good day after a snow day (the same three days), for "when to go and see the snow"
const afterSnow = (sp, d) => sp.days.find(x => x.d > d && x.good > 0 && (new Date(x.d) - new Date(d)) <= 3 * 864e5);
async function mtnSub(env, chat) { if (!env.DB) return null; await db(env); return env.DB.prepare('SELECT * FROM mtn WHERE chat_id = ?1').bind(chat).first(); }
const MTA = { ru: { pick: 'Выберите место — расскажу про снег и лучшие дни:', all: '📋 Все горы текстом' },
              uz: { pick: 'Joyni tanlang — qor va eng yaxshi kunlarni aytaman:', all: '📋 Barcha tog‘lar matnda' },
              tr: { pick: 'Yeri seçin — karı ve en iyi günleri anlatayım:', all: '📋 Tüm dağlar metin olarak' } };
function spotLines(sp, M, lang) {
  const X = MTX[lang] || MTX.ru, today = todayTZ(), days = sp.days.filter(d => d.d >= today), snow = days.filter(d => d.sn >= (M.snow_cm || 2)), out = [];
  out.push(`<b>${esc(sp.name[lang] || sp.name.ru)}</b> · ${sp.elev} ${X.m} · ${esc(sp.area[lang] || sp.area.ru)}`);
  out.push(snow.length ? `${X.snow}: ${snow.slice(0, 4).map(d => `${dayLabel(d.d, lang)} ~${Math.round(d.sn)} ${X.cm}`).join(', ')}` : X.noSnow);
  const rain = days.slice(0, 10).filter(d => (d.rn || 0) >= 2);
  if (rain.length) out.push(`${X.rain}: ${rain.slice(0, 4).map(d => `${dayLabel(d.d, lang)} ~${Math.round(d.rn)} ${X.mm}`).join(', ')}`);
  if (days[0] && days[0].depth >= 1) out.push(`${X.cover}: ~${days[0].depth} ${X.cm}`);
  const a = snow.length ? afterSnow(sp, snow[0].d) : null;
  if (a) out.push(`${X.after}: <b>${dayW(a, lang)}</b>`);
  const g = days.slice(0, 10).filter(d => d.good > 0).sort((p, q) => q.good - p.good || (p.d < q.d ? -1 : 1)).slice(0, 3).sort((p, q) => p.d < q.d ? -1 : 1);
  if (g.length) { out.push(`${X.go}:`); g.forEach(d => out.push(`   • ${dayW(d, lang)}`)); } else out.push(X.noGo);
  return out;
}
// the segment buttons: one per place (two in a row, a snowflake where fresh snow is coming), all as text, the snow signal
async function mountainsKb(env, chat, lang, M, cur) {
  const X = MTX[lang] || MTX.ru, A = MTA[lang] || MTA.ru, today = todayTZ(), s = await mtnSub(env, chat);
  const b = M.spots.map(sp => ({ text: `${cur === sp.id ? '✅' : sp.days.some(d => d.d >= today && d.sn >= (M.snow_cm || 2)) ? '❄️' : '⛰'} ${sp.name[lang] || sp.name.ru}`, callback_data: `MP:${lang}:${sp.id}` }));
  const rows = []; for (let i = 0; i < b.length; i += 2) rows.push(b.slice(i, i + 2));
  rows.push([{ text: A.all, callback_data: `MA:${lang}` }]);
  rows.push([{ text: s ? X.unsub : X.sub, callback_data: `MS:${lang}`, style: s ? undefined : 'success' }]);
  rows.push([notifBtn(lang, 'mtn')]);
  return { inline_keyboard: rows };
}
async function sendMountains(env, chat, lang) {
  const X = MTX[lang] || MTX.ru, M = await mountainsData(env);
  if (!M || !M.spots) return tg(env, 'sendMessage', { chat_id: chat, text: X.none });
  // the picture (10 days for every place) with the places as buttons under it
  if (chat < 0) {  // a group or channel: the picture and every place as text, no buttons
    await tg(env, 'sendPhoto', { chat_id: chat, photo: `${base(env)}/prob/mountains_${MTX[lang] ? lang : 'ru'}.png?v=${fresh()}`, caption: X.title, parse_mode: 'HTML' });
    return sendMountainText(env, chat, lang, null);
  }
  const kb = await mountainsKb(env, chat, lang, M), cap = `${X.title}\n${(MTA[lang] || MTA.ru).pick}`;
  const r = await tg(env, 'sendPhoto', { chat_id: chat, photo: `${base(env)}/prob/mountains_${MTX[lang] ? lang : 'ru'}.png?v=${fresh()}`, caption: cap, parse_mode: 'HTML', reply_markup: kb });
  return r.ok ? r : tg(env, 'sendMessage', { chat_id: chat, text: cap, parse_mode: 'HTML', reply_markup: kb });
}
// one place (id) or all of them as text, with the same buttons
async function sendMountainText(env, chat, lang, id) {
  const X = MTX[lang] || MTX.ru, M = await mountainsData(env);
  if (!M || !M.spots) return tg(env, 'sendMessage', { chat_id: chat, text: X.none });
  const spots = id ? M.spots.filter(sp => sp.id === id) : M.spots, out = id ? [] : [X.title];
  spots.forEach(sp => { if (out.length) out.push(''); out.push(...spotLines(sp, M, lang)); });
  out.push('', `<i>${X.foot}</i>`);
  return tg(env, 'sendMessage', { chat_id: chat, text: out.join('\n').slice(0, 4000), parse_mode: 'HTML', disable_web_page_preview: true, ...(chat > 0 ? { reply_markup: await mountainsKb(env, chat, lang, M, id) } : {}) });
}
// after each update: tell everyone who asked about NEW fresh snow in the next 6 days, with the best day to go (07–21 h)
async function mtnTick(env) {
  if (!env.DB) return; await db(env);
  const hour = new Date(Date.now() + TZ * 3600e3).getUTCHours();
  if (hour < 7 || hour > 21) return;
  const M = await mountainsData(env); if (!M || !M.spots) return;
  if ((await kv(env, 'mtn_made')) !== M.made) {
    const today = todayTZ(), lim = new Date(Date.now() + TZ * 3600e3 + 6 * 864e5).toISOString().slice(0, 10);
    const prev = JSON.parse((await kv(env, 'mtn_keys')) || '[]'), ev = [];
    for (const sp of M.spots) for (const d of sp.days) if (d.sn >= (M.snow_cm || 2) && d.d >= today && d.d <= lim && !prev.includes(`${sp.id}|${d.d}`)) ev.push({ id: sp.id, d: d.d });
    if (ev.length) {
      await setKv(env, 'mtn_new', JSON.stringify(ev)); await setKv(env, 'mtn_ver', M.made);
      await setKv(env, 'mtn_keys', JSON.stringify([...prev.slice(-200), ...ev.map(e => `${e.id}|${e.d}`)]));
    }
    await setKv(env, 'mtn_made', M.made);
  }
  const ver = await kv(env, 'mtn_ver'); if (!ver) return;
  const ev = JSON.parse((await kv(env, 'mtn_new')) || '[]'); if (!ev.length) return;
  const due = (await env.DB.prepare("SELECT * FROM mtn WHERE COALESCE(ver, '') <> ?1 LIMIT 10").bind(ver).all()).results;
  for (const s of due) {
    const lang = MTX[s.lang] ? s.lang : 'ru', X = MTX[lang], out = [X.alert];
    for (const e of ev) {
      const sp = M.spots.find(x => x.id === e.id), d = sp && sp.days.find(x => x.d === e.d); if (!d) continue;
      out.push('', `<b>${esc(sp.name[lang] || sp.name.ru)}</b> — ${dayLabel(d.d, lang)}: ${X.fresh(Math.round(d.sn), X.cm)} ${wIcon(d.code)}`);
      const a = afterSnow(sp, d.d); if (a) out.push(`${X.after}: <b>${dayW(a, lang)}</b>`);
    }
    const r = await tg(env, 'sendMessage', { chat_id: s.chat_id, text: out.join('\n'), parse_mode: 'HTML', reply_markup: { inline_keyboard: [[{ text: X.all, callback_data: `MT:${lang}` }]] } });
    if (!r.ok && /blocked|deactivated|chat not found|kicked/i.test(r.description || '')) { await env.DB.prepare('DELETE FROM mtn WHERE chat_id = ?1').bind(s.chat_id).run(); continue; }
    await env.DB.prepare('UPDATE mtn SET ver = ?2 WHERE chat_id = ?1').bind(s.chat_id, ver).run();
  }
}
// the menu is a keyboard under the input field (white buttons, as in the screenshot): one place for everything, no buttons under messages
const RKL = {
  ru: { hourly: '⏱ Сегодня и завтра по часам', regions: '🗺 Погода по регионам', days: '🗓 Прогноз на 15 дней', video: '🎬 Видео-прогноз 15 дней', outlook: '📅 Недели и месяцы (карты)', mtn: '🏔 Горы: снег и поездки', now: '🌡 Погода сейчас', air: '🌫 Воздух сегодня', cities: '🏙 Выбрать город', loc: '📍 Отправить моё место', countries: '🌍 Сменить страну', daily: '🔔 Прогноз каждое утро', notif: '⏰ Мои уведомления', accuracy: '🎯 Точность прогноза', alerts: '⚠️ Опасная погода', site: '🗺 Карта-сайт и глобус', home: '🏠 Главное меню', reset: '🔄 Начать заново', back: '⬅️ Назад', help: 'ℹ️ Инструкция' },
  uz: { hourly: '⏱ Bugun va ertaga soatma-soat', regions: '🗺 Viloyatlar bo‘yicha', days: '🗓 15 kunlik prognoz', video: '🎬 15 kunlik video-prognoz', outlook: '📅 Haftalar va oylar (xaritalar)', mtn: '🏔 Tog‘lar: qor va sayohat', now: '🌡 Hozirgi ob-havo', air: '🌫 Bugungi havo sifati', cities: '🏙 Shaharni tanlash', loc: '📍 Joyimni yuborish', countries: '🌍 Davlatni almashtirish', daily: '🔔 Har tongi prognoz', notif: '⏰ Bildirishnomalarim', accuracy: '🎯 Prognoz aniqligi', alerts: '⚠️ Xavfli ob-havo', site: '🗺 Xarita-sayt va globus', home: '🏠 Bosh menyu', reset: '🔄 Qaytadan boshlash', back: '⬅️ Orqaga', help: 'ℹ️ Yo‘riqnoma' },
  tr: { hourly: '⏱ Bugün ve yarın saat saat', regions: '🗺 Bölgelere göre', days: '🗓 15 günlük tahmin', video: '🎬 15 günlük video tahmin', outlook: '📅 Haftalar ve aylar (haritalar)', mtn: '🏔 Dağlar: kar ve gezi', now: '🌡 Şu anki hava', air: '🌫 Bugün hava kalitesi', cities: '🏙 Şehir seç', loc: '📍 Konumumu gönder', countries: '🌍 Ülke değiştir', daily: '🔔 Her sabah tahmin', notif: '⏰ Bildirimlerim', accuracy: '🎯 Tahmin doğruluğu', alerts: '⚠️ Tehlikeli hava', site: '🗺 Harita-site ve küre', home: '🏠 Ana menü', reset: '🔄 Baştan başla', back: '⬅️ Geri', help: 'ℹ️ Kılavuz' } };
// the labels the keyboard had before (people may still have the old keyboard on their phone): they keep working
const RKL_OLD = {
  ru: { days: '🗓 15 дней', video: '🎬 Видео на 15 дней', outlook: '📅 Недели и месяцы', mtn: '🏔 Горы и снег', now: '🌡 Сейчас', cities: '🏙 Города', loc: '📍 Моё место', countries: '🌍 Страны', daily: '🔔 Каждый день', accuracy: '🎯 Точность', alerts: '⚠️ Предупреждения', site: '🗺 Сайт и глобус', home: '🏠 Главная', reset: '🔄 Сбросить', help: 'ℹ️ Помощь' },
  uz: { days: '🗓 15 kun', video: '🎬 15 kunlik video', outlook: '📅 Haftalar va oylar', mtn: '🏔 Tog‘lar va qor', now: '🌡 Hozir', cities: '🏙 Shaharlar', loc: '📍 Mening joyim', countries: '🌍 Davlatlar', daily: '🔔 Har kuni', accuracy: '🎯 Aniqlik', alerts: '⚠️ Ogohlantirishlar', site: '🗺 Sayt va globus', reset: '🔄 Qayta boshlash', help: 'ℹ️ Yordam' },
  tr: { days: '🗓 15 gün', video: '🎬 15 günlük video', outlook: '📅 Haftalar ve aylar', mtn: '🏔 Dağlar ve kar', now: '🌡 Şimdi', cities: '🏙 Şehirler', loc: '📍 Konumum', countries: '🌍 Ülkeler', daily: '🔔 Her gün', accuracy: '🎯 Doğruluk', alerts: '⚠️ Uyarılar', site: '🗺 Site ve küre', reset: '🔄 Sıfırla', help: 'ℹ️ Yardım' } };
const rkAct = text => { for (const L of [...Object.values(RKL), ...Object.values(RKL_OLD)]) for (const [k, v] of Object.entries(L)) if (v === text) return k; return null; };
function replyKb(env, lang, id) {
  const X = RKL[lang] || RKL.ru, b = t => ({ text: t });
  return { keyboard: [
    [b(X.hourly)],
    [b(X.days), b(X.video)],
    ...(id === 'UZ' ? [[b(X.outlook), b(X.mtn)]] : []),
    ...(ADM.has(id) ? [[b(X.regions)]] : []),
    [b(X.now), b(X.air)],
    [b(X.cities), b(X.countries)],
    [{ text: X.loc, request_location: true }, b(X.alerts)],
    [b(X.daily), b(X.notif)],
    [b(X.accuracy), { text: X.site, web_app: { url: site(env, `prob/${id}/${lang}/prob`) } }],
    [b(X.help), b(X.home)],
    [b(X.reset)]], resize_keyboard: true, is_persistent: true, input_field_placeholder: { uz: 'Shahar nomi…', ru: 'Название города…', tr: 'Şehir adı…' }[lang] };
}
// countries and cities are keyboards too: the chosen one is marked with ✅
function countryRk(lang, cur) {
  const X = RKL[lang] || RKL.ru;
  return { keyboard: [...GROUPS.map(row => row.map(id => ({ text: `${cur === id ? '✅ ' : ''}${FLAG[id]} ${NAMES[id][lang]}` }))), [{ text: X.home }]], resize_keyboard: true };
}
const countryOf = text => { const t = text.replace(/^✅ /, ''); for (const id of Object.keys(NAMES)) for (const l of ['uz', 'ru', 'tr']) if (t === `${FLAG[id]} ${NAMES[id][l]}`) return id; return null; };
async function cityPicker(env, chat, lang, id, u) {
  const X = RKL[lang] || RKL.ru, C = (await cities(env, id, lang)) || (await cities(env, id, 'ru'));
  const rows = [[{ text: X.loc, request_location: true }]];
  const names = (C ? C.cities.map(c => c.name) : []).slice(0, 30);
  for (const p of await places(env)) {  // more towns of the country, by population, up to 30 buttons
    if (names.length >= 30) break;
    const n = pname(p, lang); if (p[4] === id && n && !names.some(x => norm(x) === norm(n))) names.push(n);
  }
  names.forEach((n, i) => { if (i % 3 === 0) rows.push([]); rows[rows.length - 1].push({ text: n }); });
  rows.push([{ text: X.countries }, { text: X.home }]);
  return tg(env, 'sendMessage', { chat_id: chat, text: `${FLAG[id]} <b>${NAMES[id][lang]}</b> · ${DK[lang].ask}`, parse_mode: 'HTML', reply_markup: { keyboard: rows, resize_keyboard: true, input_field_placeholder: { uz: 'Shahar nomi…', ru: 'Название города…', tr: 'Şehir adı…' }[lang] } });
}
function menuKb(env, lang, id) { return replyKb(env, lang, id); }
function menuKbInline(env, lang, id) {
  return { inline_keyboard: [
    // coloured buttons (Telegram 2026+): blue = main actions, green = forecast texts, the rest plain
    [{ text: T[lang].today, callback_data: `T:${lang}:${id}`, style: 'primary' }],
    [{ text: T[lang].days, callback_data: `D:${lang}:${id}`, style: 'success' }, { text: T[lang].all, callback_data: `V:${lang}:${id}`, style: 'primary' }],
    ...(id === 'UZ' ? [[{ text: OLK[lang], callback_data: `O:${lang}:${id}`, style: 'success' }]] : []),
    [{ text: T[lang].cities, callback_data: `Y:${lang}:${id}` }, { text: T[lang].sub, callback_data: `B:${lang}:${id}` }],
    [{ text: T[lang].site, web_app: { url: site(env, `prob/${id}/${lang}/prob`) } }, { text: T[lang].back, callback_data: `L:${lang}` }],
    [{ text: (HK[lang] || HK.ru).reset, callback_data: `RS:${lang}` }],
  ] };
}
const HK = {
  uz: { home: '🏠 Bosh menyu', reset: '🔄 Qayta boshlash', ask: 'Sozlamalarni o‘chirib, boshidan boshlaymizmi?\nDavlat, saqlangan joy va kunlik prognoz obunasi o‘chiriladi.', yes: '✅ Ha, qayta boshlash', no: '❌ Yo‘q', done: '🔄 Sozlamalar tozalandi. Tilni tanlang:' },
  ru: { home: '🏠 Главная', reset: '🔄 Сбросить', ask: 'Сбросить настройки и начать заново?\nБудут удалены: выбранная страна, сохранённое место и подписка на ежедневный прогноз.', yes: '✅ Да, сбросить', no: '❌ Нет', done: '🔄 Настройки сброшены. Выберите язык:' },
  tr: { home: '🏠 Ana menü', reset: '🔄 Sıfırla', ask: 'Ayarlar sıfırlanıp baştan başlansın mı?\nSeçili ülke, kayıtlı konum ve günlük tahmin aboneliği silinir.', yes: '✅ Evet, sıfırla', no: '❌ Hayır', done: '🔄 Ayarlar sıfırlandı. Dil seçin:' } };
const homeRow = lang => [{ text: (HK[lang] || HK.ru).home, callback_data: `HM:${lang}` }, { text: (HK[lang] || HK.ru).reset, callback_data: `RS:${lang}` }];
const DK = {
  uz: { ask: '15 kunlik prognoz: shaharni tanlang yoki dunyodagi istalgan shahar nomini yozing (masalan: Parij, Dubay)', mine: 'Mening joyim', loc: '📍 Joylashuvni yuborish', other: '🌍 Boshqa davlat', vid: '🎬 Shu shahar videosi', vidC: '🎬 Video 15 kun', more: '🏙 Boshqa shahar', globe: '🌍 Globusda ochish' },
  ru: { ask: 'Прогноз на 15 дней: выберите город или напишите название любого города мира (например: Париж, Дубай)', mine: 'Моё место', loc: '📍 Отправить геолокацию', other: '🌍 Другая страна', vid: '🎬 Видео этого города', vidC: '🎬 Видео на 15 дней', more: '🏙 Другой город', globe: '🌍 Открыть на глобусе' },
  tr: { ask: '15 günlük tahmin: şehir seçin ya da dünyadaki herhangi bir şehrin adını yazın (ör. Paris, Dubai)', mine: 'Konumum', loc: '📍 Konum gönder', other: '🌍 Başka ülke', vid: '🎬 Bu şehrin videosu', vidC: '🎬 15 günlük video', more: '🏙 Başka şehir', globe: '🌍 Kürede aç' } };
// under a 15-day text: the matching video (this city's own, or the country's), another city, the countries
function dayKb(lang, rid, cityVideo) {
  const X = DK[lang] || DK.ru;
  return { inline_keyboard: [
    [cityVideo ? { text: X.vid, callback_data: cityVideo, style: 'primary' } : { text: X.vidC, callback_data: `V:${lang}:${rid}`, style: 'primary' }],
    [{ text: X.more, callback_data: `D:${lang}:${rid}` }, { text: X.other, callback_data: `L:${lang}` }], homeRow(lang)] };
}
const helpKb = lang => ({ inline_keyboard: [[{ text: T[lang].pdf, callback_data: `P:${lang}` }, { text: T[lang].adm, callback_data: `M:${lang}` }]] });
// groups and channels cannot open Mini Apps from buttons: plain links
const LIVE = { ru: '🗺 Интерактивная карта по часам', uz: '🗺 Interaktiv xarita soatma-soat', tr: '🗺 Saat saat etkileşimli harita' };
// the interactive map: inside Telegram in a private chat (mini app), a plain link in groups (Telegram allows mini-app buttons only in private chats)
const LIVE15 = { ru: '🗺 Интерактивная карта на 15 дней', uz: '🗺 15 kunlik interaktiv xarita', tr: '🗺 15 günlük etkileşimli harita' };
const liveBtn = (env, lang, id, chat, d15) => { const u = `${base(env)}/live.html?r=${id}&l=${lang}${d15 ? '&m=15' : ''}`;
  return { text: (d15 ? LIVE15 : LIVE)[lang] || (d15 ? LIVE15 : LIVE).ru, ...(chat > 0 ? { web_app: { url: u } } : { url: u }) }; };
const postKb = (env, lang, id, bot, chat) => ({ inline_keyboard: [...(chat ? [[liveBtn(env, lang, id, chat)], [liveBtn(env, lang, id, chat, true)]] : []), [{ text: T[lang].rep, url: link(env, `prob/${id}/${lang}/prob`) }, { text: T[lang].site, url: link(env, 'map') }], ...(bot ? [[{ text: T[lang].bot, url: `https://t.me/${bot}` }]] : [])] });

/* ---------- forecast text ---------- */
function icon(txt) {
  const p = +((txt.match(/(\d+)\s*%/) || [])[1] || 0), snow = /снег|\bqor\b|\bkar\b/i.test(txt);
  if (p >= 60) return snow ? '❄️' : '🌧';
  if (p >= 35) return snow ? '🌨' : '🌦';
  if (/ясно|ochiq havo|açık\./i.test(txt)) return '☀️';
  if (/пасмурно|qalin bulutli|kapalı/i.test(txt)) return '☁️';
  if (/переменная|qisman|parçalı/i.test(txt)) return '⛅';
  if (/облачно|bulutl/i.test(txt)) return '🌥';
  return '⛅';
}
/* ---------- warnings about heavy rain and snow (site/prob/alerts.json, written by prob/render.py) ---------- */
const AX = {  // more kinds of warnings
  uz: { heat: 'kuchli issiq, kunduzi', frost: 'kuchli sovuq, tunda', ice: 'yaxmalak xavfi (muzlagan yo‘llar)', wind: 'kuchli shamol, o‘rtacha', storm: 'momaqaldiroq, jala', dust: 'chang bo‘roni / havo ifloslanishi', ms: 'm/s', title: '⚠️ <b>Ogohlantirish: xavfli ob-havo</b>' },
  ru: { heat: 'сильная жара, днём', frost: 'сильный мороз, ночью', ice: 'гололёд (обледенение дорог)', wind: 'сильный ветер, в среднем', storm: 'гроза, ливень', dust: 'пыльная буря / загрязнение воздуха', ms: 'м/с', title: '⚠️ <b>Предупреждение: опасная погода</b>' },
  tr: { heat: 'aşırı sıcak, gündüz', frost: 'şiddetli soğuk, gece', ice: 'buzlanma (yollarda don)', wind: 'kuvvetli rüzgâr, ortalama', storm: 'gök gürültülü sağanak', dust: 'toz fırtınası / hava kirliliği', ms: 'm/s', title: '⚠️ <b>Uyarı: tehlikeli hava</b>' },
};
const AL = {
  uz: { title: '⚠️ <b>Ogohlantirish: kuchli yog‘in</b>', r1: 'kuchli yomg‘ir', r2: 'juda kuchli yomg‘ir', s1: 'kuchli qor', s2: 'juda kuchli qor', mm: 'mm', peak: 'eng kuchli', foot: 'ECMWF, NOAA, DWD modellari ansambli bo‘yicha. Ehtiyot bo‘ling!', none: '✅ Yaqin 3 kunda kuchli yog‘in kutilmayapti.' },
  ru: { title: '⚠️ <b>Предупреждение: сильные осадки</b>', r1: 'сильный дождь', r2: 'очень сильный дождь', s1: 'сильный снег', s2: 'очень сильный снег', mm: 'мм', peak: 'пик', foot: 'По ансамблю моделей ECMWF, NOAA, DWD. Будьте осторожны!', none: '✅ В ближайшие 3 дня сильных осадков не ожидается.' },
  tr: { title: '⚠️ <b>Uyarı: kuvvetli yağış</b>', r1: 'kuvvetli yağmur', r2: 'çok kuvvetli yağmur', s1: 'yoğun kar', s2: 'çok yoğun kar', mm: 'mm', peak: 'en yoğun', foot: 'ECMWF, NOAA, DWD model topluluğuna göre. Dikkatli olun!', none: '✅ Önümüzdeki 3 günde kuvvetli yağış beklenmiyor.' },
};
async function alertsData(env) {
  const r = await fetch(`${base(env)}/prob/alerts.json?t=${Date.now()}`, { cf: { cacheTtl: 0 } });
  return r.ok ? r.json() : null;
}
function alertText(items, lang) {
  const A = AL[lang] || AL.ru, out = [items.every(i => !i.kind || i.kind === 'rain' || i.kind === 'snow') ? A.title : (AX[lang] || AX.ru).title];
  const regs = [...new Set(items.map(i => i.region))];
  for (const rg of regs) {
    out.push('', `${FLAG[rg] || ''} <b>${esc(NAMES[rg] ? NAMES[rg][lang] : rg)}</b>`);
    for (const i of items.filter(x => x.region === rg).slice(0, 10)) {
      const k = i.kind || (i.snow ? 'snow' : 'rain'), X = AX[lang] || AX.ru, nm = `<b>${esc(i.name[lang] || i.name.ru)}</b> — ${dayLabel(i.date, lang)}`;
      if (k === 'rain' || k === 'snow') { const w = i.snow ? (i.level > 1 ? A.s2 : A.s1) : (i.level > 1 ? A.r2 : A.r1); out.push(`${i.snow ? '❄️' : i.level > 1 ? '⛈' : '🌧'} ${nm}: ${w}, ~${Math.round(i.mm)} ${A.mm} (${i.p} %), ${A.peak} ${i.peak}`); }
      else if (k === 'heat') out.push(`🔥 ${nm}: ${X.heat} ${i.t > 0 ? '+' : ''}${i.t}°`);
      else if (k === 'frost') out.push(`🥶 ${nm}: ${X.frost} ${i.t}°`);
      else if (k === 'ice') out.push(`🧊 ${nm}: ${X.ice}`);
      else if (k === 'wind') out.push(`💨 ${nm}: ${X.wind} ${i.w} ${X.ms}`);
      else if (k === 'dust') out.push(`🌫 ${nm}: ${X.dust} (PM10 ~${i.pm10} µg/m³)`);
      else if (k === 'storm') out.push(`⛈ ${nm}: ${X.storm}${i.peak ? ` (${i.peak})` : ''}, ${i.p}%`);
    }
  }
  out.push('', `<i>${A.foot}</i>`);
  return out.join('\n').slice(0, 4000);
}
// after each update: warn every group and personal subscriber about NEW heavy precipitation in their countries (07–21 h)
async function alertTick(env) {
  if (!env.DB) return; await db(env);
  const hour = new Date(Date.now() + TZ * 3600e3).getUTCHours();
  if (hour < 7 || hour > 21) return;
  const A = await alertsData(env); if (!A || !A.run) return;
  const key = i => `${i.region}|${i.en}|${i.date}|${i.kind || (i.snow ? 's' : 'r')}`;
  if ((await kv(env, 'alert_run')) !== A.run) {  // a new model run: keep only the events we have not warned about yet
    const prev = JSON.parse((await kv(env, 'alert_keys')) || '[]');
    const today = todayTZ();
    await setKv(env, 'alert_new', JSON.stringify(A.items.filter(i => i.date >= today && !prev.includes(key(i)))));
    await setKv(env, 'alert_keys', JSON.stringify([...new Set([...prev.slice(-300), ...A.items.map(key)])]));
    await setKv(env, 'alert_run', A.run);
  }
  const fresh = JSON.parse((await kv(env, 'alert_new')) || '[]');
  const due = (await env.DB.prepare("SELECT * FROM subs WHERE COALESCE(alert_run, '') <> ?1 LIMIT 8").bind(A.run).all()).results;
  const me = due.length && fresh.length ? await tg(env, 'getMe', {}) : null, bot = me && me.ok ? me.result.username : '';
  for (const s of due) {
    const regs = regionsOf(s), items = fresh.filter(i => regs.includes(i.region));
    if (items.length) {
      const r = await tg(env, 'sendMessage', { chat_id: s.chat_id, text: alertText(items, T[s.lang] ? s.lang : 'ru'), parse_mode: 'HTML', reply_markup: postKb(env, T[s.lang] ? s.lang : 'ru', items[0].region, s.type === 'private' ? '' : bot), disable_web_page_preview: true });
      if (!r.ok && /kicked|blocked|deactivated|not a member|chat not found|was deleted/i.test(r.description || '')) { await env.DB.prepare('DELETE FROM subs WHERE chat_id = ?1').bind(s.chat_id).run(); continue; }
    }
    await env.DB.prepare('UPDATE subs SET alert_run = ?2 WHERE chat_id = ?1').bind(s.chat_id, A.run).run();
  }
}
/* ---------- forecast for any point: the user's location or a searched town (site/prob/pt, prob/points.py) ---------- */
const PT = {
  uz: { locBtn: '📍 Mening joyimdagi ob-havo', locHint: '📍 Pastdagi tugmani bosing — joylashuvingiz bo‘yicha 15 kunlik prognoz.\nYoki shahar nomini yozing, masalan: <i>Namangan</i>', nf: '🔎 Bunday shahar topilmadi. Boshqacha yozib ko‘ring yoki 📍 joylashuvni yuboring.', pick: '🔎 Qaysi biri?', head: '15 kunlik prognoz', none: 'yog‘insiz', rain: 'yomg‘ir', snow: 'qor', ms: 'm/s', mm: 'mm', vid: '🎬 Davlat videosi', src: 'ECMWF, NOAA, DWD ansambli · ~50 km to‘r', far: 'Bu nuqta uchun ma’lumot yo‘q.' },
  ru: { locBtn: '📍 Погода у меня', locHint: '📍 Нажмите кнопку внизу — прогноз на 15 дней для вашего места.\nИли напишите название города, например: <i>Наманган</i>', nf: '🔎 Не нашла такой город. Попробуйте написать иначе или отправьте 📍 геолокацию.', pick: '🔎 Какой из них?', head: 'Прогноз на 15 дней', none: 'без осадков', rain: 'дождь', snow: 'снег', ms: 'м/с', mm: 'мм', vid: '🎬 Видео страны', src: 'Ансамбль ECMWF, NOAA, DWD · сетка ~50 км', far: 'Для этой точки нет данных.' },
  tr: { locBtn: '📍 Bulunduğum yerde hava', locHint: '📍 Alttaki düğmeye basın — konumunuz için 15 günlük tahmin.\nYa da şehir adı yazın, örneğin: <i>Antalya</i>', nf: '🔎 Şehir bulunamadı. Farklı yazmayı deneyin veya 📍 konum gönderin.', pick: '🔎 Hangisi?', head: '15 günlük tahmin', none: 'yağışsız', rain: 'yağmur', snow: 'kar', ms: 'm/s', mm: 'mm', vid: '🎬 Ülke videosu', src: 'ECMWF, NOAA, DWD topluluğu · ~50 km ızgara', far: 'Bu nokta için veri yok.' },
};
const PK = {  // words of the point forecast
  ru: { brief: 'Коротко', allDry: 'Все 15 дней без существенных осадков', wetNow: 'Осадки возможны уже сегодня', dryUntil: 'Сухо до {d} включительно',
    wetDays: 'Дней с осадками: {n}; сильнее всего {peak}', snowOn: 'Снег: {d}', cooler: 'Похолодание: днём с {a} до {b} к концу периода', warmer: 'Потепление: днём с {a} до {b} к концу периода',
    steady: 'Без резких перемен температуры: днём от {a} до {b}', frost: 'Заморозки до {t} ({d})', wind: 'Сильный ветер до {w} м/с ({d})', windW: 'ветер',
    dry: 'без осадков', rain: 'дождь', snow: 'снег', next: 'Дальше по дням', cDay: 'День', cT: 'Темп.', cP: 'Осадки', run: 'Расчёт', upd: 'Обновлено', model: 'расчёт моделей',
    note: 'Осадки: вероятность за сутки и среднее количество по ансамблю моделей.', noRain: 'Зонт не понадобится', rainAt: '{w} вероятен {a}–{b} ч (до {p} %)', wear: 'Одежда' },
  uz: { brief: 'Qisqacha', allDry: '15 kun davomida sezilarli yog‘in kutilmaydi', wetNow: 'Bugunoq yog‘in bo‘lishi mumkin', dryUntil: '{d} gacha quruq',
    wetDays: 'Yog‘inli kunlar: {n}; eng kuchlisi {peak}', snowOn: 'Qor: {d}', cooler: 'Sovish: kunduzi {a} dan {b} gacha', warmer: 'Isish: kunduzi {a} dan {b} gacha',
    steady: 'Harorat keskin o‘zgarmaydi: kunduzi {a} … {b}', frost: 'Sovuq {t} gacha ({d})', wind: 'Kuchli shamol {w} m/s gacha ({d})', windW: 'shamol',
    dry: 'yog‘insiz', rain: 'yomg‘ir', snow: 'qor', next: 'Keyingi kunlar', cDay: 'Kun', cT: 'Harorat', cP: 'Yog‘in', run: 'Hisob', upd: 'Yangilandi', model: 'modellar hisobi',
    note: 'Yog‘in: sutkalik ehtimol va modellar ansamblining o‘rtacha miqdori.', noRain: 'Soyabon kerak bo‘lmaydi', rainAt: '{w} ehtimoli {a}–{b} soatlarda ({p} % gacha)', wear: 'Kiyim' },
  tr: { brief: 'Özet', allDry: '15 gün boyunca kayda değer yağış yok', wetNow: 'Bugünden itibaren yağış olası', dryUntil: '{d} dahil kuru',
    wetDays: 'Yağışlı gün: {n}; en kuvvetlisi {peak}', snowOn: 'Kar: {d}', cooler: 'Soğuma: gündüz {a} → {b}', warmer: 'Isınma: gündüz {a} → {b}',
    steady: 'Sıcaklıkta sert değişim yok: gündüz {a} … {b}', frost: 'Don {t} ({d})', wind: 'Kuvvetli rüzgâr {w} m/s ({d})', windW: 'rüzgâr',
    dry: 'yağışsız', rain: 'yağmur', snow: 'kar', next: 'Sonraki günler', cDay: 'Gün', cT: 'Sıcaklık', cP: 'Yağış', run: 'Hesaplama', upd: 'Güncellendi', model: 'model çalıştırması',
    note: 'Yağış: günlük olasılık ve model topluluğunun ortalama miktarı.', noRain: 'Şemsiye gerekmez', rainAt: '{w} {a}–{b} saatlerinde olası (%{p} e kadar)', wear: 'Giyim' },
};
const WEAR = {
  ru: { c: ['зимняя куртка, шапка, перчатки', 'тёплая куртка и шапка', 'куртка или пальто, шарф', 'лёгкая куртка или свитер', 'кофта, вечером лёгкая куртка', 'футболка и лёгкая одежда', 'лёгкая одежда, головной убор, вода'], u: 'зонт', b: 'непромокаемая обувь', w: 'ветровка' },
  uz: { c: ['qishki kurtka, telpak, qo‘lqop', 'issiq kurtka va telpak', 'kurtka yoki palto, sharf', 'yengil kurtka yoki sviter', 'kofta, kechqurun yengil kurtka', 'futbolka, yengil kiyim', 'yengil kiyim, bosh kiyim, suv'], u: 'soyabon', b: 'suv o‘tkazmaydigan poyabzal', w: 'shamoldan himoya kurtka' },
  tr: { c: ['kışlık mont, bere, eldiven', 'kalın mont ve bere', 'mont veya kaban, atkı', 'ince ceket veya kazak', 'hırka, akşam ince ceket', 'tişört ve hafif giysiler', 'hafif giysiler, şapka, su'], u: 'şemsiye', b: 'su geçirmez ayakkabı', w: 'rüzgârlık' },
};
function wearText(lang, lo, hi, p, snow, w) {
  const W = WEAR[lang] || WEAR.ru, t = (lo + 2 * hi) / 3, k = t <= -10 ? 0 : t <= 0 ? 1 : t <= 8 ? 2 : t <= 15 ? 3 : t <= 22 ? 4 : t <= 28 ? 5 : 6;
  return [W.c[k], ...(p >= 40 ? [snow ? W.b : W.u] : []), ...(w >= 8 ? [W.w] : [])].join(', ');
}
const MK = {  // the main keyboard under the chat: four buttons for everything
  ru: { today: '📅 Сегодня и завтра', d15: '🗓 15 дней', video: '🎬 Видео', more: '⚙️ Меню' },
  uz: { today: '📅 Bugun va ertaga', d15: '🗓 15 kun', video: '🎬 Video', more: '⚙️ Menyu' },
  tr: { today: '📅 Bugün ve yarın', d15: '🗓 15 gün', video: '🎬 Video', more: '⚙️ Menü' },
};
const mainKb = () => ({ remove_keyboard: true });  // (kept for old callers)
const locOnce = lang => ({ keyboard: [[{ text: PT[lang].locBtn, request_location: true }]], resize_keyboard: true, one_time_keyboard: true });
const FILLER = new Set('погода погоду погоды прогноз в во на для город городе сегодня завтра какая какой ob-havo obhavo havo bugun ertaga shahar shahrida hava durumu bugün yarın için weather in today tomorrow'.split(' '));
// today and tomorrow hour by hour: the country's video with the main city's timing and clothing advice (prob/hourly.py)
// Telegram caches a file by its URL, so every media link carries the hour: a new build is always fetched again
const fresh = () => Math.floor(Date.now() / 3600e3);
async function sendHourly(env, chat, lang, id) {
  let H = null;
  for (const l of [lang, 'ru', 'uz']) { const r = await fetch(`${base(env)}/prob/hr/${id}_${l}.json`, { cf: { cacheTtl: 600 } }); if (r.ok) { H = await r.json(); break; } }
  if (!H) return sendToday(env, chat, lang, id);
  const K = PK[lang], X = { ru: ['Сегодня', 'Завтра', 'по часам'], uz: ['Bugun', 'Ertaga', 'soatma-soat'], tr: ['Bugün', 'Yarın', 'saat saat'] }[lang];
  const part = (lbl, d) => d ? `<b>${lbl}</b> ${d.range}\n☂️ ${d.rain}\n🧥 ${K.wear}: ${d.wear}` : '';
  // where the coming rain or snow of the main city comes from (Uzbekistan, Kazakhstan; prob/trajectory.py)
  const TJ = TRJ.has(id) ? await trajData(env, id) : null, ti = TJ && TJ.items.filter(it => it.city[lang] === H.city || it.city.ru === H.city).sort((a, b) => a.k - b.k)[0];
  const cap = [`${FLAG[id] || ''} <b>${esc(NAMES[id][lang])}</b> · ${esc(H.city)} — ${X[0].toLowerCase()} / ${X[1].toLowerCase()} ${X[2]}`, '', part(X[0], H.info.today), '', part(X[1], H.info.tomorrow),
    ...(ti ? ['', `🧭 ${esc(ti.text[lang] || ti.text.ru)}`] : [])].join('\n').slice(0, 1024);
  await tg(env, 'sendChatAction', { chat_id: chat, action: 'upload_video' });
  const url = `${base(env)}/prob/${H.video}?v=${fresh()}`;
  // the interactive map (a Telegram mini app): touch the map, drag the hours, hear the weather — private chats only
  // (the keyboard under the input field stays as it is; this message carries the mini-app button)
  // groups and channels: only a link to the interactive map (keyboards under the input field and mini-app buttons work in private chats only)
  const kb = chat > 0 ? { inline_keyboard: [[liveBtn(env, lang, id, chat)], ...(ADM.has(id) ? [[{ text: (RGX[lang] || RGX.ru).btn, callback_data: `RG:${lang}:${id}` }]] : []), ...(TRJ.has(id) ? [[{ text: (TJX[lang] || TJX.ru).btn, callback_data: `TJ:${lang}:${id}` }]] : []), [notifBtn(lang, 'hourly')]] } : { inline_keyboard: [[liveBtn(env, lang, id, chat)]] };
  let r = await tg(env, 'sendVideo', { chat_id: chat, video: url, caption: cap, parse_mode: 'HTML', supports_streaming: true, reply_markup: kb });
  if (!r.ok) { const f = await fetch(url); if (f.ok) { const fd = new FormData(); fd.append('chat_id', String(chat)); fd.append('caption', cap); fd.append('parse_mode', 'HTML'); fd.append('supports_streaming', 'true'); fd.append('reply_markup', JSON.stringify(kb)); fd.append('video', new Blob([await f.arrayBuffer()], { type: 'video/mp4' }), `${id}_${lang}.mp4`); r = await (await fetch(`https://api.telegram.org/bot${env.BOT_TOKEN}/sendVideo`, { method: 'POST', body: fd })).json(); } }
  if (!r.ok) return tg(env, 'sendMessage', { chat_id: chat, text: cap, parse_mode: 'HTML', reply_markup: kb });
  return r;
}
const locKb = lang => ({ keyboard: [[{ text: PT[lang].locBtn, request_location: true }]], resize_keyboard: true, is_persistent: true });
const MEMO = new Map();  // per-isolate cache: answers stay fast between messages
async function memo(key, ttl, fn) { const m = MEMO.get(key); if (m && Date.now() - m.t < ttl) return m.v; const v = await fn(); if (v) MEMO.set(key, { t: Date.now(), v }); return v; }
async function places(env) { return (await memo('places', 3600e3, async () => { const r = await fetch(`${base(env)}/prob/places.json`, { cf: { cacheTtl: 3600 } }); return r.ok ? r.json() : null; })) || []; }
const norm = t => String(t || '').toLowerCase().replace(/[‘’ʻʼ`´']/g, "'").replace(/ё/g, 'е').replace(/[^\p{L}\p{N}' -]/gu, '').trim();
const pname = (p, lang) => (lang === 'uz' ? p[1] || p[2] : lang === 'tr' ? p[3] || p[2] : p[0] || p[2]);
async function searchPlaces(env, q) {
  q = norm(q); if (q.length < 2) return [];
  const P = await places(env), hit = [], part = [];
  for (const p of P) {
    const names = [p[0], p[1], p[2], p[3]].map(norm).filter(Boolean);
    if (names.some(n => n === q)) hit.push(p); else if (names.some(n => n.startsWith(q))) part.push(p);
  }
  return [...hit, ...part].slice(0, 8);
}
async function nearestPlace(env, lat, lon, km = 35) {
  let best = null, bd = km;
  for (const p of await places(env)) { const d = Math.hypot((p[5] - lat) * 111, (p[6] - lon) * 111 * Math.cos(lat * Math.PI / 180)); if (d < bd) { bd = d; best = p; } }
  return best;
}
// the weather right now (Open-Meteo current conditions: the latest model analysis and nowcast, every 15 minutes)
const WMO = {
  uz: { 0: 'ochiq osmon', 1: 'asosan ochiq', 2: 'qisman bulutli', 3: 'bulutli', 45: 'tuman', 48: 'qirovli tuman', 51: 'mayda yomg‘ir', 53: 'mayda yomg‘ir', 55: 'mayda yomg‘ir', 56: 'muzlovchi yomg‘ir', 57: 'muzlovchi yomg‘ir', 61: 'yengil yomg‘ir', 63: 'yomg‘ir', 65: 'kuchli yomg‘ir', 66: 'muzlovchi yomg‘ir', 67: 'muzlovchi yomg‘ir', 71: 'yengil qor', 73: 'qor', 75: 'kuchli qor', 77: 'qor donalari', 80: 'jala', 81: 'jala', 82: 'kuchli jala', 85: 'qor', 86: 'kuchli qor', 95: 'momaqaldiroq', 96: 'do‘lli momaqaldiroq', 99: 'do‘lli momaqaldiroq' },
  ru: { 0: 'ясно', 1: 'преимущественно ясно', 2: 'переменная облачность', 3: 'пасмурно', 45: 'туман', 48: 'изморозь, туман', 51: 'морось', 53: 'морось', 55: 'сильная морось', 56: 'ледяная морось', 57: 'ледяная морось', 61: 'небольшой дождь', 63: 'дождь', 65: 'сильный дождь', 66: 'ледяной дождь', 67: 'ледяной дождь', 71: 'небольшой снег', 73: 'снег', 75: 'сильный снег', 77: 'снежная крупа', 80: 'ливень', 81: 'ливень', 82: 'сильный ливень', 85: 'снегопад', 86: 'сильный снегопад', 95: 'гроза', 96: 'гроза с градом', 99: 'гроза с градом' },
  tr: { 0: 'açık', 1: 'çoğunlukla açık', 2: 'parçalı bulutlu', 3: 'kapalı', 45: 'sis', 48: 'kırağılı sis', 51: 'çisenti', 53: 'çisenti', 55: 'yoğun çisenti', 56: 'dondurucu çisenti', 57: 'dondurucu çisenti', 61: 'hafif yağmur', 63: 'yağmur', 65: 'kuvvetli yağmur', 66: 'dondurucu yağmur', 67: 'dondurucu yağmur', 71: 'hafif kar', 73: 'kar', 75: 'yoğun kar', 77: 'kar taneleri', 80: 'sağanak', 81: 'sağanak', 82: 'kuvvetli sağanak', 85: 'kar sağanağı', 86: 'yoğun kar sağanağı', 95: 'gök gürültülü fırtına', 96: 'dolu ile fırtına', 99: 'dolu ile fırtına' } };
const NOWX = { uz: { now: 'Hozir', feels: 'his qilinadi', hum: 'namlik', wind: 'shamol', gust: 'shiddat', ms: 'm/s' }, ru: { now: 'Сейчас', feels: 'ощущается', hum: 'влажность', wind: 'ветер', gust: 'порывы', ms: 'м/с' }, tr: { now: 'Şimdi', feels: 'hissedilen', hum: 'nem', wind: 'rüzgâr', gust: 'hamle', ms: 'm/s' } };
const wmoIcon = (c, day) => c >= 95 ? '⛈' : c >= 85 || (c >= 71 && c <= 77) ? '🌨' : c >= 80 ? '🌦' : c >= 51 ? '🌧' : c >= 45 ? '🌫' : c === 3 ? '☁️' : c === 2 ? '⛅' : day ? '☀️' : '🌙';
async function nowWeather(lat, lon) {
  const k = `now:${lat.toFixed(2)},${lon.toFixed(2)}`;
  return memo(k, 10 * 60e3, async () => {
    try {
      const r = await fetch(`https://api.open-meteo.com/v1/forecast?latitude=${lat.toFixed(3)}&longitude=${lon.toFixed(3)}&current=temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,wind_speed_10m,wind_gusts_10m,precipitation,is_day&daily=weather_code&forecast_days=16&wind_speed_unit=ms&timezone=auto`, { cf: { cacheTtl: 600 } });
      if (!r.ok) return null; const j = await r.json(); const c = j.current || {}; c.codes = {}; (j.daily && j.daily.time || []).forEach((d, i) => { c.codes[d] = j.daily.weather_code[i]; }); return c;
    } catch (e) { return null; }
  });
}
function nowLine(c, lang) {
  if (!c || c.temperature_2m == null) return '';
  const X = NOWX[lang] || NOWX.ru, f = v => `${v > 0.5 ? '+' : ''}${Math.round(v)}°`.replace(/^-0°$/, '0°');
  const w = (WMO[lang] || WMO.ru)[c.weather_code] || '';
  return `${wmoIcon(c.weather_code, c.is_day)} <b>${X.now}: ${f(c.temperature_2m)}</b>${w ? `, ${w}` : ''}\n      ${X.feels} ${f(c.apparent_temperature)} · ${X.hum} ${Math.round(c.relative_humidity_2m)}% · ${X.wind} ${Math.round(c.wind_speed_10m)} ${X.ms}${c.wind_gusts_10m >= 10 ? ` (${X.gust} ${Math.round(c.wind_gusts_10m)})` : ''}`;
}
async function pointForecast(env, chat, lang, lat, lon, place, kbOver) {
  const L = PT[lang];
  await saveUser(env, chat, { place: JSON.stringify([lat, lon]) });
  // the 0.25° tiles of the region first (the same numbers as the videos, city texts and hourly forecast), the 0.5° world tiles elsewhere
  const idx = dir => memo(dir, 600e3, async () => (await fetch(`${base(env)}/prob/${dir}/index.json`, { cf: { cacheTtl: 600 } })).json().catch(() => null));
  let I = null, r = null;
  for (const dir of ['pt25', 'pt']) {
    const J = await idx(dir); if (!J) continue;
    if (J.box && !(lon >= J.box[0] && lon <= J.box[1] - J.d && lat >= J.box[2] + J.d && lat <= J.box[3])) continue;
    if (!J.box && (lat > 80 || lat <= -60)) continue;
    const t = Math.ceil(lat / J.tile) * J.tile, l = Math.floor(lon / J.tile) * J.tile;
    const q = await fetch(`${base(env)}/prob/${dir}/${t}_${l}.bin`, { cf: { cacheTtl: 600 } });
    if (q.ok) { I = J; r = q; break; }
  }
  if (!I) return tg(env, 'sendMessage', { chat_id: chat, text: L.far });
  const top = Math.ceil(lat / I.tile) * I.tile, left = Math.floor(lon / I.tile) * I.tile, n = I.n, S = I.steps.length;
  const B = new Uint8Array(await r.arrayBuffer()), fy = (top - lat) / I.d, fx = (lon - left) / I.d;
  const y0 = Math.min(n - 2, Math.floor(fy)), x0 = Math.min(n - 2, Math.floor(fx)), ay = fy - y0, ax = fx - x0;
  const val = (s, v) => { let sum = 0, w = 0;
    for (const [dy, dx, k] of [[0, 0, (1 - ay) * (1 - ax)], [0, 1, (1 - ay) * ax], [1, 0, ay * (1 - ax)], [1, 1, ay * ax]]) { const b = B[((s * 5 + v) * n + y0 + dy) * n + x0 + dx]; if (b !== 255) { sum += b * k; w += k; } }
    return w ? sum / w : NaN; };
  const TZC = { UZ: 5, KZ: 5, KG: 6, TJ: 5, TM: 5, AZ: 4, AM: 4, GE: 4, TR: 3, BY: 3, MD: 2, UA: 2, AF: 4.5, IR: 3.5, CN: 8, IN: 5.5 };
  const cc = place ? place[4] : (lat > 37 && lat < 45.6 && lon > 56 && lon < 73.2 ? 'UZ' : '');
  const off = TZC[cc] ?? (cc === 'RU' ? Math.max(2, Math.min(12, Math.round(lon / 15))) : Math.max(-11, Math.min(12, Math.round(lon / 15))));
  const run = Date.parse(I.run), days = new Map(), wins = [];
  for (let s = 0; s < S; s++) {
    const mid = new Date(run + (I.steps[s] - I.win[s] / 2 + off) * 3600e3).toISOString().slice(0, 10);
    wins.push({ d: mid, h1: new Date(run + (I.steps[s] - I.win[s] + off) * 3600e3).getUTCHours(), h2: new Date(run + (I.steps[s] + off) * 3600e3).getUTCHours() || 24, p: val(s, 0) / 2.5, t: val(s, 1) / 2 - 60, w: val(s, 3) / 5 });
    const d = days.get(mid) || { P: 0, T: [], A: 0, C: [], W: 0, wetT: [] };
    const p = val(s, 0) / 2.5, t = val(s, 1) / 2 - 60, c = val(s, 2) / 250, w = val(s, 3) / 5, a = Math.expm1(val(s, 4) / 40);
    if (isFinite(p)) d.P = Math.max(d.P, p); if (isFinite(t)) d.T.push(t); if (isFinite(a)) d.A += a; if (isFinite(c)) d.C.push(c); if (isFinite(w)) d.W = Math.max(d.W, w);
    if (p >= 30 && isFinite(t)) d.wetT.push(t);
    days.set(mid, d);
  }
  const today = new Date(Date.now() + off * 3600e3).toISOString().slice(0, 10), tmrw = new Date(Date.now() + (off + 24) * 3600e3).toISOString().slice(0, 10);
  const f = v => `${v > 0.5 ? '+' : ''}${Math.round(v)}`.replace(/^-0$/, '0'), deg = v => f(v) + '°';
  const K = PK[lang], D = [];
  for (const [d, x] of days) {
    if (d < today || !x.T.length) continue;
    const snow = x.wetT.length ? x.wetT.reduce((a, b) => a + b) / x.wetT.length <= 0.5 : Math.min(...x.T) < -1;
    const cm = x.C.length ? x.C.reduce((a, b) => a + b) / x.C.length : 0, p = Math.round(x.P);
    D.push({ d, lo: Math.min(...x.T), hi: Math.max(...x.T), p, mm: x.A, w: x.W, snow, ic: p >= 60 ? (snow ? '❄️' : '🌧') : p >= 35 ? (snow ? '🌨' : '🌦') : cm > 0.7 ? '☁️' : cm > 0.35 ? '⛅' : '☀️' });
  }
  if (!D.length) return tg(env, 'sendMessage', { chat_id: chat, text: L.far });
  const wd = d => { const t = new Date(d + 'T12:00:00Z'); return `${WD[lang][t.getUTCDay()]} ${String(t.getUTCDate()).padStart(2, '0')}.${String(t.getUTCMonth() + 1).padStart(2, '0')}`; };
  const wet = x => x.p >= 40, pr = x => !wet(x) && x.p < 20 ? K.dry : `${x.snow ? K.snow : K.rain} ${x.p} %${x.mm >= 0.5 ? `, ~${x.mm < 9.5 ? x.mm.toFixed(0) : Math.round(x.mm)} ${L.mm}` : ''}`;
  // short analysis for the reader
  const sum = [], firstWet = D.findIndex(wet), wetDays = D.filter(wet);
  if (firstWet < 0) sum.push(K.allDry);
  else {
    sum.push(firstWet === 0 ? K.wetNow : K.dryUntil.replace('{d}', wd(D[firstWet - 1].d)));
    const peak = wetDays.reduce((a, b) => (b.mm > a.mm || (b.mm === a.mm && b.p > a.p) ? b : a));
    sum.push(K.wetDays.replace('{n}', wetDays.length).replace('{peak}', `${wd(peak.d)} — ${peak.p} %${peak.mm >= 1 ? `, ~${Math.round(peak.mm)} ${L.mm}` : ''}`));
    if (wetDays.some(x => x.snow)) sum.push(K.snowOn.replace('{d}', wetDays.filter(x => x.snow).slice(0, 3).map(x => wd(x.d)).join(', ')));
  }
  const n3 = Math.min(3, D.length), hi0 = D.slice(0, n3).reduce((a, x) => a + x.hi, 0) / n3, hi1 = D.slice(-n3).reduce((a, x) => a + x.hi, 0) / n3;
  if (hi1 - hi0 <= -4) sum.push(K.cooler.replace('{a}', deg(hi0)).replace('{b}', deg(hi1)));
  else if (hi1 - hi0 >= 4) sum.push(K.warmer.replace('{a}', deg(hi0)).replace('{b}', deg(hi1)));
  else sum.push(K.steady.replace('{a}', deg(Math.min(...D.map(x => x.hi)))).replace('{b}', deg(Math.max(...D.map(x => x.hi)))));
  const frost = D.reduce((a, x) => (x.lo < a.lo ? x : a));
  if (frost.lo < 0) sum.push(K.frost.replace('{t}', deg(frost.lo)).replace('{d}', wd(frost.d)));
  const windy = D.reduce((a, x) => (x.w > a.w ? x : a));
  if (isFinite(windy.w) && windy.w >= 10) sum.push(K.wind.replace('{w}', Math.round(windy.w)).replace('{d}', wd(windy.d)));
  // the next days as an aligned table
  const pad = (t, n) => t + ' '.repeat(Math.max(0, n - [...t].length));
  const bar = p => { const k = Math.max(0, Math.min(5, Math.round(p / 20))); return '█'.repeat(k) + '░'.repeat(5 - k); };
  const NW = await nowWeather(lat, lon), nowT = nowLine(NW, lang);
  // one icon per day: rain drops, snow, sun, clouds, and fog or thunder from the day's weather code
  for (const x of D) { const c = NW && NW.codes ? NW.codes[x.d] : null;
    x.ic = c >= 95 && x.p >= 30 ? '⛈' : (c === 45 || c === 48) && x.p < 35 ? '🌫' : x.p >= 35 ? (x.snow ? '❄️' : '💧') : x.ic; }
  const rows = D.slice(2).map(x => `${x.ic} ${pad(wd(x.d), 9)}${pad(`${f(x.lo)}…${f(x.hi)}°`, 10)}${bar(x.p)} ${pad(x.p < 20 ? '—' : `${x.p}%`, 4)}${x.mm >= 0.5 ? ` ${x.mm < 9.5 ? x.mm.toFixed(0) : Math.round(x.mm)} ${L.mm}` : ''}`);
  const nm = place ? `${FLAG[place[4]] || '📍'} <b>${esc(pname(place, lang))}</b>` : `📍 <b>${lat.toFixed(2)}, ${lon.toFixed(2)}</b>`;
  const hm = t => { const l = new Date(t + off * 3600e3); return `${String(l.getUTCDate()).padStart(2, '0')}.${String(l.getUTCMonth() + 1).padStart(2, '0')} ${String(l.getUTCHours()).padStart(2, '0')}:${String(l.getUTCMinutes()).padStart(2, '0')}`; };
  const u = I.built ? `${hm(Date.parse(I.built))} · ${K.model} ${hm(run).slice(0, 5)} ${hm(run).slice(6)}` : hm(run);
  const detail = x => {  // when it rains and what to wear (3-hour windows of that day)
    const ws = wins.filter(v => v.d === x.d), wet = ws.filter(v => v.p >= 40);
    let r = K.noRain;
    if (wet.length) { const top = wet.reduce((a, b) => (b.p > a.p ? b : a)); let a = top, b = top; const i = ws.indexOf(top);
      for (let j = i - 1; j >= 0 && ws[j].p >= 40; j--) a = ws[j]; for (let j = i + 1; j < ws.length && ws[j].p >= 40; j++) b = ws[j];
      r = K.rainAt.replace('{w}', x.snow ? K.snow : K.rain).replace('{a}', String(a.h1).padStart(2, '0')).replace('{b}', String(b.h2).padStart(2, '0')).replace('{p}', Math.round(top.p)); }
    return `\n      ☂️ ${r}\n      🧥 ${K.wear}: ${wearText(lang, x.lo, x.hi, x.p, x.snow, x.w)}`;
  };
  const day = (x, w) => `${x.ic} <b>${w}</b> · ${wd(x.d)}\n      ${deg(x.lo)}…${deg(x.hi)} · ${pr(x)}${isFinite(x.w) && x.w >= 5 ? ` · ${K.windW} ${Math.round(x.w)} ${L.ms}` : ''}${detail(x)}`;
  const isAdmin = String(chat) === (await kv(env, 'admin'));  // update times only for the bot's admin
  const text = [`${nm} · ${L.head}`, ...(isAdmin ? [`<i>${I.built ? K.upd : K.run} ${u} (UTC${off >= 0 ? '+' : ''}${off})</i>`] : []), '', ...(nowT ? [nowT, ''] : []),
    `<b>${K.brief}</b>`, ...sum.map(x => `▸ ${x}`), '',
    day(D[0], D[0].d === today ? T[lang].tdy : wd(D[0].d)), ...(D[1] ? [day(D[1], D[1].d === tmrw ? T[lang].tmw : wd(D[1].d))] : []), '',
    ...(rows.length ? [`<b>${K.next}</b>`, `<pre>${esc('   ' + pad(K.cDay, 9) + pad(K.cT, 10) + K.cP)}\n${esc(rows.join('\n'))}</pre>`] : []),
    `<i>${K.note}</i>`].join('\n');
  let kb = kbOver && kbOver.keyboard ? kbOver : null;
  if (!kb) { const uu = await getUser(env, chat); kb = replyKb(env, lang, place && NAMES[place[4]] ? place[4] : (uu && NAMES[uu.region] ? uu.region : 'UZ')); }
  return tg(env, 'sendMessage', { chat_id: chat, text: text.slice(0, 4000), parse_mode: 'HTML', ...(kb ? { reply_markup: kb } : {}) });
}
// the data stopped updating (the GitHub workflow failed): tell the bot's admin, at most every 12 hours
// every morning at 09:00 (Tashkent): how many people used the bot and the site
async function statsTick(env) {
  const now = new Date(Date.now() + TZ * 3600e3); if (now.getUTCHours() < 9) return;
  const day = now.toISOString().slice(0, 10), admin = await kv(env, 'admin');
  if (!admin || (await kv(env, 'stats_day')) === day) return;
  await setKv(env, 'stats_day', day);
  const since = new Date(Date.now() - 864e5).toISOString(), one = async (q, ...a) => (await env.DB.prepare(q).bind(...a).first()) || {};
  const tot = await one('SELECT COUNT(*) AS n FROM users'), act = await one('SELECT COUNT(*) AS n FROM users WHERE seen > ?1', since), neu = await one('SELECT COUNT(*) AS n FROM users WHERE first > ?1', since);
  const grp = await one("SELECT COUNT(*) AS n FROM subs WHERE type <> 'private'"), prv = await one("SELECT COUNT(*) AS n FROM subs WHERE type = 'private'");
  const langs = (await env.DB.prepare('SELECT lang, COUNT(*) AS n FROM users WHERE seen > ?1 GROUP BY lang ORDER BY n DESC').bind(since).all()).results;
  let site = '';
  try { const y = new Date(Date.now() - 864e5).toISOString().slice(0, 10); const h = await one('SELECT COALESCE(SUM(n),0) AS n FROM hits WHERE day = ?1', y); site = `\n🌐 Сайт за вчера: ${h.n}`; } catch (e) { /* no visits table yet */ }
  try { const S = await searchStats(env, 1); if (S.tot) site += `\n🔎 Поиск: ${S.tot} — ${S.top.slice(0, 5).map(x => `${esc(x.q)} ${x.n}`).join(', ')}${S.miss.length ? ` · не нашлось: ${S.miss.slice(0, 3).map(x => esc(x.q)).join(', ')}` : ''}`; } catch (e) { /* no searches yet */ }
  try { const V = await (await fetch(`${base(env)}/prob/verify/index.json`)).json(); const o = V.uz || V.overall; if (o) site += `\n🎯 Точность (30 дн.): осадки ${o.rain}%, температура ±${o.t_mae}°`; } catch (e) { /* not yet */ }
  await tg(env, 'sendMessage', { chat_id: admin, text: `📊 <b>Бот за сутки</b> (${day})\n👤 Заходили: <b>${act.n}</b>\n🆕 Новых: <b>${neu.n}</b>\n👥 Всего пользователей: ${tot.n}\n💬 Групп и каналов: ${grp.n}\n🔔 Личных подписок: ${prv.n}\n🗣 Языки: ${langs.map(x => `${x.lang || '?'} ${x.n}`).join(', ') || '—'}${site}\n\n/users — список`, parse_mode: 'HTML' });
}
// GitHub often skips scheduled runs: the worker starts the site build itself every 3 hours (needs the GH_TOKEN secret)
// a copy of the bot's database (users, subscriptions, settings) sent to the admin as a file every night at 03:00
async function backupTick(env) {
  if (!env.DB) return;
  const now = new Date(Date.now() + TZ * 3600e3); if (now.getUTCHours() < 3) return;
  const day = now.toISOString().slice(0, 10), admin = await kv(env, 'admin');
  if (!admin || (await kv(env, 'backup_day')) === day) return;
  await setKv(env, 'backup_day', day);
  const dump = {};
  for (const t of ['users', 'subs', 'meta']) { try { dump[t] = (await env.DB.prepare(`SELECT * FROM ${t}`).all()).results; } catch (e) { dump[t] = []; } }
  dump.meta = dump.meta.filter(r => !/^(guide|alert_|build_at)/.test(r.k));
  const fd = new FormData();
  fd.append('chat_id', admin); fd.append('caption', `💾 Резервная копия базы бота · ${day}\nПользователей: ${dump.users.length}, подписок: ${dump.subs.length}`);
  fd.append('disable_notification', 'true');
  fd.append('document', new Blob([JSON.stringify(dump, null, 1)], { type: 'application/json' }), `osmon_backup_${day}.json`);
  await fetch(`https://api.telegram.org/bot${env.BOT_TOKEN}/sendDocument`, { method: 'POST', body: fd });
}
// the second safety net for the site builds (the first is the hourly knock in .github/workflows/update.yml): this worker's
// own cron, which never skips, looks at when the live site was built (site/build.json). Over 3.5 h old and no build
// running → it starts a new build itself (needs the GH_TOKEN secret: a GitHub token with Actions read & write for this
// repository) and tells the admin; when the fresh data is on the site, it says so too.
const REPO = 'otabekvafoev92-del/ob-havo-ecmwf';
async function ghApi(env, path, init = {}) {
  return fetch(`https://api.github.com/repos/${REPO}/${path}`, { ...init, headers: { 'user-agent': 'osmon-bot', accept: 'application/vnd.github+json',
    ...(env.GH_TOKEN ? { authorization: `Bearer ${env.GH_TOKEN}` } : {}), ...(init.headers || {}) } });
}
async function staleTick(env) {
  const admin = await kv(env, 'admin');
  const B = await fetch(`${base(env)}/build.json?t=${Date.now()}`).then(r => r.ok ? r.json() : null).catch(() => null);
  if (!B || !B.built) return;  // the stamp comes with the first build after this change
  const built = Date.parse(B.built), age = (Date.now() - built) / 3600e3;
  const kicked = +(await kv(env, 'kick_at') || 0);
  // a build we started has reached the site: good news, once
  if (kicked && built > kicked) {
    await setKv(env, 'kick_at', '');
    if (admin) await tg(env, 'sendMessage', { chat_id: admin, text: `✅ Данные обновлены после перезапуска: сайт собран ${tkt(B.built)} по Ташкенту.` });
    return;
  }
  if (age < 3.5) return;
  if (kicked && Date.now() - kicked < 100 * 60e3) return;  // a build we started is still on its way (they take 40–80 min)
  const runs = await ghApi(env, 'actions/workflows/update.yml/runs?per_page=5').then(r => r.ok ? r.json() : null).catch(() => null);
  const busy = runs && (runs.workflow_runs || []).find(r => r.status === 'in_progress' || r.status === 'queued' || r.status === 'pending' || r.status === 'waiting');
  if (busy) {  // GitHub is building already: only worry when it hangs
    const mins = (Date.now() - Date.parse(busy.run_started_at || busy.created_at)) / 60e3;
    if (mins > 150 && admin && Date.now() - +(await kv(env, 'hang_at') || 0) > 6 * 3600e3) {
      await setKv(env, 'hang_at', String(Date.now()));
      await tg(env, 'sendMessage', { chat_id: admin, text: `⚠️ Сборка сайта идёт уже ${Math.round(mins)} мин (обычно 40–80). Посмотреть: ${busy.html_url}`, disable_web_page_preview: true });
    }
    return;
  }
  const last = runs && (runs.workflow_runs || [])[0], why = last && last.conclusion && last.conclusion !== 'success' ? ` Последняя сборка: ${last.conclusion}.` : '';
  if (env.GH_TOKEN) {
    const r = await ghApi(env, 'actions/workflows/update.yml/dispatches', { method: 'POST', body: JSON.stringify({ ref: 'main' }), headers: { 'content-type': 'application/json' } });
    await setKv(env, 'kick_at', String(Date.now()));
    if (admin) await tg(env, 'sendMessage', { chat_id: admin, text: r.status === 204
      ? `🔄 Обновление было пропущено: данным на сайте ${Math.round(age)} ч.${why} Запустил новую сборку сам — данные будут примерно через 45 мин, я напишу.`
      : `⚠️ Данным ${Math.round(age)} ч, но запустить сборку не удалось (GitHub ответил ${r.status}). Проверьте токен GH_TOKEN в Cloudflare.` });
    return;
  }
  // no token: tell the admin how to fix it (at most twice a day)
  if (admin && Date.now() - +(await kv(env, 'stale_at') || 0) > 12 * 3600e3) {
    await setKv(env, 'stale_at', String(Date.now()));
    await tg(env, 'sendMessage', { chat_id: admin, text: `⚠️ Данные сайта и бота не обновлялись ${Math.round(age)} ч.${why}\nЧтобы я сам перезапускал пропущенные сборки, добавьте в Cloudflare секрет GH_TOKEN (токен GitHub с правом Actions: Read and write).` });
  }
}
const dayLabel = (d, lang) => { const dt = new Date(d + 'T12:00:00Z'); return `${WD[lang][dt.getUTCDay()]} ${String(dt.getUTCDate()).padStart(2, '0')}.${String(dt.getUTCMonth() + 1).padStart(2, '0')}`; };
const localToday = off => new Date(Date.now() + (off || 0) * 3600e3).toISOString().slice(0, 10);
function forecastText(item, lang, name, id, opt = {}) {
  const days = Object.entries((item && item.days) || {}).filter(([d]) => d >= localToday(item && item.off));
  if (!days.length) return null;
  const city = item.city ? `${item.city}: ` : '';
  const strip = t => (city && t.startsWith(city) ? t.slice(city.length) : t);
  const out = [`${FLAG[id] || '🌍'} <b>${esc(name)}</b>${item.city ? ` · ${esc(item.city)}` : ''}`];
  if (opt.updated) out.push(`<i>${T[lang].upd}: ${opt.updated}</i>`);
  out.push('');
  const [d0, d1] = days;
  out.push(`${icon(d0[1])} <b>${T[lang].tdy}, ${dayLabel(d0[0], lang)}</b>\n${esc(strip(d0[1]))}`);
  if (d1) out.push(`\n${icon(d1[1])} <b>${T[lang].tmw}, ${dayLabel(d1[0], lang)}</b>\n${esc(strip(d1[1]))}`);
  const rest = days.slice(2, 2 + (opt.more ?? 5));
  if (rest.length) {
    out.push(`\n📆 <b>${T[lang].next}</b>`);
    for (const [d, t] of rest) out.push(`${icon(t)} ${dayLabel(d, lang)} — ${esc(strip(t).replace(/\.\s.*$/, '.'))}`);
  }
  let s = out.join('\n');
  if (opt.foot) s += `\n\n${opt.foot}`;
  // Telegram counts the visible characters (tags excluded): drop later days until the caption fits
  const visible = x => x.replace(/<[^>]+>/g, '').replace(/&(amp|lt|gt);/g, '_').length;
  if (opt.limit && visible(s) > opt.limit) return (opt.more ?? 5) > 0 ? forecastText(item, lang, name, id, { ...opt, more: (opt.more ?? 5) - 1 }) : s.slice(0, opt.limit);
  return s;
}
function allDays(item, lang) {
  return Object.entries((item && item.days) || {}).filter(([d]) => d >= localToday(item && item.off)).map(([d, t]) => `${icon(t)} <b>${dayLabel(d, lang)}</b> — ${esc(t)}`).join('\n');
}

/* ---------- updates ---------- */
async function handle(up, env) {
  if (up.my_chat_member) return memberChange(up.my_chat_member, env);
  const msg = up.message || up.channel_post, cb = up.callback_query;
  if (msg && msg.chat.type === 'private') return privateMsg(msg, env);
  if (msg && msg.text) {
    const chat = msg.chat, group = chat.type !== 'private';
    const cmd = (msg.text.trim().match(/^\/(\w+)(@\w+)?/) || [])[1];
    if (group) {
      if (cmd === 'sozla' || cmd === 'settings' || cmd === 'start') {
        if (!(await isAdmin(env, chat, msg.from, msg.sender_chat))) { const s = await sub(env, chat.id); return tg(env, 'sendMessage', { chat_id: chat.id, text: T[(s && s.lang) || 'ru'].gAdm, reply_to_message_id: msg.message_id }); }
        return tg(env, 'sendMessage', { chat_id: chat.id, text: T.uz.gLang + ' / ' + T.ru.gLang, reply_markup: langKb('GL') });
      }
      if (cmd === 'notify' || cmd === 'xabar' || cmd === 'bildirim') {
        const s = await sub(env, chat.id), lg = (s && s.lang) || 'ru';
        if (!(await isAdmin(env, chat, msg.from, msg.sender_chat))) return tg(env, 'sendMessage', { chat_id: chat.id, text: T[lg].gAdm, reply_to_message_id: msg.message_id });
        return groupNotif(env, chat.id, lg);
      }
      if (cmd === 'help') { const s = await sub(env, chat.id); return tg(env, 'sendMessage', { chat_id: chat.id, text: HELP[(s && s.lang) || 'ru'], parse_mode: 'HTML' }); }
      if (cmd === 'bugun' || cmd === 'today') { const s = await sub(env, chat.id), regs = regionsOf(s).length ? regionsOf(s) : ['UZ']; for (const r of regs) await sendToday(env, chat.id, s ? s.lang : cmd === 'today' ? 'ru' : 'uz', r, true); return; }
      return;
    }
  }
  if (!cb) return;
  const chat = cb.message.chat, [kind, lang, id] = cb.data.split(':');
  if (kind[0] === 'G') {  // group settings: GL language → GT toggle countries → GD done → GH hour
    if (!(await isAdmin(env, chat, cb.from))) return tg(env, 'answerCallbackQuery', { callback_query_id: cb.id, text: T[lang].gAdm, show_alert: true });
    const cur = await sub(env, chat.id);
    let sel = regionsOf(cur); const hour = cur && cur.post_hour != null ? cur.post_hour : POST_HOUR, last = cur && cur.last_run;
    if (kind === 'GL') { if (!sel.length) sel = ['UZ']; await saveSub(env, chat, sel, lang, last, hour); }
    if (kind === 'GT') { sel = sel.includes(id) ? sel.filter(r => r !== id) : [...sel, id]; await saveSub(env, chat, sel, lang, last, hour); }
    if (kind === 'GD' && !sel.length) return tg(env, 'answerCallbackQuery', { callback_query_id: cb.id, text: T[lang].gNone, show_alert: true });
    await tg(env, 'answerCallbackQuery', { callback_query_id: cb.id });
    const edit = (text, kb, html) => tg(env, 'editMessageText', { chat_id: chat.id, message_id: cb.message.message_id, text, ...(kb ? { reply_markup: kb } : {}), ...(html ? { parse_mode: 'HTML' } : {}) });
    if (kind === 'GL' || kind === 'GT') return edit(T[lang].gMulti, multiKb(lang, sel));
    if (kind === 'GD') return edit(T[lang].time, timeKb(lang, hour));
    // GH: hour chosen. Today's post is sent right now; the daily ones start tomorrow
    const h = +id;
    await saveSub(env, chat, sel, lang, todayTZ(), h);
    await edit(T[lang].gSet.replace('{time}', hh(h)).replace('{name}', sel.map(r => `${FLAG[r]} ${esc(NAMES[r][lang])}`).join(', ')).replace('{lang}', T[lang].lang), null, true);
    const M = await manifest(env), me = await tg(env, 'getMe', {});
    if (M) for (const r of sel) await post(env, M, chat.id, lang, r, me.ok ? me.result.username : '');
    return groupNotif(env, chat.id, lang);  // next: what else to send here (hourly, weeks, mountains, air) — or everything at once
  }
  if (kind === 'Y' || kind === 'Z') {  // cities of a country: Y list, Z:lang:id:index one city
    await tg(env, 'answerCallbackQuery', { callback_query_id: cb.id, ...(kind === 'Z' ? { text: ({ uz: '⏳ Tayyorlanmoqda…', ru: '⏳ Готовлю…', tr: '⏳ Hazırlanıyor…' })[lang] || '⏳' } : {}) });
    const [, , rid, ci] = cb.data.split(':'), C = await cities(env, rid, lang);
    if (!C || !C.cities.length) return tg(env, 'sendMessage', { chat_id: chat.id, text: T[lang].none });
    if (kind === 'Y' && chat.type === 'private') return cityPicker(env, chat.id, lang, rid);
    if (kind === 'Y') {
      const rows = []; C.cities.forEach((c, i) => { if (i % 3 === 0) rows.push([]); rows[rows.length - 1].push({ text: c.name, callback_data: `Z:${lang}:${rid}:${i}` }); });
      rows.push([{ text: T[lang].back, callback_data: `C:${lang}:${rid}` }]);
      return say(env, cb, { chat_id: chat.id, text: `${FLAG[rid]} <b>${NAMES[rid][lang]}</b> · ${T[lang].cPick}`, parse_mode: 'HTML', reply_markup: { inline_keyboard: rows } });
    }
    const c = C.cities[+ci]; if (!c) return;
    const kb = chat.type === 'private' ? { inline_keyboard: [[liveBtn(env, lang, rid, chat.id, true)]] } : { inline_keyboard: [[{ text: T[lang].cities, callback_data: `Y:${lang}:${rid}` }, { text: T[lang].back, callback_data: `C:${lang}:${rid}` }]] };
    const text = forecastText({ days: c.days, off: C.off, city: c.name }, lang, NAMES[rid][lang], rid, { more: c.video ? 4 : 5, limit: c.video ? 1024 : 4000 });
    if (!text) return tg(env, 'sendMessage', { chat_id: chat.id, text: T[lang].none, reply_markup: kb });
    if (c.video) {  // the precipitation video with this city's timeline (Uzbekistan and Kazakhstan)
      await tg(env, 'sendChatAction', { chat_id: chat.id, action: 'upload_video' });
      const url = `${base(env)}/prob/${c.video}?v=${fresh()}`;
      let r = await tg(env, 'sendVideo', { chat_id: chat.id, video: url, caption: text, parse_mode: 'HTML', supports_streaming: true, reply_markup: kb });
      if (!r.ok) {
        const f = await fetch(url);
        if (f.ok) {
          const fd = new FormData();
          fd.append('chat_id', String(chat.id)); fd.append('caption', text); fd.append('parse_mode', 'HTML'); fd.append('supports_streaming', 'true');
          fd.append('reply_markup', JSON.stringify(kb)); fd.append('video', new Blob([await f.arrayBuffer()], { type: 'video/mp4' }), c.video);
          r = await (await fetch(`https://api.telegram.org/bot${env.BOT_TOKEN}/sendVideo`, { method: 'POST', body: fd })).json();
        }
      }
      if (r.ok) return;
    }
    return tg(env, 'sendMessage', { chat_id: chat.id, text, parse_mode: 'HTML', reply_markup: kb });
  }
  await tg(env, 'answerCallbackQuery', { callback_query_id: cb.id, ...(['T', 'V', 'DC', 'Q', 'O', 'OP', 'OA'].includes(kind) ? { text: ({ uz: '⏳ Tayyorlanmoqda…', ru: '⏳ Готовлю…', tr: '⏳ Hazırlanıyor…' })[lang] || '⏳' } : {}) });
  if (chat.type === 'private') await saveUser(env, chat.id, who(cb.from));
  if (kind === 'S') {  // first language choice after /start: the guide, then the countries
    await saveUser(env, chat.id, { lang });
    await tg(env, 'sendMessage', { chat_id: chat.id, text: HELP[lang], parse_mode: 'HTML', reply_markup: helpKb(lang) });
    return tg(env, 'sendMessage', { chat_id: chat.id, text: T[lang].pick, reply_markup: countryRk(lang) });
  }
  if (kind === 'AC' && chat.type === 'private' && String(chat.id) === (await kv(env, 'admin'))) return sendChanges(env, chat.id);
  if (kind === 'AD' && chat.type === 'private' && String(chat.id) === (await kv(env, 'admin'))) return sendDynamics(env, chat.id, +(id || 14));
  if ((kind === 'AU' || kind === 'AY') && chat.type === 'private') return privateMsg({ chat, from: cb.from, message_id: cb.message.message_id, text: kind === 'AU' ? '/users' : '/yt' }, env);
  if (kind === 'O') return sendOutlook(env, chat.id, lang);
  if (kind === 'OP') return sendOutlookPart(env, chat.id, lang, id);
  if (kind === 'OA') return sendOutlookPart(env, chat.id, lang, null);
  if (kind === 'MP') return sendMountainText(env, chat.id, lang, id);
  if (kind === 'RG' && ADM.has(id)) return sendRegions(env, chat.id, lang, id);
  if (kind === 'TJ' && TRJ.has(id)) return sendTraj(env, chat.id, lang, id);
  if (kind === 'MV' && TRJ.has(id)) return sendMoist15(env, chat.id, lang, id);
  if (kind === 'RX' && ADM.has(id)) {  // one district: the full forecast at its centre, named "district, region"
    const A = await adminData(env, id), d = A && A.adm2[+cb.data.split(':')[3]];
    if (d) { const r = A.adm1.find(a => a.id === d.p), nm = l => `${d.name[l] || d.name.ru}${r ? ', ' + (r.name[l] || r.name.ru) : ''}`;
      return pointForecast(env, chat.id, lang, d.c[1], d.c[0], [nm('ru'), nm('uz'), d.name.en || nm('ru'), nm('tr'), id, d.c[1], d.c[0], 0, 0]); } }
  if (kind === 'RB' && ADM.has(id)) { const A = await adminData(env, id); if (A) return tg(env, 'editMessageText', { ...regionsList(A, lang, id, chat.id), message_id: cb.message.message_id }); }
  if (kind === 'RD' && ADM.has(id)) return sendDistricts(env, chat.id, lang, id, +cb.data.split(':')[3], cb.message.message_id);
  if (chat.type !== 'private' && ['NS', 'NT', 'NO', 'MS', 'WS', 'WA', 'WX'].includes(kind) && !(await isAdmin(env, chat, cb.from)))
    return tg(env, 'sendMessage', { chat_id: chat.id, text: T[lang].gAdm });
  if (kind === 'WS') { if (await mtnSub(env, chat.id)) await env.DB.prepare('DELETE FROM mtn WHERE chat_id = ?1').bind(chat.id).run(); else await env.DB.prepare('INSERT OR REPLACE INTO mtn (chat_id, lang, ver, added) VALUES (?1, ?2, ?3, ?4)').bind(chat.id, lang, (await kv(env, 'mtn_ver')) || '', new Date().toISOString()).run(); return groupNotif(env, chat.id, lang, cb.message.message_id); }
  if (kind === 'WA' || kind === 'WX') { await groupAll(env, chat.id, lang, kind === 'WA'); const G = GNX[lang] || GNX.ru, s0 = await sub(env, chat.id);
    return groupNotif(env, chat.id, lang, cb.message.message_id, kind === 'WA' ? G.allOn.replace('{h}', hh(s0 && s0.post_hour != null ? s0.post_hour : POST_HOUR)) : G.offAll); }
  if (kind === 'NS' && NSEC.includes(id)) return notifAsk(env, chat.id, lang, id);
  if (kind === 'NT' && NSEC.includes(id)) return notifSet(env, chat.id, lang, id, +cb.data.split(':')[3], cb.message.message_id);
  if (kind === 'NO' && NSEC.includes(id)) { await env.DB.prepare('DELETE FROM notif WHERE chat_id = ?1 AND sec = ?2').bind(chat.id, id).run(); if (chat.id < 0) { await tg(env, 'deleteMessage', { chat_id: chat.id, message_id: cb.message.message_id }); return groupNotif(env, chat.id, lang); } return tg(env, 'editMessageText', { chat_id: chat.id, message_id: cb.message.message_id, text: (NX_[lang] || NX_.ru).offT.replace('{s}', secName(id, lang)) }); }
  if (kind === 'MA') return sendMountainText(env, chat.id, lang, null);
  if (kind === 'MT') return sendMountains(env, chat.id, lang);
  if (kind === 'MS') {  // the snow signal on / off: the button under the mountains message changes with it
    const X = MTX[lang] || MTX.ru, cur = await mtnSub(env, chat.id);
    if (cur) await env.DB.prepare('DELETE FROM mtn WHERE chat_id = ?1').bind(chat.id).run();
    else await env.DB.prepare('INSERT OR REPLACE INTO mtn (chat_id, lang, ver, added) VALUES (?1, ?2, ?3, ?4)').bind(chat.id, lang, (await kv(env, 'mtn_ver')) || '', new Date().toISOString()).run();
    const old = cb.message.reply_markup && cb.message.reply_markup.inline_keyboard;  // keep the place buttons, flip only the signal button
    const kb = old ? old.map(row => row.map(x => x.callback_data && x.callback_data.startsWith('MS:') ? { text: cur ? X.sub : X.unsub, callback_data: `MS:${lang}`, ...(cur ? { style: 'success' } : {}) } : x)) : [[{ text: cur ? X.sub : X.unsub, callback_data: `MS:${lang}` }]];
    await tg(env, 'editMessageReplyMarkup', { chat_id: chat.id, message_id: cb.message.message_id, reply_markup: { inline_keyboard: kb } });
    return tg(env, 'sendMessage', { chat_id: chat.id, text: cur ? X.off : X.on });
  }
  if (kind === 'Q') { const [, , la, lo] = cb.data.split(':'); return pointForecast(env, chat.id, lang, +la, +lo, await nearestPlace(env, +la, +lo, 5)); }
  if (kind === 'DC') {  // 15 days for one city of the country list: the same numbers as its video, and the video under it
    const [, , rid, ci] = cb.data.split(':'), C = (await cities(env, rid, lang)) || (await cities(env, rid, 'ru')), c = C && C.cities[+ci];
    if (!c || c.lat == null) return tg(env, 'sendMessage', { chat_id: chat.id, text: T[lang].none });
    return pointForecast(env, chat.id, lang, c.lat, c.lon, (await nearestPlace(env, c.lat, c.lon, 8)) || [c.name, c.name, c.en, c.name, rid, c.lat, c.lon, 0, 0], replyKb(env, lang, rid));
  }
  if (kind === 'H') return tg(env, 'sendMessage', { chat_id: chat.id, text: HELP[lang], parse_mode: 'HTML', reply_markup: helpKb(lang) });
  if (kind === 'HM') {  // the main menu: the country chosen last time (or Uzbekistan)
    const uu = await getUser(env, chat.id), rid = uu && NAMES[uu.region] ? uu.region : 'UZ';
    return say(env, cb, { chat_id: chat.id, text: `${FLAG[rid]} <b>${NAMES[rid][lang]}</b> · ${T[lang].menu}`, parse_mode: 'HTML', reply_markup: menuKb(env, lang, rid) });
  }
  if (kind === 'RS') { const X = HK[lang] || HK.ru; return say(env, cb, { chat_id: chat.id, text: X.ask, reply_markup: { inline_keyboard: [[{ text: X.yes, callback_data: `RSY:${lang}`, style: 'danger' }, { text: X.no, callback_data: `HM:${lang}` }]] } }); }
  if (kind === 'RSY') {  // reset: forget the country, the place and the private daily subscription; start again from the language
    await env.DB.prepare('UPDATE users SET region = NULL, place = NULL, mode = NULL WHERE chat_id = ?1').bind(chat.id).run();
    if (chat.type === 'private') await env.DB.prepare('DELETE FROM subs WHERE chat_id = ?1').bind(chat.id).run();
    return say(env, cb, { chat_id: chat.id, text: (HK[lang] || HK.ru).done, reply_markup: langKb('S') });
  }
  if (kind === 'LQ') return tg(env, 'sendMessage', { chat_id: chat.id, text: T[lang].locAsk, reply_markup: locOnce(lang) });
  if (kind === 'P') return sendGuide(env, chat.id, lang);
  if (kind === 'M') { await saveUser(env, chat.id, { lang, mode: 'contact' }); return tg(env, 'sendMessage', { chat_id: chat.id, text: T[lang].admAsk }); }
  if (kind === 'L') await saveUser(env, chat.id, { lang });
  if (kind === 'C') await saveUser(env, chat.id, { lang, region: id });
  if (kind === 'B' || kind === 'BH' || kind === 'BX') {  // personal daily forecast in the private chat
    const cur = await sub(env, chat.id), nm = `${FLAG[id] || ''} ${NAMES[id] ? NAMES[id][lang] : ''}`;
    if (kind === 'BX') { await env.DB.prepare('DELETE FROM subs WHERE chat_id = ?1').bind(chat.id).run(); return tg(env, 'sendMessage', { chat_id: chat.id, text: T[lang].subOff }); }
    if (kind === 'B') {
      const kb = timeKb(lang, cur && regionsOf(cur)[0] === id ? cur.post_hour ?? POST_HOUR : -1);
      kb.inline_keyboard.forEach(row => row.forEach(b => { b.callback_data = `BH:${lang}:${id}:${b.callback_data.split(':')[2]}`; }));
      if (cur) kb.inline_keyboard.push([{ text: T[lang].unsub, callback_data: `BX:${lang}:${id}` }]);
      return say(env, cb, { chat_id: chat.id, text: T[lang].subAsk.replace('{name}', nm), reply_markup: kb });
    }
    const h = +cb.data.split(':')[3];
    await saveSub(env, chat, [id], lang, todayTZ(), h);
    return tg(env, 'sendMessage', { chat_id: chat.id, text: T[lang].subOk.replace('{time}', hh(h)).replace('{name}', nm), reply_markup: menuKb(env, lang, id) });
  }
  if (kind === 'L') return tg(env, 'sendMessage', { chat_id: chat.id, text: T[lang].pick, reply_markup: countryRk(lang, (await getUser(env, chat.id) || {}).region) });
  if (kind === 'C') return say(env, cb, { chat_id: chat.id, text: `${FLAG[id]} <b>${NAMES[id][lang]}</b> · ${T[lang].menu}`, parse_mode: 'HTML', reply_markup: menuKb(env, lang, id) });
  if (kind === 'T') return sendHourly(env, chat.id, lang, id);
  const M = await manifest(env);
  const items = M ? M.items.filter(i => i.region === id && i.lang === lang) : [];
  if (!items.length) return tg(env, 'sendMessage', { chat_id: chat.id, text: T[lang].none });
  const days = items.find(i => i.product === 'days');
  if (kind === 'D') return cityPicker(env, chat.id, lang, id);
  if (kind === 'D_old') {  // 15 days: first choose where — a city of this country, my place, or any town in the world by name
    const C = (await cities(env, id, lang)) || (await cities(env, id, 'ru'));
    const uu = await getUser(env, chat.id), pl = uu && uu.place ? JSON.parse(uu.place) : null, near = pl ? await nearestPlace(env, pl[0], pl[1], 40) : null;
    const rows = [];
    if (pl) rows.push([{ text: `📍 ${near ? pname(near, lang) : DK[lang].mine}`, callback_data: `Q:${lang}:${(+pl[0]).toFixed(3)}:${(+pl[1]).toFixed(3)}`, style: 'success' }]);
    (C ? C.cities.slice(0, 21) : []).forEach((c, i) => { if (c.lat == null) return; if (!rows.length || rows[rows.length - 1].length === 3 || (pl && rows.length === 1)) rows.push([]); rows[rows.length - 1].push({ text: c.name, callback_data: `DC:${lang}:${id}:${i}` }); });
    rows.push([{ text: DK[lang].loc, callback_data: `LQ:${lang}` }, { text: DK[lang].other, callback_data: `L:${lang}` }]);
    rows.push([{ text: T[lang].back, callback_data: `C:${lang}:${id}` }, { text: (HK[lang] || HK.ru).home, callback_data: `HM:${lang}` }]);
    if (rows.length <= 2 && !C) return tg(env, 'sendMessage', { chat_id: chat.id, text: `${FLAG[id]} <b>${NAMES[id][lang]}</b>\n\n${allDays(days, lang)}`, parse_mode: 'HTML', reply_markup: menuKb(env, lang, id) });
    return say(env, cb, { chat_id: chat.id, text: `${FLAG[id]} <b>${NAMES[id][lang]}</b> · ${DK[lang].ask}`, parse_mode: 'HTML', reply_markup: { inline_keyboard: rows } });
  }
  if (kind === 'V') {
    let vids = ['prob', 'temp', 'cloud', 'wind'].map(p => items.find(i => (i.product || 'prob') === p)).filter(Boolean);
    if (!vids.length) vids = ['prob', 'temp', 'cloud', 'wind'].map(p => M.items.find(i => i.region === id && i.lang === 'ru' && (i.product || 'prob') === p)).filter(Boolean);
    const media = vids.map(v => ({ type: 'video', media: `${base(env)}/prob/${v.video}?v=${fresh()}`, supports_streaming: true }));
    media[0].caption = forecastText(days, lang, NAMES[id][lang], id, { more: 3, limit: 1000 }) || `${NAMES[id][lang]} · ${T[lang].d15}`;
    media[0].parse_mode = 'HTML';
    await tg(env, 'sendChatAction', { chat_id: chat.id, action: 'upload_video' });
    let r = await tg(env, 'sendMediaGroup', { chat_id: chat.id, media });
    // Telegram could not take them by link: the two lightest ones (uploading from here breaks on big files)
    if (!r.ok) { console.log('album', chat.id, id, r.description); const m2 = media.slice(-2); m2[0] = { ...m2[0], caption: media[0].caption, parse_mode: 'HTML' }; r = await tg(env, 'sendMediaGroup', { chat_id: chat.id, media: m2 }); }
    if (!r.ok) await tg(env, 'sendMessage', { chat_id: chat.id, text: `${T[lang].none}\n(${r.description || r.error_code || '?'})` });
    return tg(env, 'sendMessage', { chat_id: chat.id, text: T[lang].menu, reply_markup: menuKb(env, lang, id) });
  }
}

/* ---------- private chat: commands, guide and messages to the bot's admin ---------- */
async function privateMsg(msg, env) {
  const chat = msg.chat, text = msg.text || '', cmd = (text.trim().match(/^\/(\w+)(@\w+)?/) || [])[1];
  const u = await getUser(env, chat.id), lang = (u && T[u.lang] && u.lang) || (/^ru/.test(msg.from && msg.from.language_code || '') ? 'ru' : /^tr/.test(msg.from && msg.from.language_code || '') ? 'tr' : 'uz');
  await saveUser(env, chat.id, who(msg.from));
  const admin = await kv(env, 'admin');
  // the admin answers a user: Reply to the forwarded message
  if (admin && String(chat.id) === admin && msg.reply_to_message && !cmd) {
    const to = env.DB && await env.DB.prepare('SELECT chat, lang FROM msgmap WHERE mid = ?1').bind(msg.reply_to_message.message_id).first();
    if (to) {
      const L = T[to.lang] ? to.lang : 'ru';
      await tg(env, 'sendMessage', { chat_id: to.chat, text: T[L].admAns });
      const r = await tg(env, 'copyMessage', { chat_id: to.chat, from_chat_id: chat.id, message_id: msg.message_id });
      return tg(env, 'sendMessage', { chat_id: chat.id, text: r.ok ? '✅' : `⚠️ ${r.description || ''}`, reply_to_message_id: msg.message_id });
    }
  }
  if (cmd === 'cancel') { await saveUser(env, chat.id, { mode: '' }); return tg(env, 'sendMessage', { chat_id: chat.id, text: T[lang].cancel }); }
  // the weather watch at the person's place: the answers to "where are you now?", then the question itself at each entry
  { const W = WX[lang] || WX.ru, wt = text.trim();
    if (wt === W.off) { await watchSet(env, chat.id, { on_: 0, asked: todayTZ() }); return tg(env, 'sendMessage', { chat_id: chat.id, text: W.offOk, reply_markup: replyKb(env, lang, (u && NAMES[u.region] && u.region) || 'UZ') }); }
    if (wt.startsWith(W.sameP)) { const w = await watchGet(env, chat.id); await watchSet(env, chat.id, { on_: 1, asked: todayTZ() });
      return tg(env, 'sendMessage', { chat_id: chat.id, text: W.onOk.replace('{p}', (w && w.name) || '📍'), parse_mode: 'HTML', reply_markup: replyKb(env, lang, (u && NAMES[u.region] && u.region) || 'UZ') }); }
    if (u && u.lang && !msg.location && !['now', 'loc'].includes(rkAct(wt)) && (cmd === 'start' || (u.seen && new Date(Date.parse(u.seen) + TZ * 3600e3).toISOString().slice(0, 10) < todayTZ()))) await watchAsk(env, chat.id, lang);
  }
  if (cmd === 'yt' && admin === String(chat.id)) {  // the YouTube / channel briefing, ready to publish
    const I = await (await fetch(`${base(env)}/prob/yt/index.json?t=${Date.now()}`)).json().catch(() => null);
    const want = (text.split(/\s+/)[1] || lang).toLowerCase(), b = I && (I.items.find(i => i.lang === want) || I.items[0]);
    if (!b) return tg(env, 'sendMessage', { chat_id: chat.id, text: '⏳ Видеообзора ещё нет.' });
    await tg(env, 'sendChatAction', { chat_id: chat.id, action: 'upload_video' });
    const url = `${base(env)}/prob/${b.video}?v=${fresh()}`;
    let r = await tg(env, 'sendVideo', { chat_id: chat.id, video: url, caption: b.title, supports_streaming: true });
    if (!r.ok) { const f = await fetch(url); if (f.ok) { const fd = new FormData(); fd.append('chat_id', String(chat.id)); fd.append('caption', b.title); fd.append('supports_streaming', 'true'); fd.append('video', new Blob([await f.arrayBuffer()], { type: 'video/mp4' }), `osmon_${b.lang}.mp4`); r = await (await fetch(`https://api.telegram.org/bot${env.BOT_TOKEN}/sendVideo`, { method: 'POST', body: fd })).json(); } }
    await tg(env, 'sendPhoto', { chat_id: chat.id, photo: `${base(env)}/prob/${b.thumb}?v=${fresh()}`, caption: 'YouTube thumbnail' });
    const t = await (await fetch(`${base(env)}/prob/${b.text}`)).text().catch(() => '');
    return tg(env, 'sendMessage', { chat_id: chat.id, text: (r.ok ? '' : `⚠️ ${r.description || ''}\n${url}\n\n`) + t.slice(0, 4000), disable_web_page_preview: true });
  }
  if (cmd === 'changes' && admin === String(chat.id)) return sendChanges(env, chat.id);
  if (cmd === 'dyn' && admin === String(chat.id)) return sendDynamics(env, chat.id);
  if (cmd === 'searches' && admin === String(chat.id)) {
    const S = await searchStats(env, 7);
    return tg(env, 'sendMessage', { chat_id: chat.id, parse_mode: 'HTML', text: `🔎 <b>Поиск городов за 7 дней</b>: ${S.tot}\n\n${S.top.map((x, i) => `${i + 1}. ${esc(x.q)} — ${x.n}`).join('\n') || '—'}${S.miss.length ? `\n\n❓ <b>Не нашлось</b>:\n${S.miss.map(x => `• ${esc(x.q)} — ${x.n}`).join('\n')}` : ''}` });
  }
  if ((cmd === 'users' || text === ADMIN_BTN) && admin === String(chat.id)) {
    const rows = (await env.DB.prepare('SELECT * FROM users ORDER BY seen DESC LIMIT 100').all()).results;
    const n = (await env.DB.prepare('SELECT COUNT(*) AS n FROM users').first()).n;
    const lines = rows.map((x, i) => `${i + 1}. ${esc(x.name || '—')}${x.username ? ' @' + esc(x.username) : ''} · ${x.lang || '?'}${x.region ? ' · ' + (FLAG[x.region] || x.region) : ''} · ${tkt(x.seen)}`);
    const out = [`👤 <b>Users: ${n}</b> (last 100, время Ташкента)`, ...lines]; let buf = '';
    for (const l of out) { if ((buf + l).length > 3800) { await tg(env, 'sendMessage', { chat_id: chat.id, text: buf, parse_mode: 'HTML' }); buf = ''; } buf += l + '\n'; }
    return tg(env, 'sendMessage', { chat_id: chat.id, text: buf, parse_mode: 'HTML' });
  }
  if (cmd === 'admin') {
    if (!admin && env.DB) {  // the first one to send /admin becomes the bot's admin
      await setKv(env, 'admin', String(chat.id)); await adminMenu(env, chat.id);
      return tg(env, 'sendMessage', { chat_id: chat.id, text: '👑 Siz bot adminisiz / Вы — администратор бота.\n\nFoydalanuvchilar xabarlari shu yerga keladi. Javob berish uchun xabarga Reply qiling.\nСообщения пользователей будут приходить сюда. Чтобы ответить, нажмите «Ответить» (Reply) на сообщении.' });
    }
    if (admin === String(chat.id)) {
      const g = await env.DB.prepare("SELECT COUNT(*) AS n FROM subs WHERE type <> 'private'").first(), us = await env.DB.prepare('SELECT COUNT(*) AS n FROM users').first();
      const list = (await env.DB.prepare('SELECT title, type, region, lang, post_hour FROM subs ORDER BY added DESC LIMIT 30').all()).results;
      await adminMenu(env, chat.id);
      return tg(env, 'sendMessage', { chat_id: chat.id, reply_markup: ADMIN_KB, text: `👑 Admin  (/users — list, /yt ru|uz — YouTube briefing)\n👤 Users: ${us.n}\n👥 Groups: ${g.n}\n🔔 Daily (private): ${(await env.DB.prepare("SELECT COUNT(*) AS n FROM subs WHERE type = 'private'").first()).n}\n\n${list.map(x => `• ${x.type === 'private' ? '👤' : '👥'} ${x.title || '?'} — ${x.region} · ${x.lang} · ${hh(x.post_hour ?? POST_HOUR)}`).join('\n')}`.slice(0, 4000) });
    }
    await saveUser(env, chat.id, { lang, mode: 'contact' });
    return tg(env, 'sendMessage', { chat_id: chat.id, text: T[lang].admAsk });
  }
  if (u && u.mode === 'contact' && !cmd) {  // pass the message on to the admin
    await saveUser(env, chat.id, { mode: '' });
    if (!admin) return tg(env, 'sendMessage', { chat_id: chat.id, text: T[lang].admOff });
    const f = msg.from || {}, who = `✉️ <b>${esc([f.first_name, f.last_name].filter(Boolean).join(' ') || '?')}</b>${f.username ? ' @' + esc(f.username) : ''} · <code>${chat.id}</code> · ${lang}`;
    const ids = [];
    if (text) { const r = await tg(env, 'sendMessage', { chat_id: admin, text: `${who}\n\n${esc(text)}`.slice(0, 4000), parse_mode: 'HTML' }); if (r.ok) ids.push(r.result.message_id); }
    else {
      const h = await tg(env, 'sendMessage', { chat_id: admin, text: who, parse_mode: 'HTML' }); if (h.ok) ids.push(h.result.message_id);
      const r = await tg(env, 'copyMessage', { chat_id: admin, from_chat_id: chat.id, message_id: msg.message_id }); if (r.ok) ids.push(r.result.message_id);
    }
    for (const id of ids) await env.DB.prepare('INSERT OR REPLACE INTO msgmap (mid, chat, lang) VALUES (?1, ?2, ?3)').bind(id, chat.id, lang).run();
    return tg(env, 'sendMessage', { chat_id: chat.id, text: ids.length ? T[lang].admSent : T[lang].admOff, reply_markup: replyKb(env, lang, (u && NAMES[u.region] && u.region) || 'UZ') });
  }
  if (cmd === 'guide') return sendGuide(env, chat.id, lang);
  if (cmd === 'alerts') { const A = await alertsData(env), rid = (u && NAMES[u.region] && u.region) || null; const it = A ? A.items.filter(i => !rid || i.region === rid) : []; return tg(env, 'sendMessage', { chat_id: chat.id, text: it.length ? alertText(it, lang) : AL[lang].none, parse_mode: 'HTML' }); }
  if (cmd === 'help') return tg(env, 'sendMessage', { chat_id: chat.id, text: HELP[lang], parse_mode: 'HTML', reply_markup: helpKb(lang) });
  if (cmd === 'bugun' || cmd === 'today') return sendHourly(env, chat.id, u && u.lang && T[u.lang] ? u.lang : cmd === 'today' ? 'ru' : 'uz', (u && NAMES[u.region] && u.region) || 'UZ');
  if (cmd === 'prognoz') return tg(env, 'sendMessage', { chat_id: chat.id, text: T[lang].pick, reply_markup: countryRk(lang, u && u.region) });
  if (msg.location) {  // weather right here
    const { latitude: la, longitude: lo } = msg.location;
    await tg(env, 'sendChatAction', { chat_id: chat.id, action: 'typing' });
    const np = await nearestPlace(env, la, lo), r = await pointForecast(env, chat.id, lang, la, lo, np);
    // from now on: a message when it starts to rain or snow here, a storm, great heat or frost, strong wind — not in normal weather
    await watchSet(env, chat.id, { lat: la, lon: lo, name: np ? pname(np, lang) : `${la.toFixed(2)}, ${lo.toFixed(2)}`, lang, on_: 1, asked: todayTZ() });
    await tg(env, 'sendMessage', { chat_id: chat.id, text: (WX[lang] || WX.ru).onOk.replace('{p}', esc(np ? pname(np, lang) : (WX[lang] || WX.ru).here)), parse_mode: 'HTML', reply_markup: replyKb(env, lang, (u && NAMES[u.region] && u.region) || 'UZ') });
    return r;
  }
  if (!text) return;
  // the ☰ menu (and the buttons of the old keyboard that some chats still show): one action each, no duplicates
  {
    const rid = (u && NAMES[u.region] && u.region) || 'UZ', old = k => !cmd && Object.values(MK).some(m => m[k] === text);
    const rk = !cmd && rkAct(text);
    const act = rk === 'back' ? 'home' : rk === 'loc' ? 'location' : rk || (old('today') ? 'hourly' : old('d15') ? 'days' : old('video') ? 'video' : old('more') ? 'countries' : Object.values(PT).some(m => m.locBtn === text) ? 'location' : cmd);
    const cid = !cmd && !rk && countryOf(text);
    if (cid) {  // a country from the keyboard: remember it and show its menu
      await saveUser(env, chat.id, { lang, region: cid });
      return tg(env, 'sendMessage', { chat_id: chat.id, text: `${FLAG[cid]} <b>${NAMES[cid][lang]}</b> · ${T[lang].menu}`, parse_mode: 'HTML', reply_markup: replyKb(env, lang, cid) });
    }
    if (!cmd && !rk && u && u.lang) {  // a city of the chosen country from the keyboard: the same 15-day layout as a searched town
      const C = (await cities(env, rid, lang)) || null, c = C && C.cities.find(x => x.name === text.trim());
      if (c && c.lat != null) return pointForecast(env, chat.id, lang, c.lat, c.lon, (await nearestPlace(env, c.lat, c.lon, 8)) || [c.name, c.name, c.en, c.name, rid, c.lat, c.lon, 0, 0], replyKb(env, lang, rid));
      if (c) {  // older city lists without coordinates: find the town by name in this country
        const q = norm(c.en || c.name), p = (await places(env)).find(p => p[4] === rid && [p[0], p[1], p[2], p[3]].some(x => norm(x) === q || norm(x) === norm(c.name)));
        if (p) return pointForecast(env, chat.id, lang, p[5], p[6], p, replyKb(env, lang, rid));
      }
    }
    const cbk = data => handle({ callback_query: { id: '0', from: msg.from, data, message: { chat, message_id: msg.message_id } } }, env);
    
    if (act === 'home') return tg(env, 'sendMessage', { chat_id: chat.id, text: `${FLAG[rid]} <b>${NAMES[rid][lang]}</b> · ${T[lang].menu}`, parse_mode: 'HTML', reply_markup: replyKb(env, lang, rid) });
    if (act === 'days' || act === 'cities') return cityPicker(env, chat.id, lang, rid, u);
    if (act === 'help') return tg(env, 'sendMessage', { chat_id: chat.id, text: HELP[lang], parse_mode: 'HTML', reply_markup: helpKb(lang) });
    if (act === 'alerts') { const A = await alertsData(env); const it = A ? A.items.filter(i => i.region === rid) : []; return tg(env, 'sendMessage', { chat_id: chat.id, text: it.length ? alertText(it, lang) : AL[lang].none, parse_mode: 'HTML' }); }
    if (act === 'video') {  // the video that matches the last forecast: that city's own video (Uzbekistan, Kazakhstan) or the country's
      const pl = u && u.place ? JSON.parse(u.place) : null, C = pl ? await cities(env, rid, lang) : null;
      const np = pl ? await nearestPlace(env, pl[0], pl[1], 8) : null;
      const ci = C ? C.cities.findIndex(c => c.video && (c.lat != null ? Math.hypot(c.lat - pl[0], (c.lon - pl[1]) * Math.cos(pl[0] * Math.PI / 180)) < 0.12 : np && (c.en === np[2] || norm(c.name) === norm(pname(np, lang))))) : -1;
      return cbk(ci >= 0 ? `Z:${lang}:${rid}:${ci}` : `V:${lang}:${rid}`);
    }
    if (act === 'reset') return cbk(`RS:${lang}`);
    if (act === 'hourly') return sendHourly(env, chat.id, lang, rid);
    if (act === 'outlook') return sendOutlook(env, chat.id, lang);
    if (act === 'mtn') return sendMountains(env, chat.id, lang);
    if (act === 'regions') return sendRegions(env, chat.id, lang, ADM.has(rid) ? rid : 'UZ');
    if (act === 'air') { await tg(env, 'sendChatAction', { chat_id: chat.id, action: 'typing' }); return sendAir(env, chat.id, lang, rid); }
    if (act === 'notif') return notifList(env, chat.id, lang);
    if (act === 'accuracy') return sendAccuracy(env, chat.id, lang);
    if (act === 'now') {  // right now at the user's place (or the country's capital), with the forecast below
      const pl = u && u.place ? JSON.parse(u.place) : null;
      if (pl) {  // just the weather right now, short; the 15 days are one button away
        const np = await nearestPlace(env, pl[0], pl[1]), c = await nowWeather(+pl[0], +pl[1]), line = nowLine(c, lang);
        if (line) return tg(env, 'sendMessage', { chat_id: chat.id, parse_mode: 'HTML', text: `${np ? `${FLAG[np[4]] || '📍'} <b>${esc(pname(np, lang))}</b>` : `📍 <b>${(+pl[0]).toFixed(2)}, ${(+pl[1]).toFixed(2)}</b>`}\n\n${line}`, reply_markup: replyKb(env, lang, rid) });
        return pointForecast(env, chat.id, lang, pl[0], pl[1], np);
      }
      return tg(env, 'sendMessage', { chat_id: chat.id, text: T[lang].locAsk, reply_markup: locOnce(lang) });
    }
    if (act === 'days') return cbk(`D:${lang}:${rid}`);
    if (act === 'video') return cbk(`V:${lang}:${rid}`);
    if (act === 'cities') return cbk(`Y:${lang}:${rid}`);
    if (act === 'daily') return cbk(`B:${lang}:${rid}`);
    if (act === 'countries' || act === 'prognoz') return tg(env, 'sendMessage', { chat_id: chat.id, text: T[lang].pick, reply_markup: countryRk(lang, u && u.region) });
    if (act === 'location') return tg(env, 'sendMessage', { chat_id: chat.id, text: T[lang].locAsk, reply_markup: locOnce(lang) });
    if (act === 'site') return tg(env, 'sendMessage', { chat_id: chat.id, text: `${FLAG[rid]} ${NAMES[rid][lang]}`, reply_markup: { inline_keyboard: [[{ text: T[lang].site, web_app: { url: site(env, `prob/${rid}/${lang}/prob`) } }], [{ text: T[lang].rep, web_app: { url: site(env, 'map') } }]] } });
  }
  if (!cmd && u && u.lang) {  // a town name (also "погода в Самарканде завтра"): search it anywhere in the world
    const q = text.split(/\s+/).filter(w => !FILLER.has(norm(w))).join(' ').trim() || text;
    let found = await searchPlaces(env, q);
    for (const v of [q.replace(/(ом|ем|ой|ей|ах|ях|е|у|ю|а|я|и|ы)$/iu, ''), q.replace(/(dagi|da|ga|ning|ni|dan|de|da|ta|te|'?(d|t)[ae])$/iu, '')])  // "в Самарканде", "Samarqandda", "Antalya'da"
      if (!found.length && v.length >= 3 && v !== q) found = await searchPlaces(env, v);
    ctxLog(env, logSearch(env, q, found.length));
    if (found.length === 1 || (found.length && norm([found[0][0], found[0][1], found[0][2], found[0][3]].find(x => norm(x) === norm(q)) || '') === norm(q) && !found.slice(1).some(p => [p[0], p[1], p[2], p[3]].some(x => norm(x) === norm(q)))))
      return pointForecast(env, chat.id, lang, found[0][5], found[0][6], found[0]);
    if (found.length) return tg(env, 'sendMessage', { chat_id: chat.id, text: PT[lang].pick, reply_markup: { inline_keyboard: found.map(p => [{ text: `${FLAG[p[4]] || '📍'} ${pname(p, lang)}${NAMES[p[4]] ? ', ' + NAMES[p[4]][lang] : ' (' + p[4] + ')'}`, callback_data: `Q:${lang}:${p[5]}:${p[6]}` }]) } });
    return tg(env, 'sendMessage', { chat_id: chat.id, text: PT[lang].nf + '\n\n' + T[lang].menuHint });
  }
  const kb = langKb('S');  // a returning user goes straight back to the country they chose last time
  if (u && u.region && NAMES[u.region] && T[u.lang]) kb.inline_keyboard.push([{ text: `▶️ ${FLAG[u.region]} ${NAMES[u.region][u.lang]}`, callback_data: `C:${u.lang}:${u.region}` }]);
  return tg(env, 'sendMessage', { chat_id: chat.id, text: T.uz.hi + '\n\n' + T.ru.hi.split('\n').slice(0, 2).join('\n') + '\nВыберите язык:', parse_mode: 'HTML', reply_markup: kb });
}
// what people search for (admin statistics): daily totals per query, nothing about the person
function ctxLog(env, p) { if (env._ctx) env._ctx.waitUntil(p.catch(() => {})); else p.catch(() => {}); }
async function logSearch(env, q, n) {
  if (!env.DB) return; await db(env);
  await env.DB.prepare('INSERT INTO searches (day, q, found, n) VALUES (?1, ?2, ?3, 1) ON CONFLICT(day, q) DO UPDATE SET n = n + 1, found = ?3').bind(todayTZ(), norm(q).slice(0, 60), n ? 1 : 0).run();
}
async function searchStats(env, days = 7) {
  await db(env); const since = new Date(Date.now() + TZ * 3600e3 - days * 864e5).toISOString().slice(0, 10);
  const top = (await env.DB.prepare('SELECT q, SUM(n) AS n FROM searches WHERE day >= ?1 AND found = 1 GROUP BY q ORDER BY n DESC LIMIT 15').bind(since).all()).results;
  const miss = (await env.DB.prepare('SELECT q, SUM(n) AS n FROM searches WHERE day >= ?1 AND found = 0 GROUP BY q ORDER BY n DESC LIMIT 10').bind(since).all()).results;
  const tot = await env.DB.prepare('SELECT COALESCE(SUM(n),0) AS n FROM searches WHERE day >= ?1').bind(since).first();
  return { top, miss, tot: tot.n };
}
// forecast accuracy (prob/verify.py): the last 30 days, forecast for tomorrow against what happened
async function sendAccuracy(env, chat, lang) {
  const V = await memo('verify', 1800e3, async () => { const r = await fetch(`${base(env)}/prob/verify/index.json`, { cf: { cacheTtl: 1800 } }); return r.ok ? r.json() : null; });
  const X = { uz: { t: '🎯 <b>Prognoz aniqligi</b> (oxirgi 30 kun)', rain: 'Yog‘in bor/yo‘q to‘g‘ri topildi', temp: 'Harorat xatosi o‘rtacha', t2: '±2° ichida', city: 'Shaharlar bo‘yicha', wait: 'Tekshiruv boshlandi: ertangi prognozlar saqlanmoqda, birinchi natijalar 2–3 kunda chiqadi.', how: 'Ertangi kun prognozi (24–48 soat oldin) haqiqiy ob-havo bilan solishtiriladi: yog‘in ≥ 1 mm, ehtimol ≥ 50 % = «yog‘in».', days: 'kun' },
    ru: { t: '🎯 <b>Точность прогноза</b> (последние 30 дней)', rain: 'Угадано «будут осадки / нет»', temp: 'Средняя ошибка температуры', t2: 'в пределах ±2°', city: 'По городам', wait: 'Проверка запущена: прогнозы на завтра сохраняются, первые результаты — через 2–3 дня.', how: 'Прогноз на завтра (за 24–48 ч) сравнивается с фактической погодой: осадки ≥ 1 мм, вероятность ≥ 50 % = «будут осадки».', days: 'дн.' },
    tr: { t: '🎯 <b>Tahmin doğruluğu</b> (son 30 gün)', rain: 'Yağış var/yok doğru', temp: 'Ortalama sıcaklık hatası', t2: '±2° içinde', city: 'Şehirler', wait: 'Doğrulama başladı: yarın tahminleri kaydediliyor, ilk sonuçlar 2–3 gün içinde.', how: 'Yarın tahmini (24–48 saat önce) gerçek hava ile karşılaştırılır: yağış ≥ 1 mm, olasılık ≥ %50 = «yağış».', days: 'gün' } }[lang] || null;
  const o = V && (V.uz || V.overall);
  if (!o) return tg(env, 'sendMessage', { chat_id: chat, text: `${X.t}

${X.wait}`, parse_mode: 'HTML' });
  const rows = (V.cities || []).filter(c => c.n).slice(0, 14).map(c => `${(c.name[lang] || c.name.ru).padEnd(12).slice(0, 12)} ${String(c.rain).padStart(3)}%  ±${c.t_mae ?? '—'}°`);
  const text = [X.t, '', `☂️ ${X.rain}: <b>${o.rain}%</b>`, ...(o.t_mae != null ? [`🌡 ${X.temp}: <b>±${o.t_mae}°</b> (${o.t2}% ${X.t2})`] : []), `📅 ${V.days.length} ${X.days} · ${o.n}`,
    ...(rows.length ? ['', `<b>${X.city}</b>`, `<pre>${esc(rows.join('\n'))}</pre>`] : []), `<i>${X.how}</i>`].join('\n');
  return tg(env, 'sendMessage', { chat_id: chat, text, parse_mode: 'HTML' });
}
// interactive menus: a menu message turns into the next menu in place (no new message); forecasts, videos and long texts stay
async function say(env, cb, payload) {
  const m = cb && cb.id !== '0' && cb.message;
  if (payload.reply_markup && payload.reply_markup.keyboard) {  // the answer brings the keyboard under the input: the dialog's own buttons go away
    if (m) await tg(env, 'editMessageReplyMarkup', { chat_id: payload.chat_id, message_id: m.message_id, reply_markup: { inline_keyboard: [] } });
    return tg(env, 'sendMessage', payload);
  }
  if (m && typeof m.text === 'string' && m.text.length < 260 && !/<pre>|☂️|🧥/.test(m.text)) {
    const r = await tg(env, 'editMessageText', { ...payload, message_id: m.message_id });
    if (r.ok || /not modified/.test(r.description || '')) return r;
  }
  return tg(env, 'sendMessage', payload);
}
async function kv(env, k) { if (!env.DB) return null; await db(env); const r = await env.DB.prepare('SELECT v FROM meta WHERE k = ?1').bind(k).first(); return r ? r.v : null; }
async function setKv(env, k, v) { await db(env); await env.DB.prepare('INSERT OR REPLACE INTO meta (k, v) VALUES (?1, ?2)').bind(k, v).run(); }
async function getUser(env, id) { if (!env.DB) return null; await db(env); return env.DB.prepare('SELECT * FROM users WHERE chat_id = ?1').bind(id).first(); }
const who = f => (f ? { name: [f.first_name, f.last_name].filter(Boolean).join(' ') || null, username: f.username || null } : {});
async function saveUser(env, id, f) {
  if (!env.DB) return; await db(env);
  await env.DB.prepare('INSERT INTO users (chat_id, lang, mode, name, seen, region, username, place, first) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?5) ON CONFLICT(chat_id) DO UPDATE SET lang = COALESCE(?2, lang), mode = COALESCE(?3, mode), name = COALESCE(?4, name), seen = ?5, region = COALESCE(?6, region), username = COALESCE(?7, username), place = COALESCE(?8, place)')
    .bind(id, f.lang ?? null, f.mode ?? null, f.name ?? null, new Date().toISOString(), f.region ?? null, f.username ?? null, f.place ?? null).run();
  if (id > 0) await env.DB.prepare('INSERT OR IGNORE INTO daily (day, chat_id) VALUES (?1, ?2)').bind(todayTZ(), id).run();  // people only, not groups
}
// the PDF guide: uploaded once from the repository, then re-sent by Telegram's file_id
const GUIDE_V = 3;
async function sendGuide(env, chat, lang) {
  const key = `guide${GUIDE_V}_${lang}`, fid = await kv(env, key);
  if (fid) { const r = await tg(env, 'sendDocument', { chat_id: chat, document: fid, caption: T[lang].guideCap }); if (r.ok) return r; }
  await tg(env, 'sendChatAction', { chat_id: chat, action: 'upload_document' });
  const f = await fetch(`https://raw.githubusercontent.com/otabekvafoev92-del/ob-havo-ecmwf/main/telegram/guide/osmon_guide_${lang}.pdf`);
  if (!f.ok) return tg(env, 'sendMessage', { chat_id: chat, text: HELP[lang], parse_mode: 'HTML' });
  const fd = new FormData();
  fd.append('chat_id', String(chat)); fd.append('caption', T[lang].guideCap);
  fd.append('document', new Blob([await f.arrayBuffer()], { type: 'application/pdf' }), `Osmon_${lang === 'ru' ? 'instrukciya' : lang === 'tr' ? 'kilavuz' : 'yoriqnoma'}.pdf`);
  const r = await (await fetch(`https://api.telegram.org/bot${env.BOT_TOKEN}/sendDocument`, { method: 'POST', body: fd })).json();
  if (r.ok && r.result.document && env.DB) await setKv(env, key, r.result.document.file_id);
  return r;
}


async function sendToday(env, chat, lang, id, group) {
  const M = await manifest(env);
  const days = M && M.items.find(i => i.region === id && i.lang === lang && i.product === 'days');
  const text = days && forecastText(days, lang, NAMES[id][lang], id, { more: group ? 3 : 0 });
  if (!text) return tg(env, 'sendMessage', { chat_id: chat, text: T[lang].none });
  return tg(env, 'sendMessage', { chat_id: chat, text, parse_mode: 'HTML', reply_markup: group ? postKb(env, lang, id) : menuKb(env, lang, id), disable_web_page_preview: true });
}

/* ---------- groups: subscriptions and automatic posts ---------- */
async function db(env) {
  await env.DB.exec('CREATE TABLE IF NOT EXISTS subs (chat_id INTEGER PRIMARY KEY, title TEXT, type TEXT, region TEXT, lang TEXT, last_run TEXT, added TEXT)');
  await env.DB.exec('CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT)');
  await env.DB.exec('CREATE TABLE IF NOT EXISTS users (chat_id INTEGER PRIMARY KEY, lang TEXT, mode TEXT, name TEXT, seen TEXT)');
  try { await env.DB.exec('ALTER TABLE users ADD COLUMN region TEXT'); } catch (e) { /* already there */ }
  try { await env.DB.exec('ALTER TABLE users ADD COLUMN username TEXT'); } catch (e) { /* already there */ }
  for (const c of ['place TEXT', 'first TEXT']) { try { await env.DB.exec(`ALTER TABLE users ADD COLUMN ${c}`); } catch (e) { /* already there */ } }
  await env.DB.exec('CREATE TABLE IF NOT EXISTS msgmap (mid INTEGER PRIMARY KEY, chat INTEGER, lang TEXT)');
  await env.DB.exec('CREATE TABLE IF NOT EXISTS searches (day TEXT, q TEXT, found INTEGER, n INTEGER, PRIMARY KEY (day, q))');
  try { await env.DB.exec('ALTER TABLE subs ADD COLUMN post_hour INTEGER'); } catch (e) { /* already there */ }
  try { await env.DB.exec('ALTER TABLE subs ADD COLUMN alert_run TEXT'); } catch (e) { /* already there */ }
  await env.DB.exec('CREATE TABLE IF NOT EXISTS mtn (chat_id INTEGER PRIMARY KEY, lang TEXT, ver TEXT, added TEXT)');
  // who used the bot on which day (Tashkent date) and a daily snapshot of the auto-send subscriptions: for the admin's 📈 Динамика
  await env.DB.exec('CREATE TABLE IF NOT EXISTS daily (day TEXT, chat_id INTEGER, PRIMARY KEY (day, chat_id))');
  await env.DB.exec('CREATE TABLE IF NOT EXISTS dstat (day TEXT PRIMARY KEY, prv INTEGER, grp INTEGER, mtn INTEGER, users INTEGER)');
  await env.DB.exec('CREATE TABLE IF NOT EXISTS watch (chat_id INTEGER PRIMARY KEY, lat REAL, lon REAL, name TEXT, lang TEXT, on_ INTEGER, asked TEXT, st TEXT, checked TEXT)');
  await env.DB.exec('CREATE TABLE IF NOT EXISTS notif (chat_id INTEGER, sec TEXT, hour INTEGER, lang TEXT, region TEXT, last_day TEXT, added TEXT, PRIMARY KEY (chat_id, sec))');
}
async function sub(env, chat) { if (!env.DB) return null; await db(env); return env.DB.prepare('SELECT * FROM subs WHERE chat_id = ?1').bind(chat).first(); }
async function saveSub(env, chat, regions, lang, lastDay, hour = POST_HOUR) {
  if (!env.DB) return; await db(env);
  await env.DB.prepare('INSERT INTO subs (chat_id, title, type, region, lang, last_run, added, post_hour) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8) ON CONFLICT(chat_id) DO UPDATE SET title = ?2, region = ?4, lang = ?5, last_run = ?6, post_hour = ?8')
    .bind(chat.id, chat.title || chat.first_name || '', chat.type, regions.join(','), lang, lastDay || '', new Date().toISOString(), hour).run();
}
async function memberChange(m, env) {
  const chat = m.chat, st = m.new_chat_member && m.new_chat_member.status;
  if (chat.type === 'private') { if (st === 'kicked' && env.DB) { await db(env); await env.DB.prepare('DELETE FROM subs WHERE chat_id = ?1').bind(chat.id).run(); } return; }
  if (st === 'left' || st === 'kicked') { if (env.DB) { await db(env); for (const t of ['subs', 'notif', 'mtn']) await env.DB.prepare(`DELETE FROM ${t} WHERE chat_id = ?1`).bind(chat.id).run(); } return; }
  if ((st === 'member' || st === 'administrator') && !(await sub(env, chat.id))) {
    await saveSub(env, chat, ['UZ'], 'uz', '');  // default until an admin chooses
    return tg(env, 'sendMessage', { chat_id: chat.id, text: T.uz.gHi + '\n\n' + T.ru.gHi, reply_markup: langKb('GL') });
  }
}
async function isAdmin(env, chat, user, senderChat) {
  if (chat.type === 'channel') return true;
  if (senderChat && senderChat.id === chat.id) return true;  // an anonymous admin writes as the group itself
  if (!user) return false;
  if (user.id === 1087968824) return true;  // @GroupAnonymousBot = anonymous admin  // only admins can press buttons under a channel's own post anyway
  const r = await tg(env, 'getChatMember', { chat_id: chat.id, user_id: user.id });
  if (!r.ok) console.log('getChatMember', chat.id, user.id, r.description);
  return r.ok && ['creator', 'administrator'].includes(r.result.status);
}
// one forecast post: the precipitation video with today, tomorrow and the next days in the caption, and link buttons
async function post(env, M, chat, lang0, id0, bot) {
  const lang = T[lang0] ? lang0 : 'uz', id = NAMES[id0] ? id0 : 'UZ';
  const items = M.items.filter(i => i.region === id && i.lang === lang);
  const days = items.find(i => i.product === 'days');
  let vids = ['prob', 'temp', 'cloud', 'wind'].map(p => items.find(i => (i.product || 'prob') === p)).filter(Boolean);
  if (!vids.length) vids = ['prob', 'temp', 'cloud', 'wind'].map(p => M.items.find(i => i.region === id && i.lang === 'ru' && (i.product || 'prob') === p)).filter(Boolean);
  const updated = M.run.slice(8, 10) + '.' + M.run.slice(5, 7) + ' ' + M.run.slice(11, 16) + ' UTC';
  const cap = forecastText(days, lang, NAMES[id][lang], id, { more: 3, foot: T[lang].swipe, limit: 1024 });
  if (!cap) return { ok: false, description: 'no data' };
  if (!vids.length) return tg(env, 'sendMessage', { chat_id: chat, text: cap, parse_mode: 'HTML', reply_markup: postKb(env, lang, id, bot, chat), disable_web_page_preview: true });
  const media = vids.map(v => ({ type: 'video', media: `${base(env)}/prob/${v.video}?v=${fresh()}`, supports_streaming: true }));
  media[0].caption = cap; media[0].parse_mode = 'HTML';
  let r = await tg(env, 'sendMediaGroup', { chat_id: chat, media });
  // Telegram could not take the videos by link (too big, the site slow): try the two lightest ones, then the text alone.
  // (Uploading the files from here broke the whole daily sending: "Network connection lost" on ~50 MB of video.)
  const gone = x => /kicked|blocked|deactivated|not a member|chat not found|have no rights|was deleted/i.test(x.description || '');
  if (!r.ok && !gone(r)) { console.log('album', chat, id, r.description); const m2 = media.slice(-2); m2[0] = { ...m2[0], caption: cap, parse_mode: 'HTML' }; r = await tg(env, 'sendMediaGroup', { chat_id: chat, media: m2 }); }
  if (!r.ok && !gone(r)) r = await tg(env, 'sendMessage', { chat_id: chat, text: cap, parse_mode: 'HTML', reply_markup: postKb(env, lang, id, bot, chat), disable_web_page_preview: true });
  if (!r.ok) return r;
  // weather by city for today, with the buttons the album cannot carry
  const lines = await cityLines(env, id, lang);
  if (lines) await tg(env, 'sendMessage', { chat_id: chat, text: `${T[lang].cTitle} · ${FLAG[id]} <b>${esc(NAMES[id][lang])}</b>\n\n${lines}`.slice(0, 4000), parse_mode: 'HTML', reply_markup: postKb(env, lang, id, bot, chat), disable_web_page_preview: true });
  return r;
}

// is the data on the site fresh? (site/build.json: when the last build finished). Normally a new build every ~3 hours;
// over 5 hours means an update was skipped or late (the watchdog in staleTick is already restarting it)
const FRESH_H = 5, HOLD_MAX_H = 3;  // wait for fresh data at most 3 hours past the person's hour, then send what there is
async function siteFresh(env) {
  const B = await fetch(`${base(env)}/build.json?t=${Date.now()}`).then(r => r.ok ? r.json() : null).catch(() => null);
  if (!B || !B.built) return { fresh: true, age: 0 };  // no stamp yet: do not hold anything
  const age = (Date.now() - Date.parse(B.built)) / 3600e3;
  return { fresh: age < FRESH_H, age, built: B.built };
}
// one invitation for the people who use the bot without the daily forecast: today's forecast for their country and a
// button to get it every morning. Each person gets it once at most (table invited), in small batches per call
const INV = { ru: { head: '☀️ Свежий прогноз от Osmon', btn: '🔔 Получать прогноз каждое утро', tip: 'Хотите получать такой прогноз каждый день в удобное время? Нажмите кнопку ниже.' },
              uz: { head: '☀️ Osmon’dan yangi prognoz', btn: '🔔 Har kuni ertalab prognoz olish', tip: 'Bunday prognozni har kuni qulay vaqtda olishni xohlaysizmi? Quyidagi tugmani bosing.' },
              tr: { head: '☀️ Osmon’dan taze tahmin', btn: '🔔 Her sabah tahmin al', tip: 'Bu tahmini her gün istediğiniz saatte almak ister misiniz? Aşağıdaki düğmeye dokunun.' } };
async function invite(env, n) {
  if (!env.DB) return { ok: false }; await db(env);
  await env.DB.exec('CREATE TABLE IF NOT EXISTS invited (chat_id INTEGER PRIMARY KEY, at TEXT, ok INTEGER)');
  const rows = (await env.DB.prepare('SELECT u.chat_id, u.lang, u.region FROM users u WHERE u.chat_id > 0 AND u.chat_id NOT IN (SELECT chat_id FROM subs) AND u.chat_id NOT IN (SELECT chat_id FROM invited) LIMIT ?1').bind(Math.min(20, n)).all()).results;
  if (!rows.length) return { ok: true, sent: 0, left: 0 };
  const M = await manifest(env, true); if (!M) return { ok: false, error: 'no manifest' };
  let sent = 0, failed = 0;
  for (const u of rows) {
    const lang = INV[u.lang] ? u.lang : 'uz', id = NAMES[u.region] ? u.region : 'UZ', X = INV[lang];
    await env.DB.prepare('INSERT OR REPLACE INTO invited (chat_id, at, ok) VALUES (?1, ?2, 0)').bind(u.chat_id, new Date().toISOString()).run();  // first: never twice
    const days = M.items.find(i => i.region === id && i.lang === lang && i.product === 'days') || M.items.find(i => i.region === id && i.lang === 'ru' && i.product === 'days');
    const txt = forecastText(days, lang, NAMES[id][lang], id, { more: 3 });
    if (!txt) { failed++; continue; }
    const r = await tg(env, 'sendMessage', { chat_id: u.chat_id, text: `<b>${X.head}</b>\n\n${txt}\n\n${X.tip}`.slice(0, 4000), parse_mode: 'HTML', disable_web_page_preview: true,
      reply_markup: { inline_keyboard: [[{ text: X.btn, callback_data: `B:${lang}:${id}`, style: 'success' }]] } });
    if (r.ok) { sent++; await env.DB.prepare('UPDATE invited SET ok = 1 WHERE chat_id = ?1').bind(u.chat_id).run(); } else failed++;
  }
  const left = ((await env.DB.prepare('SELECT COUNT(*) AS n FROM users WHERE chat_id > 0 AND chat_id NOT IN (SELECT chat_id FROM subs) AND chat_id NOT IN (SELECT chat_id FROM invited)').first()) || {}).n || 0;
  return { ok: true, sent, failed, left };
}
async function broadcast(env) {
  if (!env.DB) return { ok: false, error: 'no DB' };
  await db(env);
  const hour = new Date(Date.now() + TZ * 3600e3).getUTCHours(), day = todayTZ();
  let due = (await env.DB.prepare("SELECT * FROM subs WHERE COALESCE(last_run, '') <> ?1 AND COALESCE(post_hour, ?3) <= ?2 ORDER BY COALESCE(post_hour, ?3) LIMIT ?4").bind(day, hour, POST_HOUR, PER_TICK * 3).all()).results;
  if (!due.length) return { ok: true, day, hour, due: 0 };
  // late data: the daily posts wait (not marked as sent) and go out at the first run after the fresh data arrives —
  // unless the wait is already 3 hours past the chosen hour; then the forecast we have is better than none
  const F = await siteFresh(env);
  if (!F.fresh) {
    const waiting = due.filter(s => hour - (s.post_hour ?? POST_HOUR) < HOLD_MAX_H);
    due = due.filter(s => hour - (s.post_hour ?? POST_HOUR) >= HOLD_MAX_H);
    if (waiting.length && (await kv(env, 'hold_day')) !== day) {
      await setKv(env, 'hold_day', day); const a = await kv(env, 'admin');
      if (a) await tg(env, 'sendMessage', { chat_id: a, text: `⏳ Утренняя рассылка ждёт свежих данных: на сайте данные ${Math.round(F.age)} ч назад. Как только сборка закончится, рассылка уйдёт сразу (самое позднее — через ${HOLD_MAX_H} ч после времени подписчика, с тем, что есть).` });
    }
    if (!due.length) return { ok: true, day, hour, due: 0, held: waiting.length };
  }
  due = due.slice(0, PER_TICK);
  const M = await manifest(env, true);
  if (!M) return { ok: false, error: 'no manifest' };
  const me = await tg(env, 'getMe', {}), bot = me.ok ? me.result.username : '';
  let sent = 0;
  for (const s of due) {
    let gone = false;
    for (const r of (regionsOf(s).length ? regionsOf(s) : ['UZ'])) {
      const res = await post(env, M, s.chat_id, s.lang, r, s.type === 'private' ? '' : bot).catch(e => { console.log('post', s.chat_id, r, e && e.stack); return { ok: false, description: String(e) }; });  // one bad chat never stops the rest
      if (res.ok) sent++;
      // the bot was removed or cannot write there: forget the chat
      if (!res.ok && [400, 403].includes(res.error_code) && /kicked|blocked|deactivated|not a member|chat not found|have no rights|was deleted/i.test(res.description || '')) { gone = true; break; }
    }
    if (gone) await env.DB.prepare('DELETE FROM subs WHERE chat_id = ?1').bind(s.chat_id).run();
    else await env.DB.prepare('UPDATE subs SET last_run = ?2 WHERE chat_id = ?1').bind(s.chat_id, day).run();
  }
  return { ok: true, day, run: M.run, due: due.length, sent };
}

/* ---------- visit counter for the website (by country and city) ----------
   The site sends one POST /hit per visitor per day; Cloudflare already knows the visitor's country and city
   (request.cf), so nothing is stored about the person: only daily totals per city. GET /stats returns the totals. */
const CORS = { 'access-control-allow-origin': '*', 'access-control-allow-methods': 'GET,POST,OPTIONS', 'access-control-allow-headers': 'content-type' };
async function visits(req, env, url) {
  if (req.method === 'OPTIONS') return new Response(null, { headers: CORS });
  const json = (o, extra = {}) => new Response(JSON.stringify(o), { headers: { 'content-type': 'application/json; charset=utf-8', ...CORS, ...extra } });
  if (!env.DB) return json({ ok: false, error: 'no database (bind a D1 database as DB)' });
  await env.DB.exec('CREATE TABLE IF NOT EXISTS hits (day TEXT, country TEXT, city TEXT, n INTEGER, PRIMARY KEY (day, country, city))');
  if (url.pathname === '/hit' && req.method === 'POST') {
    const cf = req.cf || {}, day = new Date().toISOString().slice(0, 10);
    const country = String(cf.country || '??').slice(0, 2), city = String(cf.city || '').slice(0, 60);
    await env.DB.prepare('INSERT INTO hits (day, country, city, n) VALUES (?1, ?2, ?3, 1) ON CONFLICT(day, country, city) DO UPDATE SET n = n + 1').bind(day, country, city).run();
    return json({ ok: true });
  }
  const day = new Date().toISOString().slice(0, 10);
  const one = async (q, ...a) => (await env.DB.prepare(q).bind(...a).all()).results;
  const [tot] = await one('SELECT COALESCE(SUM(n),0) AS n FROM hits');
  const [today] = await one('SELECT COALESCE(SUM(n),0) AS n FROM hits WHERE day = ?1', day);
  const countries = await one('SELECT country, SUM(n) AS n FROM hits GROUP BY country ORDER BY n DESC LIMIT 12');
  const cities = await one("SELECT country, city, SUM(n) AS n FROM hits WHERE city <> '' GROUP BY country, city ORDER BY n DESC LIMIT 12");
  return json({ ok: true, total: tot.n, today: today.n, countries, cities }, { 'cache-control': 'public, max-age=300' });
}
