"""
    Multiply Threads Crawler for downloading torrents from SexInSex fourm
    Author: Fyound Lix
    Create: 11/05/2016
    Version: 1.0
"""
from bs4 import BeautifulSoup
import re
import datetime
import requests
import random
import time
import sqlite3
import flatbencode
import sys
import hashlib
import struct
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
        response = self.request_with_proxy(url)
        return BeautifulSoup(response.content.decode('gbk', 'ignore'), 'lxml')

    def request_with_proxy(self, url):
        while True:
            proxy = self.get_proxy()
            try:
                return requests.get(url, headers=self.get_headers(), cookies=self.cookies, proxies=proxy, timeout=10)
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


class SISPageLoader(TheDownloader):
    """ this object intend to download all topics in the given forum """

    def __init__(self, pages_generator, task_queues, topics_working_threads, proxies_pool, cookies=None, parent=None):
        super(SISPageLoader, self).__init__(proxies_pool, cookies, parent)
        self.pages_generator = pages_generator
        self.task_queues = task_queues
        self.topics_working_threads = topics_working_threads

    def run(self):
        connectDB = sqlite3.connect('SISDB.sqlite')
        # extract all downloaded topics from databases.
        allUrlDownloaded = ['thread-' + x[0] for x in connectDB.cursor().execute('SELECT tid FROM SIStops').fetchall()]
        # plus those topics in local queue.
        allUrlDownloaded.extend([x.split('.')[0] for x in self.task_queues['topics']])
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
                    self.task_queues['topics'].extend(__tps)
                except TypeError:
                    pass
                finally:
                    self.locker.unlock()
            except StopIteration:
                self.topics_working_threads[0] -= 1
                return

    def extract_info_from_page(self, page):
        ret = []
        self.emitInfo('Downloading all topics in page <a href="{}">{}</a>'.format(page, page.split('/')[-1]))
        # make soup object
        try:
            raw_info = self.make_soup(page)
            raw_info = raw_info.findAll('tbody')
        except AttributeError :
            self.emitInfo('Bad page: <a href="{}">{}</a>'.format(page, page.split('/')[-1]))
            return
        for e in raw_info:
            try:
                if '版务' in e.find('th').find('em').find('a').text:
                    continue
            except AttributeError as err:
                print('{} : Line {}'.format(err, sys.exc_info()[2].tb_frame.f_lineno))
                continue
            url = e.find('a')['href']
            ret.append(url)
        return ret


class SISTopicLoader(TheDownloader):
    def __init__(self, task_queues, sqlqueries_pool, topics_working_threads, proxies_pool, cookies=None, parent=None):
        super(SISTopicLoader, self).__init__(proxies_pool, cookies, parent)
        self.task_queues = task_queues
        self.thisqueries_pool = sqlqueries_pool
        self.topics_working_threads = topics_working_threads

    def run(self):
        while self.running:
            try:
                self.locker.lockForWrite()
                job = self.task_queues['topics'].pop()
            except IndexError:
                print('Out of topics work, bye.')
                self.topics_working_threads[0] -= 1
                return
            finally:
                self.locker.unlock()
            self.download_topics(job)
        self.topics_working_threads[0] -= 1

    def download_topics(self, url):
        url = self.baseurl + url
        topicsoup = self.make_soup(url)
        try:
            # crawl all topics info
            t_id = url.split('.')[0].replace('thread-', '')
            t_type = topicsoup.find('h1').a.text[1:-1]
            t_name = topicsoup.find('h1').a.next_sibling
            t_censor = self.isMosic(topicsoup)
            t_thumbup = topicsoup.find('a', {'id': 'ajax_thanks'}).text
            t_date = re.search(r'(\d+-\d+-\d+)', topicsoup.find('div', {'class': 'postinfo'}).text).group(1)
            if 'asia' in topicsoup.find('div', {'id': 'nav'}).text.lower():
                t_category = 1
            elif 'western' in topicsoup.find('div', {'id': 'nav'}).text.lower():
                t_category = 2
            elif 'anime' in topicsoup.find('div', {'id': 'nav'}).text.lower():
                t_category = 3
            else:
                t_category = 0
            try:
                self.locker.lockForWrite()
                self.thisqueries_pool['top'].append((t_id, t_type, t_name, t_censor, t_thumbup, t_date, t_category))
            finally:
                self.locker.unlock()
            # push tors into queue
            try:
                page_tors = topicsoup.find_all('a', {'href': re.compile(r'attachment')})
                for each in page_tors:
                    self.task_queues['tors'].append((t_id, each['href']))
            except AttributeError as err:
                print('{} : Line {}'.format(err, sys.exc_info()[2].tb_frame.f_lineno))
                return
            # push pics into queue
            for pic in topicsoup.find('div', {'class': 't_msgfont'}).find_all('img', {'src': re.compile(r'jpg|png')}):
                pic_url = pic['src']
                try:
                    self.locker.lockForWrite()
                    self.task_queues['pics'].append((t_id, pic_url))
                finally:
                    self.locker.unlock()
        except AttributeError as err:
            print('{} : Line {}'.format(err, sys.exc_info()[2].tb_frame.f_lineno))
            return

    def isMosic(self, obj):
        try:
            area1 = obj.find('div', {'id': 'foruminfo'}).text
            area2 = obj.find('div', {'class': 't_msgfont'}).text
        except AttributeError:
            return 2
        if '无码' in area1 or '无码' in area2 or '無碼' in area1 or '無碼' in area2:
            return 0
        elif '有码' in area1 or '有码' in area2 or '有碼' in area1 or '有碼' in area2:
            return 1
        else:
            return 2

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
                    # torbyte = requests.get(tor, headers=self.get_headers(), timeout=10).content
                    torbyte = self.request_with_proxy(tor).content
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
                    time.sleep(1)
                    continue
                except flatbencode.DecodingError:
                    self.thisqueries_pool['tor'].append((tid, tor))
                    print('{} decode failed.'.format(tor))
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


class SISTorLoader(TheDownloader):
    def __init__(self, task_queues, sqlqueries_pool, tors_working_threads, proxies_pool, cookies=None, parent=None):
        super(SISTorLoader, self).__init__(proxies_pool, cookies, parent)
        self.task_queues = task_queues
        self.thisqueries_pool = sqlqueries_pool
        self.tors_working_threads = tors_working_threads

    def run(self):
        while self.running:
            try:
                self.locker.lockForWrite()
                job = self.task_queues['tors'].pop()
            except IndexError:
                print('Out of topics work, bye.')
                self.tors_working_threads[0] -= 1
                return
            finally:
                self.locker.unlock()
            self.download_tors(job)
        self.tors_working_threads[0] -= 1

    def download_tors(self, job):
        url = self.baseurl + job[1]
        req = self.request_with_proxy(url)
        try:
            magnet = self.magDecoder(req.content)
            self.thisqueries_pool['tor'].append((job[0], magnet))
        except flatbencode.DecodingError as err:
            print('{} : Line {}'.format(err, sys.exc_info()[2].tb_frame.f_lineno))
            try:
                self.locker.lockForWrite()
                self.task_queues['tors'].append(job)
            finally:
                self.locker.unlock()
            return

    def magDecoder(self, byte):
        hashcontent = flatbencode.encode(flatbencode.decode(byte)[b'info'])
        digest = hashlib.sha1(hashcontent).hexdigest()
        magneturl = 'magnet:?xt=urn:btih:{}'.format(digest)
        return magneturl


class SISPicLoader(SISThread):
    # picpak_broadcast = pyqtSignal(tuple)
    def __init__(self, task_queues, sqlqueries_pool, pictures_working_threads, parent=None):
        super(SISPicLoader, self).__init__(parent)
        self.task_queues = task_queues
        self.pictures_working_threads = pictures_working_threads
        self.sqlqueries_pool = sqlqueries_pool

    def run(self):
        while self.running:
            try:
                self.locker.lockForWrite()
                job = self.task_queues['pics'].pop()
            except IndexError:
                # print('Out of pictures work, bye.')
                self.pictures_working_threads[0] -= 1
                return
            finally:
                self.locker.unlock()
            try:
                if requests.head(job[1], timeout=5).ok is False:
                    continue
                bpic = requests.get(job[1], timeout=120).content
                if self.isImage(bpic):
                    self.sqlqueries_pool['pic'].append((job[0], bpic))
                # if b'html' not in bpic and None is not bpic:
                #     self.picpak_broadcast.emit((job[0], bpic))
                # else:
                    # self.picpak_broadcast.emit((None, getjob[1]))
            except requests.exceptions.RequestException:
                # self.picpak_broadcast.emit((None, getjob[1]))
                pass
        self.pictures_working_threads[0] -= 1

    def bytes2hex(self, bytes):
        hexstr = u""
        for i in range(20):
            t = u"%x" % bytes[i]
            if len(t) % 2:
                hexstr += u"0"
            hexstr += t
        return hexstr.upper()

    def isImage(self, byte):
        typeList = {"FFD8FF": True, "89504E47": True}
        for hcode in typeList.keys():
            f_hcode = self.bytes2hex(byte)
            if hcode in f_hcode:
                return True
            else:
                return False


class SISSql(SISThread):
    """ operate the databases"""

    def __init__(self, sqlque, task_queues, parent=None):
        super(SISSql, self).__init__(parent)
        self.queries = sqlque
        self.task_queues = task_queues

    def run(self):
        while True:
            connect = sqlite3.connect('SISDB.sqlite')
            query = connect.cursor().execute
            try:
                if len(self.queries['pic']):
                    try:
                        self.locker.lockForWrite()
                        picinfo = self.queries['pic'].pop()
                        query('INSERT INTO PicByte VALUES(?, ?)', (picinfo[0], picinfo[1]))
                        query('INSERT INTO PicLink (tid) VALUES(?)', (picinfo[0],))
                    except sqlite3.IntegrityError as err:
                        print(err)
                    finally:
                        self.locker.unlock()
                if len(self.queries['tor']):
                    try:
                        self.locker.lockForWrite()
                        torinfo = self.queries['tor'].pop()
                        query('INSERT INTO SISmags VALUES(?, ?)', (torinfo[0], torinfo[1]))
                    except sqlite3.IntegrityError as err:
                        print(err)
                    finally:
                        self.locker.unlock()

                if len(self.queries['top']):
                    try:
                        self.locker.lockForWrite()
                        maininfo = self.queries['top'].pop()
                        query('INSERT INTO SIStops VALUES(?, ?, ?, ?, ?, ?, ?)',
                              (maininfo[0], maininfo[1], maininfo[2], maininfo[3],
                               maininfo[4], maininfo[5], maininfo[6]))
                    except sqlite3.IntegrityError as err:
                        print(err)
                    finally:
                        self.locker.unlock()
                # if len(self.pics_pool_for_updating_db):
                #     try:
                #         self.locker.lockForWrite()
                #         pic = self.pics_pool_for_updating_db.pop()
                #
                #             # query('UPDATE SISpic SET picb=? WHERE picaddr=?', (pic[0], pic[1]))
                #         query('insert into picb values(?,?)', (pic[0], pic[1]))
                #         query('insert into picid values(?)', (pic[0]))
                #             # print('Updated new picture {}'.format(pic[1]))
                #         # else:
                #             # query('DELETE FROM SISpic WHERE picaddr=?', (pic[1],))
                #             # print('Bad picture deleted {}'.format(pic[1]))
                #     except sqlite3.IntegrityError as err:
                #         print(err)
                #     finally:
                #         self.locker.unlock()
            finally:
                connect.commit()
                connect.close()

    # def picUpdate(self, picpak):
    #     self.pics_pool_for_updating_db.append(picpak)