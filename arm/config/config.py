#!/usr/bin/python3

import os
import yaml


class cfgWrapper:
    """ wrap the configuration, implements the dict protocol, allow to change configuration file location."""

    def __init__(self, path=None):
        # file path 
        self.path = path
        self._loaded = False
        self._data = None
        if None is self.path:
            self.path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../..", "arm.yaml")
            
    def load(self):
        """ load yaml configuration data """
        with open(self.path, "r") as f:
            self._data = yaml.load(f, Loader=yaml.FullLoader)
            self._loaded = True
        
    def __getattr__(self, name):
        if not self._loaded:
            self.load()
        if hasattr(self._data, name):
            return getattr(self._data, name)
        return self._data.get(name)

    def __getitem__(self, item):
        if not self._loaded:
            self.load()
        return self._data[item]

    def __setitem__(self, item, value):
        if not self._loaded:
            self.load()
        self._data[item] = value

    def __delitem__(self, item):
        if not self._loaded:
            self.load()
        del self._data[item]

cfg = cfgWrapper()   
