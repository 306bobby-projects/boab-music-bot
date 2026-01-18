import ytDlp from 'youtube-dl-exec';

export interface SoundCloudSuggestion {
  title: string;
  uploader: string;
  url: string;
}

interface YtDlpEntry {
  title: string;
  uploader: string;
  url: string;
}

interface YtDlpPlaylistOutput {
  entries?: YtDlpEntry[];
}

const getSoundCloudSuggestionsFor = async (query: string, limit = 5): Promise<SoundCloudSuggestion[]> => {
  try {
    const output = await ytDlp(`scsearch${limit}:${query}`, {
      dumpSingleJson: true,
      noWarnings: true,
      flatPlaylist: true,
    });

    const info = output as unknown as YtDlpPlaylistOutput;

    if (!info.entries) {
      return [];
    }

    return info.entries.map(entry => ({
      title: entry.title,
      uploader: entry.uploader,
      url: entry.url.startsWith('http') ? entry.url : `https://${entry.url}`,
    }));
  } catch (error) {
    console.error('Error fetching SoundCloud suggestions:', error);
    return [];
  }
};

export default getSoundCloudSuggestionsFor;
