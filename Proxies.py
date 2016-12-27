import requests, json
from bs4 import BeautifulSoup as bsoup

# with open('sis_addr.dat') as f:
#     test_url = f.readline()
test_url = 'http://38.103.161.156'
headers = 'Mozilla/5.0 (Windows; U; Windows NT 5.1; en-US; rv:1.9a2pre) Gecko/20061231 Minefield/3.0a2pre'
proxies = []
for page in range(1, 100):
    req = requests.get('http://www.xicidaili.com/wt/{}'.format(page), headers={'User-Agent': headers})
    pobj = bsoup(req.content, 'lxml').findAll('tr')
    for each in pobj[1:]:
        sp = each.findAll('td')
        proxy = sp[1].text + ':' + sp[2].text
        try:
            if requests.head(test_url, proxies={'http': proxy}, headers={'User-Agent': headers}, timeout=3).ok:
                print('{} is good'.format(proxy))
                proxies.append(proxy)
            else:
                print('{} is bad'.format(proxy))
        except requests.exceptions.RequestException as err:
            print('{} is bad, error code: {}'.format(proxy, err))

with open('proxies.json') as f:
    proxies_in_file = json.loads(f.read())

proxies.extend(proxies_in_file)

with open('proxies.json', 'w') as f:
    f.write(json.dumps(proxies))
    print('job done.')