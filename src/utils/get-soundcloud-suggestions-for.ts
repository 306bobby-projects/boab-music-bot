import ytDlp from 'youtube-dl-exec';

export interface SoundCloudSuggestion {
    title: string;
    uploader: string;
    url: string;
}

const getSoundCloudSuggestionsFor = async (query: string, limit = 5): Promise<SoundCloudSuggestion[]> => {
    try {
        const output = await ytDlp(`scsearch${limit}:${query}`, {
            dumpSingleJson: true,
            noWarnings: true,
            flatPlaylist: true,
        });

        const info = output as any;

        if (!info.entries) {
            return [];
        }

        return (info.entries as any[]).map(entry => ({
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
