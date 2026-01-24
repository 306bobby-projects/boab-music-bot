import {inject, injectable, optional} from 'inversify';
import * as spotifyURI from 'spotify-uri';
import ytDlp from 'youtube-dl-exec';
import {SongMetadata, QueuedPlaylist, MediaSource, YtDlpVideo} from './player.js';
import {TYPES} from '../types.js';
import ffmpeg from 'fluent-ffmpeg';
import YoutubeAPI from './youtube-api.js';
import SpotifyAPI, {SpotifyTrack} from './spotify-api.js';
import {URL} from 'node:url';

interface YtDlpPlaylistEntry {
  url: string;
  title: string;
  uploader?: string;
  duration?: number;
}

interface YtDlpPlaylistOutput {
  _type: 'playlist';
  title: string;
  uploader?: string;
  entries: YtDlpPlaylistEntry[];
}

@injectable()
export default class {
  private readonly youtubeAPI: YoutubeAPI;
  private readonly spotifyAPI?: SpotifyAPI;

  constructor(@inject(TYPES.Services.YoutubeAPI) youtubeAPI: YoutubeAPI, @inject(TYPES.Services.SpotifyAPI) @optional() spotifyAPI?: SpotifyAPI) {
    this.youtubeAPI = youtubeAPI;
    this.spotifyAPI = spotifyAPI;
  }

  async getSongs(query: string, playlistLimit: number, shouldSplitChapters: boolean): Promise<[SongMetadata[], string]> {
    const newSongs: SongMetadata[] = [];
    let extraMsg = '';

    // Test if it's a complete URL
    console.log(`[getSongs] Processing query: "${query}"`);
    try {
      const url = new URL(query);
      console.log(`[getSongs] Parsed URL host: "${url.host}"`);

      const YOUTUBE_HOSTS = [
        'www.youtube.com',
        'youtu.be',
        'youtube.com',
        'music.youtube.com',
        'www.music.youtube.com',
      ];

      if (YOUTUBE_HOSTS.includes(url.host)) {
        // Remove the 'list' parameter if it's a video being watched (not a pure playlist link)
        if (url.pathname === '/watch') {
          url.searchParams.delete('list');
        }

        if (url.host === 'youtu.be') {
          url.searchParams.delete('si');
        }

        // YouTube source
        if (url.searchParams.get('list')) {
          // YouTube playlist
          newSongs.push(...await this.youtubePlaylist(url.searchParams.get('list')!, shouldSplitChapters));
        } else {
          const songs = await this.youtubeVideo(url.href, shouldSplitChapters);

          if (songs) {
            newSongs.push(...songs);
          } else {
            throw new Error('that doesn\'t exist');
          }
        }
      } else if (url.protocol === 'spotify:' || url.host === 'open.spotify.com') {
        if (this.spotifyAPI === undefined) {
          throw new Error('Spotify is not enabled!');
        }

        const [convertedSongs, nSongsNotFound, totalSongs] = await this.spotifySource(query, playlistLimit, shouldSplitChapters);

        if (totalSongs > playlistLimit) {
          extraMsg = `a random sample of ${playlistLimit} songs was taken`;
        }

        if (totalSongs > playlistLimit && nSongsNotFound !== 0) {
          extraMsg += ' and ';
        }

        if (nSongsNotFound !== 0) {
          if (nSongsNotFound === 1) {
            extraMsg += '1 song was not found';
          } else {
            extraMsg += `${nSongsNotFound.toString()} songs were not found`;
          }
        }

        newSongs.push(...convertedSongs);
      } else if (url.host === 'soundcloud.com' || url.host === 'm.soundcloud.com' || url.host === 'on.soundcloud.com' || url.host === 'api.soundcloud.com') {
        // Strip everything after the first ?
        url.search = '';
        const songs = await this.soundcloudSource(url.href);
        if (songs) {
          newSongs.push(...songs);
        } else {
          throw new Error('that doesn\'t exist');
        }
      } else {
        const song = await this.httpLiveStream(query);

        if (song) {
          newSongs.push(song);
        } else {
          throw new Error('that doesn\'t exist');
        }
      }
    } catch (err: any) {
      console.log('[getSongs] URL parsing/processing failed or threw error:', err);
      if (err instanceof Error && err.message === 'Spotify is not enabled!') {
        throw err;
      }

      // Check if it might be a SoundCloud URL missing protocol
      if (query.includes('soundcloud.com') && !query.startsWith('http')) {
        try {
          const url = new URL(`https://${query}`);
          // Recurse or handle directly? Let's just handle it here to avoid deep recursion loop risk
          if (url.host === 'soundcloud.com' || url.host === 'm.soundcloud.com' || url.host === 'on.soundcloud.com' || url.host === 'api.soundcloud.com') {
            // Strip everything after the first ?
            url.search = '';
            const songs = await this.soundcloudSource(url.href);
            if (songs) {
              newSongs.push(...songs);
              return [newSongs, extraMsg];
            }
          }
        } catch {
          // Ignore, continue to YouTube search
        }
      }

      // Not a URL, must search YouTube
      const songs = await this.youtubeVideoSearch(query, shouldSplitChapters);

      if (songs) {
        newSongs.push(...songs);
      } else {
        throw new Error('that doesn\'t exist');
      }
    }

    return [newSongs, extraMsg];
  }

  private async youtubeVideoSearch(query: string, shouldSplitChapters: boolean): Promise<SongMetadata[]> {
    return this.youtubeAPI.search(query, shouldSplitChapters);
  }

  private async youtubeVideo(url: string, shouldSplitChapters: boolean): Promise<SongMetadata[]> {
    return this.youtubeAPI.getVideo(url, shouldSplitChapters);
  }

  private async youtubePlaylist(listId: string, shouldSplitChapters: boolean): Promise<SongMetadata[]> {
    return this.youtubeAPI.getPlaylist(listId, shouldSplitChapters);
  }

  private async spotifySource(url: string, playlistLimit: number, shouldSplitChapters: boolean): Promise<[SongMetadata[], number, number]> {
    if (this.spotifyAPI === undefined) {
      return [[], 0, 0];
    }

    const parsed = spotifyURI.parse(url);

    switch (parsed.type) {
      case 'album': {
        const [tracks, playlist] = await this.spotifyAPI.getAlbum(url, playlistLimit);
        return this.spotifyToYouTube(tracks, shouldSplitChapters, playlist);
      }

      case 'playlist': {
        const [tracks, playlist] = await this.spotifyAPI.getPlaylist(url, playlistLimit);
        return this.spotifyToYouTube(tracks, shouldSplitChapters, playlist);
      }

      case 'track': {
        const tracks = [await this.spotifyAPI.getTrack(url)];
        return this.spotifyToYouTube(tracks, shouldSplitChapters);
      }

      case 'artist': {
        const tracks = await this.spotifyAPI.getArtist(url, playlistLimit);
        return this.spotifyToYouTube(tracks, shouldSplitChapters);
      }

      default: {
        return [[], 0, 0];
      }
    }
  }

  private async httpLiveStream(url: string): Promise<SongMetadata> {
    return new Promise((resolve, reject) => {
      ffmpeg(url).ffprobe((err, _) => {
        if (err) {
          reject();
        }

        resolve({
          url,
          source: MediaSource.HLS,
          isLive: true,
          title: url,
          artist: url,
          length: 0,
          offset: 0,
          playlist: null,
          thumbnailUrl: null,
        });
      });
    });
  }

  private async soundcloudSource(url: string): Promise<SongMetadata[]> {
    const output = await ytDlp(url, {
      dumpSingleJson: true,
      noWarnings: true,
      preferFreeFormats: true,
      flatPlaylist: true,
    });

    const isPlaylist = (info: unknown): info is YtDlpPlaylistOutput =>
      typeof info === 'object'
      && info !== null
      && '_type' in info
      && (info as YtDlpPlaylistOutput)._type === 'playlist'
      && 'entries' in info
      && Array.isArray((info as YtDlpPlaylistOutput).entries);

    if (isPlaylist(output)) {
      return output.entries.map((entry: YtDlpPlaylistEntry) => {
        let {title} = entry;

        if (!title && entry.url) {
          // Fallback: extract title from URL
          const parts = entry.url.split('/');
          title = parts[parts.length - 1].replace(/-/g, ' ');
        }

        return {
          url: entry.url,
          source: MediaSource.SoundCloud,
          title: title ?? 'Unknown Title',
          artist: entry.uploader ?? output.uploader ?? 'Unknown',
          length: entry.duration ?? 0,
          offset: 0,
          playlist: {
            title: output.title,
            source: url,
          },
          isLive: false,
          thumbnailUrl: null,
        };
      });
    }

    const info = output as unknown as YtDlpVideo;

    return [{
      url: info.webpage_url ?? info.url,
      source: MediaSource.SoundCloud,
      title: info.title,
      artist: info.uploader,
      length: info.duration,
      offset: 0,
      playlist: null,
      isLive: false,
      thumbnailUrl: info.thumbnail,
    }];
  }

  private async spotifyToYouTube(tracks: SpotifyTrack[], shouldSplitChapters: boolean, playlist?: QueuedPlaylist | undefined): Promise<[SongMetadata[], number, number]> {
    const promisedResults = tracks.map(async track => this.youtubeAPI.search(`"${track.name}" "${track.artist}"`, shouldSplitChapters));
    const searchResults = await Promise.allSettled(promisedResults);

    let nSongsNotFound = 0;

    // Count songs that couldn't be found
    const songs: SongMetadata[] = searchResults.reduce((accum: SongMetadata[], result) => {
      if (result.status === 'fulfilled') {
        for (const v of result.value) {
          accum.push({
            ...v,
            ...(playlist ? {playlist} : {}),
          });
        }
      } else {
        nSongsNotFound++;
      }

      return accum;
    }, []);

    return [songs, nSongsNotFound, tracks.length];
  }
}
