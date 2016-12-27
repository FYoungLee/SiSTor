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
from PyQt5.QtCore import QThread
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtCore import QReadWriteLock
import tor2mag


class SISThread(QThread):
    locker = QReadWriteLock()

    def __init__(self, parent=None):
        super(SISThread, self).__init__(parent)
        self.finished.connect(self.deleteLater)


class TheDownloader(SISThread):
    send_text = pyqtSignal(str)

    def __init__(self, cookies, parent=None):
        super(TheDownloader, self).__init__(parent=parent)
        with open('sis_addr.dat', 'r') as f:
            self.baseurl = f.readline()
        self.cookies = cookies

    def get_headers(self):
        UserAgents = ['Mozilla/5.0 (Windows; U; Windows NT 5.1; en-US; rv:1.9a2pre) Gecko/20061231 Minefield/3.0a2pre',
                      'Mozilla/5.0 (X11; U; Linux x86_64; de; rv:1.8.1.12) Gecko/20080203 SUSE/2.0.0.12-6.1 Firefox/2.0.0.12',
                      'Mozilla/5.0 (X11; U; FreeBSD i386; ru-RU; rv:1.9.1.3) Gecko/20090913 Firefox/3.5.3',
                      'Mozilla/5.0 (X11; U; Linux i686; fr; rv:1.9.0.1) Gecko/2008070206 Firefox/2.0.0.8',
                      'Mozilla/4.0 (compatible; MSIE 5.0; Linux 2.4.20-686 i686) Opera 6.02  [en]']
        return random.choice(UserAgents)

    def make_soup(self, url):
        try_times = 5
        while try_times:
            try:
                response = requests.get(url, headers={'User-Agent': self.get_headers()}, cookies=self.cookies,
                                        timeout=10)
                return BeautifulSoup(response.content.decode('gbk', 'ignore'), 'lxml')
            except:
                self.emitInfo('Time out on <a href="{}">{}</a>, try again.'.format(url, url.split('/')[-1]))
                time.sleep(3)
                try_times -= 1
        return None

    def emitInfo(self, text):
        self.send_text.emit('[{t}] {info}'.format(t=datetime.datetime.now().strftime('%H:%M:%S'), info=text))


class SISTopic(TheDownloader):
    """ this object intend to download all topics in the given forum """

    def __init__(self, pages_generator, topics_pool, cookies=None, parent=None):
        super(SISTopic, self).__init__(cookies, parent)
        self.pages_generator = pages_generator
        self.thispool = topics_pool

    def run(self):
        connectDB = sqlite3.connect('SISDB.sqlite')
        allUrlDownloaded = [x[0] for x in connectDB.cursor().execute('SELECT tid FROM SIS').fetchall()]
        connectDB.close()
        while True:
            try:
                __tps = self.extract_info_from_page(next(self.pages_generator))
                newtpc = list(filter(lambda x: x[0].split('.')[0] not in allUrlDownloaded, __tps))
                try:
                    self.locker.lockForWrite()
                    self.thispool.extend(newtpc)
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
    thread_progress_signal = pyqtSignal(str)

    def __init__(self, topics_generator, sqlqueries_pool, cookies=None, parent=None):
        super(SISTors, self).__init__(cookies, parent)
        self.topics_generator = topics_generator
        self.thisqueries_pool = sqlqueries_pool
        self.headers = self.get_headers()
        try:
            os.mkdir(self.save_dir)
        except:
            pass

    def run(self):
        while True:
            try:
                self.download_content_from_topic(next(self.topics_generator))
                self.thread_progress_signal.emit('one thread finished')
            except StopIteration:
                self.thread_progress_signal.emit('topic thread done')
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
        self.emitInfo('Downloading {}'.format(t_name))
        pagesoup = self.make_soup(tar_page)
        # get movie information
        try:
            page_info = pagesoup.find('td', {'class': 'postcontent'})
        except AttributeError:
            self.emitInfo('{} failed.'.format(tar_page))
            return

        self.insertToQueriesPool(t_id, t_name, t_type, t_mosaic, t_thumbup, t_date, t_size, t_mtype, page_info)


    def insertToQueriesPool(self, tid, tname, ttype, tmosaic, tthumbup, tdate, tsize, tmtype, page_info):
        try:
            page_tors = page_info.find_all('a', {'href': re.compile(r'attachment')})
        except AttributeError:
            return
        if page_tors is None:
            return
        # download torrents
        tor_errs = 0
        for each_attach in page_tors:
            try:
                # print('Download {}'.format(each_attach.text))
                torbyte = requests.get(self.baseurl + each_attach['href']).content
                magaddr = tor2mag.decodeTor(torbyte)
                self.locker.lockForWrite()
                self.thisqueries_pool['tor'].append((tid, magaddr))
            except (requests.exceptions.RequestException, flatbencode.DecodingError) as err:
                print('{} {}'.format(each_attach, err))
                tor_errs += 1
                continue
            finally:
                self.locker.unlock()
        if tor_errs == len(page_tors):
            return
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
            self.thisqueries_pool['main'].append((tid, ttype, tname, tmosaic, tthumbup, tdate, tsize, tmtype, tbrief))
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
                        query('INSERT INTO SIS VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)',
                              (maininfo[0], maininfo[1], maininfo[2], maininfo[3],
                               maininfo[4], maininfo[5], maininfo[6], maininfo[7], maininfo[8]))
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
                            print('Updated new picture {}'.format(pic[1]))
                        else:
                            query('DELETE FROM SISpic WHERE picaddr=?', (pic[1],))
                            print('Bad picture deleted {}'.format(pic[1]))
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
    thread_progress_signal = pyqtSignal(str)

    def __init__(self, pics_generator, parent=None):
        super(SISPicLoader, self).__init__(parent)
        self.pics_generator = pics_generator

    def run(self):
        while True:
            try:
                getjob = next(self.pics_generator)
            except StopIteration:
                print('Picture thread waitting for job.')
                time.sleep(3)
                continue
            try:
                bpic = requests.get(getjob[1], timeout=60).content
                self.picpak_broadcast.emit((bpic, getjob[1]))
            except requests.exceptions.RequestException:
                self.picpak_broadcast.emit((None, getjob[1]))
            finally:
                self.thread_progress_signal.emit('one picture finished')


