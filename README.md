### What's it
* This is my crawler framework, it provides both downloading and displaying function, it highly efficiency with multiply threads co-work.

### Overview

![image](https://github.com/FYoungLee/SiSTor/blob/master/20161230042019.png)

### Table of content

#####[SIS.py](SIS.py)
* `SISThread` : Base object of all downloaders, it provides the locker and threads working control signal.
    *  `TheDownloader` : Inherits from SISThread, provides pick random headers and proxies functions, this object has a dict that record how many times those bad proxies unavailable, abandon those has exceed the limit; it also help make BeautifulSoup object return to caller.
        * `SISPageLoader` : Download all topics from given pages generator, store the topic urls into topics download queue.
        * `SISTopicLoader` : Download and extract all information from each topic in queue; stores brief info to sql queries thread, stores torrents and images url to queue.
        * `SISTorLoader` : Download torrents and decode to magnet string, send result to sql queries thread.
        * `SISPicLoader` : Download pictures and send the correct image to sql queries thread.
    * `SISSql` : Inherit from SISThread, it receives and implements all sql queries, save images to local direction.
    * `ProxiesThread` : The thread to crawl proxies from some proxies website, it also check the proxies if it available for target website, ignore those unavailable.

#####[SISUI.py](SISUI.py)
* `SISMainWindow`
    * `DownloaderWidget` : Downloading controller and downloading progress display.
    * `BrowserWidget` : Displaying data from sqlite databases.
        * `myTable` : The child widget in BrowserWidget, inherit from QListTable, add and modified some functions.
        * `SisPicWin` : The child widget in BrowserWidget, also modified some event functions.
            * `PicList` : child widget of sisPicWin

#####[SISDisplay.py](SISDisplay.py)
* `SISQuieis` : This thread handle all searching requests from databases, and feedback to BrowserWidget.



