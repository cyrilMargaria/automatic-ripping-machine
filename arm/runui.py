#!/usr/bin/env python3

import os  # noqa: F401
import sys
import argparse
import platform

from arm.ui import app, configure_app  # noqa E402
from arm.config.config import cfg, webserver_ip_hostname  # noqa E402
from arm.ripper.logger import setup_py_logging
import arm.ui.routes  # noqa E402

def main():
    parser = argparse.ArgumentParser(description='ARM management webserver')
    parser.add_argument('-L', dest='log_level', help="log level", default="INFO")
    parser.add_argument('-c', dest='config_file', help="""
      configuration file, can be also set in environment var ARM_CONFIG_FILE. 
      The value can be a file or an url and contain
      the following variables:
        - hostname : node hostname (here {hostname})
      for instance: http://cfgs.example.net/configs/{{hostname}}.yml
      """.format(hostname=platform.node()))
    parser.add_argument('-p', dest='port', help="port")
    parser.add_argument('-i', dest='ip', help="ip to bind")

    args = parser.parse_args()
    env_cfg = os.getenv("ARM_CONFIG_FILE", args.config_file)
    if env_cfg:
        cfg.path = args.config_file.format(hostname=platform.node())
    setup_py_logging("web-ui", level=args.log_level)
    host = args.ip    
    if not host:
        host, _ = webserver_ip_hostname()       
    port = args.port
    if not port:
        port = cfg['WEBSERVER_PORT']
    configure_app()
    for path in ["TRANSCODE_PATH", "COMPLETED_PATH", "RAW_PATH", "DATA_PATH"]:
        os.makedirs(cfg[path], exist_ok=True)
    app.run(host=host, port=port, debug=True)
    # app.run(debug=True)

if __name__ == '__main__':
    main()
