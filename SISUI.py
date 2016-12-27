import SIS
import os, requests, sqlite3
from PyQt5.QtWidgets import QWidget, QPushButton, QHBoxLayout, QVBoxLayout, QLabel, QComboBox, QLineEdit, \
     QMessageBox, QTextBrowser, QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView, QDialog
from PyQt5.QtCore import Qt
from PyQt5.Qt import QPixmap

Page_Threads = 2
Topic_Threads = 20
Picture_Threads = 100


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
            connect = sqlite3.connect('SISDB.sqlite')
            connect.cursor().execute(
                """
                create table SIS(
                tid text primary key not null,
                type text not null,
                name text not null,
                mosaic integer,
                thumbup integer,
                date text,
                size integer,
                mtype text,
                brief text)
                """)
            connect.cursor().execute(
                """
                create table SIStor(
                tid text not null,
                magnet text not null primary key)""")
            connect.cursor().execute(
                """
                create table SISpic(
                tid text not null,
                picaddr text,
                picb blob)
                """)
            connect.commit()
            connect.close()

    def whenTabClicked(self, n_tab):
        if n_tab == 1:
            connect = sqlite3.connect('SISDB.sqlite')
            self.browserWidget.setCategory(
                [x[0] for x in connect.cursor().execute('select type from sis group by type').fetchall()])
            connect.close()


class DownloaderWidget(QWidget):
    def __init__(self, parent=None):
        super(DownloaderWidget, self).__init__(parent)
        # this list store all topics that download from topic_downloader thread.
        self.topics_pool = []
        self.pics_pool_for_downloading = []
        self.pics_pool_for_downloading.extend(self.getUndownloadedPic())
        self.cookies = None
        self.initUI()
        self.sqlqueries_pool = {'main': [], 'tor': [], 'pic': []}
        self.sqloperator = SIS.SISSql(self.sqlqueries_pool, self.pics_pool_for_downloading, self)
        self.sqloperator.start()
        self.pics_generator = None
        self.topics_generator = None
        self.topics_working_threads = 0
        self.pictures_working_threads = 0
        self.pictures_finished = 0
        self.topics_finished = 0

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
        self.url_line.setText(self.get_forum_address())
        self.url_label = QLabel()
        self.url_label.setFixedWidth(30)
        self.check_url()
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

        self.start_btn = QPushButton('Start', self)
        self.start_btn.clicked.connect(self.start_btn_clicked)
        self.start_btn.setFixedWidth(180)

        self.main_box = QVBoxLayout()
        self.main_box.addLayout(self.info_box)
        self.main_box.addLayout(self.url_box)
        self.main_box.addLayout(self.login_box)
        self.main_box.addLayout(self.forum_select_box)
        self.main_box.addLayout(self.pages_box)
        # self.main_box.addLayout(self.thread_box)
        self.main_box.addWidget(self.start_btn)

        self.output_box = QVBoxLayout()
        self.output_window = QTextBrowser()
        self.output_window.setMinimumWidth(640)
        # self.progress_bar = QProgressBar()
        # self.progress_bar.setRange(0, 100)
        self.progress_label = QLabel()
        self.progress_box = QHBoxLayout()
        # self.progress_box.addWidget(self.progress_bar)
        self.progress_box.addWidget(self.progress_label)
        self.output_box.addWidget(self.output_window)
        self.output_box.addLayout(self.progress_box)

        downloaderLayout = QVBoxLayout()
        downloaderLayout.addLayout(self.main_box)
        downloaderLayout.addLayout(self.output_box)

        self.setLayout(downloaderLayout)
        # downloader stuff above
        #################################################

    def get_forum_address(self):
        with open('sis_addr.dat', 'r') as f:
            return f.readline()

    def check_url(self):
        if requests.head(self.url_line.text()).ok:
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
        if 'Failed' in self.url_label.text():
            QMessageBox().critical(self, 'URL error', 'In case the url is not correct, download failed\n'
                                                      '站点不可用，不能下载。')
            return
        if self.pages_line.text().isdigit() is False:
            QMessageBox().critical(self, 'Pages error', 'How many pages you want to download?\n请输入正确的下载页数')
            return
        self.start_btn.setEnabled(False)

        # 生成一个generator, 提供给线程协同下载topics
        pages_generator = (self.url_line.text() + self.sub_forum_addr() + '{}.html'.format(each)
                     for each in range(1, int(self.pages_line.text()) + 1))
        for each in range(Page_Threads):
            td = SIS.SISTopic(pages_generator, self.topics_pool, self.cookies, self)
            td.send_text.connect(self.infoRec)
            td.start()
        # create a generator from above list, provide to torrents_downloader threads co-work.
        self.topics_generator = (x for x in self.topics_pool)
        self.pics_generator = (x for x in self.pics_pool_for_downloading)
        self.startTimer(1000)

    def timerEvent(self, QTimerEvent):
        self.progress_label.setText('Topics Remain: {} \t Pics Remain: {} \t Topic Threads: {} \t Picture Threads: {}'
                                    .format(len(self.topics_pool) - self.topics_finished,
                                            len(self.pics_pool_for_downloading) - self.pictures_finished,
                                            self.topics_working_threads, self.pictures_working_threads))
        if len(self.pics_pool_for_downloading) - self.pictures_finished > 10 \
                and self.pictures_working_threads < Picture_Threads:
            th = SIS.SISPicLoader(self.pics_generator, self)
            th.picpak_broadcast.connect(self.sqloperator.picUpdate)
            th.thread_progress_signal.connect(self.threadClosedSlot)
            th.start()
            self.pictures_working_threads += 1
            print('New Picture Thread {} Created'.format(self.pictures_working_threads))
        if len(self.topics_pool) - self.topics_finished > 10 \
                and self.topics_working_threads < Topic_Threads:
            th = SIS.SISTors(self.topics_generator, self.sqlqueries_pool, self.cookies, self)
            th.send_text.connect(self.infoRec)
            th.thread_progress_signal.connect(self.threadClosedSlot)
            th.start()
            self.topics_working_threads += 1
            print('New Torrent Thread {} Created'.format(self.topics_working_threads))

    def threadClosedSlot(self, what):
        if 'pic thread done' in what:
            self.pictures_working_threads -= 1
        elif 'topic thread done' in what:
            self.topics_working_threads -= 1
        elif 'one thread finished' in what:
            self.topics_finished += 1
        elif 'one picture finished' in what:
            self.pictures_finished += 1

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

    def initUI(self):
        # browser stuff below
        b_menu_layout1 = QHBoxLayout()
        self.b_search_line = QLineEdit()
        self.b_search_line.setMinimumWidth(300)
        self.b_category_combox = QComboBox()
        self.b_mosaick_combox = QComboBox()
        self.b_mosaick_combox.addItems(('所有', '无码', '有码', '不确定'))
        self.b_start_load = QPushButton('Load 加载')
        self.b_start_load.clicked.connect(self.startQuery)
        b_menu_layout1.addWidget(self.b_search_line)
        b_menu_layout1.addWidget(self.b_category_combox)
        b_menu_layout1.addWidget(self.b_mosaick_combox)
        b_menu_layout1.addWidget(self.b_start_load)
        b_menu_layout1.addStretch(10)
        self.b_table_view = QTableWidget()
        self.b_table_view.itemClicked.connect(self.whenItemClicked)
        self.b_table_view.setEditTriggers(QTableWidget.NoEditTriggers)
        self.b_table_view.setSortingEnabled(True)
        self.b_table_view.setSelectionBehavior(QTableWidget.SelectRows)
        self.b_table_view.setSelectionMode(QTableWidget.SingleSelection)
        self.b_table_view.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        b_layout = QVBoxLayout()
        b_layout.addLayout(b_menu_layout1)
        b_layout.addWidget(self.b_table_view)

        self.setLayout(b_layout)
        # browser stuff above
        #################################################

    def setCategory(self, catey):
        self.b_category_combox.addItem('所有')
        self.b_category_combox.addItems(catey)

    def startQuery(self):
        query = 'SELECT * FROM SIS'
        if self.b_search_line.text() is not '':
            query += ' WHERE name GLOB "*{}*"'.format(self.b_search_line.text())
        if self.b_category_combox.currentIndex() != 0:
            if 'WHERE' in query:
                query += ' AND type="{}"'.format(self.b_category_combox.currentText())
            else:
                query += ' WHERE type="{}"'.format(self.b_category_combox.currentText())
        if self.b_mosaick_combox.currentIndex() != 0:
            if 'WHERE' in query:
                query += ' AND mosaic={}'.format(self.b_category_combox.currentIndex()-1)
            else:
                query += ' WHERE mosaic={}'.format(self.b_category_combox.currentIndex()-1)
        connect = sqlite3.connect('SISDB.sqlite')
        result = connect.cursor().execute(query).fetchall()
        connect.close()
        self.placeItem(result)

    def placeItem(self, items):
        self.b_table_view.clear()
        self.b_table_view.setColumnCount(10)
        self.b_table_view.setHorizontalHeaderLabels(('类型', '片名', '码', '赞', '日期',
                                                     '容量', '格式', '简要', '磁力链', '截图'))
        self.b_table_view.setRowCount(len(items))
        for row, each in enumerate(items):
            for _n, item in enumerate(each[1:]):
                tableitem = QTableWidgetItem()
                tableitem.setTextAlignment(Qt.AlignCenter)
                if _n == 0:
                    tableitem.setData(Qt.DisplayRole, item)
                    tableitem.setToolTip(item)
                elif _n == 7:
                    if 'NULL' not in item:
                        tableitem.setText('...')
                        tableitem.setToolTip(item)
                else:
                    tableitem.setData(Qt.DisplayRole, item)
                self.b_table_view.setItem(row, _n, tableitem)
            connect = sqlite3.connect('SISDB.sqlite')
            tors = [x[0] for x in connect.cursor().execute('SELECT magnet from SIStor WHERE tid=?', (each[0],)).fetchall()]
            pics = connect.cursor().execute('SELECT picb from SISpic WHERE tid=?', (each[0],)).fetchone()
            connect.close()

            tableitem = QTableWidgetItem('打开')
            tableitem.setTextAlignment(Qt.AlignCenter)
            tableitem.setData(1000, tors)
            self.b_table_view.setItem(row, 8, tableitem)

            if pics:
                tableitem = QTableWidgetItem('显示')
                tableitem.setTextAlignment(Qt.AlignCenter)
                tableitem.setData(1000, each[0])
                self.b_table_view.setItem(row, 9, tableitem)

        for _n in range(10):
            if _n == 1:
                continue
            self.b_table_view.horizontalHeader().setSectionResizeMode(_n, QHeaderView.ResizeToContents)

    def whenItemClicked(self, item):
        if item.column() == 8:
            sw = SISSubWin(self.b_table_view.item(item.row(), 1).data(Qt.DisplayRole), item.data(1000), 't', self)
            sw.show()
        if item.column() == 9 and item.data(1000) is not None:
            tid = item.data(1000)
            connect = sqlite3.connect('SISDB.sqlite')
            pics = [x[0] for x in connect.cursor().execute('SELECT picb from SISpic WHERE tid=?', (tid,))]
            connect.close()
            sw = SISSubWin(self.b_table_view.item(item.row(), 1).data(Qt.DisplayRole), pics, 'p', self)
            sw.show()


class SISSubWin(QDialog):
    def __init__(self, title, items, flag, parent=None):
        super(SISSubWin, self).__init__(parent)
        self.setWindowTitle(title)
        layout = QVBoxLayout()
        table = QTableWidget()
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setColumnCount(1)
        table.setRowCount(len(items))
        if flag == 't':
            table.setHorizontalHeaderLabels(('磁力链',))
            for row, each in enumerate(items):
                item = QTableWidgetItem(each)
                table.setItem(row, 0, item)
        elif flag == 'p':
            table.setHorizontalHeaderLabels(('图片',))
            for row, each in enumerate(items):
                pix = QPixmap()
                pix.loadFromData(each)
                label = QLabel()
                label.setPixmap(pix)
                table.setCellWidget(row, 0, label)
        table.resizeColumnsToContents()
        table.resizeRowsToContents()
        layout.addWidget(table)
        self.setLayout(layout)




