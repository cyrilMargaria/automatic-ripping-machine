#!/usr/bin/python3

import os
import yaml
import urllib.request

def load_yaml_file(filename):
    """ Load a yaml file, can be local file or anything that can be opened by urrlib"""
    file_ref = None
    try:
        file_ref = urllib.request.urlopen(filename)
    except (ValueError, urllib.error.URLError):
        file_ref = open(filename, "r")
    if not file_ref:
        raise ValueError(f"could not open {filename}")
    return yaml.load(file_ref, Loader=yaml.FullLoader)

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
        """ load yaml configuration data, and patch it with env data, if the env contains the same key """
        self._data = load_yaml_file(self.path)
        # override values from environment
        for k, v in self._data.items():
            env_value = os.getenv(k)
            if not env_value:
                continue
            try:
                if isinstance(v, int):
                    env_value = int(env_value)
                elif isinstance(v, float):
                    env_value = float(env_value)
                elif isinstance(v, bool):
                    env_value = env_value in ("True", "true", "1")
                self._data[k] = env_value
            except ValueError:
                pass
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
        
def webserver_ip_hostname():
    """
        return web server listening ip and hostname 
        Check if user has set an ip in the config file
        if not gets the most likely ip
        arguments:
        none
        return: the ip of the host or 127.0.0.1
    """    
    host = cfg['WEBSERVER_IP']
    hostname = cfg.get('WEBSERVER_NAME')
    if host == 'x.x.x.x':
        # autodetect host IP address
        from netifaces import interfaces, ifaddresses, AF_INET
        ip_list = []
        for interface in interfaces():
            inet_links = ifaddresses(interface).get(AF_INET, [])
            for link in inet_links:
                ip = link['addr']
                # print(str(ip))
                if ip != '127.0.0.1' and not (ip.startswith('172')):
                    ip_list.append(ip)
                    # print(str(ip))
        if len(ip_list) > 0:
            return ip_list[0], hostname or  ip_list[0]
        else:
            return '127.0.0.1', hostname or "localhost"
    else:
        return host, hostname or host

        
