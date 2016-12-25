from flatbencode import decode, encode
import hashlib


def decodeTor(byte_tor):
    hashcontent = encode(decode(byte_tor)[b'info'])
    digest = hashlib.sha1(hashcontent).hexdigest()
    magneturl = 'magnet:?xt=urn:btih:{}'.format(digest)
    return magneturl

if __name__ == '__main__':
    with open('test.torrent', 'rb') as f:
        t = decodeTor(f.read())
    print(t)


