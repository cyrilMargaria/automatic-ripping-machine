#!/usr/bin/env python3
import unittest
import random
import string
import arm.config.config
arm.config.config.cfg.path = "arm_test.yml"

import arm.ripper.utils


class TestURLGen(unittest.TestCase):
    TEST_DATA = [
        [["GROWL_HOST"],             "growl://{0}"],
        [["GROWL_HOST", "GROWL_PASS"], "growl://{1}@{0}"],
        [["KODI_HOST"], "kodi://{0}"],
        [["KODI_HOST", "KODI_PORT"], "kodi://{0}:{1}"],
        [["KODI_HOST", ("KODI_PORT", 443)], "kodis://{0}:{1}"],
        [["KODI_HOST", "KODI_USER", "KODI_PASS"], "kodi://{1}:{2}@{0}"],
        [["KODI_HOST", "KODI_PORT", "KODI_USER", "KODI_PASS"], "kodi://{2}:{3}@{0}:{1}"],
        [["KODI_HOST", ("KODI_PORT", 443), "KODI_USER", "KODI_PASS"], "kodis://{2}:{3}@{0}:{1}"],
        [["PROWL_API"], "prowl://{0}"],
        [["PROWL_API", "PROWL_PROVIDERKEY"], "prowl://{0}/{1}"],
        [["XBMC_HOST"], "xbmc://{0}"],
        [["XBMC_HOST", "XBMC_PORT"], "xbmc://{0}:{1}"],
        [["XBMC_HOST", "XBMC_USER", "XBMC_PASS"], "xbmc://{1}:{2}@{0}"],
        [["XBMC_HOST", "XBMC_PORT", "XBMC_USER", "XBMC_PASS"], "xbmc://{2}:{3}@{0}:{1}"],
        [["XMPP_HOST", "XMPP_PASS"], "xmpp://{1}@{0}"],
        [["XMPP_HOST", "XMPP_USER", "XMPP_PASS"], "xmpps://{1}:{2}@{0}"],
        [["GITTER_TOKEN", "GITTER_ROOM"],  "gitter://{0}/{1}"],
    ]    

    def test_cred(self):
        data = arm.ripper.utils.dictProxy({"U": "user", "P": "passwd"})        
        self.assertEqual(arm.ripper.utils.cfg_cred(data, "U", "P"), "user:passwd@")
        self.assertEqual(arm.ripper.utils.cfg_cred(data, "U", "NP"), "user@")
        self.assertEqual(arm.ripper.utils.cfg_cred(data, "U", ""), "user@")
        self.assertEqual(arm.ripper.utils.cfg_cred(data, "NU", "P"), "passwd@")
        self.assertEqual(arm.ripper.utils.cfg_cred(data, "NU", "NP"), "")
        self.assertEqual(arm.ripper.utils.cfg_cred(data, "NU", ""), "")
                
    def test_urls(self):
        for t in TestURLGen.TEST_DATA:            
            with self.subTest(name="-".join([repr(x) for x in t[0]])):
                test_data = []
                test_dict = {}
                for n in t[0]:
                    value = None
                    name = n
                    if isinstance(n, tuple):
                        name = n[0]
                        value = n[1]
                    else:
                        value = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
                    test_dict[name] = value
                    test_data.append(value)
                # 
                test_cfg = arm.ripper.utils.dictProxy(test_dict)
                actual = arm.ripper.utils.notification_urls_from_cfg(test_cfg, arm.ripper.utils.NOTIFICATIONS_BUILDER)
                self.assertEqual(len(actual), 1)
                expected = t[1].format(*test_data)
                self.assertEqual(actual[0], expected, msg=f"actual: {actual[0]}, expected:{expected} ")
    


if __name__ == '__main__':
    unittest.main()
