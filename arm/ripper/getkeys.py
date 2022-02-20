#!/usr/bin/env python3
import os
# Added for newer werkzeug versions
import werkzeug
import re
werkzeug.cached_property = werkzeug.utils.cached_property
from robobrowser import RoboBrowser  # noqa E402
import tinydownload.tinydownload
def grabkeys(cfg):
    if not cfg:
        return False
    br = RoboBrowser()
    # this is the same re for all links
    # http://s000.tinyupload.com/index.php?file_id=34856796669669839157
    link_re = re.compile("http://s000.tinyupload.com/index.php\?file_id=(\d+)")

    def download(url, output): 
        br.open(url)
        data = str(br.parsed())
        links = link_re.findall(data)
        if not links:
            print(f"Page {url}: no magic link found")
            return
        print(f"Page {url}: magic link found {links[0]}")
        file_id = tinydownload.tinydownload.get_file_id(links[0])
        soup = tinydownload.tinydownload.make_soup(file_id)
        link = tinydownload.tinydownload.get_filelink(soup)
        tinydownload.tinydownload.download(link, output)

    # not valid, no need to query it       
    #download('http://makemkv.com/forum2/viewtopic.php?f=12&t=16959', "keys_hashed.txt")
    # only returns errors
    #download('https://forum.doom9.org/showthread.php?t=175194', "KEYDB.cfg")
    # 
    #    os.system('mv -u -t /home/arm/.MakeMKV keys_hashed.txt KEYDB.cfg')
