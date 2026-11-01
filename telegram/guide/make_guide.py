import json, sys, html
BOT='@ObHavo_ECMWF_bot'; SITE='otabekvafoev92-del.github.io/ob-havo-ecmwf'
B=lambda *xs: '<div class="kb">'+''.join('<div class="row">'+''.join(f'<span class="b">{x}</span>' for x in r)+'</div>' for r in xs)+'</div>'
L={}
L['ru']=dict(title='Инструкция', sub='Прогноз погоды на 15 дней в Телеграме', lead='Osmon — бот и сайт с прогнозом погоды на 15 дней. Прогноз собирается из 6 моделей (ECMWF IFS и AIFS, NOAA GFS и GEFS, DWD ICON) и показывает вероятность осадков, температуру и облачность для стран СНГ, Турции и всего мира.',
toc='Содержание',
s=[
('1. Первый запуск', f'''<ol><li>Откройте бота <b>{BOT}</b> и нажмите <b>Запустить</b> (или отправьте /start).</li>
<li>Выберите язык: O‘zbekcha, Русский или Türkçe.</li>{B(['🇺🇿 O‘zbekcha','🇷🇺 Русский','🇹🇷 Türkçe'])}
<li>Бот пришлёт короткую инструкцию и кнопку <b>📄 Инструкция (PDF)</b> — этот файл.</li>
<li>Выберите страну или континент.</li>{B(['🇺🇿 Узбекистан','🇰🇿 Казахстан','🇰🇬 Кыргызстан'],['🇹🇯 Таджикистан','🇹🇲 Туркменистан','🇦🇿 Азербайджан'],['…','🌍 Весь мир','…'])}</ol>'''),
('2. Меню страны', f'''<p>После выбора страны появляется меню:</p>{B(['📅 Сегодня и завтра','🗓 По дням'],['🏙 Города','🎬 Видео на 15 дней'],['📊 Отчёт','🌍 Глобус'],['ℹ️ Помощь','✉️ Написать админу'],['↩️ Страны'])}
<table><tr><td>📅 Сегодня и завтра</td><td>Короткий прогноз по главному городу страны: температура, вероятность осадков, облачность.</td></tr>
<tr><td>🗓 По дням</td><td>Все 15 дней списком, по одной строке на день.</td></tr>
<tr><td>🏙 Города</td><td>Список городов страны. Нажмите на город — придёт прогноз именно для него.</td></tr>
<tr><td>🎬 Видео на 15 дней</td><td>Три видео одним альбомом: 🌧 осадки, 🌡 температура, ☁️ облака. Листайте их пальцем.</td></tr>
<tr><td>📊 Отчёт, 🌍 Глобус</td><td>Сайт Osmon открывается прямо внутри Телеграма.</td></tr>
<tr><td>ℹ️ Помощь</td><td>Краткая инструкция и этот PDF.</td></tr>
<tr><td>✉️ Написать админу</td><td>Вопрос, ошибка или предложение администратору бота.</td></tr></table>'''),
('3. Погода по городам и видео города', '''<p>Кнопка <b>🏙 Города</b> показывает до 15 городов выбранной страны — сначала столица, затем крупные города.</p>
<ul><li><b>Узбекистан и Казахстан:</b> по каждому городу приходит <b>видео</b> на 15 дней с бегущей шкалой времени и подписью: сегодня, завтра и ближайшие дни.</li>
<li><b>Другие страны:</b> приходит текстовый прогноз по городу с комментарием на каждый день.</li></ul>
<div class="note">Пример строки: <i>🌦 Ташкент: +9°…+15°, возможен дождь (45 %)</i>. Процент — вероятность осадков: чем он выше, тем больше моделей согласны, что пойдёт дождь или снег.</div>'''),
('4. Бот в группе или канале', f'''<p>Бот может каждый день сам присылать прогноз в вашу группу или канал.</p>
<ol><li>Добавьте <b>{BOT}</b> в группу. В канал — администратором с правом публиковать сообщения.</li>
<li><b>Администратор группы</b> пишет <b>/settings</b> (или /sozla).</li>
<li>Выбирает язык, затем отмечает страны — можно несколько, например Узбекистан и Казахстан — и нажимает <b>✅ Готово</b>.</li>{B(['✅ Узбекистан','✅ Казахстан','🇰🇬 Кыргызстан'],['✅ Готово'])}
<li>Выбирает время отправки (по Ташкенту): 06:00 … 21:00. По умолчанию — 07:00.</li>{B(['06:00','✅ 07:00','08:00','09:00','10:00'])}</ol>
<p>Сразу после настройки бот пришлёт первый прогноз. Затем каждый день в выбранное время по каждой стране приходит пост: три видео (осадки, температура, облака) с прогнозом на сегодня, завтра и ближайшие дни, и сообщение «🏙 Сегодня по городам» с кнопками на сайт.</p>
<div class="note"><b>Почему «только администратор»?</b> Настройки группы (язык, страны, время) может менять только администратор этой группы — чтобы обычные участники случайно их не сбили. Если вы видите сообщение «Настройки меняет только администратор этой группы», попросите администратора написать /settings. Прогноз сейчас может запросить любой участник командой <b>/bugun</b>.</div>'''),
('5. Сайт и глобус', f'''<p>Сайт: <b>{SITE}</b>. Он же открывается кнопками 📊 Отчёт и 🌍 Глобус.</p>
<ul><li><b>Глобус</b> — 3D-Земля. Слой «Вероятность · 15 дней» показывает осадки (высота и цвет), температуру или облачность. Внизу — шкала времени: ▶ запускает анимацию, ползунок выбирает день и час.</li>
<li><b>Панель с цветовой шкалой</b> на телефоне свёрнута в одну строку. Нажмите на заголовок, чтобы раскрыть или свернуть её; при касании глобуса она сворачивается сама.</li>
<li><b>Обзор прогноза</b> — прогноз по выбранному месту. <b>Вероятность осадков</b> — отчёт с видео по странам.</li></ul>'''),
('6. Когда обновляются данные', '''<p>Всё обновляется автоматически, 2 раза в сутки — по свежим расчётам моделей 00 и 12 UTC:</p>
<table><tr><td>≈ 05:00</td><td>утреннее обновление (по Ташкенту)</td></tr><tr><td>≈ 17:00</td><td>вечернее обновление</td></tr></table>
<p>Бот всегда берёт последние данные с сайта. Если идёт обновление, бот может ответить «⏳ Данные ещё не готовы» — повторите через несколько минут.</p>'''),
('7. Связь с администратором', '''<ol><li>Нажмите <b>✉️ Написать админу</b> в меню или отправьте <b>/admin</b>.</li>
<li>Напишите сообщение: текст, фото или голосовое.</li><li>Бот передаст его администратору, а ответ придёт в этот же чат.</li></ol><p>Передумали — отправьте /cancel.</p>'''),
('8. Команды', '''<table><tr><td>/start</td><td>язык, инструкция, выбор страны</td></tr><tr><td>/today, /bugun</td><td>Узбекистан: сегодня и завтра</td></tr><tr><td>/prognoz</td><td>выбор страны</td></tr><tr><td>/help</td><td>краткая инструкция</td></tr><tr><td>/guide</td><td>этот PDF</td></tr><tr><td>/admin</td><td>написать администратору</td></tr><tr><td>/settings, /sozla</td><td>в группе: язык, страны, время (для администраторов группы)</td></tr></table>'''),
('9. Частые вопросы', '''<dl><dt>Видео не пришло</dt><dd>Видео большие и иногда отправляются дольше. Подождите минуту и нажмите кнопку ещё раз.</dd>
<dt>«⏳ Данные ещё не готовы»</dt><dd>Идёт обновление. Попробуйте через 5–10 минут.</dd>
<dt>Бот не пишет в группу</dt><dd>Проверьте, что бот остался в группе (в канале — администратор), и что администратор прошёл /settings до конца, включая выбор времени.</dd>
<dt>Насколько точен прогноз?</dt><dd>На 1–3 дня — высокая точность, к 10–15 дням прогноз показывает тенденцию. Смотрите на процент: это доля моделей и их вариантов, где выпадают осадки.</dd></dl>'''),
])
L['uz']=dict(title='Yo‘riqnoma', sub='Telegramda 15 kunlik ob-havo prognozi', lead='Osmon — 15 kunlik ob-havo prognozi beradigan bot va sayt. Prognoz 6 ta modeldan (ECMWF IFS va AIFS, NOAA GFS va GEFS, DWD ICON) yig‘iladi va MDH davlatlari, Turkiya hamda butun dunyo uchun yog‘in ehtimoli, harorat va bulutlilikni ko‘rsatadi.',
toc='Mundarija',
s=[
('1. Birinchi ishga tushirish', f'''<ol><li><b>{BOT}</b> botini oching va <b>Boshlash</b> tugmasini bosing (yoki /start yuboring).</li>
<li>Tilni tanlang: O‘zbekcha, Русский yoki Türkçe.</li>{B(['🇺🇿 O‘zbekcha','🇷🇺 Русский','🇹🇷 Türkçe'])}
<li>Bot qisqa yo‘riqnoma va <b>📄 Yo‘riqnoma (PDF)</b> tugmasini yuboradi — bu shu fayl.</li>
<li>Davlat yoki qit’ani tanlang.</li>{B(['🇺🇿 O‘zbekiston','🇰🇿 Qozog‘iston','🇰🇬 Qirg‘iziston'],['🇹🇯 Tojikiston','🇹🇲 Turkmaniston','🇦🇿 Ozarbayjon'],['…','🌍 Butun dunyo','…'])}</ol>'''),
('2. Davlat menyusi', f'''<p>Davlat tanlangach, menyu chiqadi:</p>{B(['📅 Bugun va ertaga','🗓 Kunlar bo‘yicha'],['🏙 Shaharlar','🎬 15 kunlik video'],['📊 Hisobot','🌍 Globus'],['ℹ️ Yordam','✉️ Adminga yozish'],['↩️ Davlatlar'])}
<table><tr><td>📅 Bugun va ertaga</td><td>Asosiy shahar bo‘yicha qisqa prognoz: harorat, yog‘in ehtimoli, bulutlilik.</td></tr>
<tr><td>🗓 Kunlar bo‘yicha</td><td>15 kunning hammasi, har kunga bir qator.</td></tr>
<tr><td>🏙 Shaharlar</td><td>Davlat shaharlari ro‘yxati. Shaharni bosing — aynan shu shahar uchun prognoz keladi.</td></tr>
<tr><td>🎬 15 kunlik video</td><td>Bitta albomda 3 ta video: 🌧 yog‘in, 🌡 harorat, ☁️ bulutlar. Barmoq bilan suring.</td></tr>
<tr><td>📊 Hisobot, 🌍 Globus</td><td>Osmon sayti to‘g‘ridan-to‘g‘ri Telegram ichida ochiladi.</td></tr>
<tr><td>ℹ️ Yordam</td><td>Qisqa yo‘riqnoma va shu PDF.</td></tr>
<tr><td>✉️ Adminga yozish</td><td>Bot adminiga savol, xato yoki taklif.</td></tr></table>'''),
('3. Shaharlar bo‘yicha ob-havo va shahar videosi', '''<p><b>🏙 Shaharlar</b> tugmasi tanlangan davlatning 15 tagacha shahrini ko‘rsatadi — avval poytaxt, keyin yirik shaharlar.</p>
<ul><li><b>O‘zbekiston va Qozog‘iston:</b> har bir shahar uchun 15 kunlik <b>video</b> keladi — vaqt shkalasi va izoh bilan: bugun, ertaga va keyingi kunlar.</li>
<li><b>Boshqa davlatlar:</b> shahar bo‘yicha har kunga izohli matnli prognoz keladi.</li></ul>
<div class="note">Misol: <i>🌦 Toshkent: +9°…+15°, yomg‘ir ehtimoli bor (45 %)</i>. Foiz — yog‘in ehtimoli: qancha yuqori bo‘lsa, shuncha ko‘p model yomg‘ir yoki qor yog‘ishiga rozi.</div>'''),
('4. Bot guruh yoki kanalda', f'''<p>Bot har kuni guruhingiz yoki kanalingizga prognozni o‘zi yuboradi.</p>
<ol><li><b>{BOT}</b> ni guruhga qo‘shing. Kanalga — xabar yuborish huquqi bilan admin qilib.</li>
<li><b>Guruh admini</b> <b>/sozla</b> (yoki /settings) yozadi.</li>
<li>Tilni tanlaydi, so‘ng davlatlarni belgilaydi — bir nechtasini ham, masalan O‘zbekiston va Qozog‘iston — va <b>✅ Tayyor</b> tugmasini bosadi.</li>{B(['✅ O‘zbekiston','✅ Qozog‘iston','🇰🇬 Qirg‘iziston'],['✅ Tayyor'])}
<li>Yuborish vaqtini tanlaydi (Toshkent vaqti): 06:00 … 21:00. Odatiy — 07:00.</li>{B(['06:00','✅ 07:00','08:00','09:00','10:00'])}</ol>
<p>Sozlangandan so‘ng bot darhol birinchi prognozni yuboradi. Keyin har kuni tanlangan vaqtda har bir davlat uchun post keladi: 3 ta video (yog‘in, harorat, bulutlar) bugun, ertaga va keyingi kunlar prognozi bilan, hamda saytga tugmalari bor «🏙 Bugun shaharlarda» xabari.</p>
<div class="note"><b>Nega «faqat admin»?</b> Guruh sozlamalarini (til, davlatlar, vaqt) faqat shu guruhning admini o‘zgartira oladi — oddiy a’zolar tasodifan buzib qo‘ymasligi uchun. «Guruh sozlamalarini faqat shu guruhning admini o‘zgartira oladi» degan xabarni ko‘rsangiz, admindan /sozla yozishini so‘rang. Hozirgi prognozni istalgan a’zo <b>/bugun</b> buyrug‘i bilan so‘rashi mumkin.</div>'''),
('5. Sayt va globus', f'''<p>Sayt: <b>{SITE}</b>. U 📊 Hisobot va 🌍 Globus tugmalari orqali ham ochiladi.</p>
<ul><li><b>Globus</b> — 3D Yer. «15 kunlik ehtimol» qatlami yog‘in (balandlik va rang), harorat yoki bulutlilikni ko‘rsatadi. Pastda vaqt shkalasi: ▶ animatsiyani boshlaydi, surgich kun va soatni tanlaydi.</li>
<li><b>Rang shkalasi paneli</b> telefonda bir qatorga yig‘ilgan. Ochish yoki yig‘ish uchun sarlavhasini bosing; globusga tegsangiz, o‘zi yig‘iladi.</li>
<li><b>Prognoz sharhi</b> — tanlangan joy uchun prognoz. <b>Yog‘in ehtimoli</b> — davlatlar bo‘yicha videoli hisobot.</li></ul>'''),
('6. Ma’lumotlar qachon yangilanadi', '''<p>Hammasi avtomatik, sutkada 2 marta — modellarning 00 va 12 UTC hisoblari asosida yangilanadi:</p>
<table><tr><td>≈ 05:00</td><td>ertalabki yangilanish (Toshkent vaqti)</td></tr><tr><td>≈ 17:00</td><td>kechki yangilanish</td></tr></table>
<p>Bot har doim saytdagi eng so‘nggi ma’lumotni oladi. Yangilanish ketayotganda bot «⏳ Ma’lumot hali tayyor emas» deb javob berishi mumkin — bir necha daqiqadan so‘ng qayta urinib ko‘ring.</p>'''),
('7. Admin bilan bog‘lanish', '''<ol><li>Menyuda <b>✉️ Adminga yozish</b> tugmasini bosing yoki <b>/admin</b> yuboring.</li>
<li>Xabaringizni yozing: matn, rasm yoki ovozli xabar.</li><li>Bot uni adminga yetkazadi, javob shu chatga keladi.</li></ol><p>Fikringizni o‘zgartirsangiz — /cancel yuboring.</p>'''),
('8. Buyruqlar', '''<table><tr><td>/start</td><td>til, yo‘riqnoma, davlat tanlash</td></tr><tr><td>/bugun, /today</td><td>O‘zbekiston: bugun va ertaga</td></tr><tr><td>/prognoz</td><td>davlat tanlash</td></tr><tr><td>/help</td><td>qisqa yo‘riqnoma</td></tr><tr><td>/guide</td><td>shu PDF</td></tr><tr><td>/admin</td><td>adminga yozish</td></tr><tr><td>/sozla, /settings</td><td>guruhda: til, davlatlar, vaqt (guruh adminlari uchun)</td></tr></table>'''),
('9. Ko‘p beriladigan savollar', '''<dl><dt>Video kelmadi</dt><dd>Videolar katta, ba’zan sekinroq yuboriladi. Bir daqiqa kuting va tugmani yana bosing.</dd>
<dt>«⏳ Ma’lumot hali tayyor emas»</dt><dd>Yangilanish ketmoqda. 5–10 daqiqadan so‘ng urinib ko‘ring.</dd>
<dt>Bot guruhga yozmayapti</dt><dd>Bot guruhda qolganini (kanalda — admin ekanini) va admin /sozla ni oxirigacha, vaqt tanlashgacha bajarganini tekshiring.</dd>
<dt>Prognoz qanchalik aniq?</dt><dd>1–3 kunga — yuqori aniqlik, 10–15 kunga prognoz tendensiyani ko‘rsatadi. Foizga qarang: bu yog‘in yog‘adigan modellar va ularning variantlari ulushi.</dd></dl>'''),
])
L['tr']=dict(title='Kılavuz', sub='Telegram’da 15 günlük hava tahmini', lead='Osmon, 15 günlük hava tahmini veren bir bot ve sitedir. Tahmin 6 modelden (ECMWF IFS ve AIFS, NOAA GFS ve GEFS, DWD ICON) derlenir; BDT ülkeleri, Türkiye ve tüm dünya için yağış olasılığını, sıcaklığı ve bulutluluğu gösterir.',
toc='İçindekiler',
s=[
('1. İlk başlatma', f'''<ol><li><b>{BOT}</b> botunu açın ve <b>Başlat</b>’a basın (veya /start gönderin).</li>
<li>Dil seçin: O‘zbekcha, Русский veya Türkçe.</li>{B(['🇺🇿 O‘zbekcha','🇷🇺 Русский','🇹🇷 Türkçe'])}
<li>Bot kısa bir kılavuz ve <b>📄 Kılavuz (PDF)</b> düğmesini gönderir — bu dosya.</li>
<li>Bir ülke veya kıta seçin.</li>{B(['🇺🇿 Özbekistan','🇰🇿 Kazakistan','🇰🇬 Kırgızistan'],['🇹🇯 Tacikistan','🇹🇲 Türkmenistan','🇦🇿 Azerbaycan'],['…','🌍 Tüm dünya','…'])}</ol>'''),
('2. Ülke menüsü', f'''<p>Ülke seçildikten sonra menü açılır:</p>{B(['📅 Bugün ve yarın','🗓 Günlere göre'],['🏙 Şehirler','🎬 15 günlük video'],['📊 Rapor','🌍 Küre'],['ℹ️ Yardım','✉️ Yöneticiye yaz'],['↩️ Ülkeler'])}
<table><tr><td>📅 Bugün ve yarın</td><td>Ana şehir için kısa tahmin: sıcaklık, yağış olasılığı, bulutluluk.</td></tr>
<tr><td>🗓 Günlere göre</td><td>15 günün tamamı, her gün için bir satır.</td></tr>
<tr><td>🏙 Şehirler</td><td>Ülkenin şehir listesi. Bir şehre basın — o şehrin tahmini gelir.</td></tr>
<tr><td>🎬 15 günlük video</td><td>Tek albümde 3 video: 🌧 yağış, 🌡 sıcaklık, ☁️ bulutlar. Parmağınızla kaydırın.</td></tr>
<tr><td>📊 Rapor, 🌍 Küre</td><td>Osmon sitesi doğrudan Telegram içinde açılır.</td></tr>
<tr><td>ℹ️ Yardım</td><td>Kısa kılavuz ve bu PDF.</td></tr>
<tr><td>✉️ Yöneticiye yaz</td><td>Bot yöneticisine soru, hata veya öneri.</td></tr></table>'''),
('3. Şehirlere göre hava ve şehir videosu', '''<p><b>🏙 Şehirler</b> düğmesi seçilen ülkenin en fazla 15 şehrini gösterir — önce başkent, sonra büyük şehirler.</p>
<ul><li><b>Özbekistan ve Kazakistan:</b> her şehir için zaman çizelgeli ve açıklamalı 15 günlük bir <b>video</b> gelir: bugün, yarın ve sonraki günler.</li>
<li><b>Diğer ülkeler:</b> şehir için her güne yorumlu metin tahmini gelir.</li></ul>
<div class="note">Örnek: <i>🌦 Taşkent: +9°…+15°, yağmur olası (45 %)</i>. Yüzde, yağış olasılığıdır: ne kadar yüksekse, yağmur veya kar konusunda o kadar çok model hemfikirdir.</div>'''),
('4. Bot grupta veya kanalda', f'''<p>Bot her gün grubunuza veya kanalınıza tahmini kendisi gönderir.</p>
<ol><li><b>{BOT}</b>’u gruba ekleyin. Kanala — mesaj gönderme izniyle yönetici olarak.</li>
<li><b>Grup yöneticisi</b> <b>/settings</b> (veya /sozla) yazar.</li>
<li>Dili seçer, ardından ülkeleri işaretler — birden fazla olabilir, örneğin Özbekistan ve Kazakistan — ve <b>✅ Tamam</b>’a basar.</li>{B(['✅ Özbekistan','✅ Kazakistan','🇰🇬 Kırgızistan'],['✅ Tamam'])}
<li>Gönderme saatini seçer (Taşkent saati): 06:00 … 21:00. Varsayılan 07:00.</li>{B(['06:00','✅ 07:00','08:00','09:00','10:00'])}</ol>
<p>Ayardan hemen sonra bot ilk tahmini gönderir. Ardından her gün seçilen saatte her ülke için bir gönderi gelir: bugün, yarın ve sonraki günlerin tahminiyle 3 video (yağış, sıcaklık, bulutlar) ve siteye düğmeli «🏙 Bugün şehirlerde» mesajı.</p>
<div class="note"><b>Neden «yalnızca yönetici»?</b> Grup ayarlarını (dil, ülkeler, saat) yalnızca bu grubun yöneticisi değiştirebilir — sıradan üyeler yanlışlıkla bozmasın diye. «Ayarları yalnızca bu grubun yöneticisi değiştirebilir» mesajını görürseniz, yöneticiden /settings yazmasını isteyin. Güncel tahmini her üye <b>/bugun</b> komutuyla isteyebilir.</div>'''),
('5. Site ve küre', f'''<p>Site: <b>{SITE}</b>. 📊 Rapor ve 🌍 Küre düğmeleriyle de açılır.</p>
<ul><li><b>Küre</b> — 3D Dünya. «Olasılık · 15 gün» katmanı yağışı (yükseklik ve renk), sıcaklığı veya bulutluluğu gösterir. Altta zaman çizelgesi: ▶ animasyonu başlatır, kaydırıcı gün ve saati seçer.</li>
<li><b>Renk ölçeği paneli</b> telefonda tek satıra katlanır. Açmak veya kapatmak için başlığına basın; küreye dokununca kendiliğinden katlanır.</li>
<li><b>Tahmin özeti</b> — seçilen yer için tahmin. <b>Yağış olasılığı</b> — ülkelere göre videolu rapor.</li></ul>'''),
('6. Veriler ne zaman güncellenir', '''<p>Her şey otomatik olarak, günde 2 kez — modellerin 00 ve 12 UTC çalıştırmalarına göre güncellenir:</p>
<table><tr><td>≈ 05:00</td><td>sabah güncellemesi (Taşkent saati)</td></tr><tr><td>≈ 17:00</td><td>akşam güncellemesi</td></tr></table>
<p>Bot her zaman sitedeki en son verileri kullanır. Güncelleme sırasında bot «⏳ Veriler henüz hazır değil» diyebilir — birkaç dakika sonra tekrar deneyin.</p>'''),
('7. Yöneticiyle iletişim', '''<ol><li>Menüde <b>✉️ Yöneticiye yaz</b>’a basın veya <b>/admin</b> gönderin.</li>
<li>Mesajınızı yazın: metin, fotoğraf veya sesli mesaj.</li><li>Bot onu yöneticiye iletir, cevap bu sohbete gelir.</li></ol><p>Vazgeçerseniz /cancel gönderin.</p>'''),
('8. Komutlar', '''<table><tr><td>/start</td><td>dil, kılavuz, ülke seçimi</td></tr><tr><td>/today, /bugun</td><td>Özbekistan: bugün ve yarın</td></tr><tr><td>/prognoz</td><td>ülke seçimi</td></tr><tr><td>/help</td><td>kısa kılavuz</td></tr><tr><td>/guide</td><td>bu PDF</td></tr><tr><td>/admin</td><td>yöneticiye yaz</td></tr><tr><td>/settings, /sozla</td><td>grupta: dil, ülkeler, saat (grup yöneticileri için)</td></tr></table>'''),
('9. Sık sorulan sorular', '''<dl><dt>Video gelmedi</dt><dd>Videolar büyüktür ve bazen daha geç gönderilir. Bir dakika bekleyip düğmeye tekrar basın.</dd>
<dt>«⏳ Veriler henüz hazır değil»</dt><dd>Güncelleme sürüyor. 5–10 dakika sonra deneyin.</dd>
<dt>Bot gruba yazmıyor</dt><dd>Botun grupta kaldığını (kanalda yönetici olduğunu) ve yöneticinin /settings adımlarını saat seçimine kadar tamamladığını kontrol edin.</dd>
<dt>Tahmin ne kadar doğru?</dt><dd>1–3 gün için yüksek doğruluk; 10–15 güne doğru tahmin eğilimi gösterir. Yüzdeye bakın: yağış gösteren model ve varyantlarının payıdır.</dd></dl>'''),
])
CSS='''@page{size:A4;margin:16mm 15mm 16mm}*{box-sizing:border-box}body{font:10.5pt/1.5 Inter,'Noto Color Emoji',sans-serif;color:#1a2230;margin:0}
.cover{background:linear-gradient(135deg,#0b1730,#163a6b 60%,#c8611f);color:#fff;border-radius:14px;padding:26px 26px 22px;margin-bottom:18px}
.logo{font-weight:800;font-size:26pt;letter-spacing:-.5px}.logo i{color:#f39a4a;font-style:normal}.cover h1{margin:6px 0 2px;font-size:17pt;font-weight:600}.cover .sub{opacity:.85}
.cover .meta{margin-top:14px;display:flex;gap:10px;flex-wrap:wrap}.cover .meta span{background:rgba(255,255,255,.14);border-radius:999px;padding:3px 10px;font-size:9.5pt}
.lead{font-size:11pt;color:#334;margin:0 0 6px}
h2{font-size:13pt;color:#123a6b;margin:20px 0 6px;padding-bottom:4px;border-bottom:2px solid #f0d6c0;break-after:avoid}
section{break-inside:avoid-page}
ol,ul{margin:4px 0 6px;padding-left:20px}li{margin:3px 0}
.kb{margin:6px 0 8px;display:inline-block;background:#e9eef5;border-radius:10px;padding:6px;min-width:60%}.row{display:flex;gap:5px;margin:3px 0}.b{flex:1;text-align:center;background:#fff;border-radius:7px;padding:4px 8px;font-size:9.5pt;box-shadow:0 1px 0 #c6d0dc;white-space:nowrap}
table{border-collapse:collapse;width:100%;margin:6px 0}td{border-bottom:1px solid #e3e8ef;padding:5px 6px;vertical-align:top}td:first-child{white-space:nowrap;font-weight:600;width:1%;padding-right:14px}
.note{background:#fff5ec;border-left:4px solid #e07a2c;border-radius:6px;padding:8px 11px;margin:8px 0;font-size:10pt}
dt{font-weight:600;margin-top:7px}dd{margin:1px 0 0 0;color:#334}
.foot{margin-top:22px;font-size:9pt;color:#778;text-align:center}'''
for k,d in L.items():
    body=f'''<div class="cover"><div class="logo">osmon<i>.</i></div><h1>{d['title']}</h1><div class="sub">{d['sub']}</div><div class="meta"><span>🤖 {BOT}</span><span>🌍 {SITE}</span><span>ECMWF · NOAA · DWD</span></div></div>
<p class="lead">{d['lead']}</p>'''+''.join(f'<section><h2>{h}</h2>{c}</section>' for h,c in d['s'])+f'<div class="foot">Osmon · {BOT}</div>'
    open(f'g_{k}.html','w').write(f'<!doctype html><html lang="{k}"><head><meta charset="utf-8"><style>{CSS}</style></head><body>{body}</body></html>')
