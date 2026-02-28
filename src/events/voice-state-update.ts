import {VoiceChannel, VoiceState} from 'discord.js';
import container from '../inversify.config.js';
import {TYPES} from '../types.js';
import PlayerManager from '../managers/player.js';
import {getSizeWithoutBots} from '../utils/channels.js';
import {getGuildSettings} from '../utils/get-guild-settings.js';

export default async (oldState: VoiceState, newState: VoiceState): Promise<void> => {
  const playerManager = container.get<PlayerManager>(TYPES.Managers.Player);
  const player = playerManager.get(oldState.guild.id);

  if (newState.id === oldState.client.user?.id) {
    return;
  }

  if (player.voiceConnection) {
    const {channelId} = player.voiceConnection.joinConfig;
    if (!channelId) {
      return;
    }

    const voiceChannel = oldState.guild.channels.cache.get(channelId) as VoiceChannel;
    const settings = await getGuildSettings(player.guildId);

    const {leaveIfNoListeners} = settings;
    const size = voiceChannel ? getSizeWithoutBots(voiceChannel) : 0;

    if (!voiceChannel || (size === 0 && leaveIfNoListeners)) {
      console.log(`[voiceStateUpdate] Disconnecting from ${channelId} (size: ${size}, leaveIfNoListeners: ${String(leaveIfNoListeners)})`);
      player.disconnect();
    }
  }
};
