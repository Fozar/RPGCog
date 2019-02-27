from os import path

import yaml
from munch import Munch

config_file_path = path.join(path.dirname(__file__), 'config.yml')

with open(config_file_path) as config_file:
    _config = yaml.load(config_file)
    config = Munch.fromDict(_config)
