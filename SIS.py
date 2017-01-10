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
import json
import os
import platform
from PyQt5.QtCore import QThread, pyqtSignal, QReadWriteLock


DBPATH = ''
if 'fyang-MS-7816' in platform.node():
    DBPATH = '/media/fyang/Bakcup/My Files/SIS/'

def check_databases():
    if 'SISDB.sqlite' not in os.listdir('.'):
        connect = sqlite3.connect(DBPATH + 'SISDB.sqlite')
        try:
            connect.cursor().execute(
                """
                create table SIStops(
                tid text primary key not null,
                type text not null,
                name text not null,
                censor integer,
                thumbup integer,
                date integer,
                category integer)
                """)
            connect.cursor().execute(
                """
                create table SISmags(
                tid text not null,
                magnet text not null)""")
            connect.cursor().execute(
                '''
                create table PicPath(
                tid text not null,
                path text not null)
                ''')
            connect.cursor().execute(
                '''
                create table PicMD5(
                path text not null,
                md5 text primary key not null)
                ''')
            os.mkdir('img')
        except:
            pass
        finally:
            connect.commit()
            connect.close()

check_databases()
Working_threads = {'page': 0, 'top': 0, 'tor': 0, 'pic': 0}
SIS_Queries = {'top': [], 'tor': [], 'pic': []}
Finished_jobs = {'pic': 0, 'tor': 0, 'top': 0}
try:
    with open('Jobs.json') as f:
        SIS_POOLS = json.loads(f.read())
except:
    with open('Jobs.json', 'w') as f:
        f.write(json.dumps({'proxies': [], 'pics queue': [], 'tors queue': [], 'tops queue': [], 'piced': {}}))


class SISThread(QThread):
    locker = QReadWriteLock()

    def __init__(self, parent=None):
        super(SISThread, self).__init__(parent)
        self.finished.connect(self.deleteLater)
        self.running = True
        # print('SISThread Created')

    def setRunning(self, how):
        self.running = how


class TheDownloader(SISThread):
    send_text = pyqtSignal(str)
    bad_record = {}
    with open('sis_addr.dat', 'r') as f:
        baseurl = f.readline()

    def __init__(self, cookies, parent=None):
        super(TheDownloader, self).__init__(parent=parent)
        self.cookies = cookies

    def get_headers(self):
        UserAgents = ['Mozilla/5.0 (Windows; U; Windows NT 5.1; en-US; rv:1.9a2pre) Gecko/20061231 Minefield/3.0a2pre',
                      'Mozilla/5.0 (X11; U; Linux x86_64; de; rv:1.8.1.12) Gecko/20080203 SUSE/2.0.0.12-6.1 Firefox/2.0.0.12',
                      'Mozilla/5.0 (X11; U; FreeBSD i386; ru-RU; rv:1.9.1.3) Gecko/20090913 Firefox/3.5.3',
                      'Mozilla/5.0 (X11; U; Linux i686; fr; rv:1.9.0.1) Gecko/2008070206 Firefox/2.0.0.8',
                      'Mozilla/4.0 (compatible; MSIE 5.0; Linux 2.4.20-686 i686) Opera 6.02  [en]',
                      "Mozilla/5.0 (X11; U; Linux i686; en-US) AppleWebKit/534.3 (KHTML, like Gecko) Chrome/6.0.462.0 Safari/534.3",
                      "Mozilla/5.0 (Windows; U; Windows NT 5.2; en-US) AppleWebKit/534.3 (KHTML, like Gecko) Chrome/6.0.462.0 Safari/534.3",
                      "Mozilla/5.0 (Windows; U; Windows NT 6.1; en-US) AppleWebKit/534.3 (KHTML, like Gecko) Chrome/6.0.461.0 Safari/534.3",
                      "Mozilla/5.0 (Windows; U; Windows NT 5.1; en-US) AppleWebKit/534.3 (KHTML, like Gecko) Chrome/6.0.461.0 Safari/534.3",
                      "Mozilla/5.0 (Macintosh; U; Intel Mac OS X 10_6_4; en-US) AppleWebKit/534.3 (KHTML, like Gecko) Chrome/6.0.461.0 Safari/534.3"
                      ]
        return {'User-Agent': random.choice(UserAgents)}

    def get_proxy(self):
        while len(SIS_POOLS['proxies']) == 0:
            time.sleep(3)
        return {'http': random.choice(SIS_POOLS['proxies'])}

    def make_soup(self, url):
        response = self.request_with_proxy(url)
        if response and response.ok:
            return BeautifulSoup(response.content.decode('gbk', 'ignore'), 'lxml')
        return None

    def request_with_proxy(self, url):
        t_times = 10
        while True:
            if t_times:
                proxy = self.get_proxy()
            else:
                return None
            try:
                if requests.head(url, headers=self.get_headers(), cookies=self.cookies, proxies=proxy, timeout=5).ok:
                    req = requests.get(url, headers=self.get_headers(), cookies=self.cookies, proxies=proxy, timeout=15)
                    self.bad_record[proxy['http']] = 0
                    return req
                else:
                    raise requests.exceptions.RequestException
            except requests.exceptions.RequestException:
                # when a connection problem occurred, this procedure will record which proxy made this problem
                # and how many times of connection problem this proxy made.
                # if the error times greater than 10, this proxy will be moved from proxies pool.
                # if t_times < 2:
                #    print('Time out on {} [{}], try again.'.format(url, t_times))
                if proxy['http'] in self.bad_record.keys():
                    self.bad_record[proxy['http']] += 1
                else:
                    self.bad_record[proxy['http']] = 1
                if self.bad_record[proxy['http']] > 100 and proxy['http'] is not None:
                    try:
                        SIS_POOLS['proxies'].pop(SIS_POOLS['proxies'].index(proxy['http']))
                        # print('{} popped.'.format(proxy['http']))
                    except ValueError:
                        # print('{} has already popped.'.format(proxy['http']))
                        pass
                time.sleep(1)
                t_times -= 1

    def emitInfo(self, text):
        self.send_text.emit('[{t}] {info}'.format(t=datetime.datetime.now().strftime('%H:%M:%S'), info=text))


class SISPageLoader(TheDownloader):
    """ this object intend to download all topics in the given forum """
    while True:
        try:
            connectDB = sqlite3.connect(DBPATH + 'SISDB.sqlite')
            rst = connectDB.cursor().execute('SELECT tid FROM SIStops').fetchall()
            Localtid = [x[0] for x in rst]
            connectDB.close()
            break
        except sqlite3.OperationalError:
            continue

    def __init__(self, pages_generator, cookies=None, parent=None):
        super(SISPageLoader, self).__init__(cookies, parent)
        self.pages_generator = pages_generator
        Working_threads['page'] += 1

    def deleteLater(self):
        Working_threads['page'] -= 1
        super().deleteLater()

    def run(self):
        # extract all downloaded topics from databases.
        # plus those topics in local queue.
        while self.running:
            try:
                __tps = self.extract_info_from_page(next(self.pages_generator))
                if __tps is None:
                    continue
                unfinished_tps = []
                for each in __tps:
                    tid = each.split('.')[0].replace('thread-', '')
                    if tid in self.Localtid:
                        continue
                    unfinished_tps.append(each)
                try:
                    self.locker.lockForWrite()
                    SIS_POOLS['tops queue'].extend(unfinished_tps)
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
    while True:
        try:
            connectDB = sqlite3.connect(DBPATH + 'SISDB.sqlite')
            rst = connectDB.cursor().execute('SELECT tid FROM PicPath').fetchall()
            Localpic = [x[0] for x in rst]
            rst = connectDB.cursor().execute('SELECT tid FROM SIStops').fetchall()
            Localtop = [x[0] for x in rst]
            connectDB.close()
            break
        except sqlite3.OperationalError:
            continue

    def __init__(self, cookies=None, parent=None):
        super(SISTopicLoader, self).__init__(cookies, parent)
        Working_threads['top'] += 1

    def deleteLater(self):
        Working_threads['top'] -= 1
        super().deleteLater()

    def run(self):
        while self.running:            
            try:
                job = SIS_POOLS['tops queue'].pop(0)
            except IndexError:
                return
            self.download_topics(job)

    def put_back(self, job):
        try:
            if job in self.bad_record.keys():
                if self.bad_record[job] < 5:
                    self.locker.lockForWrite()
                    SIS_POOLS['tops queue'].append(job)
                    self.bad_record[job] += 1
            else:
                self.bad_record[job] = 1
                self.locker.lockForWrite()
                SIS_POOLS['tops queue'].append(job)
        finally:
            self.locker.unlock()

    def download_topics(self, job):
        url = self.baseurl + job
        obj = self.make_soup(url)
        if obj is None:
            # print('{} Loading failed, put job back to queue.'.format(url))
            self.put_back(job)
            return
        t_id = job.split('.')[0].replace('thread-', '')
        # crawl all topics info
        t_type, t_name, t_censor, t_thumbup, t_date, t_category = 'Unkown', 'Unkown', 2, 0, 57600.0, 0
        try:
            page_tors = obj.find_all('a', {'href': re.compile(r'attachment')})
            if len(page_tors) == 0:
                self.put_back(job)
                return
            for each in page_tors:
                SIS_POOLS['tors queue'].append((t_id, each['href']))
        except AttributeError as err:
            print('{} extract torrents err, {} : Line {}'.format(url, err, sys.exc_info()[2].tb_frame.f_lineno))
            return
        if t_id not in self.Localtop:
            try:
                t_type = obj.find('h1').a.text[1:-1]
            except AttributeError as err:
                print('{} extract type err, {} : Line {}'.format(url, err, sys.exc_info()[2].tb_frame.f_lineno))
            try:
                t_name = obj.find('h1').a.next_sibling.strip()
            except AttributeError as err:
                print('{} extract name err, {} : Line {}'.format(url, err, sys.exc_info()[2].tb_frame.f_lineno))
            try:
                t_censor = self.isMosic(obj)
            except AttributeError as err:
                print('{} extract censor err, {} : Line {}'.format(url, err, sys.exc_info()[2].tb_frame.f_lineno))
            try:
                t_thumbup = obj.find('a', {'id': 'ajax_thanks'}).text
            except AttributeError as err:
                print('{} extract thumbup err, {} : Line {}'.format(url, err, sys.exc_info()[2].tb_frame.f_lineno))
            try:
                t_date = re.search(r'(\d+-\d+-\d+)', obj.find('div', {'class': 'postinfo'}).text).group(1)
                int_date = t_date.split('-')
                t_date = datetime.datetime(int(int_date[0]), int(int_date[1]), int(int_date[2])).timestamp()
            except AttributeError as err:
                print('{} extract date err, {} : Line {}'.format(url, err, sys.exc_info()[2].tb_frame.f_lineno))
            try:
                catey_text = obj.find('div', {'id': 'nav'}).text.lower()
                if 'asia' in catey_text:
                    t_category = 1
                elif 'western' in catey_text:
                    t_category = 2
                elif 'anime' in catey_text:
                    t_category = 3
                try:
                    self.locker.lockForWrite()
                    SIS_Queries['top'].append((t_id, t_type, t_name, t_censor, t_thumbup, t_date, t_category))
                finally:
                    self.locker.unlock()
            # push tors into queue
            except AttributeError as err:
                print('{} extract category err, {} : Line {}'.format(url, err, sys.exc_info()[2].tb_frame.f_lineno))
            

        # push pics into queue
        if t_id not in self.Localpic:
            try:
                for pic in obj.find('div', {'class': 't_msgfont'}).find_all('img', {'src': re.compile(r'jpg|png')}):
                    pic_url = pic['src']
                    if pic_url in SIS_POOLS['piced'].keys():
                        continue
                    try:
                        self.locker.lockForWrite()
                        SIS_POOLS['pics queue'].append((t_id, pic_url))
                        SIS_POOLS['piced'][pic_url] = 1
                    finally:
                        self.locker.unlock()
            except AttributeError as err:
                print('{} extract pictures err, {} : Line {}'.format(url, err, sys.exc_info()[2].tb_frame.f_lineno))
        self.emitInfo('({}) {} Downloaded.'.format(t_id, t_name))

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


class SISTorLoader(TheDownloader):
    def __init__(self, cookies=None, parent=None):
        super(SISTorLoader, self).__init__(cookies, parent)
        Working_threads['tor'] += 1

    def deleteLater(self):
        Working_threads['tor'] -= 1
        super().deleteLater()

    def run(self):
        while self.running:
            try:
                job = SIS_POOLS['tors queue'].pop(0)
            except IndexError:
                return
            self.download_tors(job)

    def put_back(self, job):
        try:
            if job[1] in self.bad_record.keys():
                if self.bad_record[job[1]] < 5:
                    self.locker.lockForWrite()
                    SIS_POOLS['tors queue'].append(job)
                    self.bad_record[job[1]] += 1
            else:
                self.bad_record[job[1]] = 1
                self.locker.lockForWrite()
                SIS_POOLS['tors queue'].append(job)
        finally:
            self.locker.unlock()

    def download_tors(self, job):
        url = self.baseurl + job[1]
        req = self.request_with_proxy(url)
        if req is None or req.ok is False:
            # print('{} downloading failed, back to queue.'.format(url))
            self.put_back(job)
            return
        try:
            magnet = self.magDecoder(req.content)
            SIS_Queries['tor'].append((job[0], magnet))
            self.emitInfo('{} magnet success.'.format(job[0]))
        except flatbencode.DecodingError:
            self.put_back(job)
            return

    def magDecoder(self, byte):
        hashcontent = flatbencode.encode(flatbencode.decode(byte)[b'info'])
        digest = hashlib.sha1(hashcontent).hexdigest()
        magneturl = 'magnet:?xt=urn:btih:{}'.format(digest)
        return magneturl


class SISPicLoader(SISThread):
    def __init__(self, parent=None):
        super(SISPicLoader, self).__init__(parent)
        Working_threads['pic'] += 1

    def deleteLater(self):
        Working_threads['pic'] -= 1
        super().deleteLater()

    def run(self):
        while self.running:
            try:
                job = SIS_POOLS['pics queue'].pop()
            except IndexError:
                return
            try:
                if requests.head(job[1], timeout=5).ok is False:
                    continue
                bpic = requests.get(job[1], timeout=150).content
                pictype = self.isImage(bpic)
                if 'none' in pictype:
                    print('{} is not an image.'.format(job[1]))
                    continue
                try:
                    self.locker.lockForWrite()
                    SIS_Queries['pic'].append((job[0], bpic, pictype))
                finally:
                    self.locker.unlock()
            except requests.exceptions.RequestException:
                pass

    def isImage(self, byte):
        if len(byte) < 10:
            return 'none'
        hexstr = u""
        for i in range(10):
            t = u"%x" % byte[i]
            if len(t) % 2:
                hexstr += u"0"
            hexstr += t
        img_header = hexstr.upper()
        if 'FFD8FF' in img_header:
            return 'jpg'
        if '89504E47' in img_header:
            return 'png'
        else:
            print('Image header: {} does not look like an image'.format(img_header))
            return 'none'


class SISSql(SISThread):
    """ operate the databases"""

    def __init__(self, parent=None):
        super(SISSql, self).__init__(parent)
        print('SISSql Created')
        self.md5 = hashlib.md5()

    def run(self):
        while True:
            try:
                connect = sqlite3.connect(DBPATH + 'SISDB.sqlite')
            except sqlite3.OperationalError:
                time.sleep(1)
                continue
            query = connect.cursor().execute
            try:
                if len(SIS_Queries['pic']):
                    try:
                        picinfo = SIS_Queries['pic'].pop(0)
                        add_info = query('select category, type, date from SIStops where tid=?', (picinfo[0],)).fetchone()
                        if add_info is None:
                            continue
                        self.md5.update(picinfo[1])
                        imgmd5 = self.md5.hexdigest()
                        path = 'img{}{}{}{}{}{}{}{}.{}'.format(os.sep, add_info[0], os.sep, add_info[1], os.sep, add_info[2], os.sep, imgmd5, picinfo[2])
                        try:
                            query('insert into PicMD5 values(?, ?)', (path, imgmd5))
                            query('insert into PicPath values(?, ?)', (picinfo[0], path))
                        except sqlite3.IntegrityError as err:
                            if 'UNIQUE' in str(err):
                                print('Duplicate pic[{}]: {}'.format(picinfo[0], imgmd5))
                                exists_path = query('select tid, path from PicMD5 where md5=?', (imgmd5,)).fetchone()
                                query('insert into PicPath values(?, ?)', (picinfo[0], exists_path[1]))
                                print('Using path [{}]: {} instead'.format(exists_path[0], exists_path[1]))
                                continue
                        self.save_pic(path, picinfo[1])                       
                        connect.commit()
                        Finished_jobs['pic'] += 1
                    except sqlite3.IntegrityError as err:
                        # print('Pics inserting err, code: ', err)
                        pass
                if len(SIS_Queries['tor']):
                    try:
                        torinfo = SIS_Queries['tor'].pop(0)
                        query('INSERT INTO SISmags VALUES(?, ?)', (torinfo[0], torinfo[1]))
                        Finished_jobs['tor'] += 1
                        connect.commit()
                    except sqlite3.IntegrityError as err:
                        pass
                if len(SIS_Queries['top']):
                    try:
                        maininfo = SIS_Queries['top'].pop(0)
                        query('INSERT INTO SIStops VALUES(?, ?, ?, ?, ?, ?, ?)',
                              (maininfo[0], maininfo[1], maininfo[2], maininfo[3],
                               maininfo[4], maininfo[5], maininfo[6]))
                        connect.commit()
                        Finished_jobs['top'] += 1
                    except sqlite3.IntegrityError as err:
                        # print('Tops inserting err, code', err)
                        pass
            except sqlite3.OperationalError:
                time.sleep(1)
            finally:
                connect.close()

    def save_pic(self, path, byte):
        path_list = path.split(os.sep)
        for index in range(1, len(path_list)):
            try:
                each_path = DBPATH + os.sep.join(path_list[:index])
                os.mkdir(each_path)
            except FileExistsError:
                continue
        with open(DBPATH + path, 'wb') as f:
            f.write(byte)


class ProxiesThread(TheDownloader):
    test_url = 'http://38.103.161.156'
    headers = 'Mozilla/5.0 (Windows; U; Windows NT 5.1; en-US; rv:1.9a2pre) Gecko/20061231 Minefield/3.0a2pre'

    def __init__(self, which, parent=None):
        super().__init__(None, parent)
        self.which = which
        print('ProxiesThread Created')

    def run(self):
        if self.which == 1:
            print('proxies 1 is running')
            url = 'http://haoip.cc/'
            next_page = ''
            while True:
                try:
                    req = requests.get(url + next_page, headers=self.get_headers())
                except requests.exceptions.RequestException:
                    time.sleep(5)
                    continue
                pobj = BeautifulSoup(req.content, 'lxml')
                try:
                    next_page = pobj.find('ul', {'class': 'pagination'}).li.a['href']
                except AttributeError:
                    continue
                for each in pobj.find('table', {'class': 'table table-hover'}).findAll('tr'):
                    sp = each.findAll('td')[:2]
                    proxy = sp[0].text + ':' + sp[1].text
                    try:
                        if requests.head(self.test_url, proxies={'http': proxy}, headers={'User-Agent': self.headers}, timeout=3).ok:
                            SIS_POOLS['proxies'].append(proxy)
                    except requests.exceptions.RequestException:
                        continue
        elif self.which == 2:
            print('proxies 2 is running')
            url = 'http://www.kuaidaili.com/free/outha/{}/'
            while True:
                for page in range(1, 1415):
                    try:
                        req = requests.get(url.format(page), headers={'User-Agent': self.headers})
                    except requests.exceptions.RequestException:
                        time.sleep(5)
                        continue
                    pobj = BeautifulSoup(req.content, 'lxml').findAll('tr')
                    for each in pobj[1:]:
                        sp = each.findAll('td')
                        proxy = sp[0].text + ':' + sp[1].text
                        try:
                            if requests.head(self.test_url, proxies={'http': proxy},
                                             headers={'User-Agent': self.headers}, timeout=3).ok:
                                SIS_POOLS['proxies'].append(proxy)
                        except requests.exceptions.RequestException:
                            continue
        """
        elif self.which == 2:
            print('proxies 2 is running')
            url = 'http://www.xicidaili.com/nn/{}'
            while True:
                for page in range(1, 1001):
                    try:
                        req = requests.get(url.format(page), headers=self.get_headers())
                    except requests.exceptions.RequestException:
                        time.sleep(5)
                        continue
                    pobj = BeautifulSoup(req.content, 'lxml').findAll('tr')
                    for each in pobj[1:]:
                        sp = each.findAll('td')
                        proxy = sp[1].text + ':' + sp[2].text
                        try:
                            if requests.head(self.test_url, proxies={'http': proxy}, headers=self.get_headers(), timeout=3).ok:
                                SIS_POOLS['proxies'].append(proxy)
                        except requests.exceptions.RequestException:
                            continue
        """
        
