```markdown
# 🎬 API Rutube v2 — руководство (Реверс-инжиниринг)

**Автор:** @bytebudda 
**Последнее обновление:** 2 июня 2026 г.

⚠️ **Важно:** Официальной документации по этой версии API не существует. Вся информация собрана путём наблюдения за запросами официального сайта rutube.ru и его приложений. Возможны изменения на стороне платформы.

---

## 📖 1. Что такое API Rutube и зачем оно нужно

API (Application Programming Interface) позволяет получать данные с Rutube в обход стандартного веб-интерфейса. Это даёт возможность:
- Строить кастомные каталоги фильмов, сериалов и шоу.
- Интегрировать видеопотоки в сторонние плееры и приложения (Smart TV, мобильные клиенты, Stremio/Kodi аддоны).
- Реализовывать независимый поиск и системы рекомендаций.

API отдаёт данные в формате **JSON**, что позволяет легко парсить их на любом современном языке программирования (Node.js, Python, Go, C#).

---

## 🧱 2. Базовые понятия

### Базовый URL
Все запросы к публичному API начинаются с:  
`https://rutube.ru/api`

### Ограничения, CORS и заголовки (Headers)
При прямых запросах из браузера (через `fetch` или `Axios`) вы столкнётесь с блокировкой **CORS**. Для работы веб-приложений необходим прокси-сервер. Кроме того, Rutube активно борется с краулерами. Чтобы избежать ошибок `403 Forbidden` или капчи, в заголовки запроса **обязательно** нужно передавать:
- `User-Agent`: Реальный браузерный юзер-агент.
- `Referer`: `https://rutube.ru/` (критично для эндпоинтов воспроизведения).
- `Accept`: `application/json`

> ⚠️ **Геоблокировка:** Ряд эндпоинтов (особенно выдача медиапотоков для лицензионного контента) отдают пустые ответы или ошибки за пределами РФ. Ваш сервер/прокси должен находиться на территории России.

### Пагинация (Страницы)
Для списков контента Rutube использует стандартную постраничную навигацию. Структура ответа:
```json
{
  "results": [...],
  "page": 1,
  "has_next": true,
  "next": "/api/tags/video/7487/?page=2",
  "per_page": 20
}
```

· page — текущая страница.
· has_next — флаг наличия следующей страницы.
· next — относительный или абсолютный URL для загрузки следующей порции данных (если страниц больше нет — null).
· per_page — количество элементов на одну страницу.

---

🌐 3. Публичные Эндпоинты (Каталог и Навигация)

3.1. Категории видео

GET https://rutube.ru/api/video/categories/

Возвращает глобальный список всех тематических категорий (основа для главного меню).

Пример ответа:

```json
[
  {
    "id": 4,
    "name": "Фильмы",
    "short_name": "kino",
    "category_url": "https://rutube.ru/video/category/4/",
    "related_showcase": null,
    "for_kids": false,
    "for_import": true
  }
]
```

3.2. Витрины категорий (Поиск правильных Slugs)

GET https://rutube.ru/api/v1/feeds/categories

Важнейший эндпоинт для роутинга. Поля short_name из базовых категорий часто не совпадают с реальными адресами страниц. Этот метод отдаёт точные slug для построения страниц-витрин.

Пример ответа:

```json
[
  {
    "id": 1,
    "name": "Фильмы",
    "slug": "movies",
    "url": "/api/feeds/movies/"
  },
  {
    "id": 2,
    "name": "Сериалы",
    "slug": "serials",
    "url": "/api/feeds/serials/"
  }
]
```

3.3. Структура витрины (Главные страницы разделов)

GET https://rutube.ru/api/feeds/{slug}
(Где {slug} берётся из предыдущего шага: movies, serials, kids и т.д.)

Описывает архитектуру главной страницы конкретного раздела: вкладки (tabs), типы отображения (карусель/сетка) и источники данных (resources).

Пример ответа (https://rutube.ru/api/feeds/movies?format=json):

```json
{
  "id": 1,
  "slug": "movies",
  "name": "Фильмы",
  "tabs": [
    {
      "id": 1,
      "name": "Все",
      "sort": "created_date",
      "slug": "all",
      "resources": [
        {
          "id": 7487,
          "content_type": { "model": "tag" },
          "url": "/api/tags/video/7487/?limit=50",
          "name": "Рекомендуем"
        }
      ]
    }
  ]
}
```

---

🧱 4. Парсинг Контента (Плоские и Вложенные структуры)

Когда вы запрашиваете поле url из объектов resources, структура ответа зависит от значения content_type.model.

4.1. Разделение типов моделей

Модель Тип контента Как парсить
tag Тематическая подборка Плоская структура (видео сразу в корне results)
playlist Плейлист пользователя/канала Плоская
tv ТВ-шоу / Сериал Плоская (список серий) или Мета-данные
cardgroup Смешанный промо-контейнер Вложенная структура (данные внутри object)
promogroup Промо-блок (витрина) Вложенная
userchannel Канал автора Вложенная
live Прямая трансляция Особая структура стрима

4.2. Пример: Плоская структура (Видео-элемент)

Данные лежат на верхнем уровне массива results.

```json
{
  "id": "abc123e4f5g6h7j8k9l0f912a7d3a6eb",
  "title": "Название видеоролика",
  "duration": 7234,
  "thumbnail_url": "https://pic.rutube.ru/...",
  "author": {
    "id": 456,
    "name": "Название канала"
  },
  "hits": 1500000,
  "publication_ts": 1672531200,
  "is_paid": false,
  "description": "Описание ролика..."
}
```

⚠️ Важно: id видео — это всегда 32-символьный буквенно-цифровой хэш (строка), в то время как ID каналов или категорий — числа.

4.3. Пример: Вложенная структура (cardgroup / promogroup)

Данные изолированы внутри объекта object, а content_type определяет тип сущности.

```json
{
  "content_type": { "model": "tv" },
  "object": {
    "id": 998126,
    "name": "Название сериала",
    "poster_url": "https://pic.rutube.ru/...",
    "year_start": 2025,
    "kinopoisk_rating": 7.5,
    "seasons_count": 2
  }
}
```

---

🎬 5. Воспроизведение и Детальные Данные

5.1. Детальная информация о видео

GET https://rutube.ru/api/video/{video_id}/

Отдаёт полную мета-информацию: привязку к сезонам/эпизодам, ссылки на метаинформацию о персонах, возрастные рейтинги и разрешённые страны (restrictions.country).

5.2. Стриминг: Получение прямой ссылки на видеопоток (HLS/m3u8)

GET https://rutube.ru/api/play/options/{video_id}/?format=json

Самый ценный эндпоинт для разработчиков видеоплееров. Он возвращает конфигурацию для плеера и ссылки на манифесты потокового вещания в объекте video_balancer.

Пример ответа:

```json
{
  "video_balancer": {
    "m3u8": "https://video-storage.rutube.ru/hls/.../master.m3u8"
  },
  "subtitles": [
    { "language": "ru", "url": "https://..." }
  ],
  "is_live": false
}
```

Прямой запуск: Ссылку из поля m3u8 можно напрямую скармливать в Native-плееры (AVPlayer, ExoPlayer, VLC) или веб-библиотеки (HLS.js).

DRM Защита: Если в детальной информации о видео флаг "is_paid": true, то выданный .m3u8 поток будет защищён DRM (Widevine/FairPlay). Для его воспроизведения потребуется передавать токен лицензии.

5.3. Специфика Трансляций (Live)

Если ролик имеет флаг "is_live": true, структура ответа /play/options/ меняется: вместо video_balancer отдаётся объект live_streams, содержащий динамически обновляемые HLS-плейлисты прямого эфира.

---

💬 6. Дополнительные Эндпоинты

6.1. Поиск по видео

GET https://rutube.ru/api/search/video/?query={запрос}&page=1&limit=20

Возвращает стандартную плоскую структуру списка видео, релевантных поисковому запросу.

6.2. Похожие видео (Рекомендации)

GET https://rutube.ru/api/video/{video_id}/related/?page=1&limit=10

Используется для формирования блока «Что посмотреть дальше» под текущим видеоплеером.

6.3. Комментарии

GET https://rutube.ru/api/v2/comments/?video_id={video_id}&page=1

Вынесенная система комментариев. Для совершения деструктивных действий (POST для отправки, DELETE для удаления) требуется авторизационная кука и заголовок X-CSRFToken.

6.4. Метаинформация (Персоны и Жанры)

· Персоны (Актеры, режиссеры): GET /api/metainfo/video/{video_id}/videoperson
· Жанры конкретного видео: GET /api/metainfo/video/{video_id}/videogenre
· Связанное ТВ-шоу: GET /api/metainfo/contenttvs/{video_id}

---

🛠️ 7. Готовое решение: CORS-Прокси на Node.js (Express)

Для обхода ограничений CORS на фронтенде и автоматического подкладывания доверенных заголовков, используйте следующий прокси-сервер:

```javascript
const express = require('express');
const cors = require('cors');
const app = express();

app.use(cors()); // Разрешаем CORS-запросы с любых доменов

app.get('/api/*', async (req, res) => {
  // Собираем оригинальный URL Rutube с сохранением параметров строки запроса
  const targetUrl = `https://rutube.ru${req.originalUrl}`;
  try {
    const response = await fetch(targetUrl, {
      method: 'GET',
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://rutube.ru/',
        'Accept': 'application/json'
      }
    });
    if (!response.ok) {
      return res.status(response.status).json({ error: `Rutube API returned status ${response.status}` });
    }
    const data = await response.json();
    res.status(200).json(data);
  } catch (error) {
    res.status(500).json({ error: 'Proxy Error', details: error.message });
  }
});

const PORT = 3000;
app.listen(PORT, () => console.log(`Rutube CORS Proxy успешно запущен на порту ${PORT}`));
```

---

📎 Приложение: Сводная таблица соответствия категорий и витрин

Используйте этот справочник для настройки хардкодного маппинга разделов в интерфейсе приложения.

ID Название категории short_name (Категории) slug (Витрины из /v1/feeds/categories)
4 Фильмы kino movies
5 Сериалы serials serials
43 Телепередачи tv tv
6 Музыка music music
7 Мультфильмы cartoons cartoons
42 Детям cartoons-kids kids
41 Аниме cartoons-anime anime
8 Новости и СМИ news news
16 Спорт sport sport
17 Обучение education education
19 Юмор humor humor
22 Видеоигры games games
35 Хобби hobby hobby
10 Животные animals animals
11 Путешествия travel travel
13 Разное different different
2 Авто-мото auto auto
44 Красота beauty beauty beauty
45 Технологии technologies technologies
48 Аудио audio audio
50 Психология psychology psychology
51 Политика politics politics
52 Наука science science
53 Охота и рыбалка fishing fishing
54 Эзотерика esoterics esoterics
55 Лайфхаки lifehack lifehack
57 Развлечения entertainment entertainment
58 Интервью interview interview
59 Еда recipe recipe
60 Аудиокниги audiobooks audiobooks
61 Сад и огород garden garden
62 Строительство repairs repairs
63 Религия religion religion
64 Культура art art
67 Бизнес business business
68 Техника technics technics
69 Дизайн design design
70 Природа nature nature
71 Здоровье health health
72 Недвижимость property property
73 Лайфстайл lifestyle lifestyle
78 Обзоры товаров goods goods

```