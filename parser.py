# rutube_parser.py
"""
Universal Rutube API Parser
Version: 1.0.0
One-file solution - just copy and use!

Features:
- Async/await support
- Automatic caching
- Rate limiting
- Retry logic
- Full type hints
- No external dependencies (only aiohttp)

Usage:
    async with RutubeParser() as parser:
        # Search all (videos + channels)
        results = await parser.search("python")
        
        # Search only videos
        videos = await parser.search_videos("python")
        
        # Search only channels (same endpoint, filtered)
        channels = await parser.search_channels("python")
        
        # Get category feed
        movies = await parser.get_category_feed("Фильмы")
        
        # Get video details
        video = await parser.get_video("video_id")
"""

import asyncio
import hashlib
import json
import os
import pickle
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from urllib.parse import urlencode

try:
    import aiohttp
except ImportError:
    raise ImportError("Please install aiohttp: pip install aiohttp")


# ============================================================================
# EXCEPTIONS
# ============================================================================

class RutubeParserError(Exception):
    """Base exception for Rutube parser"""
    pass

class NetworkError(RutubeParserError):
    """Network related errors"""
    pass

class ParseError(RutubeParserError):
    """JSON parsing errors"""
    pass

class RateLimitError(RutubeParserError):
    """Rate limit exceeded"""
    pass


# ============================================================================
# DATA MODELS
# ============================================================================

class EntityType(str, Enum):
    """Type of entity returned from API"""
    FEED = 'FEED'
    CONTAINER = 'CONTAINER'
    VIDEO_LIST = 'VIDEO_LIST'
    VIDEO_ITEM = 'VIDEO_ITEM'
    CHANNEL = 'CHANNEL'
    TV_SHOW = 'TV_SHOW'
    EXTERNAL = 'EXTERNAL'
    UNKNOWN = 'UNKNOWN'
    EMPTY = 'EMPTY'
    PROMO_LIST = 'PROMO_LIST'


@dataclass
class ChannelInfo:
    """Channel information"""
    id: Optional[str]
    name: str
    avatar: Optional[str] = None
    is_verified: bool = False


@dataclass
class VideoStats:
    """Video statistics"""
    views: str
    views_count: int
    likes: Optional[int] = None
    dislikes: Optional[int] = None
    comments: Optional[int] = None


@dataclass
class SeriesInfo:
    """Series/Episode information"""
    season: int
    episode: int
    title: Optional[str] = None


@dataclass
class VideoCard:
    """Video card data model"""
    type: str = 'VIDEO'
    id: str = ''
    title: str = ''
    thumbnail: Optional[str] = None
    preview_gif: Optional[str] = None
    duration: str = '00:00'
    duration_seconds: int = 0
    channel: ChannelInfo = field(default_factory=lambda: ChannelInfo(None, ''))
    stats: VideoStats = field(default_factory=lambda: VideoStats('', 0))
    rating: Optional[str] = None
    is_paid: bool = False
    is_live: bool = False
    description: str = ''
    tags: List[str] = field(default_factory=list)
    url: str = ''
    embed_url: str = ''
    series: Optional[SeriesInfo] = None
    published_at: Optional[datetime] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            'type': self.type,
            'id': self.id,
            'title': self.title,
            'thumbnail': self.thumbnail,
            'duration': self.duration,
            'channel': {
                'id': self.channel.id,
                'name': self.channel.name,
                'avatar': self.channel.avatar
            },
            'stats': {
                'views': self.stats.views,
                'views_count': self.stats.views_count
            },
            'url': self.url,
            'embed_url': self.embed_url
        }


@dataclass
class TvShowCard:
    """TV Show card data model"""
    type: str = 'TV_SHOW'
    id: str = ''
    title: str = ''
    original_title: Optional[str] = None
    poster: Optional[str] = None
    year: Optional[str] = None
    kinopoisk_rating: Optional[float] = None
    imdb_rating: Optional[float] = None
    seasons: int = 0
    episodes: Optional[int] = None
    description: Optional[str] = None
    genres: List[str] = field(default_factory=list)
    url: str = ''


@dataclass
class ChannelCard:
    """Channel card data model"""
    type: str = 'CHANNEL'
    id: str = ''
    name: str = ''
    avatar: Optional[str] = None
    cover: Optional[str] = None
    description: Optional[str] = None
    subscribers: str = '0'
    subscribers_count: int = 0
    videos: int = 0
    views: Optional[int] = None
    is_verified: bool = False
    url: str = ''


@dataclass
class PromoCard:
    """Promo card data model"""
    type: str = 'PROMO'
    id: str = ''
    title: str = ''
    thumbnail: Optional[str] = None
    description: Optional[str] = None
    action_url: Optional[str] = None
    action_type: str = 'LINK'


@dataclass
class PaginationInfo:
    """Pagination information"""
    has_next: bool = False
    next_url: Optional[str] = None
    page: int = 1
    per_page: int = 20
    total: Optional[int] = None


@dataclass
class ParsedResponse:
    """Complete parsed response from API"""
    type: EntityType
    items: List[Union[VideoCard, TvShowCard, ChannelCard, PromoCard]]
    title: Optional[str] = None
    tabs: Optional[List[Dict]] = None
    pagination: Optional[PaginationInfo] = None
    error: Optional[str] = None
    meta: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def has_next(self) -> bool:
        """Check if there is next page"""
        return self.pagination is not None and self.pagination.has_next
    
    @property
    def next_url(self) -> Optional[str]:
        """Get next page URL"""
        return self.pagination.next_url if self.pagination else None
    
    @property
    def is_empty(self) -> bool:
        """Check if response is empty"""
        return self.type == EntityType.EMPTY or len(self.items) == 0
    
    @property
    def videos(self) -> List[VideoCard]:
        """Get only video cards"""
        return [item for item in self.items if isinstance(item, VideoCard)]
    
    @property
    def tv_shows(self) -> List[TvShowCard]:
        """Get only TV show cards"""
        return [item for item in self.items if isinstance(item, TvShowCard)]
    
    @property
    def channels(self) -> List[ChannelCard]:
        """Get only channel cards"""
        return [item for item in self.items if isinstance(item, ChannelCard)]


# ============================================================================
# CONFIGURATION
# ============================================================================

@dataclass
class ParserConfig:
    """Parser configuration"""
    api_base: str = "https://rutube.ru"
    timeout: int = 10
    max_retries: int = 3
    retry_delay: float = 1.0
    enable_cache: bool = True
    cache_ttl: int = 300  # seconds
    cache_dir: str = ".rutube_cache"
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    rate_limit: float = 1.0  # requests per second
    max_concurrent: int = 5


# ============================================================================
# CACHE MANAGER
# ============================================================================

class CacheManager:
    """Simple file-based cache manager"""
    
    def __init__(self, cache_dir: str = ".rutube_cache", ttl: int = 300):
        self.cache_dir = Path(cache_dir)
        self.ttl = ttl
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._memory_cache: Dict[str, tuple] = {}
    
    def _get_cache_path(self, key: str) -> Path:
        """Get cache file path"""
        key_hash = hashlib.md5(key.encode()).hexdigest()
        return self.cache_dir / f"{key_hash}.cache"
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        if key in self._memory_cache:
            value, expiry = self._memory_cache[key]
            if expiry is None or datetime.now() < expiry:
                return value
            del self._memory_cache[key]
        
        path = self._get_cache_path(key)
        if not path.exists():
            return None
        
        try:
            with open(path, 'rb') as f:
                data = pickle.load(f)
            
            if 'expiry' in data and data['expiry']:
                if datetime.now() > data['expiry']:
                    await self.delete(key)
                    return None
            
            self._memory_cache[key] = (data['value'], data.get('expiry'))
            return data['value']
        except Exception:
            return None
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """Set value in cache"""
        ttl = ttl or self.ttl
        expiry = datetime.now() + timedelta(seconds=ttl) if ttl > 0 else None
        
        self._memory_cache[key] = (value, expiry)
        
        path = self._get_cache_path(key)
        try:
            with open(path, 'wb') as f:
                pickle.dump({'value': value, 'expiry': expiry}, f)
        except Exception:
            pass
    
    async def delete(self, key: str):
        """Delete from cache"""
        if key in self._memory_cache:
            del self._memory_cache[key]
        
        path = self._get_cache_path(key)
        if path.exists():
            try:
                path.unlink()
            except Exception:
                pass
    
    async def clear(self):
        """Clear all cache"""
        self._memory_cache.clear()
        for file in self.cache_dir.glob("*.cache"):
            try:
                file.unlink()
            except Exception:
                pass
    
    def get_size(self) -> int:
        """Get cache size"""
        return len(self._memory_cache) + len(list(self.cache_dir.glob("*.cache")))


# ============================================================================
# RATE LIMITER
# ============================================================================

class RateLimiter:
    """Simple rate limiter"""
    
    def __init__(self, requests_per_second: float = 1.0):
        self.rate = requests_per_second
        self.min_interval = 1.0 / requests_per_second if requests_per_second > 0 else 0
        self.last_request_time = 0
        self._lock = asyncio.Lock()
    
    async def acquire(self):
        """Acquire permission to make request"""
        if self.min_interval <= 0:
            return
        
        async with self._lock:
            now = asyncio.get_event_loop().time()
            elapsed = now - self.last_request_time
            if elapsed < self.min_interval:
                await asyncio.sleep(self.min_interval - elapsed)
            self.last_request_time = asyncio.get_event_loop().time()


# ============================================================================
# MAIN PARSER CLASS
# ============================================================================

class RutubeParser:
    """
    Universal Rutube API Parser
    
    Usage:
        async with RutubeParser() as parser:
            # Search all (videos + channels)
            results = await parser.search("python")
            for item in results.items:
                if isinstance(item, VideoCard):
                    print(f"Video: {item.title}")
                elif isinstance(item, ChannelCard):
                    print(f"Channel: {item.name}")
            
            # Search only videos
            videos = await parser.search_videos("python")
            
            # Search only channels (same endpoint, filtered)
            channels = await parser.search_channels("python")
            
            # Get category feed
            movies = await parser.get_category_feed("Фильмы")
            
            # Get video details
            video = await parser.get_video("video_id_here")
            
            # Load next page
            if results.has_next:
                next_page = await parser.load_next(results)
    """
    
    def __init__(self, config: Optional[ParserConfig] = None):
        self.config = config or ParserConfig()
        self._session: Optional[aiohttp.ClientSession] = None
        self._cache = CacheManager(self.config.cache_dir, self.config.cache_ttl)
        self._rate_limiter = RateLimiter(self.config.rate_limit)
        self._semaphore = asyncio.Semaphore(self.config.max_concurrent)
        
        # Category mapping
        self.category_map = {
            'Фильмы': 'movies',
            'Сериалы': 'serials',
            'Телепередачи': 'tv',
            'Музыка': 'music',
            'Мультфильмы': 'cartoons',
            'Спорт': 'sport',
            'Юмор': 'umor',
            'Видеоигры': 'games',
            'Технологии': 'technologies',
            'Блоги': 'blogs',
            'Новости': 'news',
            'Путешествия': 'travel',
            'Кулинария': 'food',
            'Обучение': 'education'
        }
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session"""
        if self._session is None or self._session.closed:
            headers = {
                'User-Agent': self.config.user_agent,
                'Accept': 'application/json, text/plain, */*',
                'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8',
                'Referer': 'https://rutube.ru/'
            }
            connector = aiohttp.TCPConnector(limit=self.config.max_concurrent)
            self._session = aiohttp.ClientSession(headers=headers, connector=connector)
        return self._session
    
    def _normalize_url(self, url: str) -> str:
        """Normalize URL to full API URL"""
        if not url:
            return ""
        
        if url.startswith('http'):
            if 'rutube.ru' in url:
                path = re.sub(r'https?://rutube\.ru', '', url)
                if path.startswith('/api/'):
                    return f"{self.config.api_base}{path}"
                return f"{self.config.api_base}/api{path}"
            return url
        
        if url.startswith('/api/'):
            return f"{self.config.api_base}{url}"
        
        if url.startswith('/'):
            return f"{self.config.api_base}/api{url}"
        
        return f"{self.config.api_base}/api/{url}"
    
    def _format_duration(self, seconds: int) -> str:
        """Format duration from seconds to string"""
        if seconds <= 0:
            return "00:00"
        
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        
        if hours > 0:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        return f"{minutes:02d}:{secs:02d}"
    
    def _format_count(self, num: int) -> str:
        """Format count with K/M suffix"""
        if num >= 1_000_000:
            return f"{num/1_000_000:.1f}M"
        if num >= 1_000:
            return f"{num/1_000:.1f}K"
        return str(num)
    
    def _parse_series_info(self, title: str) -> Optional[SeriesInfo]:
        """Parse series information from title"""
        patterns = [
            (r's(\d+)e(\d+)', 'international'),
            (r'(\d+)x(\d+)', 'x_format'),
            (r'(\d+)\s+сезон\s+(\d+)\s+серия', 'russian_full'),
            (r'сезон\s+(\d+)\s+серия\s+(\d+)', 'russian_reversed'),
            (r'(\d+)\s*сезон\s*(\d+)\s*серия', 'russian_compact'),
            (r'эпизод\s+(\d+)', 'episode_only'),
            (r'выпуск\s+(\d+)', 'release_only')
        ]
        
        for pattern, _ in patterns:
            match = re.search(pattern, title, re.IGNORECASE)
            if match:
                groups = match.groups()
                if len(groups) >= 2:
                    return SeriesInfo(
                        season=int(groups[0]),
                        episode=int(groups[1])
                    )
                elif len(groups) == 1:
                    return SeriesInfo(
                        season=1,
                        episode=int(groups[0])
                    )
        return None
    
    def _normalize_video(self, data: Dict) -> VideoCard:
        """Normalize video data"""
        # Check for nested object (search results format)
        obj = data.get('object', data)
        
        video_id = obj.get('id') or obj.get('video_id') or obj.get('code', '')
        title = obj.get('title') or obj.get('name', 'Untitled')
        
        # Get channel info
        author = obj.get('author', {})
        channel = ChannelInfo(
            id=author.get('id') or obj.get('channel_id'),
            name=author.get('name') or obj.get('feed_name') or obj.get('channel', 'Unknown Channel'),
            avatar=author.get('avatar_url'),
            is_verified=obj.get('is_verified', False)
        )
        
        # Get stats
        views_count = obj.get('views_count') or obj.get('hits') or 0
        stats = VideoStats(
            views=self._format_count(views_count),
            views_count=views_count,
            likes=obj.get('likes_count'),
            dislikes=obj.get('dislikes_count'),
            comments=obj.get('comments_count')
        )
        
        # Get duration
        duration_seconds = obj.get('duration', 0)
        if isinstance(duration_seconds, str):
            try:
                duration_seconds = int(duration_seconds)
            except ValueError:
                duration_seconds = 0
        
        # Get thumbnail
        thumbnail = obj.get('thumbnail_url') or obj.get('picture_url') or obj.get('poster_url')
        
        # Get publish date
        published_at = None
        pub_str = obj.get('publication_ts') or obj.get('created_ts')
        if pub_str:
            try:
                published_at = datetime.fromisoformat(pub_str.replace('Z', '+00:00'))
            except ValueError:
                pass
        
        video = VideoCard(
            id=str(video_id) if video_id else '',
            title=title,
            thumbnail=thumbnail,
            preview_gif=obj.get('preview_url'),
            duration=self._format_duration(duration_seconds),
            duration_seconds=duration_seconds,
            channel=channel,
            stats=stats,
            rating=obj.get('pg_rating', {}).get('age') if isinstance(obj.get('pg_rating'), dict) else None,
            is_paid=obj.get('is_paid', False),
            is_live=obj.get('is_live', False),
            description=obj.get('description', ''),
            tags=obj.get('tags', []),
            url=f"https://rutube.ru/video/{video_id}/" if video_id else '',
            embed_url=f"https://rutube.ru/play/embed/{video_id}/" if video_id else '',
            published_at=published_at
        )
        
        series_info = self._parse_series_info(title)
        if series_info:
            video.series = series_info
        
        return video
    
    def _normalize_tv_show(self, data: Dict) -> TvShowCard:
        """Normalize TV show data"""
        obj = data.get('object', data)
        
        images = obj.get('images', [])
        poster = obj.get('poster_url')
        if not poster and images and len(images) > 0:
            poster = images[0].get('image')
        
        tv_id = obj.get('id', '')
        
        return TvShowCard(
            id=str(tv_id) if tv_id else '',
            title=obj.get('title') or obj.get('name', 'Untitled'),
            original_title=obj.get('original_title'),
            poster=poster,
            year=obj.get('year_start') or obj.get('year'),
            kinopoisk_rating=obj.get('kinopoisk_rating'),
            imdb_rating=obj.get('imdb_rating'),
            seasons=obj.get('seasons_count', 0),
            episodes=obj.get('episodes_count'),
            description=obj.get('description'),
            genres=obj.get('genres', []),
            url=f"https://rutube.ru/metainfo/tv/{tv_id}/" if tv_id else ''
        )
    
    def _normalize_channel(self, data: Dict) -> ChannelCard:
        """
        Normalize channel data from search results.
        Channels come from the SAME endpoint /api/search/video/
        with content_type.model = "person"
        """
        # Check for nested object structure (search results format)
        obj = data.get('object', data)
        
        # Get channel ID from various possible fields
        channel_id = (
            obj.get('id') or 
            obj.get('person_id') or 
            obj.get('channel_id') or
            data.get('id')
        )
        
        # Get channel name
        channel_name = (
            obj.get('name') or 
            obj.get('title') or 
            obj.get('username') or
            obj.get('channel_name') or
            data.get('name', 'Unknown Channel')
        )
        
        # Get subscribers count
        subscribers_count = (
            obj.get('subscribers_count') or 
            obj.get('subscribers') or
            data.get('subscribers_count', 0)
        )
        if isinstance(subscribers_count, str):
            try:
                subscribers_count = int(subscribers_count)
            except ValueError:
                subscribers_count = 0
        
        # Get avatar from various possible fields
        avatar = (
            obj.get('user_channel_image') or
            obj.get('avatar_url') or
            obj.get('avatar') or
            obj.get('icon') or
            obj.get('picture') or
            data.get('avatar_url')
        )
        
        # Get cover image
        cover = (
            obj.get('cover_url') or
            obj.get('cover')
        )
        
        # Get description
        description = (
            obj.get('description') or
            obj.get('about')
        )
        
        # Get video count
        videos_count = (
            obj.get('video_count') or 
            obj.get('videos_count') or
            data.get('video_count', 0)
        )
        
        # Get verification status
        is_verified = (
            obj.get('is_verified') or
            obj.get('verified', False)
        )
        
        # Get total views
        views = obj.get('views_count') or obj.get('total_views')
        
        return ChannelCard(
            id=str(channel_id) if channel_id else '',
            name=channel_name,
            avatar=avatar,
            cover=cover,
            description=description,
            subscribers=self._format_count(subscribers_count),
            subscribers_count=subscribers_count,
            videos=videos_count if isinstance(videos_count, int) else 0,
            views=views,
            is_verified=bool(is_verified),
            url=f"https://rutube.ru/channel/{channel_id}/" if channel_id else ''
        )
    
    def _normalize_promo(self, data: Dict) -> PromoCard:
        """Normalize promo data"""
        obj = data.get('object', data)
        
        action_url = (
            obj.get('button', {}).get('button_url') or 
            obj.get('target') or 
            obj.get('link') or 
            obj.get('url') or
            data.get('target')
        )
        
        action_type = 'LINK'
        if action_url:
            if '/video/' in action_url:
                action_type = 'VIDEO'
            elif '/channel/' in action_url:
                action_type = 'CHANNEL'
            elif '/tv/' in action_url:
                action_type = 'TV_SHOW'
            
            if action_url.startswith('/') and not action_url.startswith('/api/'):
                action_url = f"/api{action_url}"
        
        return PromoCard(
            id=str(obj.get('id', '')),
            title=obj.get('title', 'Untitled'),
            thumbnail=obj.get('picture') or obj.get('thumbnail_url') or obj.get('image'),
            description=obj.get('description'),
            action_url=action_url,
            action_type=action_type
        )
    
    def _normalize_item(self, item: Dict) -> Union[VideoCard, TvShowCard, ChannelCard, PromoCard]:
        """
        Normalize any item based on its type.
        Important: Channels and Videos come from the SAME endpoint!
        """
        content_type = item.get('content_type', {})
        model = content_type.get('model') if isinstance(content_type, dict) else None
        
        obj = item.get('object', item)
        
        # Check for channel (person model or channel-specific fields)
        if model == 'person' or model == 'userchannel':
            return self._normalize_channel(item)
        
        # Check for channel by fields (search results often have these)
        if 'subscribers_count' in obj or 'subscribers' in obj:
            if 'duration' not in obj:  # Make sure it's not a video with subscribers field
                return self._normalize_channel(item)
        
        # Check for TV show
        if model == 'tv' or 'seasons_count' in obj or obj.get('type') == 'tv':
            return self._normalize_tv_show(item)
        
        # Check for video
        if 'duration' in obj or 'video_url' in obj or 'video_id' in obj or model == 'video':
            return self._normalize_video(item)
        
        # Default to promo
        return self._normalize_promo(item)
    
    def _get_pagination(self, data: Dict) -> PaginationInfo:
        """Extract pagination info from response"""
        next_url = data.get('next')
        if next_url and isinstance(next_url, str):
            next_url = self._normalize_url(next_url)
        
        return PaginationInfo(
            has_next=bool(data.get('has_next') or data.get('next')),
            next_url=next_url,
            page=data.get('page', 1),
            per_page=data.get('per_page', 20),
            total=data.get('total')
        )
    
    async def _parse_response(self, data: Dict, source_url: str) -> ParsedResponse:
        """Parse API response"""
        # Feed with tabs
        if 'tabs' in data and isinstance(data['tabs'], list):
            tabs = []
            for tab in data.get('tabs', []):
                resources = []
                for res in tab.get('resources', []):
                    resources.append({
                        'name': res.get('name', 'Resource'),
                        'url': self._normalize_url(res.get('url', '')),
                        'type': EntityType.UNKNOWN
                    })
                tabs.append({
                    'id': tab.get('id'),
                    'name': tab.get('name', 'Tab'),
                    'resources': resources
                })
            
            return ParsedResponse(
                type=EntityType.FEED,
                items=[],
                title=data.get('name', 'Каталог'),
                tabs=tabs,
                meta={'source_url': source_url, 'timestamp': datetime.now().isoformat()}
            )
        
        # Paginated results (search, feeds, etc.)
        if 'results' in data:
            results = data.get('results', [])
            
            if not results:
                return ParsedResponse(
                    type=EntityType.EMPTY,
                    items=[],
                    pagination=self._get_pagination(data),
                    meta={'source_url': source_url, 'timestamp': datetime.now().isoformat()}
                )
            
            # Check if promo group
            is_promo = 'promogroup' in source_url
            
            items = []
            for item in results:
                if is_promo:
                    items.append(self._normalize_promo(item))
                else:
                    items.append(self._normalize_item(item))
            
            # Determine response type
            if items:
                first = items[0]
                if isinstance(first, PromoCard):
                    resp_type = EntityType.PROMO_LIST
                elif isinstance(first, TvShowCard):
                    resp_type = EntityType.TV_SHOW
                elif isinstance(first, ChannelCard):
                    resp_type = EntityType.CHANNEL
                else:
                    resp_type = EntityType.VIDEO_LIST
            else:
                resp_type = EntityType.VIDEO_LIST
            
            return ParsedResponse(
                type=resp_type,
                items=items,
                pagination=self._get_pagination(data),
                meta={'source_url': source_url, 'timestamp': datetime.now().isoformat()}
            )
        
        # Single video
        if 'id' in data and ('video_url' in data or 'duration' in data):
            return ParsedResponse(
                type=EntityType.VIDEO_ITEM,
                items=[self._normalize_video(data)],
                meta={'source_url': source_url, 'timestamp': datetime.now().isoformat()}
            )
        
        # Unknown response
        return ParsedResponse(
            type=EntityType.UNKNOWN,
            items=[],
            error='Unrecognized response structure',
            meta={'source_url': source_url, 'timestamp': datetime.now().isoformat()}
        )
    
    async def _make_request(self, url: str, skip_cache: bool = False) -> Dict:
        """Make HTTP request with retries and caching"""
        normalized_url = self._normalize_url(url)
        
        if self.config.enable_cache and not skip_cache:
            cached = await self._cache.get(normalized_url)
            if cached:
                return cached
        
        await self._rate_limiter.acquire()
        
        last_error = None
        for attempt in range(self.config.max_retries):
            try:
                async with self._semaphore:
                    session = await self._get_session()
                    async with session.get(normalized_url, timeout=self.config.timeout) as response:
                        if response.status == 429:
                            raise RateLimitError("Rate limit exceeded")
                        
                        if response.status != 200:
                            raise NetworkError(f"HTTP {response.status}: {response.reason}")
                        
                        data = await response.json()
                        
                        if self.config.enable_cache:
                            await self._cache.set(normalized_url, data)
                        
                        return data
                        
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                last_error = NetworkError(f"Network error: {str(e)}")
            except RateLimitError as e:
                last_error = e
                await asyncio.sleep(self.config.retry_delay * (attempt + 1) * 2)
            
            if attempt < self.config.max_retries - 1:
                await asyncio.sleep(self.config.retry_delay * (attempt + 1))
        
        raise last_error or NetworkError(f"Failed after {self.config.max_retries} attempts")
    
    async def fetch(self, url: str, skip_cache: bool = False) -> ParsedResponse:
        """Fetch and parse URL"""
        try:
            data = await self._make_request(url, skip_cache)
            return await self._parse_response(data, url)
        except RutubeParserError:
            raise
        except Exception as e:
            return ParsedResponse(
                type=EntityType.UNKNOWN,
                items=[],
                error=str(e),
                meta={'source_url': url, 'timestamp': datetime.now().isoformat()}
            )
    
    async def load_next(self, response: ParsedResponse) -> Optional[ParsedResponse]:
        """Load next page of results"""
        if not response.has_next or not response.next_url:
            return None
        return await self.fetch(response.next_url, skip_cache=True)
    
    async def search(self, query: str, page: int = 1, search_type: str = "all") -> ParsedResponse:
        """
        Search videos and channels (they come from the SAME endpoint!)
        
        Args:
            query: Search query
            page: Page number
            search_type: "all", "video", or "channel"
        """
        encoded_query = query.replace(' ', '+')
        # Единый эндпоинт для поиска ВСЕГО (видео + каналы)
        url = f"/api/search/video/?query={encoded_query}&page={page}"
        
        result = await self.fetch(url)
        
        # Пост-фильтрация по типу если нужно
        if search_type == "video":
            result.items = [item for item in result.items if isinstance(item, VideoCard)]
        elif search_type == "channel":
            result.items = [item for item in result.items if isinstance(item, ChannelCard)]
        
        return result
    
    async def search_videos(self, query: str, page: int = 1) -> ParsedResponse:
        """Search only videos"""
        return await self.search(query, page, search_type="video")
    
    async def search_channels(self, query: str, page: int = 1) -> ParsedResponse:
        """
        Search only channels.
        IMPORTANT: Uses the SAME endpoint as video search!
        Channels are filtered by content_type.model = "person"
        """
        return await self.search(query, page, search_type="channel")
    
    async def get_category_feed(self, category: str, page: int = 1) -> ParsedResponse:
        """Get category feed"""
        slug = self.category_map.get(category, category.lower())
        url = f"/api/feeds/{slug}/?page={page}"
        return await self.fetch(url)
    
    async def get_video(self, video_id: str) -> ParsedResponse:
        """Get video details"""
        url = f"/api/video/{video_id}/"
        return await self.fetch(url)
    
    async def get_channel_videos(self, channel_id: str, page: int = 1) -> ParsedResponse:
        """Get channel videos"""
        url = f"/api/video/person/{channel_id}/?page={page}"
        return await self.fetch(url)
    
    async def get_tv_show(self, tv_id: str) -> ParsedResponse:
        """Get TV show details"""
        url = f"/api/metainfo/tv/{tv_id}/"
        return await self.fetch(url)
    
    async def get_tv_show_episodes(self, tv_id: str, page: int = 1) -> ParsedResponse:
        """Get TV show episodes"""
        url = f"/api/metainfo/tv/{tv_id}/video/?page={page}"
        return await self.fetch(url)
    
    async def get_popular_videos(self, page: int = 1) -> ParsedResponse:
        """Get popular videos"""
        url = f"/api/feeds/popular/?page={page}"
        return await self.fetch(url)
    
    async def get_recommendations(self, video_id: str) -> ParsedResponse:
        """Get video recommendations"""
        url = f"/api/video/{video_id}/recommendations/"
        return await self.fetch(url)
    
    async def get_new_videos(self, page: int = 1) -> ParsedResponse:
        """Get newest videos"""
        url = f"/api/feeds/new/?page={page}"
        return await self.fetch(url)
    
    def clear_cache(self):
        """Clear all cached data"""
        asyncio.create_task(self._cache.clear())
    
    async def close(self):
        """Close session and cleanup"""
        if self._session and not self._session.closed:
            await self._session.close()
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()


# ============================================================================
# SYNC WRAPPER (for non-async code)
# ============================================================================

class SyncRutubeParser:
    """
    Synchronous wrapper for RutubeParser
    
    Usage:
        parser = SyncRutubeParser()
        
        # Search all
        results = parser.search("python")
        for item in results.items:
            if isinstance(item, VideoCard):
                print(f"Video: {item.title}")
            elif isinstance(item, ChannelCard):
                print(f"Channel: {item.name}")
        
        # Search only channels (same endpoint)
        channels = parser.search_channels("python")
        for channel in channels.channels:
            print(f"Channel: {channel.name} - {channel.subscribers}")
        
        parser.close()
    """
    
    def __init__(self, config: Optional[ParserConfig] = None):
        self.config = config or ParserConfig()
        self._loop = None
        self._parser = None
    
    def _get_loop(self):
        """Get or create event loop"""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop
    
    def _run_async(self, coro):
        """Run async coroutine in sync context"""
        loop = self._get_loop()
        return loop.run_until_complete(coro)
    
    def _get_parser(self) -> RutubeParser:
        """Get or create parser instance"""
        if self._parser is None:
            self._parser = RutubeParser(self.config)
            self._run_async(self._parser.__aenter__())
        return self._parser
    
    def search(self, query: str, page: int = 1, search_type: str = "all") -> ParsedResponse:
        """Search videos and channels (sync)"""
        return self._run_async(self._get_parser().search(query, page, search_type))
    
    def search_videos(self, query: str, page: int = 1) -> ParsedResponse:
        """Search only videos (sync)"""
        return self._run_async(self._get_parser().search_videos(query, page))
    
    def search_channels(self, query: str, page: int = 1) -> ParsedResponse:
        """Search only channels - uses SAME endpoint as video search (sync)"""
        return self._run_async(self._get_parser().search_channels(query, page))
    
    def get_category_feed(self, category: str, page: int = 1) -> ParsedResponse:
        """Get category feed (sync)"""
        return self._run_async(self._get_parser().get_category_feed(category, page))
    
    def get_video(self, video_id: str) -> ParsedResponse:
        """Get video details (sync)"""
        return self._run_async(self._get_parser().get_video(video_id))
    
    def get_channel_videos(self, channel_id: str, page: int = 1) -> ParsedResponse:
        """Get channel videos (sync)"""
        return self._run_async(self._get_parser().get_channel_videos(channel_id, page))
    
    def get_popular_videos(self, page: int = 1) -> ParsedResponse:
        """Get popular videos (sync)"""
        return self._run_async(self._get_parser().get_popular_videos(page))
    
    def clear_cache(self):
        """Clear cache"""
        self._run_async(self._get_parser().clear_cache())
    
    def close(self):
        """Close parser"""
        if self._parser:
            self._run_async(self._parser.close())
            self._parser = None


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

async def async_example():
    """Async usage example"""
    async with RutubeParser() as parser:
        # Search all (videos + channels from same endpoint)
        print("=== Search 'python' (all) ===")
        results = await parser.search("python")
        
        print(f"Total items: {len(results.items)}")
        print(f"Videos: {len(results.videos)}")
        print(f"Channels: {len(results.channels)}")
        
        for video in results.videos[:3]:
            print(f"  📹 Video: {video.title}")
            print(f"     Channel: {video.channel.name}")
            print(f"     Duration: {video.duration}")
        
        for channel in results.channels[:3]:
            print(f"  📺 Channel: {channel.name}")
            print(f"     Subscribers: {channel.subscribers}")
            print(f"     Videos: {channel.videos}")
        
        # Search only channels
        print("\n=== Search 'python' (only channels) ===")
        channels = await parser.search_channels("python")
        for channel in channels.channels[:5]:
            print(f"  📺 {channel.name} - {channel.subscribers}")
        
        # Search only videos
        print("\n=== Search 'python' (only videos) ===")
        videos = await parser.search_videos("python")
        for video in videos.videos[:5]:
            print(f"  📹 {video.title}")
        
        # Get category feed
        print("\n=== Category: Фильмы ===")
        movies = await parser.get_category_feed("Фильмы")
        for movie in movies.videos[:5]:
            print(f"  🎬 {movie.title}")
        
        # Pagination example
        if results.has_next:
            print(f"\n=== Next page ===")
            next_page = await parser.load_next(results)
            print(f"Next page items: {len(next_page.items)}")


def sync_example():
    """Sync usage example"""
    parser = SyncRutubeParser()
    
    print("=== Sync example ===")
    
    # Search channels (same endpoint as video search)
    channels = parser.search_channels("tech")
    print(f"Found {len(channels.channels)} channels:")
    for channel in channels.channels[:5]:
        print(f"  📺 {channel.name} - {channel.subscribers}")
    
    # Search videos
    videos = parser.search_videos("tutorial")
    print(f"\nFound {len(videos.videos)} videos:")
    for video in videos.videos[:5]:
        print(f"  📹 {video.title}")
    
    parser.close()


if __name__ == "__main__":
    # Run async example
    asyncio.run(async_example())
    
    # Or run sync example
    # sync_example()
