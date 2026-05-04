🎬 API Rutube v2 — Полное руководство для начинающих

Автор: @bytebudda
Последнее обновление: 4 мая 2026 г.

⚠️ Важно: официальной документации по этой версии API не существует. Вся информация собрана путём наблюдения за запросами, которые отправляет официальный сайт rutube.ru. Возможны неточности — если заметите расхождение, сообщите автору.

---

📖 Что такое API Rutube и зачем оно нужно

API (Application Programming Interface) — это способ получать данные с Rutube для своих программ или сайтов. Например, вы можете:

· Показывать список фильмов из определённой категории на своём сайте.
· Встроить плеер с видео в своё приложение.
· Сделать поиск по видео без захода на rutube.ru.
· Создать собственное приложение для Smart TV или телефона.

API отдаёт данные в формате JSON — это текстовый формат, который легко обрабатывается в любом языке программирования.

---

🧱 Базовые понятия

Базовый URL

Все запросы начинаются с https://rutube.ru/api.
Например, чтобы получить список категорий, нужно открыть:

```
https://rutube.ru/api/video/categories/
```

Как отправлять запросы

· Браузер — просто вставьте адрес в строку и нажмите Enter (работает, если у вас не заблокирован CORS, см. ниже).
· JavaScript (fetch) — внутри веб-приложения.
· Командная строка (cURL):
  ```bash
  curl "https://rutube.ru/api/video/categories/"
  ```
· Python:
  ```python
  import requests
  r = requests.get("https://rutube.ru/api/video/categories/")
  data = r.json()
  ```

CORS и прокси

Если вы пишете веб-приложение на JavaScript и пытаетесь сделать fetch напрямую к rutube.ru, браузер заблокирует запрос. Это политика безопасности (CORS).
Решение: сделайте прокси-сервер (например, на Node.js), который будет принимать запросы от вашего приложения и перенаправлять их на Rutube. Подробнее в разделе «Решение проблем».

Пагинация (страницы)

Когда вы запрашиваете список видео, сервер не отдаст сразу все тысячи записей. Он вернёт страницу с ограниченным количеством элементов. В ответе будут поля:

· page — номер текущей страницы,
· has_next — есть ли следующая,
· next — ссылка на следующую страницу (или null),
· per_page — сколько элементов на странице.

Пример:

```json
{
  "results": [...],
  "page": 1,
  "has_next": true,
  "next": "/api/tags/video/7487/?page=2",
  "per_page": 20
}
```

---

🌐 Список эндпоинтов (точек входа)

1. Категории видео

GET https://rutube.ru/api/video/categories/

Возвращает все возможные категории (жанры/тематики) видео. Это основа для навигации.

Пример ответа (сокращён):

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

Что значат поля:

Поле Тип Описание
id number Уникальный ID категории
name string Название на русском
short_name string Латинский идентификатор (slug), например kino, series
category_url string Адрес страницы категории на сайте
related_showcase string или null Связанная витрина (feed), если есть
for_kids boolean Детский контент
for_import boolean Разрешён ли импорт видео в эту категорию через партнёрское API
update_ts string Время последнего обновления

Полная таблица категорий (id → название → short_name):
(см. таблицу в разделе «Приложение»)

2. Витрины категорий (список всех feed-страниц)

GET https://rutube.ru/api/v1/feeds/categories

Возвращает список всех витрин (главных страниц разделов) с их правильными слагами (slug).
Это самый точный источник slugs, потому что short_name категории не всегда совпадает с реальным адресом витрины.

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

Поля:

· id — ID витрины.
· name — название раздела.
· slug — правильный идентификатор для URL (например, movies, serials, kids). Именно его нужно подставлять в /api/feeds/{slug}.
· url — ссылка на эндпоинт витрины.

Важное отличие от short_name категорий: у категории «Сериалы» short_name = series, но витрина доступна по serials. Поэтому для построения навигации используйте этот эндпоинт, а не short_name.

3. Витрины (главные страницы разделов)

GET https://rutube.ru/api/feeds/{slug}
где {slug} — правильный идентификатор из /v1/feeds/categories (например, movies, serials, kids).

Витрина описывает структуру главной страницы раздела: вкладки и источники контента (ресурсы).

Пример: https://rutube.ru/api/feeds/movies?format=json

```json
{
  "id": 1,
  "slug": "movies",
  "name": "Фильмы",
  "meta_description": "...",
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
          "url": "/api/tags/video/7487/?limit=50&...",
          "name": "Рекомендуем",
          "extra_params": {}
        }
      ]
    }
  ]
}
```

Поля витрины:

Поле Тип Описание
id number ID витрины
slug string Идентификатор витрины
name string Название
meta_description string Описание
page_url string Адрес страницы на rutube.ru
tabs array Массив вкладок

Поля вкладки (tabs[]):

Поле Тип Описание
id number ID вкладки
name string Название
sort string Предпочтительный порядок сортировки (created_date, original, random)
order_number number Порядок показа
slug string/null Slug для URL-якоря
link string/null Внешняя ссылка (если есть — вкладка ведёт на неё)
resources array Список источников контента

Поля ресурса (resources[]):

Поле Тип Описание
id number ID ресурса
object_id string Внутренний ID
content_type object Тип контента (см. ниже)
url string Куда идти за реальными данными
name string Название (показывается пользователю)
extra_params object Дополнительные параметры (лимиты, флаги)

4. Типы ресурсов (content_type.model)

Внутри ресурсов витрины поле content_type.model говорит, какой именно контент лежит по ссылке. Это нужно, чтобы знать, как парсить ответ.

Модель Тип контента Структура данных
tag Подборка видео Плоская (поля в корне объекта)
playlist Плейлист Плоская
tv ТВ-шоу / сериал Плоская (эпизоды) или вложенная (мета)
cardgroup Смешанный контейнер Вложенная (item.object)
subscriptiontvseries Партнёрская подборка Вложенная
subscriptionfilms Партнёрские фильмы Вложенная
promogroup / promofeed Промо-блоки Вложенная (не видео)
userchannel Канал Вложенная
person Персона (актёр и т.п.) Вложенная
feedsource Внешний баннер Ссылка, не парсится

Как отличать плоскую структуру от вложенной:

· Если у элемента есть object и content_type → берите данные из object.
· Иначе все поля (название, длительность, превью) лежат прямо в элементе.

5. Загрузка содержимого ресурса

После того как вы получили URL ресурса (например, /api/tags/video/7487/...), вы запрашиваете его — и получаете либо плоский список видео, либо вложенный список (для cardgroup).

5.1. Плоский список (теги, плейлисты)

GET https://rutube.ru/api/tags/video/{tag_id}/?page=1&format=json
GET https://rutube.ru/api/metainfo/tv/{tv_id}/video/?season=1

Пример ответа:

```json
{
  "results": [
    {
      "id": "abc123",
      "title": "Название видео",
      "duration": 7234,
      "thumbnail_url": "https://pic.rutube.ru/...",
      "author": { "name": "Канал", "id": 456 },
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
```

Поля видео:

Поле Тип Описание
id string Уникальный ID видео (32 символа)
title string Название
duration number Длительность в секундах
thumbnail_url string Ссылка на обложку
preview_url string или null Анимированная gif-превьюшка
author object Автор (name, id)
hits number Количество просмотров
publication_ts number Дата публикации (timestamp)
is_paid boolean Платное ли видео
pg_rating object Возрастное ограничение (age)
description string Описание

5.2. Вложенный список (cardgroup, subscription…)

GET https://rutube.ru/api/feeds/cardgroup/{id}/?format=json

Пример ответа:

```json
{
  "results": [
    {
      "content_type": { "model": "tv" },
      "object": {
        "id": 998126,
        "name": "Подслушано в Рыбинске",
        "poster_url": "...",
        "year_start": 2025,
        "kinopoisk_rating": 7.5,
        "seasons_count": 1
      }
    }
  ],
  "has_next": false,
  "page": 1
}
```

Здесь данные лежат внутри object, а тип указан в content_type.model. Аналогично обрабатываются userchannel, person.

6. Детальная информация о видео

GET https://rutube.ru/api/video/{video_id}/

Возвращает мега-подробный объект с кучей полей: описание, теги, ограничения по странам, ссылки на сериал, персоны, жанры, embed-код и т.д.

Пример (сильно сокращён):

```json
{
  "id": "f912a7d3a6eb0b0350f1043105841307",
  "title": "Подслушано в Рыбинске, 1 сезон, 1 серия",
  "duration": 3114,
  "hits": 217320,
  "author": { "name": "PREMIER" },
  "embed_url": "https://rutube.ru/play/embed/f912a7d3a6eb0b0350f1043105841307",
  "html": "<iframe ...></iframe>",
  "is_serial": true,
  "episode": 1,
  "season": 1,
  "tv_show_id": 998126,
  "persons": "https://rutube.ru/api/metainfo/video/f912a7d3a.../videoperson",
  "genres": "https://rutube.ru/api/metainfo/video/f912a7d3a.../videogenre",
  "restrictions": { "country": { "allowed": ["RU"], "restricted": ["US", ...] } }
}
```

7. Поиск видео

GET https://rutube.ru/api/search/video/?query=комедия&page=1&limit=20&format=json

Работает, как теги: возвращает плоский список видео.

8. Параметры воспроизведения (Play Options)

GET https://rutube.ru/api/play/options/{video_id}/

Отдаёт настройки плеера: цвета, рекламные блоки, субтитры и т.п. Нужно только если вы делаете кастомный плеер.

9. Персоны и жанры видео

Из детальной информации видео можно загрузить:

· Персоны: GET /api/metainfo/video/{video_id}/videoperson
· Жанры: GET /api/metainfo/video/{video_id}/videogenre
· Связанное ТВ-шоу: GET /api/metainfo/contenttvs/{video_id}

10. Подписка на сериал

POST (или DELETE) https://rutube.ru/api/subscription/card/tv/{tv_show_id}
GET-метод не поддерживается (возвращает 405). Требуется авторизация. Используется для подписки/отписки от сериала.

11. Жанры кино (moviesgenres)

GET https://rutube.ru/api/feeds/moviesgenres

Это витрина, где каждая вкладка соответствует киножанру (комедия, драма, боевик и т.д.). Удобно для построения каталога по жанрам.

---

💡 Практические советы

1. Всегда проверяйте has_next и загружайте следующую страницу по next, чтобы собрать полный список.
2. Используйте v1/feeds/categories для получения slugs — они точнее, чем short_name в категориях.
3. Для встраивания видео берите embed_url из детального объекта видео, а если оно не грузится в iframe — открывайте video_url в новой вкладке.
4. Кэшируйте данные витрин и категорий — они редко меняются.
5. Сортируйте с помощью параметра sort (для тегов) или ordering (для cardgroup).

---

📎 Приложение: Полная таблица категорий

ID Название short_name (категория) slug витрины (из v1/feeds/categories)
4 Фильмы kino movies
5 Сериалы series serials
43 Телепередачи tv tv
6 Музыка music music
7 Мультфильмы cartoons cartoons
42 Детям cartoons-kids kids
41 Аниме cartoons-anime cartoons-anime (?)
8 Новости и СМИ news news
16 Спорт sport sport
17 Обучение education education
19 Юмор umor umor
22 Видеоигры games games
35 Хобби hobby hobby
10 Животные animals animals
11 Путешествия travel travel
13 Разное different different
2 Авто-мото auto auto
44 Красота beauty beauty
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

(Для некоторых slug'ов требуются точные подтверждения — ориентируйтесь на вывод /v1/feeds/categories).

---

Удачи в изучении API Rutube! Если появятся вопросы, вы всегда можете написать автору.
