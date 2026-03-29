import json
import os

CONFIG_FILE = "server_configs.json"

def load_configs():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_configs(configs):
    with open(CONFIG_FILE, "w") as f:
        json.dump(configs, f, indent=4)

def get_server_config(guild_id):
    configs = load_configs()
    guild_id_str = str(guild_id)
    if guild_id_str not in configs:
        return {
            "crossfade_enabled": False,
            "crossfade_duration": 5
        }
    return configs[guild_id_str]

def update_server_config(guild_id, **kwargs):
    configs = load_configs()
    guild_id_str = str(guild_id)
    if guild_id_str not in configs:
        configs[guild_id_str] = {
            "crossfade_enabled": False,
            "crossfade_duration": 5
        }
    for key, value in kwargs.items():
        configs[guild_id_str][key] = value
    save_configs(configs)
