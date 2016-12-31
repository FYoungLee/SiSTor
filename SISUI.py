import SIS, SISDisplay, Proxies
import os, requests, sqlite3, json, random
from datetime import datetime
from PyQt5.QtWidgets import QWidget, QPushButton, QHBoxLayout, QVBoxLayout, QLabel, QComboBox, QLineEdit, \
     QMessageBox, QTextBrowser, QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView, QListWidget, QListView, \
    QListWidgetItem, QDialog, QSlider
from PyQt5.QtCore import Qt, QSize, pyqtSignal, QUrl
from PyQt5.Qt import QPixmap, QDesktopServices, QIcon, QScrollArea


class SISMainWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.check_databases()
        self.init_ui()

    def init_ui(self):
        self.setToolTip('SIS Torrents Downloader '
                        '\n第一会所论坛种子下载器')

        self.downloaderWidget = DownloaderWidget()
        self.browserWidget = BrowserWidget()

        # tab widget
        tabWidget = QTabWidget()
        tabWidget.addTab(self.downloaderWidget, 'Downloader 下载器')
        tabWidget.addTab(self.browserWidget, 'Browser 浏览器')
        tabWidget.tabBarClicked.connect(self.whenTabClicked)

        allLayout = QVBoxLayout()
        allLayout.addWidget(tabWidget)

        self.setLayout(allLayout)

        self.setWindowTitle('SIS Torrents Downloader v1.0 by Fyang (肥羊)')
        self.setMinimumWidth(800)
        self.setMinimumHeight(600)

    def check_databases(self):
        if 'SISDB.sqlite' not in os.listdir('.'):
            connect = sqlite3.connect('SIS.sqlite')
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
                """
                create table PicByte(
                tid text not null,
                picb blob primary key not null)
                """)
            connect.cursor().execute(
                """
                create table PicLink(
                tid text not null primary key,
                )
                """
            )
            # connect.cursor().execute(
            #     """
            #     create table Picb(
            #     tid text not null,
            #     byte bolb not null
            #     )
            #     """
            # )
            connect.commit()
            connect.close()

    def whenTabClicked(self, n_tab):
        if n_tab == 1:
            connect = sqlite3.connect('SISDB.sqlite')
            self.browserWidget.setTypeCombox(
                [x[0] for x in connect.cursor().execute('select type from SIStops group by type').fetchall()])
            self.browserWidget.b_count_label\
                .setText(' {} in stock'.format(connect.cursor().execute('select count(tid) from SIStops').fetchone()[0]))
            connect.close()


class DownloaderWidget(QWidget):
    stop_thread_signal = pyqtSignal(bool)

    def __init__(self, parent=None):
        super(DownloaderWidget, self).__init__(parent)
        # this list store all topics that download from topic_downloader thread.
        self.task_queues = {'topics': [], 'tors': [], 'pics': []}
        try:
            with open('TaskQueue.json') as f:
                content = json.loads(f.read())
                self.task_queues['topics'].extend(content['topics'])
                self.task_queues['tors'].extend(content['tors'])
                self.task_queues['pics'].extend(content['pics'])
        except FileNotFoundError:
            pass
        except json.decoder.JSONDecodeError as err:
            print('Queue loading error, code:', err)
        self.proxies_pool = [None]
        self.sqlqueries_pool = {'top': [], 'tor': [], 'pic': []}
        self.cookies = None
        self.initUI()
        # set proxies updater threads.
        for which in range(1, 3):
            proxiesoperator = Proxies.ProxiesThread(self.proxies_pool, which, self)
            proxiesoperator.start()
        # set sql operator
        self.sqloperator = SIS.SISSql(self.sqlqueries_pool, self.task_queues, self)
        self.sqloperator.start()
        self.pages_generator = None
        self.topics_working_threads = [0]
        self.pictures_working_threads = [0]
        self.startTimer(1000)

    def __del__(self):
        with open('TaskQueue.json', 'w') as f:
            f.write(json.dumps(self.task_queues))

    def initUI(self):
        #################################################
        # downloader stuff below
        self.info_box = QHBoxLayout()
        self.info_label = QLabel()
        self.info_label.setText('This application is supposed to private use, DO NOT share to anyone!'
                                '\n考虑到法律问题，本软件仅作为个人学习研究使用，请不要向他人传播。\n')
        self.info_box.addWidget(self.info_label)

        self.url_box = QHBoxLayout()
        self.url_label_title = QLabel('SiS Address (站点地址) ')
        self.url_line = QLineEdit()
        self.url_line.setMinimumWidth(260)
        self.url_line.setText(get_forum_address())
        self.url_label = QLabel('Unkown')
        self.url_label.setFixedWidth(50)
        # self.check_url()
        self.url_test_btn = QPushButton('Test(测试)')
        self.url_test_btn.clicked.connect(self.check_url)
        self.url_box.addWidget(self.url_label_title)
        self.url_box.addWidget(self.url_line)
        self.url_box.addWidget(self.url_label)
        self.url_box.addWidget(self.url_test_btn)
        self.url_box.addStretch(100)

        self.login_box = QHBoxLayout()
        login_id_label = QLabel('UserName')
        self.login_id_line = QLineEdit()
        login_pw_label = QLabel('Password')
        self.login_pw_line = QLineEdit()
        self.login_box.addWidget(login_id_label)
        self.login_box.addWidget(self.login_id_line)
        self.login_box.addWidget(login_pw_label)
        self.login_box.addWidget(self.login_pw_line)
        login_btn = QPushButton('Login')
        login_btn.clicked.connect(self.get_sis_cookies)
        self.login_box.addWidget(login_btn)
        self.login_status_label = QLabel('')
        self.login_status_label.setFixedWidth(100)
        self.login_box.addWidget(self.login_status_label)
        self.login_box.addStretch(1)

        self.forum_select_box = QHBoxLayout()
        self.forum_info = QLabel('Choose sub-forum (选择子版块)')
        self.forum_menu = QComboBox()
        self.forum_menu.addItem('Asia Uncensored Authorship Seed 亚洲无码原创区')
        self.forum_menu.addItem('Asia Censored Authorship Seed 亚洲有码原创区')
        self.forum_menu.addItem('Western Uncensored Authorship Seed 欧美无码原创区')
        self.forum_menu.addItem('Anime Authorship Seed 成人游戏动漫原创区')
        self.forum_menu.addItem('Asia Uncensored Section 亚洲无码转帖区 ')
        self.forum_menu.addItem('Asia Censored Section 亚洲有码转帖区')
        self.forum_menu.addItem('Western Uncensored 欧美无码转帖区')
        self.forum_menu.addItem('Anime Fans Castle 成人游戏动漫转帖区')
        self.forum_menu.setMaximumWidth(350)
        self.forum_select_box.addWidget(self.forum_info)
        self.forum_select_box.addWidget(self.forum_menu)
        self.forum_select_box.addStretch(1)

        self.pages_box = QHBoxLayout()
        self.pages_label = QLabel("How many pages to download (下载页数，每页有30-40个种子)")
        self.pages_line = QLineEdit()
        self.pages_line.setText('1')
        self.pages_line.setFixedWidth(30)
        self.pages_box.addWidget(self.pages_label)
        self.pages_box.addWidget(self.pages_line)
        self.pages_box.addStretch(1)

        # self.thread_box = QHBoxLayout()
        # self.thread_label = QLabel('How many downloading threads (开启线程数，线程太多容易崩溃)')
        # self.thread_menu = QComboBox()
        # for each in range(1, 11):
        #     self.thread_menu.addItem(str(each))
        # self.thread_box.addWidget(self.thread_label)
        # self.thread_box.addWidget(self.thread_menu)
        # self.thread_box.addStretch(1)

        btnlayout = QHBoxLayout()
        self.start_btn = QPushButton('Start', self)
        self.start_btn.clicked.connect(self.start_btn_clicked)
        self.start_btn.setFixedWidth(180)
        self.stop_btn = QPushButton('Stop', self)
        self.stop_btn.setFixedWidth(180)
        self.stop_btn.clicked.connect(self.stop_btn_clicked)
        btnlayout.addWidget(self.start_btn)
        btnlayout.addWidget(self.stop_btn)
        btnlayout.addStretch(100)

        self.main_box = QVBoxLayout()
        self.main_box.addLayout(self.info_box)
        self.main_box.addLayout(self.url_box)
        self.main_box.addLayout(self.login_box)
        self.main_box.addLayout(self.forum_select_box)
        self.main_box.addLayout(self.pages_box)
        # self.main_box.addLayout(self.thread_box)
        self.main_box.addLayout(btnlayout)

        threads_control_layout = QVBoxLayout()

        pages_threads_layout = QHBoxLayout()
        pages_threads_layout.addWidget(QLabel('PgThreads'))
        self.pages_threads_slider = QSlider(Qt.Horizontal)
        self.pages_threads_slider.setRange(1, 5)
        self.pages_threads_slider.setValue(2)
        pages_threads_layout.addWidget(self.pages_threads_slider)
        page_t_label = QLabel(str(self.pages_threads_slider.value()))
        page_t_label.setFixedWidth(20)
        pages_threads_layout.addWidget(page_t_label)
        self.pages_threads_slider.valueChanged.connect(lambda x: page_t_label.setText(str(x)))
        threads_control_layout.addLayout(pages_threads_layout)

        topics_threads_layout = QHBoxLayout()
        topics_threads_layout.addWidget(QLabel('TpThreads'))
        self.tops_threads_silder = QSlider(Qt.Horizontal)
        self.tops_threads_silder.setRange(1, 30)
        self.tops_threads_silder.setValue(15)
        topics_threads_layout.addWidget(self.tops_threads_silder)
        topics_t_label = QLabel(str(self.tops_threads_silder.value()))
        topics_t_label.setFixedWidth(20)
        topics_threads_layout.addWidget(topics_t_label)
        self.tops_threads_silder.valueChanged.connect(lambda x: topics_t_label.setText(str(x)))
        threads_control_layout.addLayout(topics_threads_layout)

        tors_threads_layout = QHBoxLayout()
        tors_threads_layout.addWidget(QLabel('TrThreads'))
        self.tors_threads_silder = QSlider(Qt.Horizontal)
        self.tors_threads_silder.setRange(1, 30)
        self.tors_threads_silder.setValue(15)
        tors_threads_layout.addWidget(self.tors_threads_silder)
        tors_t_label = QLabel(str(self.tors_threads_silder.value()))
        tors_t_label.setFixedWidth(20)
        tors_threads_layout.addWidget(tors_t_label)
        self.tors_threads_silder.valueChanged.connect(lambda x: tors_t_label.setText(str(x)))
        threads_control_layout.addLayout(tors_threads_layout)

        pics_thread_layout = QHBoxLayout()
        pics_thread_layout.addWidget(QLabel('PcThreads'))
        self.pics_threads_silder = QSlider(Qt.Horizontal)
        self.pics_threads_silder.setRange(1, 500)
        self.pics_threads_silder.setValue(250)
        pics_thread_layout.addWidget(self.pics_threads_silder)
        pics_t_label = QLabel(str(self.pics_threads_silder.value()))
        pics_t_label.setFixedWidth(20)
        pics_thread_layout.addWidget(pics_t_label)
        self.pics_threads_silder.valueChanged.connect(lambda x: pics_t_label.setText(str(x)))
        threads_control_layout.addLayout(pics_thread_layout)

        self.output_box = QVBoxLayout()
        self.output_window = QTextBrowser()
        self.output_window.setMinimumWidth(640)
        self.progress_label = QLabel()
        self.progress_box = QHBoxLayout()
        self.progress_box.addWidget(self.progress_label)
        self.output_box.addWidget(self.output_window)
        self.output_box.addLayout(self.progress_box)

        upper_layout = QHBoxLayout()
        upper_layout.addLayout(self.main_box)
        upper_layout.addLayout(threads_control_layout)

        downloaderLayout = QVBoxLayout()
        downloaderLayout.addLayout(upper_layout)
        downloaderLayout.addLayout(self.output_box)

        self.setLayout(downloaderLayout)
        # downloader stuff above
        #################################################

    def check_url(self):
        if len(self.proxies_pool):
            proxy = random.choice(self.proxies_pool)
        else:
            return
        try:
            req = requests.head(self.url_line.text(), proxies=proxy, timeout=10)
        except requests.exceptions.RequestException:
            self.url_label.setText('Failed')
            return
        if req.ok:
            self.url_label.setText('OK')
            with open('sis_addr.dat', 'w') as f:
                f.write(self.url_line.text())
        else:
            self.url_label.setText('Failed')
            failed_msg = 'The address is not available now, try to find other one.' \
                         '\nAddress must be under the correct form: http://example/forum/' \
                         '\n前论坛地址已经不可用了，请输入新的地址。\n新地址输入，请务必保持正确的格式，包括符号！'
            QMessageBox().warning(self, 'Address Failed', failed_msg, QMessageBox.Ok)
            
    def get_sis_cookies(self):
        loginname = self.login_id_line.text()
        password = self.login_pw_line.text()
        if loginname is '' or password is '':
            return None
        login_data = {'action': 'login',
                      'loginsubmit': 'true',
                      '62838ebfea47071969cead9d87a2f1f7': loginname,
                      'c95b1308bda0a3589f68f75d23b15938': password}

        cookies = requests.post(self.url_line.text() + 'logging.php', data=login_data).cookies
        if len(cookies.values()[0]) > 10:
            self.cookies = cookies
            self.login_status_label.setText('Success')
        else:
            self.login_status_label.setText('Failed')
            return

    def getUndownloadedPic(self):
        connect = sqlite3.connect('SISDB.sqlite')
        ret = connect.cursor().execute('SELECT * FROM SISpic WHERE picb IS NULL').fetchall()
        connect.close()
        return ret

    def start_btn_clicked(self):
        self.check_url()
        if 'Start' in self.start_btn.text():
            if 'OK' not in self.url_label.text():
                QMessageBox().critical(self, 'URL error', 'In case the url is not correct or did not verify, try again.\n'
                                                          '站点还未连通或者不可用，不能下载，请重试。')
                return
            if self.pages_line.text().isdigit() is False:
                QMessageBox().critical(self, 'Pages error', 'How many pages you want to download?\n请输入正确的下载页数')
                return
            self.start_btn.setText('Downloading...')

    def stop_btn_clicked(self):
        self.start_btn.setText('Start')
        self.stop_thread_signal.emit(False)

    def timerEvent(self, QTimerEvent):
        self.progress_label.setText('Topics Remain: {}   Tors Remain: {}   Pics Remain: {}'
                                    '   Forum Threads: {}   Picture Threads: {}   Proxies: {}'
                                    .format(len(self.task_queues['topics']),
                                            len(self.task_queues['tors']),
                                            len(self.task_queues['pics']),
                                            self.topics_working_threads[0],
                                            self.pictures_working_threads[0],
                                            len(self.proxies_pool)))
        if 'Download' not in self.start_btn.text():
            return
        if len(self.task_queues['pics']) > self.pictures_working_threads[0] \
                and self.pictures_working_threads[0] < self.pics_threads_silder.value():
            th = SIS.SISPicLoader(self.task_queues, self.sqlqueries_pool, self.pictures_working_threads, self)
            # th.picpak_broadcast.connect(self.sqloperator.picUpdate)
            # self.stop_thread_signal.connect(th.setRunning)
            th.start()
            self.pictures_working_threads[0] += 1

        if len(self.task_queues['tors']) > 0 and self.topics_working_threads[0] < self.tors_threads_silder.value():
            tth = SIS.SISTorLoader(self.task_queues, self.sqlqueries_pool, self.topics_working_threads,
                                    self.proxies_pool, self.cookies, self)
            tth.send_text.connect(self.infoRec)
            self.stop_thread_signal.connect(tth.setRunning)
            tth.start()
            self.topics_working_threads[0] += 1

        if len(self.task_queues['topics']) > self.topics_working_threads[0] \
                and self.topics_working_threads[0] < self.tops_threads_silder.value():
            th = SIS.SISTopicLoader(self.task_queues, self.sqlqueries_pool, self.topics_working_threads,
                                    self.proxies_pool, self.cookies, self)
            th.send_text.connect(self.infoRec)
            self.stop_thread_signal.connect(th.setRunning)
            th.start()
            self.topics_working_threads[0] += 1

        if len(self.task_queues['topics']) == 0 and self.topics_working_threads[0] < self.pages_threads_slider.value():
            if self.pages_generator is None:
                self.pages_generator = (self.url_line.text() + self.sub_forum_addr() + '{}.html'.format(each)
                             for each in range(1, int(self.pages_line.text()) + 1))
            td = SIS.SISPageLoader(self.pages_generator, self.task_queues, self.topics_working_threads,
                                   self.proxies_pool, self.cookies, self)
            td.send_text.connect(self.infoRec)
            self.stop_thread_signal.connect(td.setRunning)
            td.start()
            self.topics_working_threads[0] += 1

    def infoRec(self, info):
        self.output_window.append(info)

    def sub_forum_addr(self):
        index = self.forum_menu.currentIndex()
        return {0: 'forum-143-', 1: 'forum-230-', 2: 'forum-229-', 3: 'forum-231-',
                4: 'forum-25-', 5: 'forum-58-', 6: 'forum-77-', 7: 'forum-27-'}[index]


class BrowserWidget(QWidget):
    def __init__(self, parent=None):
        super(BrowserWidget, self).__init__(parent)
        self.initUI()
        self.currentIndex = 0

    def initUI(self):
        # browser stuff below
        b_menu_layout1 = QHBoxLayout()
        self.b_search_line = QLineEdit()
        self.b_search_line.setMinimumWidth(200)
        self.b_type_combox = QComboBox()
        self.b_category_combox = QComboBox()
        self.b_category_combox.addItems(('所有', '亚洲', '欧美', '动漫'))
        self.b_censor_combox = QComboBox()
        self.b_censor_combox.addItems(('所有', '无码', '有码', '未知'))
        self.b_count_label = QLabel()
        self.b_count_label.setFixedWidth(100)
        b_menu_layout1.addWidget(QLabel('关键字'))
        b_menu_layout1.addWidget(self.b_search_line)
        b_menu_layout1.addWidget(self.b_type_combox)
        b_menu_layout1.addWidget(self.b_category_combox)
        b_menu_layout1.addWidget(self.b_censor_combox)
        b_menu_layout1.addWidget(self.b_count_label)

        b_menu_layout2 = QHBoxLayout()
        self.prev_page_btn = QPushButton(' << ')
        self.prev_page_btn.setEnabled(False)
        self.prev_page_btn.clicked.connect(self.prevClicked)
        self.next_page_btn = QPushButton(' >> ')
        self.next_page_btn.setEnabled(False)
        self.next_page_btn.clicked.connect(self.nextClicked)
        self.result_label = QLabel()
        self.result_label.setFixedWidth(50)
        self.b_topic_each_page_slider = QSlider(Qt.Horizontal)
        self.b_topic_each_page_slider.setRange(50, 5000)
        silderLabel = QLabel('50条/每页')
        silderLabel.setFixedWidth(100)
        silderLabel.setAlignment(Qt.AlignCenter)
        self.b_topic_each_page_slider.valueChanged.connect(lambda x: silderLabel.setText('{} 条/每页'.format(x)))
        self.b_start_load = QPushButton('Load 加载')
        self.b_start_load.clicked.connect(self.startQuery)
        b_menu_layout2.addWidget(self.prev_page_btn)
        b_menu_layout2.addWidget(self.next_page_btn)
        b_menu_layout2.addWidget(self.result_label)
        b_menu_layout2.addStretch(1)
        b_menu_layout2.addWidget(self.b_start_load)
        b_menu_layout2.addWidget(self.b_topic_each_page_slider)
        b_menu_layout2.addWidget(silderLabel)

        self.b_table_view = myTable()
        self.b_table_view.itemClicked.connect(self.whenItemClicked)
        self.b_table_view.setEditTriggers(QTableWidget.NoEditTriggers)
        self.b_table_view.setSortingEnabled(True)
        self.b_table_view.setSelectionBehavior(QTableWidget.SelectRows)
        self.b_table_view.setSelectionMode(QTableWidget.SingleSelection)
        self.b_table_view.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        b_layout = QVBoxLayout()
        b_layout.addLayout(b_menu_layout1)
        b_layout.addLayout(b_menu_layout2)
        b_layout.addWidget(self.b_table_view)

        self.magLine = QLineEdit('下载链接')
        b_layout.addWidget(self.magLine)

        self.setLayout(b_layout)
        # browser stuff above
        #################################################

    def setTypeCombox(self, typs):
        self.b_type_combox.addItem('所有')
        self.b_type_combox.addItems(typs)

    def startQuery(self):
        if self.b_topic_each_page_slider.value() > 1000:
            reply = QMessageBox().warning(self, '提示', '每页显示大于1000，可能会造成卡顿，要继续吗？',
                                          QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.No:
                return
        query = 'SELECT * FROM SIStops'
        if self.b_search_line.text() is not '':
            query += ' WHERE name GLOB "*{}*"'.format(self.b_search_line.text())
        if self.b_type_combox.currentIndex() != 0:
            if 'WHERE' in query:
                query += ' AND type="{}"'.format(self.b_type_combox.currentText())
            else:
                query += ' WHERE type="{}"'.format(self.b_type_combox.currentText())
        if self.b_category_combox.currentIndex() != 0:
            if 'WHERE' in query:
                query += ' AND category="{}"'.format(self.b_category_combox.currentIndex())
            else:
                query += ' WHERE category="{}"'.format(self.b_category_combox.currentIndex())
        if self.b_censor_combox.currentIndex() != 0:
            if 'WHERE' in query:
                query += ' AND censor={}'.format(self.b_type_combox.currentIndex() - 1)
            else:
                query += ' WHERE censor={}'.format(self.b_type_combox.currentIndex() - 1)
        # connect = sqlite3.connect('SISDB.sqlite')
        # result = connect.cursor().execute(query).fetchall()
        # connect.close()
        # self.placeItem(result)
        # self.b_table_view.clear()
        # self.b_table_view.setRowCount(0)
        qw = SISDisplay.SISQuieis(query, self)
        qw.result_feadback.connect(self.searchResult)
        qw.start()

    def searchResult(self, result):
        if len(result):
            spliter = self.b_topic_each_page_slider.value()
            self.result_container = [result[i:i+spliter] for i in range(0, len(result), spliter)]
            self.placeItem(self.result_container[0])
        if len(result) > 1:
            self.next_page_btn.setEnabled(True)
            self.currentIndex = 0
        self.prev_page_btn.setEnabled(False)
        self.result_label.setText('{}/{}'.format(self.currentIndex+1, len(self.result_container)))

    def placeItem(self, items):
        self.b_table_view.clear()
        self.b_table_view.setRowCount(0)
        base_url = get_forum_address()
        self.b_table_view.setColumnCount(10)
        self.b_table_view.setHorizontalHeaderLabels(('类型', '片名', '有无码', '赞', '日期',
                                                     '地区', '磁力链', '截图', '原址', ''))
        self.b_table_view.setRowCount(len(items))

        for row, each in enumerate(items):
            for _n, item in enumerate(each[1:]):
                tableitem = QTableWidgetItem()
                tableitem.setTextAlignment(Qt.AlignCenter)
                if _n == 1:
                    tableitem.setData(Qt.DisplayRole, item)
                    tableitem.setToolTip('{}'.format(item))
                elif _n == 2:
                    if item == 0:
                        tableitem.setData(Qt.DisplayRole, '无')
                    elif item == 1:
                        tableitem.setData(Qt.DisplayRole, '有')
                    else:
                        tableitem.setData(Qt.DisplayRole, '未知')
                elif _n == 4:
                    tableitem.setData(Qt.DisplayRole, datetime.fromtimestamp(float(item)).strftime('%Y-%m-%d'))
                elif _n == 5:
                    cate = {1:'亚洲', 2:'欧美', 3:'动漫'}
                    tableitem.setData(Qt.DisplayRole, cate[item])
                else:
                    tableitem.setData(Qt.DisplayRole, item)
                self.b_table_view.setItem(row, _n, tableitem)
            connect = sqlite3.connect('SISDB.sqlite')
            tors = [x[0] for x in connect.cursor().execute('SELECT magnet from SISmags WHERE tid=?', (each[0],)).fetchall()]
            pics = connect.cursor().execute('SELECT tid from PicLink WHERE tid=?', (each[0],)).fetchone()
            connect.close()

            if tors:
                tableitem = QTableWidgetItem('打开')
                tableitem.setTextAlignment(Qt.AlignCenter)
                tableitem.setData(1000, tors)
                self.b_table_view.setItem(row, 6, tableitem)

            if pics and pics[0]:
                tableitem = QTableWidgetItem('显示')
                tableitem.setTextAlignment(Qt.AlignCenter)
                tableitem.setData(1000, pics)
                self.b_table_view.setItem(row, 7, tableitem)

            tableitem = QTableWidgetItem('...')
            tableitem.setTextAlignment(Qt.AlignCenter)
            tableitem.setToolTip(base_url + 'thread-' + each[0] + '.html')
            self.b_table_view.setItem(row, 8, tableitem)

            tableitem = QTableWidgetItem('删')
            tableitem.setToolTip(each[0])
            tableitem.setData(1000, each[0])
            tableitem.setTextAlignment(Qt.AlignCenter)
            self.b_table_view.setItem(row, 9, tableitem)

        for _n in range(10):
            if _n == 1:
                continue
            self.b_table_view.horizontalHeader().setSectionResizeMode(_n, QHeaderView.ResizeToContents)

    def whenItemClicked(self, item):
        if item.column() == 6:
            magtext = ''
            for each in item.data(1000):
                magtext += each + '\t'
            self.magLine.setText(magtext)
        elif item.column() == 7 and item.data(1000) is not None:
            tid = item.data(1000)[0]
            connect = sqlite3.connect('SISDB.sqlite')
            picbs = connect.cursor().execute('SELECT tid, picb from PicByte WHERE tid=?', (tid,)).fetchall()
            connect.close()
            if len(picbs) == 0:
                self.b_table_view.clearPicFromTable(item)
                return
            sw = SisPicWin(picbs, self)
            sw.show()
        elif item.column() == 8:
            QDesktopServices().openUrl(QUrl(item.toolTip()))
        elif item.column() == 9:
            reply = QMessageBox().question(self, '删除确认', '移除\n{}'.format(item.toolTip()), QMessageBox.Ok|QMessageBox.Cancel)
            if reply == QMessageBox.Ok:
                tid = item.data(1000)
                conn = sqlite3.connect('SIS.sqlite')
                conn.cursor().execute('DELETE from SIS WHERE tid=?', (tid,))
                conn.cursor().execute('DELETE from SISmags WHERE tid=?', (tid,))
                conn.cursor().execute('DELETE from PicLink WHERE tid=?', (tid,))
                conn.cursor().execute('DELETE from PicByte WHERE tid=?', (tid,))
                conn.commit()
                conn.close()
                self.b_table_view.removeRow(item.row())

    def prevClicked(self):
        self.currentIndex -= 1
        self.placeItem(self.result_container[self.currentIndex])
        if self.currentIndex == 0:
            self.prev_page_btn.setEnabled(False)
        if self.next_page_btn.isEnabled() is False:
            self.next_page_btn.setEnabled(True)
        self.result_label.setText('{}/{}'.format(self.currentIndex + 1, len(self.result_container)))

    def nextClicked(self):
        self.currentIndex += 1
        self.placeItem(self.result_container[self.currentIndex])
        if len(self.result_container) == self.currentIndex + 1:
            self.next_page_btn.setEnabled(False)
        if self.prev_page_btn.isEnabled() is False:
            self.prev_page_btn.setEnabled(True)
        self.result_label.setText('{}/{}'.format(self.currentIndex + 1, len(self.result_container)))


class myTable(QTableWidget):
    def mousePressEvent(self, *args, **kwargs):
        if args[0].button() == Qt.RightButton:
            try:
                clickedItem = self.itemAt(args[0].x(), args[0].y())
                if clickedItem.column() == 7:
                    clickedRow = clickedItem.row()
                    replay = QMessageBox().question(self, '删除图片',
                                                    '【{}】的图片将会被移除'.format(self.itemAt(clickedRow, 2).text()),
                                                    QMessageBox.Ok|QMessageBox.Cancel)
                    if replay == QMessageBox.Ok:
                        self.clearPicFromTable(clickedItem)

            except AttributeError:
                super().mousePressEvent(*args, **kwargs)
            return
        super().mousePressEvent(*args, **kwargs)

    def clearPicFromTable(self, item):
        tid = item.toolTip()
        self.deletePicturesFromDB(tid)
        item.setData(1000, None)
        item.setText('')

    def deletePicturesFromDB(self, tid):
        con = sqlite3.connect('SISDB.sqlite')
        try:
            con.cursor().execute('DELETE FROM PicLink WHERE tid=?', (tid,))
            con.cursor().execute('DELETE FROM PicByte WHERE tid=?', (tid,))
            con.commit()
        except sqlite3.IntegrityError as err:
            print(err)
        finally:
            con.close()


class SisPicWin(QDialog):
    def __init__(self, picbs, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout()
        self.picbs = picbs
        # self.selected = 0
        self.m_pListWidget = picList()
        self.m_pListWidget.setIconSize(QSize(100, 100))
        self.m_pListWidget.setResizeMode(QListView.Adjust)
        self.m_pListWidget.setViewMode(QListView.IconMode)
        self.m_pListWidget.setMovement(QListView.Static)
        self.m_pListWidget.setSpacing(5)
        self.m_pListWidget.itemClicked.connect(self.item_clicked)
        self.m_pListWidget.delete_signal.connect(self.deletePic)
        self.m_pListWidget.setFixedHeight(110)
        layout.addWidget(self.m_pListWidget)
        self.imageLabel = QLabel()
        scroll = QScrollArea()
        scroll.setWidget(self.imageLabel)
        layout.addWidget(scroll)
        self.placeItems()
        self.setLayout(layout)
        # self.setWindowFlags(Qt.WindowMinimizeButtonHint)
        self.setWindowFlags(Qt.Window)
        self.resize(800, 600)

    def placeItems(self):
        for index, each in enumerate(self.picbs):
            pix = QPixmap()
            pix.loadFromData(each[1])
            icon = QIcon()
            icon.addPixmap(pix)
            listItem = QListWidgetItem()
            listItem.setIcon(icon)
            listItem.setSizeHint(QSize(90, 90))
            listItem.setData(1000, index)
            listItem.setData(1001, pix)
            self.m_pListWidget.insertItem(index, listItem)
            if index == 0:
                self.imageLabel.setPixmap(pix)
                self.imageLabel.resize(pix.size().width(), pix.size().height())

    def item_clicked(self, item):
        if item:
            pix = item.data(1001)
            self.imageLabel.setPixmap(pix)

    def deletePic(self, item):
        index = item.data(1000)
        reply = QMessageBox().question(self, '删除图片', '{} 号图片将会被移除'.format(index+1),
                                       QMessageBox.Ok | QMessageBox.Cancel)
        if reply == QMessageBox.Cancel:
            return
        con = sqlite3.connect('SISDB.sqlite')
        try:
            delItem = self.picbs.pop(index)
            con.cursor().execute('DELETE FROM PicByte WHERE tid=? AND picb=?', (delItem[0], delItem[1]))
            if len(self.picbs) == 0:
                con.cursor().execute('DELETE FROM PicLink WHERE tid=?', (delItem[0],))
            con.commit()
        except IndexError:
            print(item.data(1000), ' delete err')
        finally:
            con.close()
            self.m_pListWidget.clear()
            self.placeItems()


class picList(QListWidget):
    delete_signal = pyqtSignal(QListWidgetItem)

    def mousePressEvent(self, event):
        item = self.itemAt(event.x(), event.y())
        if event.button() == Qt.RightButton and item:
            self.delete_signal.emit(item)
            return
        super().mousePressEvent(event)


def get_forum_address():
    with open('sis_addr.dat', 'r') as f:
        return f.readline()
