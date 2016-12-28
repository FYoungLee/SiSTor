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
import flatbencode
import json
from PyQt5.QtCore import QThread
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtCore import QReadWriteLock
import tor2mag


class SISThread(QThread):
    locker = QReadWriteLock()

    def __init__(self, parent=None):
        super(SISThread, self).__init__(parent)
        self.finished.connect(self.deleteLater)
        self.running = True

    def setRunning(self, how):
        self.running = how


class TheDownloader(SISThread):
    send_text = pyqtSignal(str)
    bad_proxies_record = {}

    def __init__(self, proxies_pool, cookies, parent=None):
        super(TheDownloader, self).__init__(parent=parent)
        with open('sis_addr.dat', 'r') as f:
            self.baseurl = f.readline()
        self.proxies_pool = proxies_pool
        self.cookies = cookies

    def get_headers(self):
        UserAgents = ['Mozilla/5.0 (Windows; U; Windows NT 5.1; en-US; rv:1.9a2pre) Gecko/20061231 Minefield/3.0a2pre',
                      'Mozilla/5.0 (X11; U; Linux x86_64; de; rv:1.8.1.12) Gecko/20080203 SUSE/2.0.0.12-6.1 Firefox/2.0.0.12',
                      'Mozilla/5.0 (X11; U; FreeBSD i386; ru-RU; rv:1.9.1.3) Gecko/20090913 Firefox/3.5.3',
                      'Mozilla/5.0 (X11; U; Linux i686; fr; rv:1.9.0.1) Gecko/2008070206 Firefox/2.0.0.8',
                      'Mozilla/4.0 (compatible; MSIE 5.0; Linux 2.4.20-686 i686) Opera 6.02  [en]']
        return {'User-Agent': random.choice(UserAgents)}

    def get_proxy(self):
        return {'http': random.choice(self.proxies_pool)}

    def make_soup(self, url):
        while True:
            proxy = self.get_proxy()
            try:
                response = requests.get(url, headers=self.get_headers(), cookies=self.cookies,
                                        proxies=proxy, timeout=10)
                return BeautifulSoup(response.content.decode('gbk', 'ignore'), 'lxml')
            except requests.exceptions.RequestException:
                # when a connection problem occurred, this procedure will record which proxy made this problem
                # and how many times of connection problem this proxy made.
                # if the error times greater than 10, this proxy will be moved from proxies pool.
                self.emitInfo('Time out on <a href="{}">{}</a> with proxy, try again.'.format(url, url.split('/')[-1]))
                if proxy['http'] in self.bad_proxies_record.keys():
                    self.bad_proxies_record[proxy['http']] += 1
                else:
                    self.bad_proxies_record[proxy['http']] = 1
                if self.bad_proxies_record[proxy['http']] > 10 and proxy['http'] is not None:
                    try:
                        self.locker.lockForWrite()
                        self.proxies_pool.pop(self.proxies_pool.index(proxy['http']))
                        print('{} popped.'.format(proxy['http']))
                    except ValueError:
                        print('{} has already popped.'.format(proxy['http']))
                    finally:
                        self.locker.unlock()
                time.sleep(3)

    def emitInfo(self, text):
        self.send_text.emit('[{t}] {info}'.format(t=datetime.datetime.now().strftime('%H:%M:%S'), info=text))


class SISTopic(TheDownloader):
    """ this object intend to download all topics in the given forum """

    def __init__(self, pages_generator, topics_pool, proxies_pool, cookies=None, parent=None):
        super(SISTopic, self).__init__(proxies_pool, cookies, parent)
        self.pages_generator = pages_generator
        self.thispool = topics_pool

    def run(self):
        connectDB = sqlite3.connect('SISDB.sqlite')
        allUrlDownloaded = [x[0] for x in connectDB.cursor().execute('SELECT tid FROM SIS').fetchall()]
        connectDB.close()
        while self.running:
            try:
                __tps = self.extract_info_from_page(next(self.pages_generator))
                try:
                    __tps = list(filter(lambda x: x[0].split('.')[0] not in allUrlDownloaded, __tps))
                except TypeError:
                    pass
                try:
                    self.locker.lockForWrite()
                    self.thispool.extend(__tps)
                except TypeError:
                    pass
                finally:
                    self.locker.unlock()
            except StopIteration:
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
            try:
                thumb_up = int(e.find('cite').contents[-1].strip())
            except KeyError:
                thumb_up = 0
            _s_t = e.findAll('td', {'class': 'nums'})[-1].text.split('/')
            size = _s_t[0].strip()
            mov_type = _s_t[1].strip()
            mosaic = self.ismosaic(page)
            cate = self.getCategory(page)
            ret.append((url, topic_type, name, mosaic, thumb_up, create_date, size, mov_type, cate))
        return ret

    def ismosaic(self, url):
        if 'forum-143-' in url or 'forum-229-' in url or 'forum-25-' in url or 'forum-77-' in url:
            return 0
        elif 'forum-230-' in url or 'forum-58-' in url:
            return 1
        else:
            return 2

    def getCategory(self, url):
        if 'forum-143-' in url or 'forum-230-' in url or 'forum-25-' in url or 'forum-58-' in url:
            return 'asia'
        elif 'forum-229-' in url or 'forum-77-' in url:
            return 'western'
        else:
            return 'cartoon'


class SISTors(TheDownloader):
    def __init__(self, topics_pool, sqlqueries_pool, proxies_pool, topics_working_threads, cookies=None, parent=None):
        super(SISTors, self).__init__(proxies_pool, cookies, parent)
        self.topics_pool = topics_pool
        self.thisqueries_pool = sqlqueries_pool
        self.headers = self.get_headers()
        self.topics_working_threads = topics_working_threads

    def run(self):
        while self.running:
            try:
                self.locker.lockForWrite()
                job = self.topics_pool.pop()
            except IndexError:
                print('Out of topics work, bye.')
                self.topics_working_threads[0] -= 1
                return
            finally:
                self.locker.unlock()
            self.download_content_from_topic(job)
        self.topics_working_threads[0] -= 1

    def download_content_from_topic(self, topics):
        tar_page = self.baseurl + topics[0]
        t_id = topics[0].split('.')[0]
        t_type = topics[1]
        t_name = topics[2]
        t_mosaic = topics[3]
        t_thumbup = topics[4]
        t_date = topics[5]
        t_size = topics[6]
        try:
            if 'G' in t_size:
                t_size = float(re.match(r'(\d+\.?\d+)', t_size).group(1)) * 1000
            else:
                t_size = float(re.match(r'(\d+\.?\d+)', t_size).group(1))
        except (AttributeError, ValueError):
            t_size = 0
        t_mtype = topics[7]
        t_catey = topics[8]
        self.emitInfo('Downloading {}'.format(t_name))
        pagesoup = self.make_soup(tar_page)
        # get movie information
        try:
            page_info = pagesoup.find('td', {'class': 'postcontent'})
        except AttributeError:
            self.emitInfo('{} failed.'.format(tar_page))
            return

        self.insertToQueriesPool(t_id, t_name, t_type, t_mosaic, t_thumbup, t_date, t_size, t_mtype, t_catey, page_info)

    def insertToQueriesPool(self, tid, tname, ttype, tmosaic, tthumbup, tdate, tsize, tmtype, tcatey, page_info):
        try:
            page_tors = page_info.find_all('a', {'href': re.compile(r'attachment')})
        except AttributeError:
            return
        if page_tors is None:
            return
        # download torrents
        for each_attach in page_tors:
            tor = self.baseurl + each_attach['href']
            tries = 5
            while tries:
                try:
                    # print('Download {}'.format(each_attach.text))
                    torbyte = requests.get(tor, headers=self.get_headers(), timeout=10).content
                    magaddr = tor2mag.decodeTor(torbyte)
                    try:
                        self.locker.lockForWrite()
                        self.thisqueries_pool['tor'].append((tid, magaddr))
                    finally:
                        self.locker.unlock()
                    break
                except requests.exceptions.RequestException:
                    print('Torrent "{}" download failed, try again.'.format(tor))
                    tries -= 1
                    time.sleep(2)
                    continue
                except flatbencode.DecodingError:
                    print('Torrent "{}" decode failed, abort.'.format(tor))
                    break
        try:
            tbrief = page_info.find('div', {'class': 't_msgfont'}).text
        except AttributeError:
            tbrief = '没有'
        if tmosaic == 2:
            if '无码' in tname or '无码' in tbrief or '無碼' in tbrief or '無碼' in tname:
                tmosaic = 0
            elif '有码' in tname or '有码' in tbrief or '有碼' in tname or '有碼' in tbrief:
                tmosaic = 1
        try:
            self.locker.lockForWrite()
            self.thisqueries_pool['main']\
                .append((tid, ttype, tname, tmosaic, tthumbup, tdate, tsize, tmtype, tbrief, tcatey))
        finally:
            self.locker.unlock()

        for each_pic in page_info.find_all('img', {'src': re.compile(r'jpg|png')}):
            pic_url = each_pic['src']
            try:
                self.locker.lockForWrite()
                self.thisqueries_pool['pic'].append((tid, pic_url))
            finally:
                self.locker.unlock()


class SISSql(SISThread):
    """ operate the databases"""

    def __init__(self, sqlque, pics_pool_for_downloading, parent=None):
        super(SISSql, self).__init__(parent)
        self.queries = sqlque
        self.pics_pool_for_downloading = pics_pool_for_downloading
        self.pics_pool_for_updating_db = []

    def run(self):
        while True:
            connect = sqlite3.connect('SISDB.sqlite')
            query = connect.cursor().execute
            try:
                if len(self.queries['pic']):
                    try:
                        self.locker.lockForWrite()
                        picinfo = self.queries['pic'].pop()
                        query('INSERT INTO SISpic (tid, picaddr) VALUES(?, ?)', (picinfo[0], picinfo[1]))
                        self.pics_pool_for_downloading.append(picinfo)
                    except sqlite3.IntegrityError as err:
                        print(err)
                    finally:
                        self.locker.unlock()
                if len(self.queries['tor']):
                    try:
                        self.locker.lockForWrite()
                        torinfo = self.queries['tor'].pop()
                        query('INSERT INTO SIStor VALUES(?, ?)', (torinfo[0], torinfo[1]))
                    except sqlite3.IntegrityError as err:
                        print(err)
                    finally:
                        self.locker.unlock()

                if len(self.queries['main']):
                    try:
                        self.locker.lockForWrite()
                        maininfo = self.queries['main'].pop()
                        query('INSERT INTO SIS VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                              (maininfo[0], maininfo[1], maininfo[2], maininfo[3],
                               maininfo[4], maininfo[5], maininfo[6], maininfo[7], maininfo[8], maininfo[9]))
                    except sqlite3.IntegrityError as err:
                        print(err)
                    finally:
                        self.locker.unlock()
                if len(self.pics_pool_for_updating_db):
                    try:
                        self.locker.lockForWrite()
                        pic = self.pics_pool_for_updating_db.pop()
                        if pic[0]:
                            query('UPDATE SISpic SET picb=? WHERE picaddr=?', (pic[0], pic[1]))
                            # print('Updated new picture {}'.format(pic[1]))
                        else:
                            query('DELETE FROM SISpic WHERE picaddr=?', (pic[1],))
                            # print('Bad picture deleted {}'.format(pic[1]))
                    except sqlite3.IntegrityError as err:
                        print(err)
                    finally:
                        self.locker.unlock()
            finally:
                connect.commit()
                connect.close()

    def picUpdate(self, picpak):
        self.pics_pool_for_updating_db.append(picpak)


class SISPicLoader(SISThread):
    picpak_broadcast = pyqtSignal(tuple)

    def __init__(self, pics_pool_for_downloading, pictures_working_threads, parent=None):
        super(SISPicLoader, self).__init__(parent)
        self.pics_pool_for_downloading = pics_pool_for_downloading
        self.pictures_working_threads = pictures_working_threads

    def run(self):
        while self.running:
            try:
                self.locker.lockForWrite()
                getjob = self.pics_pool_for_downloading.pop()
            except IndexError:
                # print('Out of pictures work, bye.')
                self.pictures_working_threads[0] -= 1
                return
            finally:
                self.locker.unlock()
            try:
                if requests.head(getjob[1], timeout=5).ok is False:
                    continue
                bpic = requests.get(getjob[1], timeout=120).content
                if b'html' not in bpic and None is not bpic:
                    self.picpak_broadcast.emit((bpic, getjob[1]))
                else:
                    self.picpak_broadcast.emit((None, getjob[1]))
            except requests.exceptions.RequestException:
                self.picpak_broadcast.emit((None, getjob[1]))
        self.pictures_working_threads[0] -= 1
