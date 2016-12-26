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
import sqlite3
from PyQt5.QtCore import QThread
from PyQt5.QtCore import pyqtSignal
import tor2mag


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

        cookies = requests.post(self.baseurl + 'logging.php', data=login_data).cookies
        if len(cookies.values()[0]) > 10:
            return cookies
        else:
            return None

    def make_soup(self, url):
        try_times = 5
        while try_times:
            try:
                response = requests.get(url, headers={'User-Agent': self.get_headers()}, cookies=self.cookies,
                                        timeout=10)
                return BeautifulSoup(response.content.decode('gbk', 'ignore'), 'lxml')
            except:
                self.emitInfo('Time out on <a href="{}">this</a>, try again.'.format(url))
                time.sleep(3)
                try_times -= 1
        return None

    def emitInfo(self, text):
        self.send_text.emit('[{t}] {info}'.format(t=datetime.datetime.now().strftime('%H:%M:%S'), info=text))


class SISTopic(TheDownloader):
    """ this object intend to download all topics in the given forum """

    def __init__(self, pages_generator, topics_pool, maxtopics, loginname=None, password=None, parent=None):
        super(SISTopic, self).__init__(loginname, password, parent)
        self.pages_generator = pages_generator
        self.thispool = topics_pool
        self.thistopics = maxtopics


    def run(self):
        self.emitInfo('Topics collecting, 开始搜集所有帖子地址...')
        connectDB = sqlite3.connect('SISDB.sqlite')
        allUrlDownloaded = [x[0] for x in connectDB.cursor().execute('SELECT tid FROM SIS').fetchall()]
        connectDB.close()
        while True:
            try:
                __tps = self.extract_info_from_page(next(self.pages_generator))
                newtpc = list(filter(lambda x: x[0].split('.')[0] not in allUrlDownloaded, __tps))
                self.thispool.extend(newtpc)
                self.thistopics[0] += len(newtpc)
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
            create_date = e.find('td', {'class': 'author'}).em.text.strip()
            thumb_up = int(e.find('cite').contents[-1].strip())
            _s_t = e.findAll('td', {'class': 'nums'})[-1].text.split('/')
            size = _s_t[0].strip()
            mov_type = _s_t[1].strip()
            mosaic = self.ismosaic(page)
            ret.append((url, topic_type, name, mosaic, thumb_up, create_date, size, mov_type))
        return ret

    def ismosaic(self, url):
        if 'forum-143-' in url or 'forum-229-' in url or 'forum-25-' in url or 'forum-77-' in url:
            return 0
        elif 'forum-230-' in url or 'forum-58-' in url:
            return 1
        else:
            return 2


class SISTors(TheDownloader):
    def __init__(self, topics_pool, sqlqueries_pool, current_progress, myname, loginname=None, password=None,
                 parent=None):
        super(SISTors, self).__init__(loginname, password, parent)
        self.thispool = topics_pool
        self.thisqueries_pool = sqlqueries_pool
        self.headers = self.get_headers()
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
        tar_page = self.baseurl + topics[0]
        t_id = topics[0].split('.')[0]
        t_type = topics[1]
        t_name = topics[2]
        t_mosaic = topics[3]
        t_thumbup = topics[4]
        t_date = topics[5]
        t_size = topics[6]
        if 'M' in t_size:
            t_size = int(t_size.replace('M', '').replace('B', ''))
        elif 'G' in t_size:
            t_size = int(float(t_size.replace('G', '').replace('B', '')) * 1000)
        t_mtype = topics[7]
        self.emitInfo('({}) Downloading {}'.format(self.myname, t_name))
        pagesoup = self.make_soup(tar_page)
        # get movie information
        try:
            page_info = pagesoup.find('td', {'class': 'postcontent'})
        except AttributeError:
            self.emitInfo('({}) {} failed.'.format(self.myname, tar_page))
            return
        try:
            self.insertToQueriesPool(t_id, t_name, t_type, t_mosaic, t_thumbup, t_date, t_size, t_mtype, page_info)
        except BaseException as err:
            self.emitInfo(err)
            return
        self.progress[0] += 1

    def insertToQueriesPool(self, tid, tname, ttype, tmosaic, tthumbup, tdate, tsize, tmtype, page_info):
        page_tors = page_info.find_all('a', {'href': re.compile(r'attachment')})
        if page_tors is None:
            raise BaseException('Broken page (页面错误)')
        # download torrents
        for each_attach in page_tors:
            try:
                print('Download {}'.format(each_attach.text))
                torbyte = requests.get(self.baseurl + each_attach['href']).content
                magaddr = tor2mag.decodeTor(torbyte)
                self.thisqueries_pool['tor'].append((tid, magaddr))
            except BaseException as err:
                print('{} {}'.format(each_attach, err))
                continue
        try:
            tbrief = page_info.find('div', {'class': 't_msgfont'}).text
        except:
            tbrief = 'NULL'
        if tmosaic == 2:
            if '无码' in tname or '无码' in tbrief or '無碼' in tbrief or '無碼' in tname:
                tmosaic = 0
            elif '有码' in tname or '有码' in tbrief or '有碼' in tname or '有碼' in tbrief:
                tmosaic = 1
        self.thisqueries_pool['main'].append((tid, ttype, tname, tmosaic, tthumbup, tdate, tsize, tmtype, tbrief))

        for each_pic in page_info.find_all('img', {'src': re.compile(r'jpg|png')}):
            pic_url = each_pic['src']
            try:
                if requests.head(pic_url, timeout=5).ok:
                    self.thisqueries_pool['pic'].append((tid, pic_url))
            except BaseException:
                print('Broken picture: {} (ignored)'.format(pic_url))
                continue


class SISSql(QThread):
    """ operate the databases"""

    def __init__(self, sqlque, parent=None):
        super(SISSql, self).__init__(parent)
        self.queries = sqlque

    def run(self):
        while True:
            connect = sqlite3.connect('SISDB.sqlite')
            query = connect.cursor().execute
            try:
                picinfo = self.queries['pic'].pop()
                query('INSERT INTO SISpic VALUES(?, ?)', (picinfo[0], picinfo[1]))
                torinfo = self.queries['tor'].pop()
                query('INSERT INTO SIStor VALUES(?, ?)', (torinfo[0], torinfo[1]))
                maininfo = self.queries['main'].pop()
                query('INSERT INTO SIS VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)',
                           (maininfo[0], maininfo[1], maininfo[2], maininfo[3],
                            maininfo[4], maininfo[5], maininfo[6], maininfo[7], maininfo[8]))
            except IndexError:
                if 0 == len(self.queries['pic']):
                    # print('No more queries in pool, let me take a break.')
                    time.sleep(5)
            finally:
                connect.commit()
                connect.close()


class SISPicLoader(QThread):
    jobDone = pyqtSignal(dict, name='picjob')

    def __init__(self, task, target, parent=None):
        super(SISPicLoader, self).__init__(parent)
        self.local_task = task
        self.local_target = target

    def run(self):
        try_times = 5
        while try_times:
            try:
                bpic = requests.get(self.local_target, timeout=60).content
                self.local_task['job'].append(bpic)
                self.local_task['local'] += 1
                if self.local_task['local'] == self.local_task['total']:
                    self.jobDone.emit(self.local_task)
                return
            except:
                try_times -= 1
