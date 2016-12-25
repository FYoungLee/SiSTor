"""
    Multiply Threads Crawler for downloading torrents from SexInSex fourm
    Author: Fyound Lix
    Create: 11/05/2016
    Version: 1.0
"""
from bs4 import BeautifulSoup
import re
import os
import datetime
import requests
import random
import time
from PyQt5.QtCore import QThread
from PyQt5.QtCore import pyqtSignal


class TheDownloader(QThread):
    send_text = pyqtSignal(str)

    def __init__(self, loginname=None, password=None, parent=None):
        super(TheDownloader, self).__init__(parent=parent)
        with open('sis_addr.dat', 'r') as f:
            self.baseurl = f.readline()
        self.cookies = self.get_sis_cookies(loginname, password)

    def get_headers(self):
        UserAgents = ['Mozilla/5.0 (Windows; U; Windows NT 5.1; en-US; rv:1.9a2pre) Gecko/20061231 Minefield/3.0a2pre',
                      'Mozilla/5.0 (X11; U; Linux x86_64; de; rv:1.8.1.12) Gecko/20080203 SUSE/2.0.0.12-6.1 Firefox/2.0.0.12',
                      'Mozilla/5.0 (X11; U; FreeBSD i386; ru-RU; rv:1.9.1.3) Gecko/20090913 Firefox/3.5.3',
                      'Mozilla/5.0 (X11; U; Linux i686; fr; rv:1.9.0.1) Gecko/2008070206 Firefox/2.0.0.8',
                      'Mozilla/4.0 (compatible; MSIE 5.0; Linux 2.4.20-686 i686) Opera 6.02  [en]']
        return random.choice(UserAgents)

    def get_sis_cookies(self, loginname, password):
        if loginname is '' or password is '':
            return None
        login_data = {'action': 'login',
                      'loginsubmit': 'true',
                      '62838ebfea47071969cead9d87a2f1f7': loginname,
                      'c95b1308bda0a3589f68f75d23b15938': password}

        ck = requests.post(self.baseurl + 'logging.php', data=login_data).cookies
        if len(ck.values()[0]) > 10:
            return ck
        else:
            return None

    def make_soup(self, url):
        while True:
            try:
                response = requests.get(url, headers={'User-Agent': self.get_headers()}, cookies=self.cookies, timeout=10)
                return BeautifulSoup(response.content.decode('gbk', 'ignore'), 'lxml')
            except:
                self.emitInfo('Time out on <a href="{}">this</a>, try again.'.format(url))
                time.sleep(3)


    def emitInfo(self, text):
        self.send_text.emit('[{t}] {info}'.format(t=datetime.datetime.now().strftime('%H:%M:%S'), info=text))


class SISTopic(TheDownloader):
    """ this object intend to download all topics in the given forum """

    def __init__(self, url, topics_pool, maxtopics, loginname=None, password=None, parent=None):
        super(SISTopic, self).__init__(loginname, password, parent)
        self.url = url
        self.thispool = topics_pool
        self.thistopics = maxtopics

    def run(self):
        self.emitInfo('Topics collecting, 开始搜集所有帖子地址...')
        while True:
            try:
                __tps = self.extract_info_from_page(next(self.url))
                self.thispool.extend(__tps)
                self.thistopics[0] += len(__tps)
            except StopIteration:
                self.emitInfo('This thread topics collector done, 该线程帖子搜集完毕.')
                return

    def extract_info_from_page(self, page):
        ret = []
        self.emitInfo('Downloading all topics in page <a href="{}">{}</a>'.format(page, page.split('/')[-1]))
        # make soup object
        try:
            raw_info = self.make_soup(page)
            raw_info = raw_info.findAll('tbody')
        except:
            self.emitInfo('Bad page: <a href="{}">{}</a>'.format(page, page.split('/')[-1]))
            return
        for e in raw_info:
            try:
                # requrie the movie type
                topic_type = e.find('th').find('em').find('a').text
            except AttributeError:
                continue
            # filter the non-moive topic
            if topic_type == '版务':
                continue
            name = e.span.a.text
            url = e.find('a')['href']
            ret.append((topic_type, name, url))
        return ret


class SISTors(TheDownloader):
    def __init__(self, topics_pool, save_dir, current_progress, myname, pics=0, loginname=None, password=None, parent=None):
        super(SISTors, self).__init__(loginname, password, parent)
        self.thispool = topics_pool
        self.save_dir = save_dir
        self.slash = self.get_os_slash()
        self.headers = self.get_headers()
        self.pics = pics
        self.progress = current_progress
        self.myname = myname
        try:
            os.mkdir(self.save_dir)
        except:
            pass

    def run(self):
        while True:
            try:
                self.download_content_from_topic(next(self.thispool))
            except StopIteration:
                self.emitInfo('{} thread has finished, 该线程种子下载完了.'.format(self.myname))
                return

    def download_content_from_topic(self, topics):
        # get target path
        tar_path = self.save_dir + self.slash + topics[0]
        tar_page = self.baseurl + topics[2]
        try:
            os.mkdir(tar_path)
        except:
            pass
        clean_topic_name = topics[1]
        for each in '/:<>':
            clean_topic_name = clean_topic_name.replace(each, '')
        tar_path += self.slash + clean_topic_name + self.slash
        self.emitInfo('({}) Download from {}'.format(self.myname, tar_path.split(self.slash)[-2]))
        try:
            os.mkdir(tar_path)
        except FileExistsError:
            self.emitInfo('({}) {} exists (已经下载过了).'.format(self.myname, clean_topic_name))
            self.progress[0] += 1
            return
        except OSError as err:
            self.emitInfo('({}) Making Dir err, Please check it.\n{}'.format(self.myname, err))
            return
        pagesoup = self.make_soup(tar_page)
        # get movie information
        page_info = pagesoup.find('td', {'class': 'postcontent'})
        # get torrents address and download
        try:
            self.save_torrents(page_info, tar_path)
        except BaseException as err:
            print(err)
            self.emitInfo(err)
            return 
        # write movie information to local file
        self.save_info_text(page_info, tar_path)
        # download pictures
        self.save_pictures(page_info, tar_path)
        self.progress[0] += 1

    def save_torrents(self, pagesoup, tar_path):
        page_tors = pagesoup.find_all('a', {'href': re.compile(r'attachment')})
        if page_tors is None:
            raise BaseException('Broken page (页面错误)')
        # download torrents
        for each_attach in page_tors:
            try:
                print('Download {}'.format(each_attach.text))
                filename = tar_path + each_attach.text
                with open(filename, 'wb') as tor:
                    tor.write(requests.get(self.baseurl + each_attach['href']).content)
            except BaseException as err:
                print('{} {}'.format(each_attach, err))
                continue

    def save_info_text(self, page_info, tar_path):
        text = page_info.find('div', {'class': 't_msgfont'}).text
        with open(tar_path + 'info.txt', 'w') as f:
            try:
                f.write(text)
            except:
                print('Information download failed.')
                return

    def save_pictures(self, page_info, tar_path):
        for each_pic in page_info.find_all('img', {'src': re.compile(r'jpg|png')})[:self.pics]:
            pic_url = each_pic['src']
            filename = pic_url[pic_url.rfind('/') + 1:]
            try:
                print('\t\t\t{}'.format(filename))
                filename_with_path = tar_path + filename
                with open(filename_with_path, 'wb') as pic:
                    pic.write(requests.get(pic_url, timeout=30).content)
            except BaseException:
                print('\t\t\tBroken picture, trying next one.')
                continue

    def get_os_slash(self):
        if os.name == 'posix':
            return '/'
        elif os.name == 'nt':
            return '\\'