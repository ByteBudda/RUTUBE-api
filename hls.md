## Извлечение HLS-потока (.m3u8) из Rutube API

Парсинг прямой ссылки на видеопоток выполняется в **два последовательных шага** через внутренние эндпоинты Rutube. Метод полностью автономен, работает на стороне Node.js и не требует использования браузерного плеера для получения ссылки.

### 🛠️ Алгоритм работы

1. **Поиск видео (/api/search/video/)** — отправляем поисковый запрос, чтобы получить метаданные ролика и его уникальный id.
2. **Получение параметров (/api/play/options/{id}/)** — дергаем эндпоинт конфигурации плеера для конкретного id и забираем прямую ссылку на мастер-манифест из объекта `video_balancer.m3u8`.

### ⚠️ Важные нюансы (Заголовки)

Rutube жестко блокирует запросы без корректного окружения. Для обхода защиты в **каждом** запросе обязательно передавать:

- `Referer: https://rutube.ru/` — имитирует, что запрос идет со страниц самого сервиса.
- `User-Agent` — должен быть валидным браузерным юзер-агентом, иначе API вернет ошибку или пустой результат.

### 💻 Реализация на Node.js (v18+)

```javascript
/**
 * Базовые заголовки для обхода ограничений Rutube API
 */
const RUTUBE_HEADERS = {
    'Accept': 'application/json, text/plain, */*',
    'Referer': 'https://rutube.ru/',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
};

/**
 * Ищет видео и возвращает прямую ссылку на .m3u8 поток
 * @param {string} query - Поисковый запрос (название видео)
 * @returns {Promise<string|null>} Ссылка на поток или null в случае ошибки
 */
async function getRutubeStreamUrl(query) {
    try {
        // Шаг 1: Поиск видео для получения ID
        const searchUrl = `https://rutube.ru/api/search/video/?query=${encodeURIComponent(query)}&page=1&limit=1`;
        const searchResponse = await fetch(searchUrl, { headers: RUTUBE_HEADERS });
        
        if (!searchResponse.ok) {
            throw new Error(`Ошибка поиска API: HTTP ${searchResponse.status}`);
        }
        
        const searchData = await searchResponse.json();
        const video = searchData.results?.[0];
        
        if (!video) {
            console.warn(`[Rutube] Ничего не найдено по запросу: "${query}"`);
            return null;
        }

        // Шаг 2: Запрос параметров плеера по ID видео
        const optionsUrl = `https://rutube.ru/api/play/options/${video.id}/?format=json`;
        const optionsResponse = await fetch(optionsUrl, { headers: RUTUBE_HEADERS });
        
        if (!optionsResponse.ok) {
            throw new Error(`Ошибка play/options API: HTTP ${optionsResponse.status}`);
        }
        
        const optionsData = await optionsResponse.json();
        const m3u8Url = optionsData.video_balancer?.m3u8;

        if (!m3u8Url) {
            throw new Error('Эндпоинт не вернул video_balancer.m3u8. Возможно, требуется авторизация.');
        }

        return m3u8Url;

    } catch (error) {
        console.error(`[Rutube Parser Error]: ${error.message}`);
        return null;
    }
}

// Пример использования:
// (async () => {
//     const streamUrl = await getRutubeStreamUrl('клип дуа липа');
//     console.log('Финальный стрим-URL:', streamUrl);
// })();