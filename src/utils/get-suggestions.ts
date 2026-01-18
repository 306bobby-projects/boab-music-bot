import {APIApplicationCommandOptionChoice} from 'discord-api-types/v10';
import SpotifyWebApi from 'spotify-web-api-node';
import getYouTubeSuggestionsFor from './get-youtube-suggestions-for.js';
import getSoundCloudSuggestionsFor from './get-soundcloud-suggestions-for.js';

const filterDuplicates = <T extends {name: string}>(items: T[]) => {
  const results: T[] = [];

  for (const item of items) {
    if (!results.some(result => result.name === item.name)) {
      results.push(item);
    }
  }

  return results;
};

const getSuggestions = async (query: string, spotify?: SpotifyWebApi, limit = 25): Promise<APIApplicationCommandOptionChoice[]> => {
  const promises = [];

  // YouTube
  promises.push(getYouTubeSuggestionsFor(query));

  // Spotify
  if (spotify) {
    promises.push(spotify.search(query, ['album', 'track'], {limit: 10}));
  } else {
    promises.push(Promise.resolve(undefined));
  }

  // SoundCloud
  promises.push(getSoundCloudSuggestionsFor(query, 5));

  const [youtubeSuggestions, spotifyResponse, soundcloudSuggestions] = await Promise.all(promises) as [string[], any, any[]];

  const suggestions: APIApplicationCommandOptionChoice[] = [];

  // Add YouTube suggestions
  // Take up to 10 YouTube suggestions
  const maxYouTube = 10;
  suggestions.push(
    ...youtubeSuggestions
      .slice(0, maxYouTube)
      .map(suggestion => ({
        name: `YouTube: ${suggestion}`,
        value: suggestion,
      })),
  );

  // Add SoundCloud suggestions
  // Take up to 5 SoundCloud suggestions
  if (soundcloudSuggestions) {
    suggestions.push(
      ...soundcloudSuggestions.map((suggestion: any) => ({
        name: `SoundCloud: ☁️ ${suggestion.title} - ${suggestion.uploader}`,
        value: suggestion.url,
      })),
    );
  }

  // Add Spotify suggestions
  if (spotifyResponse?.body) {
    const response = spotifyResponse.body;
    const spotifyAlbums = filterDuplicates(response.albums?.items ?? []);
    const spotifyTracks = filterDuplicates(response.tracks?.items ?? []);

    const remainingSlots = limit - suggestions.length;
    const maxSpotify = Math.min(remainingSlots, 10); // Check cap

    if (maxSpotify > 0) {
      const maxAlbums = Math.floor(maxSpotify / 2);
      const maxTracks = maxSpotify - maxAlbums;

      suggestions.push(
        ...spotifyAlbums.slice(0, maxAlbums).map((album: any) => ({
          name: `Spotify: 💿 ${album.name}${album.artists.length > 0 ? ` - ${album.artists[0].name}` : ''}`,
          value: `spotify:album:${album.id}`,
        })),
      );

      suggestions.push(
        ...spotifyTracks.slice(0, maxTracks).map((track: any) => ({
          name: `Spotify: 🎵 ${track.name}${track.artists.length > 0 ? ` - ${track.artists[0].name}` : ''}`,
          value: `spotify:track:${track.id}`,
        })),
      );
    }
  }

  return suggestions.slice(0, limit);
};

export default getSuggestions;
