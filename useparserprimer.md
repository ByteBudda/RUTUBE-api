// JavaScript/TypeScript example
import RutubeParser from './rutube-parser';

const parser = new RutubeParser({
  enableCache: true,
  timeout: 15000
});

// Search videos
async function searchVideos() {
  const result = await parser.search('kotlin programming');
  console.log(`Found ${result.items.length} videos`);
  
  for (const video of result.items) {
    if (video.type === 'VIDEO') {
      console.log(`${video.title} - ${video.duration}`);
    }
  }
  
  // Load next page
  if (result.pagination?.hasNext) {
    const nextPage = await parser.loadNextPage(result);
    console.log(`Next page: ${nextPage?.items.length} videos`);
  }
}

// Get category feed
async function getMovies() {
  const movies = await parser.getCategoryFeed('Фильмы');
  console.log(`Movies: ${movies.items.length}`);
}

// Get video details
async function getVideoDetails(videoId) {
  const video = await parser.getVideo(videoId);
  if (video.items[0]?.type === 'VIDEO') {
    const v = video.items[0];
    console.log(`Title: ${v.title}`);
    console.log(`Channel: ${v.channel.name}`);
    console.log(`Views: ${v.stats.views}`);
  }
}

// Cancel all requests (useful for navigation)
function cleanup() {
  parser.cancelAllRequests();
  parser.clearCache();
}
