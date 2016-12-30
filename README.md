![image](https://github.com/FYoungLee/SiSTor/blob/master/20161230042019.png)

[SIS.py](SIS.py)
Thread的核心：
包含基类SISDownloader继承至QThread。
子类SISTopic专门下载主页面，将结果放入topics任务队列；
子类SISTor专门下载topics队列中的每条任务，封装好数据放入sql插入对列。
包含SISsql继承至QThread， 检查sql队列中的任务，将其插入到数据库中，图片信息包装好放入到图片下载队列。
包含SISPic继承制QThread， 检查图片下载队列任务，下载好反馈给SISsql插入数据库。

[Proxies.py](Proxies.py)
包含ProxiesThread继承制QThread， 从代理网站爬取代理并验证，成功放入代理池提供给各个下载Thread使用。

[SISUI.py](SISUI.py)
界面图形，包括：
downloader tab，下载器的用户交互界面。
browser tab， 展示数据库内容。

[tor2mag.py](tor2mag.py) 提供torrent转换magnet磁力链功能。

