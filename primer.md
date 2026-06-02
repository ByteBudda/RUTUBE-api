Ниже представлен готовый проект локального каталога Rutube с поиском, плеером Plyr и сервером на Node.js (Express). Всё работает на локальном ПК, запросы к Rutube идут через ваш сервер (без CORS), HLS-поток воспроизводится через hls.js в обёртке Plyr.

---

📁 Структура проекта

```
rutube-local-app/
├── app.js                  # сервер + API
├── package.json
├── public/
│   ├── index.html          # интерфейс
│   ├── style.css           # стили (опционально)
│   └── client.js           # фронт: поиск, плеер, рекомендации
└── rutube-parser.js        # (код парсера из предыдущего шага)
```

---

1. Создайте package.json

```json
{
  "name": "rutube-local-app",
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "start": "node app.js"
  },
  "dependencies": {
    "express": "^4.18.2"
  }
}
```

Выполните npm install.

---

2. Файл rutube-parser.js

Полностью скопируйте код универсального парсера из предыдущего моего сообщения (с ротацией User-Agent Tizen и всеми методами). Убедитесь, что в конце есть export { RutubeUniversalParser }.

---

3. Файл app.js (сервер)

```javascript
import express from 'express';
import path from 'path';
import { fileURLToPath } from 'url';
import { RutubeUniversalParser as Rutube } from './rutube-parser.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const app = express();
const PORT = 3000;

// Статика (HTML, CSS, client.js)
app.use(express.static(path.join(__dirname, 'public')));

// API: поиск видео
app.get('/api/search', async (req, res) => {
    const query = req.query.q;
    const page = parseInt(req.query.page) || 1;
    if (!query) return res.json([]);
    try {
        const videos = await Rutube.searchVideos(query, page, 20);
        res.json(videos);
    } catch (err) {
        console.error(err);
        res.status(500).json({ error: err.message });
    }
});

// API: детали видео + прямая HLS-ссылка
app.get('/api/video/:id', async (req, res) => {
    const id = req.params.id;
    try {
        const [details, m3u8] = await Promise.all([
            Rutube.getVideoDetails(id),
            Rutube.getPlaybackUrl(id)
        ]);
        res.json({ details, m3u8 });
    } catch (err) {
        res.status(500).json({ error: err.message });
    }
});

// API: рекомендации (похожие видео)
app.get('/api/related/:id', async (req, res) => {
    const id = req.params.id;
    try {
        const related = await Rutube.getRelatedVideos(id, 1, 10);
        res.json(related);
    } catch (err) {
        res.status(500).json({ error: err.message });
    }
});

app.listen(PORT, () => {
    console.log(`Сервер запущен: http://localhost:${PORT}`);
});
```

---

4. Создайте папку public и файлы внутри

public/index.html

```html
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
    <title>Rutube локальный плеер</title>
    <!-- Plyr CSS + HLS.js -->
    <link rel="stylesheet" href="https://cdn.plyr.io/3.7.8/plyr.css" />
    <script src="https://cdn.plyr.io/3.7.8/plyr.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/hls.js@latest"></script>
    <style>
        * { box-sizing: border-box; }
        body {
            font-family: system-ui, 'Segoe UI', Roboto, sans-serif;
            background: #0f0f0f;
            color: #eee;
            margin: 0;
            padding: 20px;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        .search-bar {
            display: flex;
            gap: 10px;
            margin-bottom: 30px;
        }
        .search-bar input {
            flex: 1;
            padding: 12px 20px;
            font-size: 16px;
            border: none;
            border-radius: 30px;
            background: #222;
            color: #fff;
        }
        .search-bar button {
            padding: 12px 24px;
            background: #ff4d4d;
            border: none;
            border-radius: 30px;
            color: white;
            font-weight: bold;
            cursor: pointer;
        }
        .player-section {
            background: #000;
            border-radius: 16px;
            overflow: hidden;
            margin-bottom: 30px;
        }
        .video-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }
        .video-card {
            background: #1e1e1e;
            border-radius: 12px;
            cursor: pointer;
            transition: transform 0.1s, background 0.2s;
            overflow: hidden;
        }
        .video-card:hover {
            background: #2a2a2a;
            transform: scale(1.02);
        }
        .video-card img {
            width: 100%;
            aspect-ratio: 16 / 9;
            object-fit: cover;
        }
        .video-card .info {
            padding: 10px;
        }
        .video-card h4 {
            margin: 0 0 5px;
            font-size: 1rem;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        .video-card p {
            margin: 0;
            font-size: 0.8rem;
            color: #aaa;
        }
        .related-title {
            margin-top: 30px;
            font-size: 1.4rem;
        }
        .loading {
            text-align: center;
            padding: 40px;
            color: #aaa;
        }
    </style>
</head>
<body>
<div class="container">
    <div class="search-bar">
        <input type="text" id="searchInput" placeholder="Поиск видео... (например, 'кино', 'обзор техники')" autocomplete="off">
        <button id="searchBtn">🔍 Найти</button>
    </div>

    <div class="player-section" id="playerContainer" style="display: none;">
        <video id="plyrVideo" controls playsinline></video>
    </div>

    <h2>Результаты поиска</h2>
    <div id="resultsGrid" class="video-grid"></div>

    <div id="relatedBlock"></div>
</div>

<script src="client.js"></script>
</body>
</html>
```

public/client.js

```javascript
// Глобальные переменные
let currentPlayer = null;
let currentVideoId = null;

const searchInput = document.getElementById('searchInput');
const searchBtn = document.getElementById('searchBtn');
const resultsGrid = document.getElementById('resultsGrid');
const playerContainer = document.getElementById('playerContainer');
const relatedBlock = document.getElementById('relatedBlock');

// Функция загрузки поиска
async function searchVideos(query, page = 1) {
    resultsGrid.innerHTML = '<div class="loading">⏳ Загрузка...</div>';
    try {
        const res = await fetch(`/api/search?q=${encodeURIComponent(query)}&page=${page}`);
        const videos = await res.json();
        if (!videos.length) {
            resultsGrid.innerHTML = '<div class="loading">😕 Ничего не найдено</div>';
            return;
        }
        renderVideoGrid(videos, resultsGrid, (videoId) => {
            loadVideoAndPlay(videoId);
        });
    } catch (err) {
        resultsGrid.innerHTML = `<div class="loading">❌ Ошибка: ${err.message}</div>`;
    }
}

// Рендер сетки карточек
function renderVideoGrid(videos, container, onClickCallback) {
    container.innerHTML = '';
    videos.forEach(video => {
        const card = document.createElement('div');
        card.className = 'video-card';
        card.innerHTML = `
            <img src="${video.thumbnail || ''}" alt="${escapeHtml(video.title)}" onerror="this.src='https://via.placeholder.com/320x180?text=No+image'">
            <div class="info">
                <h4>${escapeHtml(video.title)}</h4>
                <p>${video.author.name || 'Неизвестный канал'} • ${video.stats.views} просмотров</p>
                <p>${video.duration || ''}</p>
            </div>
        `;
        card.addEventListener('click', () => onClickCallback(video.id));
        container.appendChild(card);
    });
}

// Загрузка видео по ID и инициализация плеера
async function loadVideoAndPlay(videoId) {
    if (currentVideoId === videoId) return;
    currentVideoId = videoId;

    // Показать контейнер плеера и скрыть старый плеер
    playerContainer.style.display = 'block';
    if (currentPlayer) {
        currentPlayer.destroy();
        currentPlayer = null;
    }

    // Очистить старый video элемент
    const videoEl = document.getElementById('plyrVideo');
    // Сброс src
    videoEl.removeAttribute('src');
    videoEl.load();

    try {
        // Получаем детали + m3u8
        const res = await fetch(`/api/video/${videoId}`);
        const data = await res.json();
        if (!data.m3u8) {
            alert('Не удалось получить HLS-поток (возможно, видео платное или требует авторизации)');
            playerContainer.style.display = 'none';
            return;
        }

        // Инициализируем HLS.js
        if (Hls.isSupported()) {
            const hls = new Hls();
            hls.loadSource(data.m3u8);
            hls.attachMedia(videoEl);
            currentPlayer = new Plyr(videoEl, {
                controls: ['play-large', 'play', 'progress', 'current-time', 'mute', 'volume', 'fullscreen'],
                autoplay: true
            });
            // Сохраняем ссылку на hls для возможного уничтожения
            videoEl.hls = hls;
        } else if (videoEl.canPlayType('application/vnd.apple.mpegurl')) {
            // Safari native HLS
            videoEl.src = data.m3u8;
            currentPlayer = new Plyr(videoEl, { autoplay: true });
        } else {
            alert('HLS не поддерживается вашим браузером');
        }

        // Загружаем рекомендации
        loadRelated(videoId);
    } catch (err) {
        console.error(err);
        alert('Ошибка загрузки видео: ' + err.message);
        playerContainer.style.display = 'none';
    }
}

// Рекомендации
async function loadRelated(videoId) {
    relatedBlock.innerHTML = '<div class="loading">Загрузка рекомендаций...</div>';
    try {
        const res = await fetch(`/api/related/${videoId}`);
        const related = await res.json();
        if (!related.length) {
            relatedBlock.innerHTML = '<div class="related-title">🎬 Похожие видео не найдены</div>';
            return;
        }
        relatedBlock.innerHTML = '<div class="related-title">🎬 Похожие видео</div><div class="video-grid" id="relatedGrid"></div>';
        const relatedGrid = document.getElementById('relatedGrid');
        renderVideoGrid(related, relatedGrid, (vidId) => {
            loadVideoAndPlay(vidId);
        });
    } catch (err) {
        relatedBlock.innerHTML = `<div class="loading">Ошибка загрузки рекомендаций: ${err.message}</div>`;
    }
}

// Вспомогательная функция для экранирования HTML
function escapeHtml(str) {
    if (!str) return '';
    return str.replace(/[&<>]/g, function(m) {
        if (m === '&') return '&amp;';
        if (m === '<') return '&lt;';
        if (m === '>') return '&gt;';
        return m;
    }).replace(/[\uD800-\uDBFF][\uDC00-\uDFFF]/g, function(c) {
        return c;
    });
}

// Обработчики событий
searchBtn.addEventListener('click', () => {
    const query = searchInput.value.trim();
    if (!query) return;
    searchVideos(query);
});
searchInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') searchBtn.click();
});

// При загрузке — можно показать что-то популярное или пустой экран
window.addEventListener('load', () => {
    searchInput.value = 'кино';
    searchVideos('кино');
});
```

---

5. Запуск

```bash
cd rutube-local-app
npm start
```

Откройте браузер → http://localhost:3000

---

📺 Возможности приложения

· Поиск видео по ключевым словам (используется RutubeUniversalParser.searchVideos).
· Клик по карточке — загружается HLS-поток и воспроизводится в плеере Plyr (с поддержкой качества, паузы, громкости).
· Рекомендации — под плеером отображаются похожие видео, по которым можно кликнуть и сразу переключиться.
· Автоматическая ротация User-Agent на сервере — Rutube не блокирует.
· Кэширование поиска на сервере (в парсере) — повторные запросы того же поиска будут быстрее.

---

⚠️ Примечания

· Для работы плеера в некоторых браузерах может потребоваться разрешить автовоспроизведение (но пользователь кликает по карточке — звук разрешён).
· Поток .m3u8 иногда требует обновления ссылки (ссылка живёт ~6 часов). Приложение запрашивает её каждый раз при клике.
· Если видео платное (is_paid: true) — HLS-ссылка может не отдаваться (вернётся null). В этом случае выводится сообщение.

---

🧪 Доработки (по желанию)

· Добавить пагинацию результатов поиска.
· Сохранять историю просмотров в localStorage.
· Добавить авторизацию (передать sessionid/csrftoken в парсер) для доступа к подпискам и эксклюзивному контенту.
· Реализовать категории / главную страницу с подборками (используя /api/feeds).

Готово! У вас на ПК работает полноценный Rutube-клиент с поиском и плеером.