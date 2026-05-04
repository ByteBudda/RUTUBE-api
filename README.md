# Полная документация API Rutube v2

**Автор расшифровки:** @bytebudda  
**Важное примечание:** Это описание актуальной версии API Rutube (v2), которая не имеет публичной документации. Все данные собраны путём реверс-инжиниринга. Официальная документация для разработчиков (`http://rutube.ru/info/to_developers/`) описывает устаревшую версию API.  
**Последнее обновление:** 2026-05-03

## Оглавление
1. [Обзор](#1-обзор)
2. [Content API](#2-content-api)
   - 2.1 [Витрины (Feeds)](#21-витрины-feeds)
   - 2.2 [Типы источников (`content_type.model`)](#22-типы-источников-content_typemodel)
   - 2.3 [Список видео (Теги / Плейлисты)](#23-список-видео-теги--плейлисты)
   - 2.4 [Кардгруппы (Смешанные списки)](#24-кардгруппы-смешанные-списки)
   - 2.5 [Метаинформация ТВ-шоу](#25-метаинформация-тв-шоу)
   - 2.6 [Видео пользователя (Канал)](#26-видео-пользователя-канал)
   - 2.7 [Метаданные видео (расширенная структура)](#27-метаданные-видео-расширенная-структура)
   - 2.8 [Поиск видео](#28-поиск-видео)
   - 2.9 [Параметры воспроизведения (Play Options)](#29-параметры-воспроизведения-play-options)
   - 2.10 [Пагинация](#210-пагинация)
   - 2.11 [Категории видео (полный список)](#211-категории-видео-полный-список)
   - 2.12 [Связанные эндпоинты метаинформации](#212-связанные-эндпоинты-метаинформации)
3. [oEmbed API](#3-oembed-api)
4. [Player API](#4-player-api)
5. [Partner API (авторизованный доступ)](#5-partner-api-авторизованный-доступ)
6. [Тонкости и особенности](#6-тонкости-и-особенности)
7. [Примеры запросов](#7-примеры-запросов)
8. [Полезные ссылки](#8-полезные-ссылки)

## 1. Обзор

Rutube предоставляет несколько уровней API:
- **Content API** — получение контента (витрины, видео, плейлисты, каналы, поиск, категории);
- **Player API** — управление встроенным плеером;
- **oEmbed API** — встраивание видео по стандарту oEmbed;
- **Partner API** — загрузка и управление видео (требует авторизации).

API возвращает данные в форматах JSON, JSONP и XML. Основной базовый URL — `https://rutube.ru/api`.

## 2. Content API

### 2.1. Витрины (Feeds)

Витрины — это способ организации и представления видеоконтента на портале Rutube. Каждая витрина состоит из вкладок, которые содержат источники карточек (теги, ТВ-шоу, пользователи и т.д.).

**Эндпоинт:**
GET https://rutube.ru/api/feeds/{slug}?format=json


**Параметры:**
| Параметр | Тип | Описание |
|---|---|---|
| `slug` | string | Уникальный идентификатор витрины (например, `movies`, `series`, `tnt`) |
| `format` | string | Формат ответа (`json`, `jsonp`, `xml`, `api` для human-readable) |

**Пример ответа:**
```json
{
  "id": 1,
  "slug": "movies",
  "name": "Фильмы",
  "meta_description": "Описание витрины",
  "page_url": "https://rutube.ru/feeds/movies/",
  "tabs": [
    {
      "id": 1,
      "name": "Все",
      "sort": "created_date",
      "order_number": 1,
      "slug": "all",
      "link": null,
      "resources": [
        {
          "id": 7487,
          "object_id": "...",
          "content_type": {
            "model": "tag"
          },
          "url": "/api/tags/video/7487/...",
          "name": "Рекомендуем",
          "extra_params": {}
        }
      ]
    }
  ]
}
Поля ответа витрины:

Поле Тип Описание id number ID витрины slug string Идентификатор витрины name string Название витрины meta_description string Описание page_url string Адрес на rutube.ru tabs array Массив вкладок

Поля вкладки (tabs[]):

Поле Тип Описание id number ID вкладки name string Название sort string Рекомендация сортировки (created_date, original, random) order_number number Порядковый номер slug string/null Уникальное название для hash-навигации link string/null Внешняя ссылка (если задана, вкладка делает редирект) resources array Источники карточек

Поля ресурса (resources[]):

Поле Тип Описание id number ID источника object_id string Служебный ID content_type object Тип источника (model: tag, tv, cardgroup, userchannel, promogroup, feedsource и др.) url string Адрес для загрузки карточек name string Название источника extra_params object Дополнительные параметры

2.2. Типы источников (content_type.model)

Возможные типы источников (объект content_type):

Модель Тип контента Описание tag Список видео Тег/подборка видео tv ТВ-шоу Сериал или телешоу tvlastepisode Последний эпизод Последний эпизод конкретного ТВ-шоу playlist Плейлист Список видео (плоская структура) cardgroup Кардгруппа Смешанный контейнер (может содержать видео, сериалы, каналы) subscriptiontvseries Подписка Подборка от партнера (структура как cardgroup) promogroup / promofeed Промо Промо-элементы (не видео) userchannel Канал Пользователь Rutube person Персона Актер, режиссер и т.д. feedsource Внешняя ссылка Баннер или редирект

2.3. Список видео (Теги / Плейлисты)

Эндпоинт:

GET https://rutube.ru/api/tags/video/{tag_id}/?page=1&limit=20&format=json
Параметры:

Параметр Тип Описание page number Номер страницы limit number Количество элементов на странице sort string Сортировка (tagged_a, tagged_d, created_a, created_d, publication_a, publication_d)

Пример ответа (плоская структура):

{
  "results": [
    {
      "id": "abc123",
      "type": "video",
      "title": "Название фильма",
      "duration": 7234,
      "thumbnail_url": "https://pic.rutube.ru/video/...",
      "author": {
        "name": "Канал",
        "id": 456
      },
      "hits": 1500000,
      "publication_ts": 1672531200,
      "is_paid": false,
      "pg_rating": { "age": 16 }
    }
  ],
  "has_next": true,
  "next": "/api/tags/video/7487/?page=2",
  "page": 1,
  "per_page": 20
}
Поля элемента списка (видео):

Поле Тип Описание id string ID видео (32 символа hex) type string Тип ("video", реже "tv") title string Название duration number Длительность в секундах thumbnail_url string URL превью preview_url string Анимированное превью (GIF) author object Автор (name, id) hits number Количество просмотров publication_ts number Timestamp публикации is_paid boolean Платное видео pg_rating object Возрастной рейтинг (age) description string Описание

2.4. Кардгруппы (Смешанные списки)

Эндпоинт:

GET https://rutube.ru/api/feeds/cardgroup/{id}/?format=json
Особенности:

· Каждый элемент содержит вложенный объект object и content_type.model. · Может содержать разнородные сущности: tv, userchannel, tag.

Пример ответа:

{
  "results": [
    {
      "content_type": { "model": "tv" },
      "object": {
        "id": 1478618,
        "type": "movie",
        "name": "Сериал XYZ",
        "poster_url": "https://...",
        "year_start": 2021,
        "kinopoisk_rating": 7.8,
        "seasons_count": 3
      }
    },
    {
      "content_type": { "model": "userchannel" },
      "object": {
        "id": 789,
        "name": "Киноканал",
        "subscribers_count": 50000,
        "user_channel_image": "https://..."
      }
    }
  ],
  "has_next": false,
  "page": 1
}
2.5. Метаинформация ТВ-шоу

Эндпоинт:

GET https://rutube.ru/api/metainfo/tv/{tv_id}/?format=json
Эндпоинт списка эпизодов:

GET https://rutube.ru/api/metainfo/tv/{tv_id}/video/?page=1&sort=series_d&format=json
Параметры сортировки для ТВ-шоу:

Значение Описание series_a По возрастанию серий series_d По убыванию серий created_a По дате добавления (возрастание) created_d По дате добавления (убывание) publication_a По дате публикации (возрастание) publication_d По дате публикации (убывание)

Дополнительные параметры:

Параметр Описание season Номер сезона episode Номер эпизода origin__type Платформа (rtb — Rutube, rst — трансляции, ytb — YouTube)

2.6. Видео пользователя (Канал)

Эндпоинт:

GET https://rutube.ru/api/video/person/{person_id}/?page=1&limit=20&format=json
Возвращает список видео пользователя.

2.7. Метаданные видео (расширенная структура)

Эндпоинт: GET https://rutube.ru/api/video/{video_id}/ {video_id} — 32-значный hex-идентификатор.

Возвращает подробную информацию о видео, включая автора, категорию, теги, статистику, ограничения и встроенные ссылки на связанные ресурсы.

Пример ответа:

{
  "id": "8431c687e7e44c2bb4f020b77f07e38b",
  "title": "Путешествие к бессмертию, 176 серия",
  "description": "",
  "thumbnail_url": "https://pic.rtbcdn.ru/video/2026-01-03/dc/53/dc532acef66b836ed6685063f39ca3ec.jpg",
  "is_audio": false,
  "created_ts": "2026-01-03T15:55:05",
  "video_url": "https://rutube.ru/video/8431c687e7e44c2bb4f020b77f07e38b/",
  "track_id": 442811214,
  "hits": 436099,
  "duration": 1175,
  "is_livestream": false,
  "is_on_air": false,
  "last_update_ts": "2026-01-03T20:00:13",
  "stream_type": null,
  "origin_type": "rtb",
  "picture_url": "",
  "preview_url": null,
  "author": {
    "id": 27141608,
    "name": "РуАниме",
    "avatar_url": "https://pic.rtbcdn.ru/user/82/60/8260b0c7d3dc0841a9d6e81e1f593400.jpeg",
    "site_url": "https://rutube.ru/video/person/27141608/",
    "is_allowed_offline": true
  },
  "is_adult": false,
  "pg_rating": {
    "age": 18,
    "logo": "https://pic.rtbcdn.ru/agerestriction/8c/37/8c37c740367ef785ae1693da1fa4e449.png"
  },
  "publication_ts": "2026-01-03T20:00:13",
  "is_paid": false,
  "category": { "id": 41, "name": "Аниме", "short_name": "cartoons-anime" },
  "is_official": true,
  "is_licensed": true,
  "embed_url": "https://rutube.ru/play/embed/8431c687e7e44c2bb4f020b77f07e38b",
  "html": "<iframe width=\"720\" height=\"405\" src=\"https://rutube.ru/play/embed/8431c687e7e44c2bb4f020b77f07e38b\" frameborder=\"0\" webkitAllowFullScreen mozallowfullscreen allowfullscreen allow=\"encrypted-media\"></iframe>",
  "is_hidden": false,
  "has_high_quality": false,
  "is_deleted": false,
  "source_url": "https://rutube.ru/video/8431c687e7e44c2bb4f020b77f07e38b/",
  "show": "https://rutube.ru/api/metainfo/contenttvs/8431c687e7e44c2bb4f020b77f07e38b",
  "persons": "https://rutube.ru/api/metainfo/video/8431c687e7e44c2bb4f020b77f07e38b/videoperson",
  "genres": "https://rutube.ru/api/metainfo/video/8431c687e7e44c2bb4f020b77f07e38b/videogenre",
  "hashtags": [],
  "all_tags": [
    { "id": 5989, "name": "Рекомендуем", "url": "https://rutube.ru/tags/video/5989/", "type": "simple" }
  ],
  "restrictions": {
    "country": {
      "allowed": ["RU", "BY", "KZ", ...],
      "restricted": ["US", "DE", ...]
    }
  },
  "feed_url": "https://rutube.ru/metainfo/tv/211247/",
  "feed_name": "Путешествие к бессмертию / Fan ren xiu xian chuan",
  "feed_subscription_url": "https://rutube.ru/api/subscription/card/tv/211247",
  "feed_subscribers_count": 678570,
  "episode": 176,
  "season": 0,
  "is_serial": true,
  "tv_show_id": 211247,
  "hide_comments": false,
  "hide_chat": false,
  "hide_likes": false,
  "hide_dislikes": false,
  "properties": {
    "hide_comments": false,
    "is_donate_allowed": false,
    "is_chat_saved": null
  }
}
Полный перечень полей:

Поле Тип Описание id string ID видео (32 hex) title string Название description string Описание thumbnail_url string URL постера is_audio boolean Только аудио created_ts string (datetime) Дата добавления на платформу video_url string Адрес страницы видео на Rutube track_id number Внутренний числовой идентификатор hits number Количество просмотров duration number Длительность в секундах is_livestream boolean Является ли прямой трансляцией is_on_air boolean Идёт ли эфир в данный момент last_update_ts string (datetime) Время последнего обновления stream_type string|null Тип стрима (для live) origin_type string Платформа происхождения (rtb, ytb, vim и т.д.) picture_url string Дополнительное изображение preview_url string|null Анимированное превью (gif) author object Информация об авторе (id, name, avatar_url, site_url, is_allowed_offline) is_adult boolean Контент 18+ pg_rating object Возрастной рейтинг (age, logo) publication_ts string (datetime) Время публикации is_paid boolean Платный контент product_id number|null ID продукта (для платного) category object Категория видео is_official boolean Официальное видео is_licensed boolean Лицензионный контент action_reason object Причина действия (id, name) embed_url string URL для встраивания html string HTML-код для вставки (iframe) is_hidden boolean Скрытое видео has_high_quality boolean Доступно высокое качество is_deleted boolean Удалено source_url string Исходный URL show string (URL) Ссылка на метаинформацию ТВ-шоу (если видео является эпизодом) persons string (URL) Эндпоинт для получения персон (актёры, режиссёры) genres string (URL) Эндпоинт для получения жанров music null Ссылка на музыку (не используется) hashtags array Хэштеги видео all_tags array Все теги видео restrictions object Ограничения по стране feed_url string (URL) Ссылка на родительский сериал/шоу feed_name string Название родительского шоу feed_subscription_url string (URL) Эндпоинт для управления подпиской на шоу feed_subscribers_count number Количество подписчиков шоу episode number Номер эпизода season number Номер сезона is_serial boolean Является ли сериалом tv_show_id number ID ТВ-шоу hide_comments boolean Скрыты ли комментарии hide_chat boolean Скрыт ли чат hide_likes boolean Скрыты ли лайки hide_dislikes boolean Скрыты ли дизлайки properties object Дополнительные свойства (hide_comments, is_donate_allowed, is_chat_saved)

2.8. Поиск видео

Эндпоинт:

GET https://rutube.ru/api/search/video/?query={query}&page=1&limit=20&format=json
Параметры:

Параметр Тип Описание query string Поисковый запрос page number Номер страницы limit number Количество результатов filter object Фильтры (created, author_id, category_id, duration) short string Сортировка

2.9. Параметры воспроизведения (Play Options)

Эндпоинт: GET https://rutube.ru/api/play/options/{video_id}/

Возвращает техническую информацию, необходимую для работы официального плеера Rutube: данные о доступном видео, рекламных блоках, внешнем виде плеера, субтитрах, авторе и категории.

Служебные поля

Поле Тип Описание acl_access.allowed boolean Доступ к видео разрешён black_rabbit boolean Флаг спецрежима защиты (DRM) count_load_time boolean Считать время загрузки cuepoints array Пользовательские маркеры на таймлайне

Автор (author)

Поле Тип Описание id number ID автора name string Название канала url string Ссылка на канал avatar_url string URL аватарки logo string|null Отдельный логотип

Внешний вид плеера (appearance)

Управляет интерфейсом плеера. Ключевые поля: color, auto_start, show_title, show_author, show_avatar, show_subscription, show_endscreen, show_related, cinema_mode, mini_player и другие (всего более 30 параметров).

Реклама (advert)

Массив объектов с конфигурацией рекламных блоков. Каждый блок содержит:

· name — тип (preroll201, midroll80101, midpostroll) · url_template — URL-шаблон с плейсхолдерами (AdFox + SSP) · start — секунда запуска · count, delay, only_fire, xmltimeout, adtimeout, vast и др.

Субтитры (captions)

Массив дорожек субтитров. Каждая дорожка имеет поля: sub_id, format, langTitle, file, is_autogenerated, code.

Категория (category)

Поля: id, name, short_name, category_url, for_kids, update_ts.

Описание (description)

Текстовое описание видео.

2.10. Пагинация

Все списки поддерживают пагинацию со следующими полями:

Поле Тип Описание results array Массив элементов текущей страницы page number Номер текущей страницы has_next boolean Наличие следующей страницы next string/null URL следующей страницы per_page number Элементов на странице

2.11. Категории видео (полный список)

Эндпоинт: GET https://rutube.ru/api/video/categories/

Возвращает массив категорий. Поля: id, category_url, related_showcase, update_ts, name, short_name, for_kids, for_import.

Полный список категорий:

ID Название Slug Связанная витрина 2 Авто-мото auto null 4 Фильмы kino null 5 Сериалы series null 6 Музыка music null 7 Мультфильмы cartoons null 8 Новости и СМИ news null 10 Животные animals null 11 Путешествия travel null 13 Разное different null 16 Спорт sport null 17 Обучение education null 19 Юмор umor null 22 Видеоигры games null 35 Хобби hobby null 41 Аниме cartoons-anime null 42 Детям cartoons-kids null 43 Телепередачи tv https://rutube.ru/api/feeds/tv/ 44 Красота beauty null 45 Технологии и интернет technologies null 48 Аудио audio null 50 Психология psychology null 51 Политика politics null 52 Наука science null 53 Охота и рыбалка fishing null 54 Эзотерика esoterics null 55 Лайфхаки lifehack null 57 Развлечения entertainment null 58 Интервью interview null 59 Еда recipe null 60 Аудиокниги audiobooks null 61 Сад и огород garden null 62 Строительство и ремонт repairs null 63 Религия religion null 64 Культура art null 67 Бизнес и предпринимательство business null 68 Техника и оборудование technics null 69 Дизайн design null 70 Природа nature null 71 Здоровье health null 72 Недвижимость property null 73 Лайфстайл lifestyle null 78 Обзоры и распаковки товаров goods null

2.12. Связанные эндпоинты метаинформации

Персоны видео

GET https://rutube.ru/api/metainfo/video/{video_id}/videoperson Возвращает список персон (актёры, режиссёры и т.д.)

Жанры видео

GET https://rutube.ru/api/metainfo/video/{video_id}/videogenre Возвращает список жанров.

Информация о ТВ-шоу

GET https://rutube.ru/api/metainfo/contenttvs/{video_id} Метаинформация о сериале/шоу, к которому относится видео.

Управление подпиской на ТВ-шоу

POST (или DELETE) https://rutube.ru/api/subscription/card/tv/{tv_show_id} Важно: Метод GET запрещён (405 Method Not Allowed). Используется для подписки/отписки. Требуется аутентификация.

oEmbed API
Эндпоинт:

GET https://rutube.ru/api/oembed/?url={video_url}&format=json
Возвращает стандартный oEmbed-ответ.

Player API
· Встраивание через iframe · Управление через postMessage (play, pause, seek, volume, etc.) · События (player:ready, player:playStart, player:changeState, player:currentTime и др.)

(Подробное описание в предыдущих версиях документации.)

Partner API (авторизованный доступ)
Требуется авторизация. Доступны методы: загрузка видео, управление видео, плейлисты. (См. официальную документацию v1.)

Тонкости и особенности
· Плоская vs вложенная структура: теги/плейлисты – плоская, cardgroup – вложенная. · Превью: размеры ?size=l, m, s. · CORS: необходим прокси-сервер. · Коды ошибок: 400, 401, 403, 404, 405, 500.

Примеры запросов
GET https://rutube.ru/api/feeds/movies?format=json
GET https://rutube.ru/api/tags/video/7487/?page=1&format=json
GET https://rutube.ru/api/video/b07639337aa57ce56578bbb9e40e0102/
GET https://rutube.ru/api/search/video/?query=комедия&page=1&limit=20&format=json
GET https://rutube.ru/api/video/person/123/?page=1&limit=20&format=json
GET https://rutube.ru/api/metainfo/tv/28/video?sort=series_d&season=1&format=json
GET https://rutube.ru/api/play/options/{video_id}/
GET https://rutube.ru/api/video/categories/
