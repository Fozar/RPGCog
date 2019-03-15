from os import path

import json
from munch import Munch

config_file_path = path.join(path.dirname(__file__), 'config.json')

with open(config_file_path) as config_file:
    _config = json.load(config_file)
    config = Munch.fromDict(_config)
