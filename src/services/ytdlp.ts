import { execa } from 'execa';
import debug from '../utils/debug.js';

export interface YtDlpFormat {
    format_id: string;
    format_note: string;
    ext: string;
    acodec: string;
    vcodec: string;
    url: string;
    width?: number;
    height?: number;
    fps?: number;
    audio_ext?: string;
    video_ext?: string;
    format: string;
    resolution: string;
    dynamic_range: string;
    abr?: number;
    tbr?: number;
}

export interface YtDlpVideo {
    id: string;
    title: string;
    formats: YtDlpFormat[];
    thumbnail: string;
    description: string;
    uploader: string;
    duration: number;
    view_count: number;
    webpage_url: string;
    is_live: boolean;
    live_status?: string;
    loudness?: number;
}

export class YtDlp {
    private static readonly binary = 'yt-dlp';

    public static async getVideoInfo(url: string): Promise<YtDlpVideo> {
        const { stdout } = await execa(this.binary, [
            '--dump-json',
            '--no-playlist',
            '--no-warnings',
            url
        ]);
        return JSON.parse(stdout) as YtDlpVideo;
    }

    public static async getStreamUrl(url: string, live = false): Promise<string> {
        // For live streams, we might want to let yt-dlp handle HLS (m3u8) or just get best audio
        // 'bestaudio/best' is usually good.
        // For non-live, we want opus/webm if possible, or best audio.
        const args = [
            '-f',
            'bestaudio[ext=webm][acodec=opus][asr=48000]/bestaudio', // Prefer opus webm 48k
            '--get-url',
            '--no-playlist',
            '--no-warnings',
            url
        ];

        const { stdout } = await execa(this.binary, args);
        return stdout.trim();
    }

    public static async updateBinary(): Promise<void> {
        try {
            debug('Updating yt-dlp...');
            const { stdout } = await execa(this.binary, ['-U']);
            debug(`yt-dlp update result: ${stdout}`);
        } catch (error) {
            debug('Failed to update yt-dlp:', error);
        }
    }
}
