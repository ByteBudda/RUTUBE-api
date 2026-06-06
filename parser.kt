// RutubeParser.kt
package com.rutube.parser

import kotlinx.coroutines.*
import kotlinx.serialization.*
import kotlinx.serialization.json.*
import okhttp3.*
import okhttp3.logging.HttpLoggingInterceptor
import java.io.IOException
import java.text.SimpleDateFormat
import java.util.*
import java.util.concurrent.TimeUnit
import kotlin.math.floor

/**
 * Main parser class for Rutube API
 */
class RutubeParser(
    private val config: Config = Config()
) {
    data class Config(
        val apiBase: String = "https://rutube.ru",
        val timeoutSeconds: Long = 10,
        val maxRetries: Int = 3,
        val enableCache: Boolean = true,
        val cacheTTLSeconds: Long = 300,
        val userAgent: String = "RutubeParser/1.0"
    )
    
    enum class EntityType {
        FEED, CONTAINER, VIDEO_LIST, VIDEO_ITEM, CHANNEL, TV_SHOW, EXTERNAL, UNKNOWN, EMPTY, PROMO_LIST
    }
    
    @Serializable
    data class VideoCard(
        val type: String = "VIDEO",
        val id: String,
        val title: String,
        val thumbnail: String?,
        val previewGif: String?,
        val duration: String,
        val durationSeconds: Int,
        val channel: ChannelInfo,
        val stats: VideoStats,
        val rating: RatingInfo,
        val isPaid: Boolean,
        val isLive: Boolean,
        val description: String,
        val tags: List<String>,
        val url: String,
        val embedUrl: String,
        val series: SeriesInfo? = null
    )
    
    @Serializable
    data class ChannelInfo(
        val id: String?,
        val name: String,
        val avatar: String?
    )
    
    @Serializable
    data class VideoStats(
        val views: String,
        val viewsCount: Long,
        val published: String,
        val publishedTimestamp: Long
    )
    
    @Serializable
    data class RatingInfo(
        val age: String?,
        val likes: Long?,
        val dislikes: Long?
    )
    
    @Serializable
    data class SeriesInfo(
        val season: Int,
        val episode: Int
    )
    
    @Serializable
    data class TvShowCard(
        val type: String = "TV_SHOW",
        val id: String,
        val title: String,
        val originalTitle: String?,
        val poster: String?,
        val year: String?,
        val kinopoiskRating: Double?,
        val imdbRating: Double?,
        val seasons: Int,
        val episodes: Int?,
        val description: String?,
        val genres: List<String>,
        val url: String
    )
    
    @Serializable
    data class ChannelCard(
        val type: String = "CHANNEL",
        val id: String,
        val name: String,
        val avatar: String?,
        val cover: String?,
        val description: String?,
        val subscribers: String,
        val subscribersCount: Long,
        val videos: Int,
        val views: Long?,
        val isVerified: Boolean,
        val url: String
    )
    
    @Serializable
    data class PromoCard(
        val type: String = "PROMO",
        val id: String,
        val title: String,
        val thumbnail: String?,
        val description: String?,
        val actionUrl: String?,
        val actionType: String
    )
    
    @Serializable
    data class ParsedResponse(
        val type: EntityType,
        val items: List<Any>,
        val title: String? = null,
        val tabs: List<TabInfo>? = null,
        val hasNext: Boolean = false,
        val nextUrl: String? = null,
        val page: Int = 1,
        val total: Int? = null,
        val error: String? = null,
        val meta: ResponseMeta? = null
    )
    
    @Serializable
    data class TabInfo(
        val id: Int,
        val name: String,
        val resources: List<ResourceInfo>
    )
    
    @Serializable
    data class ResourceInfo(
        val name: String,
        val url: String?,
        val type: EntityType,
        val meta: Map<String, Any>
    )
    
    @Serializable
    data class ResponseMeta(
        val sourceUrl: String,
        val timestamp: Long,
        val cached: Boolean = false
    )
    
    private val client: OkHttpClient
    private val cache = mutableMapOf<String, CacheEntry>()
    private val json = Json { ignoreUnknownKeys = true }
    
    data class CacheEntry(
        val data: ParsedResponse,
        val timestamp: Long
    )
    
    init {
        val loggingInterceptor = HttpLoggingInterceptor().apply {
            level = if (config.enableCache) HttpLoggingInterceptor.Level.BASIC else HttpLoggingInterceptor.Level.NONE
        }
        
        client = OkHttpClient.Builder()
            .connectTimeout(config.timeoutSeconds, TimeUnit.SECONDS)
            .readTimeout(config.timeoutSeconds, TimeUnit.SECONDS)
            .writeTimeout(config.timeoutSeconds, TimeUnit.SECONDS)
            .addInterceptor(loggingInterceptor)
            .addInterceptor { chain ->
                val original = chain.request()
                val request = original.newBuilder()
                    .header("User-Agent", config.userAgent)
                    .header("Accept", "application/json, text/plain, */*")
                    .header("Accept-Language", "ru-RU,ru;q=0.9,en-US;q=0.8")
                    .header("Referer", "https://rutube.ru/")
                    .method(original.method, original.body)
                    .build()
                chain.proceed(request)
            }
            .build()
    }
    
    /**
     * Normalize URL to full API URL
     */
    private fun normalizeUrl(url: String): String {
        if (url.isEmpty()) return ""
        
        return when {
            url.startsWith("http") -> {
                if (url.contains("rutube.ru")) {
                    val path = url.replace(Regex("https?://rutube\\.ru"), "")
                    if (path.startsWith("/api/")) {
                        "${config.apiBase}$path"
                    } else {
                        "${config.apiBase}/api$path"
                    }
                } else {
                    url
                }
            }
            url.startsWith("/api/") -> "${config.apiBase}$url"
            url.startsWith("/") -> "${config.apiBase}/api$url"
            else -> "${config.apiBase}/api/$url"
        }
    }
    
    /**
     * Format duration from seconds to string
     */
    private fun formatDuration(seconds: Int): String {
        if (seconds <= 0) return "00:00"
        
        val hours = seconds / 3600
        val minutes = (seconds % 3600) / 60
        val secs = seconds % 60
        
        return if (hours > 0) {
            String.format("%d:%02d:%02d", hours, minutes, secs)
        } else {
            String.format("%02d:%02d", minutes, secs)
        }
    }
    
    /**
     * Format count with K/M suffix
     */
    private fun formatCount(num: Long): String {
        return when {
            num >= 1_000_000 -> String.format("%.1fM", num / 1_000_000.0)
            num >= 1_000 -> String.format("%.1fK", num / 1_000.0)
            else -> num.toString()
        }
    }
    
    /**
     * Parse date string to timestamp
     */
    private fun parseDate(dateString: String): Long {
        if (dateString.isEmpty()) return System.currentTimeMillis()
        
        return try {
            val formats = listOf(
                "yyyy-MM-dd'T'HH:mm:ss",
                "yyyy-MM-dd HH:mm:ss",
                "yyyy-MM-dd"
            )
            
            for (format in formats) {
                try {
                    val sdf = SimpleDateFormat(format, Locale.US)
                    sdf.timeZone = TimeZone.getTimeZone("UTC")
                    return sdf.parse(dateString)?.time ?: System.currentTimeMillis()
                } catch (e: Exception) {
                    // Try next format
                }
            }
            System.currentTimeMillis()
        } catch (e: Exception) {
            System.currentTimeMillis()
        }
    }
    
    /**
     * Format date for display
     */
    private fun formatDate(timestamp: Long): String {
        val date = Date(timestamp)
        val now = Date()
        val diff = now.time - timestamp
        
        return when {
            diff < 24 * 60 * 60 * 1000 -> {
                val hours = floor(diff / (60.0 * 60 * 1000)).toInt()
                if (hours < 1) {
                    val minutes = floor(diff / (60.0 * 1000)).toInt()
                    "$minutes минут назад"
                } else {
                    "$hours часов назад"
                }
            }
            diff < 7 * 24 * 60 * 60 * 1000 -> {
                val days = floor(diff / (24.0 * 60 * 60 * 1000)).toInt()
                "$days дней назад"
            }
            else -> {
                val sdf = SimpleDateFormat("d MMM yyyy", Locale("ru"))
                sdf.format(date)
            }
        }
    }
    
    /**
     * Parse series info from title
     */
    private fun parseSeriesInfo(title: String): SeriesInfo? {
        val patterns = listOf(
            Regex("""s(\d+)e(\d+)""", RegexOption.IGNORE_CASE),
            Regex("""(\d+)x(\d+)""", RegexOption.IGNORE_CASE),
            Regex("""(\d+)\s+сезон\s+(\d+)\s+серия""", RegexOption.IGNORE_CASE),
            Regex("""сезон\s+(\d+)\s+серия\s+(\d+)""", RegexOption.IGNORE_CASE)
        )
        
        for (pattern in patterns) {
            val match = pattern.find(title)
            if (match != null && match.groupValues.size >= 3) {
                return SeriesInfo(
                    season = match.groupValues[1].toIntOrNull() ?: 1,
                    episode = match.groupValues[2].toIntOrNull() ?: 1
                )
            }
        }
        
        return null
    }
    
    /**
     * Normalize video data
     */
    private fun normalizeVideo(data: JsonElement): VideoCard {
        val obj = data.jsonObject
        val id = obj["id"]?.jsonPrimitive?.content ?: 
                 obj["video_id"]?.jsonPrimitive?.content ?: 
                 obj["code"]?.jsonPrimitive?.content ?: ""
        
        val title = obj["title"]?.jsonPrimitive?.content ?: 
                    obj["name"]?.jsonPrimitive?.content ?: "Untitled"
        
        val author = obj["author"]?.jsonObject ?: JsonObject(emptyMap())
        val channelId = author["id"]?.jsonPrimitive?.content ?:
                        obj["channel_id"]?.jsonPrimitive?.content
        val channelName = author["name"]?.jsonPrimitive?.content ?:
                          obj["feed_name"]?.jsonPrimitive?.content ?:
                          obj["channel"]?.jsonPrimitive?.content ?: "Unknown Channel"
        
        val viewsCount = obj["views_count"]?.jsonPrimitive?.long ?:
                         obj["hits"]?.jsonPrimitive?.long ?: 0L
        
        val durationSeconds = obj["duration"]?.jsonPrimitive?.int ?: 0
        val duration = formatDuration(durationSeconds)
        
        val publishedTimestamp = parseDate(
            obj["publication_ts"]?.jsonPrimitive?.content ?:
            obj["created_ts"]?.jsonPrimitive?.content ?: ""
        )
        
        val seriesInfo = parseSeriesInfo(title)
        
        return VideoCard(
            id = id,
            title = title,
            thumbnail = obj["thumbnail_url"]?.jsonPrimitive?.content ?:
                        obj["picture_url"]?.jsonPrimitive?.content ?:
                        obj["poster_url"]?.jsonPrimitive?.content,
            previewGif = obj["preview_url"]?.jsonPrimitive?.content,
            duration = duration,
            durationSeconds = durationSeconds,
            channel = ChannelInfo(
                id = channelId,
                name = channelName,
                avatar = author["avatar_url"]?.jsonPrimitive?.content
            ),
            stats = VideoStats(
                views = formatCount(viewsCount),
                viewsCount = viewsCount,
                published = formatDate(publishedTimestamp),
                publishedTimestamp = publishedTimestamp
            ),
            rating = RatingInfo(
                age = obj["pg_rating"]?.jsonObject?.get("age")?.jsonPrimitive?.content,
                likes = null,
                dislikes = null
            ),
            isPaid = obj["is_paid"]?.jsonPrimitive?.boolean ?: false,
            isLive = obj["is_live"]?.jsonPrimitive?.boolean ?: false,
            description = obj["description"]?.jsonPrimitive?.content ?: "",
            tags = emptyList(),
            url = "https://rutube.ru/video/$id/",
            embedUrl = "https://rutube.ru/play/embed/$id/",
            series = seriesInfo
        )
    }
    
    /**
     * Normalize TV show data
     */
    private fun normalizeTvShow(data: JsonElement): TvShowCard {
        val obj = data.jsonObject
        val images = obj["images"]?.jsonArray ?: JsonArray(emptyList())
        val poster = obj["poster_url"]?.jsonPrimitive?.content ?:
                     images.firstOrNull()?.jsonObject?.get("image")?.jsonPrimitive?.content
        
        return TvShowCard(
            id = obj["id"]?.jsonPrimitive?.content ?: "",
            title = obj["title"]?.jsonPrimitive?.content ?:
                    obj["name"]?.jsonPrimitive?.content ?: "Untitled",
            originalTitle = obj["original_title"]?.jsonPrimitive?.content,
            poster = poster,
            year = obj["year_start"]?.jsonPrimitive?.content ?:
                   obj["year"]?.jsonPrimitive?.content,
            kinopoiskRating = obj["kinopoisk_rating"]?.jsonPrimitive?.double,
            imdbRating = obj["imdb_rating"]?.jsonPrimitive?.double,
            seasons = obj["seasons_count"]?.jsonPrimitive?.int ?: 0,
            episodes = obj["episodes_count"]?.jsonPrimitive?.int,
            description = obj["description"]?.jsonPrimitive?.content,
            genres = emptyList(),
            url = "https://rutube.ru/metainfo/tv/${obj["id"]?.jsonPrimitive?.content}/"
        )
    }
    
    /**
     * Normalize channel data
     */
    private fun normalizeChannel(data: JsonElement): ChannelCard {
        val obj = data.jsonObject
        val subscribersCount = obj["subscribers_count"]?.jsonPrimitive?.long ?: 0L
        
        return ChannelCard(
            id = obj["id"]?.jsonPrimitive?.content ?:
                 obj["person_id"]?.jsonPrimitive?.content ?: "",
            name = obj["name"]?.jsonPrimitive?.content ?:
                   obj["title"]?.jsonPrimitive?.content ?: "Untitled",
            avatar = obj["user_channel_image"]?.jsonPrimitive?.content ?:
                     obj["icon"]?.jsonPrimitive?.content ?:
                     obj["avatar_url"]?.jsonPrimitive?.content,
            cover = obj["cover_url"]?.jsonPrimitive?.content,
            description = obj["description"]?.jsonPrimitive?.content,
            subscribers = formatCount(subscribersCount),
            subscribersCount = subscribersCount,
            videos = obj["video_count"]?.jsonPrimitive?.int ?: 0,
            views = obj["views_count"]?.jsonPrimitive?.long,
            isVerified = obj["is_verified"]?.jsonPrimitive?.boolean ?: false,
            url = "https://rutube.ru/channel/${obj["id"]?.jsonPrimitive?.content}/"
        )
    }
    
    /**
     * Normalize promo data
     */
    private fun normalizePromo(data: JsonElement): PromoCard {
        val obj = data.jsonObject
        var actionUrl = obj["button"]?.jsonObject?.get("button_url")?.jsonPrimitive?.content ?:
                        obj["target"]?.jsonPrimitive?.content ?:
                        obj["link"]?.jsonPrimitive?.content ?:
                        obj["url"]?.jsonPrimitive?.content
        
        var actionType = "LINK"
        if (actionUrl != null) {
            actionType = when {
                actionUrl.contains("/video/") -> "VIDEO"
                actionUrl.contains("/channel/") -> "CHANNEL"
                actionUrl.contains("/tv/") -> "TV_SHOW"
                else -> "LINK"
            }
            
            if (actionUrl.startsWith("/") && !actionUrl.startsWith("/api/")) {
                actionUrl = "/api$actionUrl"
            }
        }
        
        return PromoCard(
            id = obj["id"]?.jsonPrimitive?.content ?: 
                 (1..1000000).random().toString(),
            title = obj["title"]?.jsonPrimitive?.content ?: "Untitled",
            thumbnail = obj["picture"]?.jsonPrimitive?.content ?:
                        obj["thumbnail_url"]?.jsonPrimitive?.content ?:
                        obj["image"]?.jsonPrimitive?.content,
            description = obj["description"]?.jsonPrimitive?.content,
            actionUrl = actionUrl,
            actionType = actionType
        )
    }
    
    /**
     * Parse response
     */
    private suspend fun parseResponse(jsonString: String, sourceUrl: String): ParsedResponse {
        return withContext(Dispatchers.IO) {
            try {
                val json = Json.parseToJsonElement(jsonString)
                
                // Feed with tabs
                if (json.jsonObject.containsKey("tabs")) {
                    val tabs = json.jsonObject["tabs"]?.jsonArray?.map { tab ->
                        val tabObj = tab.jsonObject
                        TabInfo(
                            id = tabObj["id"]?.jsonPrimitive?.int ?: 0,
                            name = tabObj["name"]?.jsonPrimitive?.content ?: "Tab",
                            resources = tabObj["resources"]?.jsonArray?.map { res ->
                                val resObj = res.jsonObject
                                ResourceInfo(
                                    name = resObj["name"]?.jsonPrimitive?.content ?: "Resource",
                                    url = resObj["url"]?.jsonPrimitive?.content?.let { normalizeUrl(it) },
                                    type = EntityType.UNKNOWN,
                                    meta = emptyMap()
                                )
                            } ?: emptyList()
                        )
                    } ?: emptyList()
                    
                    return@withContext ParsedResponse(
                        type = EntityType.FEED,
                        items = emptyList(),
                        title = json.jsonObject["name"]?.jsonPrimitive?.content,
                        tabs = tabs,
                        meta = ResponseMeta(sourceUrl, System.currentTimeMillis())
                    )
                }
                
                // Paginated results
                if (json.jsonObject.containsKey("results")) {
                    val results = json.jsonObject["results"]?.jsonArray ?: JsonArray(emptyList())
                    
                    if (results.isEmpty()) {
                        return@withContext ParsedResponse(
                            type = EntityType.EMPTY,
                            items = emptyList(),
                            hasNext = json.jsonObject["has_next"]?.jsonPrimitive?.boolean ?: false,
                            nextUrl = json.jsonObject["next"]?.jsonPrimitive?.content?.let { normalizeUrl(it) },
                            page = json.jsonObject["page"]?.jsonPrimitive?.int ?: 1,
                            total = json.jsonObject["total"]?.jsonPrimitive?.int,
                            meta = ResponseMeta(sourceUrl, System.currentTimeMillis())
                        )
                    }
                    
                    val isPromoGroup = sourceUrl.contains("promogroup")
                    val items = results.map { item ->
                        if (isPromoGroup) {
                            normalizePromo(item)
                        } else {
                            normalizeItem(item)
                        }
                    }
                    
                    return@withContext ParsedResponse(
                        type = when (items.firstOrNull()) {
                            is PromoCard -> EntityType.PROMO_LIST
                            is TvShowCard -> EntityType.TV_SHOW
                            is ChannelCard -> EntityType.CHANNEL
                            else -> EntityType.VIDEO_LIST
                        },
                        items = items,
                        hasNext = json.jsonObject["has_next"]?.jsonPrimitive?.boolean ?: false,
                        nextUrl = json.jsonObject["next"]?.jsonPrimitive?.content?.let { normalizeUrl(it) },
                        page = json.jsonObject["page"]?.jsonPrimitive?.int ?: 1,
                        total = json.jsonObject["total"]?.jsonPrimitive?.int,
                        meta = ResponseMeta(sourceUrl, System.currentTimeMillis())
                    )
                }
                
                // Single video
                if (json.jsonObject.containsKey("id") && 
                    (json.jsonObject.containsKey("video_url") || json.jsonObject.containsKey("duration"))) {
                    return@withContext ParsedResponse(
                        type = EntityType.VIDEO_ITEM,
                        items = listOf(normalizeVideo(json)),
                        meta = ResponseMeta(sourceUrl, System.currentTimeMillis())
                    )
                }
                
                ParsedResponse(
                    type = EntityType.UNKNOWN,
                    items = emptyList(),
                    error = "Unrecognized response structure",
                    meta = ResponseMeta(sourceUrl, System.currentTimeMillis())
                )
                
            } catch (e: Exception) {
                ParsedResponse(
                    type = EntityType.UNKNOWN,
                    items = emptyList(),
                    error = "Parse error: ${e.message}",
                    meta = ResponseMeta(sourceUrl, System.currentTimeMillis())
                )
            }
        }
    }
    
    /**
     * Normalize any item
     */
    private fun normalizeItem(item: JsonElement): Any {
        val obj = item.jsonObject
        
        // Determine type and normalize accordingly
        if (obj.containsKey("subscribers_count") || 
            obj["content_type"]?.jsonObject?.get("model")?.jsonPrimitive?.content == "userchannel") {
            return normalizeChannel(item)
        }
        
        if (obj.containsKey("seasons_count") ||
            obj["content_type"]?.jsonObject?.get("model")?.jsonPrimitive?.content == "tv") {
            return normalizeTvShow(item)
        }
        
        if (obj.containsKey("duration") || obj.containsKey("video_url") || obj.containsKey("video_id")) {
            return normalizeVideo(item)
        }
        
        return normalizePromo(item)
    }
    
    /**
     * Fetch and parse URL
     */
    suspend fun fetchUrl(url: String, skipCache: Boolean = false): ParsedResponse {
        val normalizedUrl = normalizeUrl(url)
        val cacheKey = normalizedUrl
        
        // Check cache
        if (config.enableCache && !skipCache) {
            cache[cacheKey]?.let { entry ->
                if (System.currentTimeMillis() - entry.timestamp < config.cacheTTLSeconds * 1000) {
                    return entry.data.copy(
                        meta = entry.data.meta?.copy(cached = true)
                    )
                } else {
                    cache.remove(cacheKey)
                }
            }
        }
        
        // Make request with retries
        var lastError: Exception? = null
        
        for (attempt in 1..config.maxRetries) {
            try {
                val request = Request.Builder()
                    .url(normalizedUrl)
                    .get()
                    .build()
                
                val response = client.newCall(request).execute()
                val body = response.body?.string() ?: ""
                
                if (!response.isSuccessful) {
                    throw IOException("HTTP ${response.code}: ${response.message}")
                }
                
                val result = parseResponse(body, normalizedUrl)
                
                // Cache result
                if (config.enableCache) {
                    cache[cacheKey] = CacheEntry(result, System.currentTimeMillis())
                }
                
                return result
                
            } catch (e: Exception) {
                lastError = e
                if (attempt < config.maxRetries) {
                    delay(1000L * attempt)
                }
            }
        }
        
        return ParsedResponse(
            type = EntityType.UNKNOWN,
            items = emptyList(),
            error = lastError?.message ?: "Unknown error",
            meta = ResponseMeta(normalizedUrl, System.currentTimeMillis())
        )
    }
    
    /**
     * Load next page
     */
    suspend fun loadNextPage(response: ParsedResponse): ParsedResponse? {
        val nextUrl = response.nextUrl
        if (nextUrl == null || !response.hasNext) return null
        
        return fetchUrl(nextUrl, skipCache = true)
    }
    
    /**
     * Search videos
     */
    suspend fun search(query: String, page: Int = 1): ParsedResponse {
        val encodedQuery = java.net.URLEncoder.encode(query, "UTF-8")
        val url = "/api/search/video/?query=$encodedQuery&page=$page"
        return fetchUrl(url)
    }
    
    /**
     * Get category feed
     */
    suspend fun getCategoryFeed(category: String, page: Int = 1): ParsedResponse {
        val categoryMap = mapOf(
            "Фильмы" to "movies",
            "Сериалы" to "serials",
            "Телепередачи" to "tv",
            "Музыка" to "music",
            "Мультфильмы" to "cartoons",
            "Спорт" to "sport",
            "Видеоигры" to "games"
        )
        
        val slug = categoryMap[category] ?: category.lowercase()
        val url = "/api/feeds/$slug/?page=$page"
        return fetchUrl(url)
    }
    
    /**
     * Get video info
     */
    suspend fun getVideo(videoId: String): ParsedResponse {
        val url = "/api/video/$videoId/"
        return fetchUrl(url)
    }
    
    /**
     * Get channel videos
     */
    suspend fun getChannelVideos(channelId: String, page: Int = 1): ParsedResponse {
        val url = "/api/video/person/$channelId/?page=$page"
        return fetchUrl(url)
    }
    
    /**
     * Get popular videos
     */
    suspend fun getPopularVideos(page: Int = 1): ParsedResponse {
        val url = "/api/feeds/popular/?page=$page"
        return fetchUrl(url)
    }
    
    /**
     * Clear cache
     */
    fun clearCache() {
        cache.clear()
    }
    
    /**
     * Get cache stats
     */
    fun getCacheStats(): Map<String, Any> {
        return mapOf(
            "size" to cache.size,
            "keys" to cache.keys.toList()
        )
    }
}
