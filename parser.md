# Универсальный парсер Rutube (Tizen TV / Node.js)

Получение HLS-потоков, поиск, рекомендации, комментарии, авторизация. Работает через `fetch`, с ротацией User-Agent (Tizen TV), повторными попытками и кэшированием.

```javascript
/**
 * УНИВЕРСАЛЬНЫЙ ПАРСЕР RUTUBE v1.0
 * - Работает через fetch (Node.js 18+ или браузер с CORS-прокси)
 * - Защита от блокировок: ротация User-Agent (Tizen TV), Referer, задержки, повторы
 * - Кэширование результатов поиска (TTL 5 минут)
 * - Поддержка авторизации (setCredentials)
 * - Получение HLS-потока (.m3u8), поиск, детали видео, рекомендации, комментарии, информация о канале/шоу
 */

// ---------- НАСТРОЙКИ ----------
const CONFIG = {
    API_BASE: 'https://rutube.ru',
    REQUEST_TIMEOUT: 10000,
    MAX_RETRIES: 2,                // количество повторов при ошибке
    RETRY_DELAY_MS: 1000,          // задержка между повторами
    CACHE_TTL_MS: 300000,          // 5 минут кэш для поиска
    ENABLE_CACHE: true,
    MIN_REQUEST_DELAY_MS: 200,      // минимальная задержка между запросами (rate limiting)
    // Ротация User-Agent для Tizen TV (разные версии)
    USER_AGENTS: [
        'Mozilla/5.0 (SmartHub; SMART-TV; Tizen 6.0) AppleWebKit/537.36 (KHTML, like Gecko)  SamsungBrowser/4.0 Chrome/108.0.5359.128',
        'Mozilla/5.0 (SmartHub; SMART-TV; Tizen 5.5) AppleWebKit/537.36 (KHTML, like Gecko)  SamsungBrowser/4.0 Chrome/96.0.4664.45',
        'Mozilla/5.0 (SmartHub; SMART-TV; Tizen 7.0) AppleWebKit/537.36 (KHTML, like Gecko)  SamsungBrowser/5.0 Chrome/112.0.5615.204',
        'Mozilla/5.0 (Linux; Tizen 6.5) AppleWebKit/537.36 (KHTML, like Gecko) Version/6.0 SamsungBrowser/4.0 Chrome/106.0.5249.65'
    ]
};

// Базовые заголовки (общие для всех запросов)
let currentHeaders = {
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8',
    'Referer': 'https://rutube.ru/',
    'User-Agent': CONFIG.USER_AGENTS[0]   // будет ротироваться при каждом запросе
};

// Хранилище авторизации
let credentials = {
    sessionid: null,
    csrftoken: null
};

// Кэш (Map: ключ -> { data, timestamp })
const cache = new Map();

// Простой Rate Limiter: запоминаем время последнего запроса
let lastRequestTime = 0;

// ---------- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ----------

/**
 * Ротация User-Agent (выбирается случайный из списка)
 */
function rotateUserAgent() {
    const randomIndex = Math.floor(Math.random() * CONFIG.USER_AGENTS.length);
    currentHeaders['User-Agent'] = CONFIG.USER_AGENTS[randomIndex];
}

/**
 * Задержка (промис)
 */
function delay(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

/**
 * Выполнение запроса с повторными попытками и rate limiting
 */
async function fetchWithRetry(url, options = {}, retries = CONFIG.MAX_RETRIES) {
    // Rate limiting: выдерживаем паузу между запросами
    const now = Date.now();
    const timeSinceLast = now - lastRequestTime;
    if (timeSinceLast < CONFIG.MIN_REQUEST_DELAY_MS) {
        await delay(CONFIG.MIN_REQUEST_DELAY_MS - timeSinceLast);
    }
    lastRequestTime = Date.now();

    // Ротируем User-Agent перед каждым запросом (в том числе перед повторными)
    rotateUserAgent();

    const finalOptions = {
        ...options,
        headers: {
            ...currentHeaders,
            ...options.headers
        },
        signal: AbortSignal.timeout(CONFIG.REQUEST_TIMEOUT)
    };

    // Если есть авторизация, добавляем Cookie и CSRF-токен
    if (credentials.sessionid || credentials.csrftoken) {
        const cookieParts = [];
        if (credentials.sessionid) cookieParts.push(`sessionid=${credentials.sessionid}`);
        if (credentials.csrftoken) cookieParts.push(`csrftoken=${credentials.csrftoken}`);
        finalOptions.headers['Cookie'] = cookieParts.join('; ');
        if (credentials.csrftoken) {
            finalOptions.headers['X-CSRFToken'] = credentials.csrftoken;
        }
    }

    let lastError = null;
    for (let attempt = 0; attempt <= retries; attempt++) {
        try {
            const response = await fetch(url, finalOptions);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            const contentType = response.headers.get('content-type');
            if (!contentType || !contentType.includes('application/json')) {
                throw new Error('Invalid response: not JSON');
            }
            const data = await response.json();
            return data;
        } catch (err) {
            lastError = err;
            if (attempt < retries) {
                await delay(CONFIG.RETRY_DELAY_MS * (attempt + 1)); // увеличиваем задержку
            }
        }
    }
    throw lastError;
}

/**
 * Нормализация URL (добавляет базовый адрес при необходимости)
 */
function normalizeUrl(path) {
    if (path.startsWith('http')) return path;
    if (path.startsWith('/api/')) return `${CONFIG.API_BASE}${path}`;
    if (path.startsWith('/')) return `${CONFIG.API_BASE}/api${path}`;
    return `${CONFIG.API_BASE}/api/${path}`;
}

/**
 * Получить из кэша или выполнить запрос с кэшированием
 */
async function fetchCached(url, options = {}, ttl = CONFIG.CACHE_TTL_MS) {
    if (!CONFIG.ENABLE_CACHE) {
        return fetchWithRetry(url, options);
    }
    const cacheKey = `${url}|${JSON.stringify(options)}`;
    const cached = cache.get(cacheKey);
    if (cached && (Date.now() - cached.timestamp) < ttl) {
        return cached.data;
    }
    const data = await fetchWithRetry(url, options);
    cache.set(cacheKey, { data, timestamp: Date.now() });
    return data;
}

// ---------- ОСНОВНОЙ КЛАСС ПАРСЕРА ----------

class RutubeUniversalParser {
    /**
     * Установить данные авторизации (сессия)
     * @param {string|null} sessionid
     * @param {string|null} csrftoken
     */
    static setCredentials(sessionid, csrftoken) {
        credentials.sessionid = sessionid;
        credentials.csrftoken = csrftoken;
    }

    /**
     * Очистить кэш
     */
    static clearCache() {
        cache.clear();
    }

    /**
     * Поиск видео (возвращает массив нормализованных объектов)
     * @param {string} query
     * @param {number} page
     * @param {number} limit
     * @returns {Promise<Array>}
     */
    static async searchVideos(query, page = 1, limit = 20) {
        const url = normalizeUrl(`/api/search/video/?query=${encodeURIComponent(query)}&page=${page}&limit=${limit}`);
        const data = await fetchCached(url, {}, 60000); // поиск кэшируем на 1 минуту
        const results = data.results || [];
        return results.map(item => this._normalizeVideo(item));
    }

    /**
     * Получить детальную информацию о видео по ID
     * @param {string} videoId (32-символьный хэш)
     * @returns {Promise<Object>}
     */
    static async getVideoDetails(videoId) {
        const url = normalizeUrl(`/api/video/${videoId}/`);
        const data = await fetchWithRetry(url);
        return this._normalizeVideo(data);
    }

    /**
     * Получить HLS-ссылку (.m3u8) для видео по ID
     * @param {string} videoId
     * @returns {Promise<string|null>}
     */
    static async getPlaybackUrl(videoId) {
        const url = normalizeUrl(`/api/play/options/${videoId}/?format=json`);
        const data = await fetchWithRetry(url);
        return data.video_balancer?.m3u8 || data.live_streams?.m3u8 || null;
    }

    /**
     * Поиск видео по названию и сразу получение HLS-ссылки (удобный метод)
     * @param {string} query
     * @returns {Promise<{ video: Object, m3u8: string|null } | null>}
     */
    static async findAndGetStream(query) {
        const videos = await this.searchVideos(query, 1, 1);
        if (!videos.length) return null;
        const video = videos[0];
        const m3u8 = await this.getPlaybackUrl(video.id);
        return { video, m3u8 };
    }

    /**
     * Получить похожие видео (рекомендации)
     * @param {string} videoId
     * @param {number} page
     * @param {number} limit
     * @returns {Promise<Array>}
     */
    static async getRelatedVideos(videoId, page = 1, limit = 20) {
        const url = normalizeUrl(`/api/video/${videoId}/related/?page=${page}&limit=${limit}`);
        const data = await fetchWithRetry(url);
        const results = data.results || [];
        return results.map(item => this._normalizeVideo(item));
    }

    /**
     * Получить комментарии к видео
     * @param {string} videoId
     * @param {number} page
     * @returns {Promise<Array>}
     */
    static async getComments(videoId, page = 1) {
        const url = normalizeUrl(`/api/v2/comments/?video_id=${videoId}&page=${page}`);
        const data = await fetchWithRetry(url);
        const results = data.results || [];
        return results.map(item => this._normalizeComment(item));
    }

    /**
     * Получить информацию о канале (авторе) по ID канала (число)
     * @param {number} channelId
     * @returns {Promise<Object>}
     */
    static async getChannelInfo(channelId) {
        const url = normalizeUrl(`/api/video/person/${channelId}/`);
        const data = await fetchWithRetry(url);
        return this._normalizeChannel(data);
    }

    /**
     * Получить информацию о ТВ-шоу (сериале)
     * @param {number} tvId
     * @returns {Promise<Object>}
     */
    static async getTvShowInfo(tvId) {
        const url = normalizeUrl(`/api/metainfo/tv/${tvId}/video/`);
        const data = await fetchWithRetry(url);
        return this._normalizeTvShow(data);
    }

    /**
     * Получить серии конкретного сезона ТВ-шоу
     * @param {number} tvId
     * @param {number} seasonNumber
     * @param {number} page
     * @returns {Promise<Array>}
     */
    static async getSeasonEpisodes(tvId, seasonNumber, page = 1) {
        const url = normalizeUrl(`/api/metainfo/tv/${tvId}/video/?season=${seasonNumber}&page=${page}`);
        const data = await fetchWithRetry(url);
        const results = data.results || [];
        return results.map(item => this._normalizeVideo(item));
    }

    // ---------- ВНУТРЕННИЕ НОРМАЛИЗАТОРЫ ----------

    static _normalizeVideo(item) {
        if (!item || typeof item !== 'object') return null;
        const id = item.id || item.video_id;
        return {
            id,
            title: item.title || 'Без названия',
            thumbnail: item.thumbnail_url || item.picture_url || null,
            duration: item.duration ? this._formatDuration(item.duration) : null,
            author: {
                id: item.author?.id || null,
                name: item.author?.name || item.feed_name || null,
                avatar: item.author?.avatar_url || null
            },
            stats: {
                views: item.hits || item.views_count || 0,
                published: item.publication_ts || item.created_ts || null
            },
            isPaid: item.is_paid || false,
            description: item.description || ''
        };
    }

    static _normalizeComment(item) {
        return {
            id: item.id,
            author: item.author?.name || 'Anonymous',
            text: item.text || '',
            likes: item.likes_count || 0,
            date: item.created_ts || null,
            replies: (item.replies || []).map(r => this._normalizeComment(r))
        };
    }

    static _normalizeChannel(data) {
        return {
            id: data.id,
            name: data.name,
            avatar: data.user_channel_image || data.icon || null,
            subscribers: data.subscribers_count || 0,
            videoCount: data.video_count || 0,
            description: data.description || ''
        };
    }

    static _normalizeTvShow(data) {
        return {
            id: data.id,
            title: data.title || data.name,
            poster: data.poster_url || null,
            year: data.year_start,
            rating: data.kinopoisk_rating || null,
            seasonsCount: data.seasons_count || 0,
            description: data.description || ''
        };
    }

    static _formatDuration(seconds) {
        const h = Math.floor(seconds / 3600);
        const m = Math.floor((seconds % 3600) / 60);
        const s = seconds % 60;
        return h > 0 ? `${h}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`
                     : `${m}:${s.toString().padStart(2, '0')}`;
    }
}

// Экспорт (для ES-модулей)
export { RutubeUniversalParser };