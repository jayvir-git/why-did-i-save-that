"""Bounded public-page fetcher. Resolve and pin each connection; validate redirects."""
import html.parser, http.client, ipaddress, socket, ssl, urllib.parse

class TextParser(html.parser.HTMLParser):
    def __init__(self):super().__init__();self.parts=[];self.hidden=0
    def handle_starttag(self,tag,attrs):
        if tag in ['script','style']:self.hidden+=1
        if tag in ['p','div','li','br','h1','h2','h3']:self.parts.append('\n')
    def handle_endtag(self,tag):
        if tag in ['script','style']:self.hidden=max(0,self.hidden-1)
    def handle_data(self,value):
        if not self.hidden:self.parts.append(value)

def validate_url(url):
    u=urllib.parse.urlsplit(url)
    if u.scheme not in ['https','http'] or not u.hostname or u.username or u.password or u.port not in [None,80,443]:raise ValueError('Only public HTTP(S) URLs on standard ports are supported')
    addresses=socket.getaddrinfo(u.hostname,u.port or (443 if u.scheme=='https' else 80),type=socket.SOCK_STREAM)
    ips=[a[4][0] for a in addresses]
    if not ips or any(not ipaddress.ip_address(ip).is_global for ip in ips):raise ValueError('Private, loopback, reserved and link-local destinations are not allowed')
    return u,ips[0]

def fetch_bytes(url,max_bytes=2_000_000,media=False):
    original=url
    for redirect in range(6):
        u,ip=validate_url(url);port=u.port or (443 if u.scheme=='https' else 80)
        connection=http.client.HTTPConnection(u.hostname,port,timeout=15)
        sock=socket.create_connection((ip,port),timeout=15)
        connection.sock=ssl.create_default_context().wrap_socket(sock,server_hostname=u.hostname) if u.scheme=='https' else sock
        try:
            target=urllib.parse.urlunsplit(('', '',u.path or '/',u.query,''))
            connection.request('GET',target,headers={'User-Agent':'GoldWorkspace/0.3 (local research)','Accept':'text/html,text/plain,application/json','Accept-Encoding':'identity'})
            response=connection.getresponse()
            if response.status in [301,302,303,307,308]:url=urllib.parse.urljoin(url,response.getheader('Location',''));continue
            if response.status!=200:raise ValueError(f'HTTP {response.status}; access failure recorded, no bypass attempted')
            mime=response.getheader('Content-Type','').split(';')[0]
            if not (mime.startswith('text/') or mime in ['application/json','application/xml'] or media and (mime.startswith('image/') or mime=='application/pdf')):raise ValueError(f'Unsupported representation {mime}; use an explicit extraction adapter')
            raw=response.read(max_bytes+1)
            if len(raw)>max_bytes:raise ValueError(f'Response exceeds the {max_bytes} byte fetch limit; no partial page stored as complete')
            return {'original_url':original,'url':url,'mime':mime,'raw':raw}
        finally:connection.close()
    raise ValueError('Too many redirects')

def fetch(url):
            value=fetch_bytes(url);raw=value['raw'];mime=value['mime']
            decoded=raw.decode('utf-8',errors='replace');text=decoded
            if mime=='text/html':
                parser=TextParser();parser.feed(decoded);text='\n'.join(line.strip() for line in ''.join(parser.parts).splitlines() if line.strip())
            return {**value,'text':text,'extractor':'html-parser-v1' if mime=='text/html' else 'utf8-v1'}
