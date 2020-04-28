#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# @Time    : 2019/7/4 10:18 PM
# @Author  : w8ay
# @File    : loader.py
from urllib.parse import urlparse

import requests

from lib.controller.controller import task_push
from lib.core.common import isListLike, get_parent_paths, random_str
from lib.core.data import conf, KB
from lib.core.enums import WEB_PLATFORM, OS, HTTPMETHOD
from lib.core.plugins import PluginBase
from lib.core.settings import TOP_RISK_POST_PARAMS, TOP_RISK_GET_PARAMS
from lib.helper.htmlparser import getParamsFromHtml
from lib.parse.parse_request import FakeReq
from lib.parse.parse_responnse import FakeResp


class W13SCAN(PluginBase):
    type = 'loader'
    desc = '''Loader插件对请求以及响应进行解析，从而调度更多插件运行'''
    name = 'plugin loader'

    def audit(self):
        headers = self.requests.headers
        url = self.requests.url

        # if conf.no_active:
        #     # 语义解析获得参数,重新生成新的fakereq,fakeresps
        #     parse_params = set(getParamsFromHtml(self.response.text))
        #     params_data = {}
        #     if self.requests.method == HTTPMETHOD.GET:
        #         parse_params = (parse_params | TOP_RISK_GET_PARAMS) - set(self.requests.params.keys())
        #         for key in parse_params:
        #             params_data[key] = random_str(6)
        #         self.requests.params = params_data
        #     elif self.requests.method == HTTPMETHOD.POST:
        #         parse_params = (parse_params | TOP_RISK_POST_PARAMS) - set(self.requests.post_data.keys())
        #         for key in parse_params:
        #             params_data[key] = random_str(6)
        #         self.requests.post_data = params_data

        # fingerprint basic info
        exi = self.requests.suffix.lower()
        if exi == ".asp":
            self.response.programing.append(WEB_PLATFORM.ASP)
            self.response.os.append(OS.WINDOWS)
        elif exi == ".aspx":
            self.response.programing.append(WEB_PLATFORM.ASPX)
            self.response.os.append(OS.WINDOWS)
        elif exi == ".php":
            self.response.programing.append(WEB_PLATFORM.PHP)
        elif exi == ".jsp" or exi == ".do" or exi == ".action":
            self.response.programing.append(WEB_PLATFORM.JAVA)

        for name, values in KB["fingerprint"].items():
            if not getattr(self.response, name):
                _result = []
                for mod in values:
                    m = mod.fingerprint(self.response.headers, self.response.text)
                    if isinstance(m, str):
                        _result.append(m)
                    if isListLike(m):
                        _result += list(m)
                if _result:
                    setattr(self.response, name, _result)

        # Fingerprint basic end
        if KB["spiderset"].add(url, 'PerFile'):
            task_push('PerFile', self.requests, self.response)

        # Send PerServe
        p = urlparse(url)
        domain = "{}://{}".format(p.scheme, p.netloc)
        if KB["spiderset"].add(domain, 'PerServe'):
            req = requests.get(domain, headers=headers, allow_redirects=False)
            fake_req = FakeReq(domain, headers, HTTPMETHOD.GET, "")
            fake_resp = FakeResp(req.status_code, req.content, req.headers)
            task_push('PerServe', fake_req, fake_resp)

        # Collect directory from response
        urls = set(get_parent_paths(url))
        for parent_url in urls:
            if not KB["spiderset"].add(parent_url, 'get_link_directory'):
                continue
            req = requests.get(parent_url, headers=headers, allow_redirects=False)
            if KB["spiderset"].add(req.url, 'PerFolder'):
                fake_req = FakeReq(req.url, headers, HTTPMETHOD.GET, "")
                fake_resp = FakeResp(req.status_code, req.content, req.headers)
                task_push('PerFolder', fake_req, fake_resp)
