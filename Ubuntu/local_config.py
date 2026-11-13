"""
Machine-specific settings for the rig, read from local_config.json next to this file.

local_config.json is not tracked by git (the repository is public): copy
local_config.example.json to local_config.json and fill in the real values (see README).
"""

import json
import os

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'local_config.json')


def load():
    if not os.path.exists(CONFIG_PATH):
        raise FileNotFoundError(f'{CONFIG_PATH} not found; copy local_config.example.json to it and '
                                f'fill in the real values (see README)')
    with open(CONFIG_PATH) as f:
        return json.load(f)
