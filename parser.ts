// rutube-parser.ts
// Universal Rutube API Parser v1.0
// Works with: JavaScript, TypeScript, Node.js, Browser, React Native

/**
 * Configuration interface
 */
interface ParserConfig {
  apiBase?: string;
  timeout?: number;
  maxRetries?: number;
  enableCache?: boolean;
  cacheTTL?: number;
  userAgent?: string;
}

/**
 * Entity types enumeration
 */
enum EntityType {
  FEED = 'FEED',
  CONTAINER = 'CONTAINER',
  VIDEO_LIST = 'VIDEO_LIST',
  VIDEO_ITEM = 'VIDEO_ITEM',
  CHANNEL = 'CHANNEL',
  TV_SHOW = 'TV_SHOW',
  EXTERNAL = 'EXTERNAL',
  UNKNOWN = 'UNKNOWN',
  EMPTY = 'EMPTY',
  PROMO_LIST = 'PROMO_LIST'
}

/**
 * Video card interface
 */
interface VideoCard {
  type: 'VIDEO';
  id: string;
  title: string;
  thumbnail: string | null;
  previewGif: string | null;
  duration: string;
  durationSeconds: number;
  channel: {
    id: string | null;
    name: string;
    avatar: string | null;
  };
  stats: {
    views: string;
    viewsCount: number;
    published: string;
    publishedTimestamp: number;
  };
  rating: {
    age: string | null;
    likes: number | null;
    dislikes: number | null;
  };
  isPaid: boolean;
  isLive: boolean;
  description: string;
  tags: string[];
  url: string;
  embedUrl: string;
}

/**
 * TV Show card interface
 */
interface TvShowCard {
  type: 'TV_SHOW';
  id: string;
  title: string;
  originalTitle: string | null;
  poster: string | null;
  year: string | null;
  rating: {
    kinopoisk: number | null;
    imdb: number | null;
  };
  seasons: number;
  episodes: number | null;
  description: string | null;
  genres: string[];
  url: string;
}

/**
 * Channel card interface
 */
interface ChannelCard {
  type: 'CHANNEL';
  id: string;
  name: string;
  avatar: string | null;
  cover: string | null;
  description: string | null;
  stats: {
    subscribers: string;
    subscribersCount: number;
    videos: number;
    views: number | null;
  };
  isVerified: boolean;
  url: string;
  rssUrl: string | null;
}

/**
 * Promo card interface
 */
interface PromoCard {
  type: 'PROMO';
  id: string;
  title: string;
  thumbnail: string | null;
  description: string | null;
  action: {
    type: 'LINK' | 'VIDEO' | 'CHANNEL' | 'TV_SHOW';
    url: string | null;
    target: string | null;
  };
}

/**
 * Pagination info
 */
interface PaginationInfo {
  hasNext: boolean;
  nextUrl: string | null;
  page: number;
  perPage: number;
  total: number | null;
}

/**
 * Parsed response
 */
interface ParsedResponse {
  type: EntityType;
  items: (VideoCard | TvShowCard | ChannelCard | PromoCard)[];
  title?: string | null;
  tabs?: TabInfo[];
  pagination?: PaginationInfo;
  error?: string | null;
  meta?: {
    sourceUrl: string;
    timestamp: number;
    cached?: boolean;
  };
}

/**
 * Tab information
 */
interface TabInfo {
  id: number;
  name: string;
  resources: ResourceInfo[];
}

/**
 * Resource information
 */
interface ResourceInfo {
  name: string;
  url: string | null;
  type: EntityType;
  meta: Record<string, any>;
}

/**
 * Cache entry
 */
interface CacheEntry {
  data: any;
  timestamp: number;
}

/**
 * Request queue item
 */
interface QueueItem {
  promise: Promise<any>;
  timestamp: number;
}

/**
 * Main parser class
 */
class RutubeParser {
  private config: Required<ParserConfig>;
  private cache: Map<string, CacheEntry>;
  private requestQueue: Map<string, QueueItem>;
  private abortControllers: Map<string, AbortController>;

  constructor(config: ParserConfig = {}) {
    this.config = {
      apiBase: config.apiBase || 'https://rutube.ru',
      timeout: config.timeout || 10000,
      maxRetries: config.maxRetries || 3,
      enableCache: config.enableCache !== false,
      cacheTTL: config.cacheTTL || 300000, // 5 minutes
      userAgent: config.userAgent || 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    };
    
    this.cache = new Map();
    this.requestQueue = new Map();
    this.abortControllers = new Map();
  }

  /**
   * Normalize URL to full API URL
   */
  private normalizeUrl(url: string): string {
    if (!url) return '';
    
    // Already absolute URL
    if (url.startsWith('http')) {
      if (url.includes('rutube.ru')) {
        const path = url.replace(/https?:\/\/rutube\.ru/, '');
        if (path.startsWith('/api/')) {
          return `${this.config.apiBase}${path}`;
        }
        return `${this.config.apiBase}/api${path}`;
      }
      return url;
    }
    
    // Relative path
    if (url.startsWith('/api/')) {
      return `${this.config.apiBase}${url}`;
    }
    
    if (url.startsWith('/')) {
      return `${this.config.apiBase}/api${url}`;
    }
    
    return `${this.config.apiBase}/api/${url}`;
  }

  /**
   * Format duration from seconds to HH:MM:SS or MM:SS
   */
  private formatDuration(seconds: number): string {
    if (!seconds && seconds !== 0) return '00:00';
    
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;
    
    if (hours > 0) {
      return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    }
    return `${minutes}:${secs.toString().padStart(2, '0')}`;
  }

  /**
   * Format count (views, subscribers) with K/M suffix
   */
  private formatCount(num: number): string {
    if (!num && num !== 0) return '0';
    if (num >= 1_000_000) return (num / 1_000_000).toFixed(1) + 'M';
    if (num >= 1_000) return (num / 1_000).toFixed(1) + 'K';
    return num.toString();
  }

  /**
   * Parse date string to timestamp
   */
  private parseDate(dateString: string): number {
    if (!dateString) return Date.now();
    try {
      return new Date(dateString).getTime();
    } catch {
      return Date.now();
    }
  }

  /**
   * Parse series information from title
   */
  private parseSeriesInfo(title: string): { season: number; episode: number } | null {
    const patterns = [
      /s(\d+)e(\d+)/i,
      /(\d+)x(\d+)/i,
      /(\d+)\s+сезон\s+(\d+)\s+серия/i,
      /сезон\s+(\d+)\s+серия\s+(\d+)/i,
      /(\d+)\s*(?:-|–|—)?\s*(?:й|ый|ой|го|ий|ая|е|ое)?\s*сезон\w*\s*[,.\s-]*\s*(\d+)/i
    ];
    
    for (const pattern of patterns) {
      const match = title.match(pattern);
      if (match && match[1] && match[2]) {
        return {
          season: parseInt(match[1], 10),
          episode: parseInt(match[2], 10)
        };
      }
    }
    
    return null;
  }

  /**
   * Normalize video data
   */
  private normalizeVideo(data: any): VideoCard {
    const id = data.id || data.video_id || data.code;
    const title = data.title || data.name || 'Untitled';
    
    // Get channel info
    const author = data.author || data.owner || {};
    const channelId = author.id || author.person_id || data.channel_id;
    const channelName = author.name || author.username || data.feed_name || data.channel || 'Unknown Channel';
    
    // Get stats
    const viewsCount = data.views_count || data.hits || data.views || 0;
    const likesCount = data.likes_count || null;
    const dislikesCount = data.dislikes_count || null;
    
    // Get duration
    const durationSeconds = data.duration || 0;
    const duration = this.formatDuration(durationSeconds);
    
    // Get timestamps
    const publishedTimestamp = this.parseDate(data.publication_ts || data.created_ts);
    
    // Parse series info if present
    const seriesInfo = this.parseSeriesInfo(title);
    
    return {
      type: 'VIDEO',
      id,
      title,
      thumbnail: data.thumbnail_url || data.picture_url || data.poster_url || null,
      previewGif: data.preview_url || null,
      duration,
      durationSeconds,
      channel: {
        id: channelId,
        name: channelName,
        avatar: author.avatar_url || author.avatar || null
      },
      stats: {
        views: this.formatCount(viewsCount),
        viewsCount,
        published: this.formatDate(publishedTimestamp),
        publishedTimestamp
      },
      rating: {
        age: data.pg_rating?.age || data.age_limit || null,
        likes: likesCount,
        dislikes: dislikesCount
      },
      isPaid: data.is_paid || false,
      isLive: data.is_live || false,
      description: data.description || '',
      tags: data.tags || [],
      url: `https://rutube.ru/video/${id}/`,
      embedUrl: `https://rutube.ru/play/embed/${id}/`,
      ...(seriesInfo && { series: seriesInfo })
    } as VideoCard;
  }

  /**
   * Normalize TV show data
   */
  private normalizeTvShow(data: any): TvShowCard {
    const images = data.images || [];
    const poster = data.poster_url || (images[0]?.image) || data.thumbnail_url || null;
    
    return {
      type: 'TV_SHOW',
      id: data.id,
      title: data.title || data.name || 'Untitled',
      originalTitle: data.original_title || null,
      poster,
      year: data.year_start || data.year || null,
      rating: {
        kinopoisk: data.kinopoisk_rating || null,
        imdb: data.imdb_rating || null
      },
      seasons: data.seasons_count || 0,
      episodes: data.episodes_count || null,
      description: data.description || null,
      genres: data.genres || [],
      url: `https://rutube.ru/metainfo/tv/${data.id}/`
    };
  }

  /**
   * Normalize channel data
   */
  private normalizeChannel(data: any): ChannelCard {
    const subscribersCount = data.subscribers_count || 0;
    
    return {
      type: 'CHANNEL',
      id: data.id || data.person_id,
      name: data.name || data.title || 'Untitled',
      avatar: data.user_channel_image || data.icon || data.picture || data.avatar_url || null,
      cover: data.cover_url || null,
      description: data.description || null,
      stats: {
        subscribers: this.formatCount(subscribersCount),
        subscribersCount,
        videos: data.video_count || 0,
        views: data.views_count || null
      },
      isVerified: data.is_verified || false,
      url: `https://rutube.ru/channel/${data.id}/`,
      rssUrl: data.rss_url || null
    };
  }

  /**
   * Normalize promo data
   */
  private normalizePromo(data: any): PromoCard {
    let actionUrl = data.button?.button_url || data.target || data.link || data.url;
    let actionType: PromoCard['action']['type'] = 'LINK';
    
    // Determine action type from URL
    if (actionUrl) {
      if (actionUrl.includes('/video/')) actionType = 'VIDEO';
      else if (actionUrl.includes('/channel/')) actionType = 'CHANNEL';
      else if (actionUrl.includes('/tv/')) actionType = 'TV_SHOW';
    }
    
    if (actionUrl && actionUrl.startsWith('/') && !actionUrl.startsWith('/api/')) {
      actionUrl = `/api${actionUrl}`;
    }
    
    return {
      type: 'PROMO',
      id: data.id || Math.random().toString(36).substr(2, 9),
      title: data.title || 'Untitled',
      thumbnail: data.picture || data.thumbnail_url || data.image || null,
      description: data.description || null,
      action: {
        type: actionType,
        url: actionUrl || null,
        target: data.button?.target || null
      }
    };
  }

  /**
   * Format date for display
   */
  private formatDate(timestamp: number): string {
    const date = new Date(timestamp);
    const now = new Date();
    const diff = now.getTime() - timestamp;
    
    // Less than 24 hours
    if (diff < 24 * 60 * 60 * 1000) {
      const hours = Math.floor(diff / (60 * 60 * 1000));
      if (hours < 1) {
        const minutes = Math.floor(diff / (60 * 1000));
        return `${minutes} минут назад`;
      }
      return `${hours} часов назад`;
    }
    
    // Less than 7 days
    if (diff < 7 * 24 * 60 * 60 * 1000) {
      const days = Math.floor(diff / (24 * 60 * 60 * 1000));
      return `${days} дней назад`;
    }
    
    // Format as date
    return date.toLocaleDateString('ru-RU', {
      day: 'numeric',
      month: 'short',
      year: 'numeric'
    });
  }

  /**
   * Get pagination info from response
   */
  private getPagination(json: any): PaginationInfo {
    return {
      hasNext: !!(json.has_next || json.next),
      nextUrl: json.next ? this.normalizeUrl(json.next) : null,
      page: json.page || 1,
      perPage: json.per_page || 20,
      total: json.total || null
    };
  }

  /**
   * Parse feed with tabs
   */
  private parseFeed(json: any): ParsedResponse {
    const tabs: TabInfo[] = (json.tabs || []).map((tab: any) => ({
      id: tab.id,
      name: tab.name || 'Tab',
      resources: (tab.resources || []).map((res: any) => ({
        name: res.name || 'Resource',
        url: res.url ? this.normalizeUrl(res.url) : null,
        type: this.classifyResource(res),
        meta: res.extra_params || {}
      }))
    }));
    
    return {
      type: EntityType.FEED,
      items: [],
      title: json.name || 'Каталог',
      tabs,
      meta: {
        sourceUrl: '',
        timestamp: Date.now()
      }
    };
  }

  /**
   * Classify resource type
   */
  private classifyResource(resource: any): EntityType {
    const model = resource.content_type?.model;
    
    switch (model) {
      case 'tag':
      case 'playlist':
        return EntityType.VIDEO_LIST;
      case 'tv':
        return EntityType.TV_SHOW;
      case 'cardgroup':
      case 'subscriptiontvseries':
      case 'promogroup':
        return EntityType.CONTAINER;
      case 'userchannel':
        return EntityType.CHANNEL;
      case 'feedsource':
        return EntityType.EXTERNAL;
      default:
        return EntityType.UNKNOWN;
    }
  }

  /**
   * Parse response based on structure
   */
  private parseResponse(json: any, sourceUrl: string): ParsedResponse {
    // Empty response
    if (!json || typeof json !== 'object') {
      return {
        type: EntityType.EMPTY,
        items: [],
        error: 'Empty or invalid response',
        meta: { sourceUrl, timestamp: Date.now() }
      };
    }
    
    // Feed with tabs
    if (json.tabs && Array.isArray(json.tabs)) {
      return this.parseFeed(json);
    }
    
    // Paginated results
    if (Array.isArray(json.results)) {
      if (json.results.length === 0) {
        return {
          type: EntityType.EMPTY,
          items: [],
          pagination: this.getPagination(json),
          meta: { sourceUrl, timestamp: Date.now() }
        };
      }
      
      // Check if this is a promo group
      const isPromoGroup = sourceUrl.includes('promogroup');
      
      const items = json.results.map((item: any) => {
        if (isPromoGroup) {
          return this.normalizePromo(item);
        }
        return this.normalizeItem(item);
      });
      
      // Determine type from first item
      let type = EntityType.VIDEO_LIST;
      if (items.length > 0) {
        const firstItem = items[0];
        if (firstItem.type === 'PROMO') type = EntityType.PROMO_LIST;
        else if (firstItem.type === 'TV_SHOW') type = EntityType.TV_SHOW;
        else if (firstItem.type === 'CHANNEL') type = EntityType.CHANNEL;
      }
      
      return {
        type,
        items,
        pagination: this.getPagination(json),
        meta: { sourceUrl, timestamp: Date.now() }
      };
    }
    
    // Single video item
    if (json.id && (json.video_url || json.duration !== undefined)) {
      return {
        type: EntityType.VIDEO_ITEM,
        items: [this.normalizeVideo(json)],
        meta: { sourceUrl, timestamp: Date.now() }
      };
    }
    
    // Unknown response
    return {
      type: EntityType.UNKNOWN,
      items: [],
      error: 'Unrecognized response structure',
      meta: { sourceUrl, timestamp: Date.now() }
    };
  }

  /**
   * Normalize any item
   */
  private normalizeItem(item: any): VideoCard | TvShowCard | ChannelCard | PromoCard {
    if (!item || typeof item !== 'object') {
      return {
        type: 'PROMO',
        id: 'unknown',
        title: 'Unknown',
        thumbnail: null,
        description: null,
        action: { type: 'LINK', url: null, target: null }
      } as PromoCard;
    }
    
    const isNested = item.content_type && item.object;
    const data = isNested ? item.object : item;
    const model = isNested ? item.content_type.model : (data.type || 'video');
    
    // Classify and normalize based on type
    if (model === 'userchannel' || data.subscribers_count !== undefined) {
      return this.normalizeChannel(data);
    }
    
    if (model === 'tv' || data.type === 'tv' || data.seasons_count !== undefined) {
      return this.normalizeTvShow(data);
    }
    
    if (data.duration !== undefined || data.video_url || data.video_id) {
      return this.normalizeVideo(data);
    }
    
    // Default to promo card for unknown types
    return this.normalizePromo(data);
  }

  /**
   * Make HTTP request with retries and timeout
   */
  private async fetchWithRetry(url: string, retryCount: number = 0): Promise<any> {
    const controller = new AbortController();
    this.abortControllers.set(url, controller);
    
    const timeoutId = setTimeout(() => {
      controller.abort();
    }, this.config.timeout);
    
    try {
      const response = await fetch(url, {
        headers: {
          'User-Agent': this.config.userAgent,
          'Accept': 'application/json, text/plain, */*',
          'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8',
          'Referer': 'https://rutube.ru/'
        },
        signal: controller.signal
      });
      
      clearTimeout(timeoutId);
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      
      const contentType = response.headers.get('content-type');
      if (!contentType || !contentType.includes('application/json')) {
        throw new Error('Invalid response format: expected JSON');
      }
      
      return await response.json();
      
    } catch (error: any) {
      clearTimeout(timeoutId);
      
      if (error.name === 'AbortError' && retryCount < this.config.maxRetries) {
        await new Promise(resolve => setTimeout(resolve, 1000 * (retryCount + 1)));
        return this.fetchWithRetry(url, retryCount + 1);
      }
      
      throw error;
    } finally {
      this.abortControllers.delete(url);
    }
  }

  /**
   * Fetch and parse URL
   */
  async fetchUrl(url: string, options: { skipCache?: boolean } = {}): Promise<ParsedResponse> {
    const normalizedUrl = this.normalizeUrl(url);
    const cacheKey = normalizedUrl;
    
    // Check cache
    if (this.config.enableCache && !options.skipCache) {
      const cached = this.cache.get(cacheKey);
      if (cached && Date.now() - cached.timestamp < this.config.cacheTTL) {
        const cachedResponse = { ...cached.data };
        if (cachedResponse.meta) {
          cachedResponse.meta.cached = true;
        }
        return cachedResponse;
      }
    }
    
    // Deduplicate concurrent requests
    if (this.requestQueue.has(cacheKey)) {
      return this.requestQueue.get(cacheKey)!.promise;
    }
    
    const promise = (async () => {
      try {
        const json = await this.fetchWithRetry(normalizedUrl);
        const result = this.parseResponse(json, normalizedUrl);
        
        // Cache result
        if (this.config.enableCache) {
          this.cache.set(cacheKey, {
            data: result,
            timestamp: Date.now()
          });
        }
        
        return result;
      } catch (error: any) {
        return {
          type: EntityType.UNKNOWN,
          items: [],
          error: error.message,
          meta: { sourceUrl: normalizedUrl, timestamp: Date.now() }
        } as ParsedResponse;
      }
    })();
    
    this.requestQueue.set(cacheKey, {
      promise,
      timestamp: Date.now()
    });
    
    try {
      return await promise;
    } finally {
      // Clean up queue after 5 seconds
      setTimeout(() => {
        this.requestQueue.delete(cacheKey);
      }, 5000);
    }
  }

  /**
   * Load next page
   */
  async loadNextPage(response: ParsedResponse): Promise<ParsedResponse | null> {
    if (!response.pagination?.nextUrl) {
      return null;
    }
    
    return this.fetchUrl(response.pagination.nextUrl, { skipCache: true });
  }

  /**
   * Search videos
   */
  async search(query: string, page: number = 1): Promise<ParsedResponse> {
    const encodedQuery = encodeURIComponent(query);
    const url = `/api/search/video/?query=${encodedQuery}&page=${page}`;
    return this.fetchUrl(url);
  }

  /**
   * Get category feed
   */
  async getCategoryFeed(category: string, page: number = 1): Promise<ParsedResponse> {
    const categorySlugs: Record<string, string> = {
      'movies': 'Фильмы',
      'serials': 'Сериалы',
      'tv': 'Телепередачи',
      'music': 'Музыка',
      'cartoons': 'Мультфильмы',
      'sport': 'Спорт',
      'games': 'Видеоигры',
      'technologies': 'Технологии'
    };
    
    const slug = Object.keys(categorySlugs).find(
      key => categorySlugs[key].toLowerCase() === category.toLowerCase()
    ) || category;
    
    const url = `/api/feeds/${slug}/?page=${page}`;
    return this.fetchUrl(url);
  }

  /**
   * Get video info
   */
  async getVideo(videoId: string): Promise<ParsedResponse> {
    const url = `/api/video/${videoId}/`;
    return this.fetchUrl(url);
  }

  /**
   * Get channel videos
   */
  async getChannelVideos(channelId: string, page: number = 1): Promise<ParsedResponse> {
    const url = `/api/video/person/${channelId}/?page=${page}`;
    return this.fetchUrl(url);
  }

  /**
   * Get TV show info
   */
  async getTvShow(tvId: string): Promise<ParsedResponse> {
    const url = `/api/metainfo/tv/${tvId}/`;
    return this.fetchUrl(url);
  }

  /**
   * Get popular videos
   */
  async getPopularVideos(page: number = 1): Promise<ParsedResponse> {
    const url = `/api/feeds/popular/?page=${page}`;
    return this.fetchUrl(url);
  }

  /**
   * Get recommendations
   */
  async getRecommendations(videoId: string): Promise<ParsedResponse> {
    const url = `/api/video/${videoId}/recommendations/`;
    return this.fetchUrl(url);
  }

  /**
   * Cancel all pending requests
   */
  cancelAllRequests(): void {
    this.abortControllers.forEach(controller => controller.abort());
    this.abortControllers.clear();
    this.requestQueue.clear();
  }

  /**
   * Clear cache
   */
  clearCache(): void {
    this.cache.clear();
  }

  /**
   * Get cache stats
   */
  getCacheStats(): { size: number; keys: string[] } {
    return {
      size: this.cache.size,
      keys: Array.from(this.cache.keys())
    };
  }
}

// Export for different module systems
export {
  RutubeParser,
  EntityType,
  type VideoCard,
  type TvShowCard,
  type ChannelCard,
  type PromoCard,
  type ParsedResponse,
  type PaginationInfo,
  type TabInfo,
  type ResourceInfo,
  type ParserConfig
};

// Default export for CommonJS
export default RutubeParser;
