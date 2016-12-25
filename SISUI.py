import SIS
import os, requests
from PyQt5.QtWidgets import QWidget, QPushButton, QHBoxLayout, QVBoxLayout, QLabel, QComboBox, QLineEdit, \
    QFileDialog, QMessageBox, QProgressBar, QTextBrowser


class SISMainWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        #
        # if os.name == 'nt':
        #     self.path_slash = '\\'
        # elif os.name == 'posix':
        #     self.path_slash = '/'
        # else:
        #     if QMessageBox().critical(self, 'Error', 'Unknown Operate System\n未知系统错误') == QMessageBox.OK:
        #         exit()
        self.init_ui()
        # this list store all topics that download from topic_downloader thread.
        self.topics_pool = []
        self.topics_generator = None
        self.tors_thread_name = None
        self.current_progress = [0]
        self.max_topics = [0]
        self.thread_done = 0
        self.working_threads = 0
        self.show()

    def init_ui(self):
        self.setToolTip('SIS Torrents Downloader '
                        '\n第一会所论坛种子下载器')

        self.info_box = QHBoxLayout()
        self.info_label = QLabel()
        self.info_label.setText('This application is supposed to private use, DO NOT share to anyone!'
                           '\n考虑到法律问题，本软件仅作为个人学习研究使用，请不要向他人传播。\n')
        self.info_box.addWidget(self.info_label)

        self.url_box = QHBoxLayout()
        self.url_label_title = QLabel('SiS Address (站点地址) ')
        self.url_line = QLineEdit()
        self.url_line.setText(self.get_forum_address())
        self.url_label = QLabel()
        self.url_label.setFixedWidth(50)
        self.check_url()
        self.url_test_btn = QPushButton('Test(测试)')
        self.url_test_btn.clicked.connect(self.check_url)
        self.url_box.addWidget(self.url_label_title)
        self.url_box.addWidget(self.url_line)
        self.url_box.addWidget(self.url_label)
        self.url_box.addWidget(self.url_test_btn)


        self.login_box = QHBoxLayout()
        self.login_id_label = QLabel('UserName')
        self.login_id_line = QLineEdit()
        self.login_pw_label = QLabel('Password')
        self.login_pw_line = QLineEdit()
        self.login_box.addWidget(self.login_id_label)
        self.login_box.addWidget(self.login_id_line)
        self.login_box.addWidget(self.login_pw_label)
        self.login_box.addWidget(self.login_pw_line)

        # self.path_box = QHBoxLayout()
        # self.path_label = QLabel('Save to (保存路径)')
        # self.path_line = QLineEdit()
        # self.path_loc_btn = QPushButton('...')
        # self.path_loc_btn.setFixedWidth(40)
        # self.path_loc_btn.clicked.connect(self.path_btn_clicked)
        # self.path_line.setText(os.getcwd()+self.path_slash)
        # self.path_box.addWidget(self.path_label)
        # self.path_box.addWidget(self.path_line)
        # self.path_box.addWidget(self.path_loc_btn)

        self.forum_select_box = QHBoxLayout()
        self.forum_info = QLabel('Which one (选择子版块)')
        self.forum_menu = QComboBox()
        self.forum_menu.addItem('Asia Uncensored Authorship Seed 亚洲无码原创区')
        self.forum_menu.addItem('Asia Censored Authorship Seed 亚洲有码原创区')
        self.forum_menu.addItem('Western Uncensored Authorship Seed 欧美无码原创区')
        self.forum_menu.addItem('Anime Authorship Seed 成人游戏动漫原创区')
        self.forum_menu.addItem('Asia Uncensored Section 亚洲无码转帖区 ')
        self.forum_menu.addItem('Asia Censored Section 亚洲有码转帖区')
        self.forum_menu.addItem('Western Uncensored 欧美无码转帖区')
        self.forum_menu.addItem('Anime Fans Castle 成人游戏动漫转帖区')
        self.forum_select_box.addWidget(self.forum_info)
        self.forum_select_box.addWidget(self.forum_menu)

        self.pages_box = QHBoxLayout()
        self.pages_label = QLabel("How many pages (下载页数，每页有30-40个种子)")
        self.pages_line = QLineEdit()
        self.pages_line.setText('1')
        self.pages_line.setFixedWidth(30)
        self.pages_box.addWidget(self.pages_label)
        self.pages_box.addWidget(self.pages_line)
        self.pages_box.addStretch(1)

        self.thread_box = QHBoxLayout()
        self.thread_label = QLabel('How many download threads (开启线程数，线程太多容易崩溃)')
        self.thread_menu = QComboBox()
        for each in range(1, 11):
            self.thread_menu.addItem(str(each))
        self.thread_box.addWidget(self.thread_label)
        self.thread_box.addWidget(self.thread_menu)
        self.thread_box.addStretch(1)

        # self.pic_box = QHBoxLayout()
        # self.pic_label = QLabel('How many pictures you\'d like to download in each topic.'
        #                         '\n(每个主题下载多少影片介绍图片，图越多耗时越久)')
        # self.pic_menu = QComboBox()
        # for each in range(0, 11):
        #     self.pic_menu.addItem(str(each))
        # self.pic_box.addWidget(self.pic_label)
        # self.pic_box.addWidget(self.pic_menu)
        # self.pic_box.addStretch(1)

        self.start_btn = QPushButton('Start', self)
        self.start_btn.clicked.connect(self.start_btn_clicked)
        self.start_btn.setFixedWidth(180)

        self.main_box = QVBoxLayout()
        self.main_box.addLayout(self.info_box)
        self.main_box.addLayout(self.url_box)
        self.main_box.addLayout(self.login_box)
        # self.main_box.addLayout(self.path_box)
        self.main_box.addLayout(self.forum_select_box)
        self.main_box.addLayout(self.pages_box)
        self.main_box.addLayout(self.thread_box)
        # self.main_box.addLayout(self.pic_box)
        self.main_box.addWidget(self.start_btn)

        self.output_box = QVBoxLayout()
        self.output_window = QTextBrowser()
        self.output_window.setFixedWidth(640)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_label = QLabel()
        self.progress_box = QHBoxLayout()
        self.progress_box.addWidget(self.progress_bar)
        self.progress_box.addWidget(self.progress_label)
        self.output_box.addWidget(self.output_window)
        self.output_box.addLayout(self.progress_box)

        self.allLayout = QVBoxLayout()
        self.allLayout.addLayout(self.main_box)
        self.allLayout.addLayout(self.output_box)

        self.setLayout(self.allLayout)

        self.setWindowTitle('SIS Torrents Downloader v1.0 by Fyang (肥羊)')
        self.setFixedWidth(680)
        self.setMinimumHeight(600)

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
            failed_msg = 'The address is not available now, try other one.' \
                         '\nPlease keep the address form: http://example/forum/' \
                         '\n前论坛地址已经不可用了，请输入新的地址。\n新地址输入，请务必保持正确的格式，包括符号！'
            QMessageBox().warning(self, 'Address Failed', failed_msg)

    def path_btn_clicked(self):
        path = QFileDialog.getExistingDirectory()
        if os.name == 'nt':
            path = path.replace('/', '\\')
        if path == '':
            return
        self.path_line.setText(path+self.path_slash)

    def start_btn_clicked(self):
        if 'Failed' in self.url_label.text():
            QMessageBox().critical(self, 'URL error', 'In case the url is not correct, download failed\n'
                                                    '站点不可用，不能下载。')
            return
        # if self.path_line.text() == '':
        #     QMessageBox().critical(self, 'Path error', 'Please provide correct saving direction.\n请输入正确的保存路径')
        #     return
        if self.pages_line.text().isdigit() is False:
            QMessageBox().critical(self, 'Pages error', 'How many pages you want to download?\n请输入正确的下载页数')
            return
        self.start_btn.setEnabled(False)
        self.max_topics[0] = 0
        self.current_progress[0] = 0
        self.topics_pool = []
        self.thread_done = 0
        self.working_threads = int(self.thread_menu.currentText())
        # create a generator from above list, provide to torrents_downloader threads co-work.
        self.topics_generator = (x for x in self.topics_pool)
        # create a generator, provide to torrents_downloader's name.
        self.tors_thread_name = (name for name in range(1, 30))
        # 生成一个generator, 提供给线程协同下载topics
        pages_url = (self.url_line.text() + self.sub_forum_addr() + '{}.html'.format(each)
                         for each in range(1, int(self.pages_line.text()) + 1))
        for each in range(int(self.thread_menu.currentText())):
            td = SIS.SISTopic(pages_url, self.topics_pool, self.max_topics,
                              self.login_id_line.text(), self.login_pw_line.text(), self)
            td.send_text.connect(self.infoRec)
            td.start()

    def infoRec(self, info):
        self.output_window.append(info)
        try:
            self.progress_bar.setValue(self.current_progress[0]*100/self.max_topics[0])
        except ZeroDivisionError:
            self.progress_bar.setValue(0)
        self.progress_label.setText('{}/{}'.format(self.current_progress[0], self.max_topics[0]))
        if 'This thread topics collector done' in info:
            th = SIS.SISTors(self.topics_generator, self.current_progress, next(self.tors_thread_name),
                             self.login_id_line.text(), self.login_pw_line.text(), self)
            th.send_text.connect(self.infoRec)
            th.start()
        if 'thread has finished' in info:
            self.thread_done += 1
            if self.thread_done == self.working_threads:
                self.start_btn.setEnabled(True)

        #
        # if pages < self.current_working_threads:
        #     QMessageBox().critical(self, 'Threads error', 'Threads must less than pages, reset again.\n'
        #                                                 '线程数需要小于页数，请重新设置')
        #     return
        # # calculating the pages for each thread
        # divined_pages = int(pages / self.current_working_threads)
        # start_page = 1
        # usrnm = self.login_id_line.text()
        # usrpw = self.login_pw_line.text()
        # path = self.path_line.text()
        # pics = int(self.pic_menu.currentText())
        # self.current_progress = 0
        # self.max_topics = 0
        # self.threads_finished = 0
        # for e in range(self.current_working_threads):
        #     end_page = start_page + divined_pages - 1
        #     thread = SIS.SISObj(e, self.url_line.text(), subforum, usrnm, usrpw, path, start_page, end_page, pics, self)
        #     thread.trigger_text.connect(self.update_info_window)
        #     thread.trigger_progress.connect(self.progress_received)
        #     thread.trigger_sent_all_topics_quantity.connect(self.topics_quantity_received)
        #     thread.trigger_done.connect(self.thread_finished)
        #     thread.start()
        #     start_page += divined_pages

    # def thread_finished(self, done):
    #     self.threads_finished += done
    #     if self.threads_finished == self.current_working_threads:
    #         self.start_btn.setEnabled(True)
    #         self.threads_finished = 0
    #         self.current_working_threads = 0

    def sub_forum_addr(self):
        index = self.forum_menu.currentIndex()
        if index == 0:
            return 'forum-143-'
        elif index == '1':
            return 'forum-230-'
        elif index == '2':
            return 'forum-229-'
        elif index == '3':
            return 'forum-231-'
        elif index == '4':
            return 'forum-25-'
        elif index == '5':
            return 'forum-58-'
        elif index == '6':
            return 'forum-77-'
        elif index == '7':
            return 'forum-27-'

