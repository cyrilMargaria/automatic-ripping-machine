#!/usr/bin/env python3

import os  # noqa: F401
import sys
import argparse

from arm.ui import app, configure_app  # noqa E402
from arm.config.config import cfg, webserver_ip_hostname  # noqa E402
import arm.ui.routes  # noqa E402

def main():
    parser = argparse.ArgumentParser(description='Process disc using ARM')
    parser.add_argument('-L', dest='log_level', help="log level", default="INFO")
    parser.add_argument('-c', dest='config_file', help="configuration file")
    parser.add_argument('-p', dest='port', help="port")
    parser.add_argument('-i', dest='ip', help="ip to bind")
    args = parser.parse_args()
    if args.config_file:
        cfg.path = args.config_file
    host = args.ip    
    if not host:
        host, _ = webserver_ip_hostname()       
    port = args.port
    if not port:
        port = cfg['WEBSERVER_PORT']
    configure_app()
    app.run(host=host, port=port, debug=True)
    # app.run(debug=True)

if __name__ == '__main__':
    main()
