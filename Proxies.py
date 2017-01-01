import requests, datetime, time
from bs4 import BeautifulSoup as bsoup
from PyQt5.QtCore import QThread


class ProxiesThread(QThread):
    test_url = 'http://38.103.161.156'
    headers = 'Mozilla/5.0 (Windows; U; Windows NT 5.1; en-US; rv:1.9a2pre) Gecko/20061231 Minefield/3.0a2pre'

    def __init__(self, proxies_pool, which, parent=None):
        super().__init__(parent)
        self.proxies_pool = proxies_pool
        self.which = which

    def run(self):
        if self.which == 1:
            url = 'http://haoip.cc/'
            next_page = ''
            while True:
                try:
                    req = requests.get(url + next_page, headers={'User-Agent': self.headers})
                except requests.exceptions.RequestException:
                    time.sleep(5)
                    continue
                pobj = bsoup(req.content, 'lxml')
                try:
                    next_page = pobj.find('ul', {'class': 'pagination'}).li.a['href']
                except AttributeError:
                    continue
                for each in pobj.find('table', {'class': 'table table-hover'}).findAll('tr'):
                    sp = each.findAll('td')[:2]
                    proxy = sp[0].text + ':' + sp[1].text
                    try:
                        if requests.head(self.test_url, proxies={'http': proxy}, headers={'User-Agent': self.headers}, timeout=3).ok:
                            # print('[{}]({}){} is good'.format(datetime.datetime.now().strftime('%H:%M:%S'), self.which,
                            #                                   proxy))
                            self.proxies_pool.append(proxy)
                    except requests.exceptions.RequestException:
                        continue
        elif self.which == 2:
            for page in range(1, 1001):
                try:
                    req = requests.get('http://www.xicidaili.com/nn/{}'.format(page), headers={'User-Agent': self.headers})
                except requests.exceptions.RequestException:
                    time.sleep(5)
                    continue
                pobj = bsoup(req.content, 'lxml').findAll('tr')
                for each in pobj[1:]:
                    sp = each.findAll('td')
                    proxy = sp[1].text + ':' + sp[2].text
                    try:
                        if requests.head(self.test_url, proxies={'http': proxy}, headers={'User-Agent': self.headers}, timeout=3).ok:
                            # print('[{}]({}){} is good'.format(datetime.datetime.now().strftime('%H:%M:%S'), self.which,
                            #                                   proxy))
                            self.proxies_pool.append(proxy)
                    except requests.exceptions.RequestException:
                        continue
        elif self.which == 3:
            url = 'http://www.kuaidaili.com/free/outha/{}/'
            for page in range(1, 1415):
                try:
                    req = requests.get(url.format(page), headers={'User-Agent': self.headers})
                except requests.exceptions.RequestException:
                    time.sleep(5)
                    continue
                pobj = bsoup(req.content, 'lxml').findAll('tr')
                for each in pobj[1:]:
                    sp = each.findAll('td')
                    proxy = sp[0].text + ':' + sp[1].text
                    try:
                        if requests.head(self.test_url, proxies={'http': proxy},
                                         headers={'User-Agent': self.headers}, timeout=3).ok:
                            # print('[{}]({}){} is good'.format(datetime.datetime.now().strftime('%H:%M:%S'), self.which,
                            #                                   proxy))
                            self.proxies_pool.append(proxy)
                    except requests.exceptions.RequestException:
                        continue
