# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Shared inert website-to-Markdown conversion and selection validation."""
import re
from urllib.parse import parse_qsl,urlencode,urljoin,urlsplit,urlunsplit,unquote
from bs4 import BeautifulSoup
from markdownify import MarkdownConverter
from soupsieve import compile as compile_selector,SelectorSyntaxError
from .source_http import CollectionError as C0Error, public_url
EXTRACTOR='markdownify-1.2.3/c0-website-3'
DEFAULTS={'seeds':[],'allowed_roots':[],'sitemaps':[],'exclude':[],
    'profile':'generic','selectors':[],'remove_selectors':[],
    'language':'','product':'','product_version':'','manual':'',
    'interval_ms':1000,'max_total_bytes':33554432,'max_cache_pages':1000,
    'configuration_version':'1'}
SELECTORS={'docusaurus':['article .theme-doc-markdown','.theme-doc-markdown','article'],
    'sphinx':['[role=main] .body','[role=main]','div.document div.body','article'],
    'generic':['article','main']}
NOISE='script,style,noscript,svg,nav,footer,form,button,.table-of-contents,.theme-doc-toc-mobile,.theme-doc-breadcrumbs,.theme-doc-footer,.headerlink,.copybutton,.copy-code-button,.toc-backref > span'
TRACKING={'fbclid','gclid','dclid','msclkid','mc_cid','mc_eid'}
MAX_FRONTIER=10000


def normalize(url,base=''):
    absolute=urljoin(base,url);parts=urlsplit(absolute)
    # No path case-folding, slash folding, locale/version stripping or query sort:
    # those operations can merge distinct resources on a documentation server.
    query=[(k,v) for k,v in parse_qsl(parts.query,keep_blank_values=True) if not k.lower().startswith('utm_') and k.lower() not in TRACKING]
    result=urlunsplit((parts.scheme.lower(),parts.netloc.lower(),parts.path or '/',urlencode(query),''))
    return public_url(result)


def configuration(value):
    if type(value) is not dict or set(value)-DEFAULTS.keys():raise C0Error('invalid_website_configuration')
    result={**DEFAULTS,**value}
    for field in ('seeds','allowed_roots','sitemaps','exclude','selectors','remove_selectors'):
        values=result[field]
        if type(values) is not list or len(values)>100 or any(type(v) is not str or not v or len(v)>4096 for v in values):
            raise C0Error('invalid_website_selection')
    if not result['seeds'] or not result['allowed_roots'] or result['profile'] not in SELECTORS:
        raise C0Error('explicit_documentation_roots_required')
    try:
        for selector in result['selectors']+result['remove_selectors']:compile_selector(selector)
    except (SelectorSyntaxError,RecursionError):raise C0Error('invalid_website_selector') from None
    for field in ('seeds','allowed_roots','sitemaps'):
        result[field]=[normalize(v) for v in result[field]]
    for field in ('language','product','product_version','manual','configuration_version'):
        if type(result[field]) is not str or len(result[field])>128 or '\0' in result[field]:raise C0Error('invalid_website_metadata')
    for field,low,high in (('interval_ms',100,60000),('max_total_bytes',65536,67108864),('max_cache_pages',1,1000)):
        if type(result[field]) is not int or not low<=result[field]<=high:raise C0Error('invalid_website_limit')
    for seed in result['seeds']:boundary(seed,result)
    for url in result['sitemaps']:boundary(url,result,inventory=True)
    return result


def boundary(url,config,*,inventory=False):
    url=normalize(url);parsed=urlsplit(url)
    decoded=parsed.path
    for _ in range(4):
        following=unquote(decoded)
        if '\\' in following or any(part in ('.','..') for part in following.split('/')):raise C0Error('website_path_escape')
        if following==decoded:break
        decoded=following
    else:raise C0Error('website_path_encoding_limit')
    for root in config['allowed_roots']:
        allowed=urlsplit(root)
        if (parsed.scheme,parsed.netloc)!=(allowed.scheme,allowed.netloc):continue
        prefix=allowed.path.rstrip('/')
        if inventory or parsed.path==prefix or parsed.path.startswith(prefix+'/'):return url
    raise C0Error('website_destination_not_approved')


def extract(raw,url,config,*,extractor=None):
    try:html=raw.decode('utf-8-sig')
    except UnicodeError:raise C0Error('website_invalid_utf8') from None
    soup=BeautifulSoup(html,'html.parser')
    if len(soup.find_all(True,limit=100001))>100000:raise C0Error('website_dom_limit')
    links=[]
    for anchor in soup.select('a[href]',limit=MAX_FRONTIER):
        try:links.append(normalize(anchor['href'],url))
        except (C0Error,ValueError):continue
    canonical=soup.select_one('link[rel~=canonical][href]')
    canonical=boundary(normalize(canonical['href'],url),config) if canonical else url
    def partition(value):
        parsed=urlsplit(value)
        roots=[root for root in config['allowed_roots'] if urlsplit(root).scheme==parsed.scheme and urlsplit(root).netloc==parsed.netloc and (parsed.path==urlsplit(root).path.rstrip('/') or parsed.path.startswith(urlsplit(root).path.rstrip('/')+'/'))]
        return max(roots,key=len) if roots else None
    if partition(canonical)!=partition(url):raise C0Error('website_canonical_crosses_document_partition')
    title=soup.title.get_text(' ',strip=True) if soup.title else ''
    selectors=config['selectors'] or SELECTORS[config['profile']]
    article=None
    for selector in selectors:
        nodes=soup.select(selector,limit=2)
        if len(nodes)==1 and nodes[0].get_text(strip=True):article=nodes[0];break
    if article is None:raise C0Error('website_article_missing_or_javascript_only')
    heading=article.find('h1');title=heading.get_text(' ',strip=True) if heading else title
    if (re.fullmatch(r'\s*(?:404(?:\s*[-:|].*)?|page not found|not found|pagina non trovata|sign in|log in|login)\s*',title,re.I)
            or article.select_one('input[type=password]')):raise C0Error('website_error_or_login_page')
    # Docusaurus/Sphinx tabs often contain server-rendered hidden variants. Keep
    # all panels and add their labels before removing interactive controls.
    for panel in article.select('[role=tabpanel]'):
        label=soup.find(id=panel.get('aria-labelledby',''))
        if label:
            heading=soup.new_tag('h3');heading.string=label.get_text(' ',strip=True);panel.insert(0,heading)
    for selector in [NOISE,*config['remove_selectors']]:
        for node in article.select(selector):node.decompose()
    # Docusaurus wraps each code line in a div. Converting those divs as prose
    # strips indentation and inserts blank lines that break continued commands.
    for pre in article.select('pre'):
        code=pre.find('code')
        lines=code.find_all(class_='token-line',recursive=False) if code else []
        if lines:
            content='\n'.join(line.get_text() for line in lines)
            code.clear();code.append(content)
    for node in article.select('[href],[src]'):
        for attribute in ('href','src'):
            if attribute not in node.attrs:continue
            value=node[attribute]
            if attribute=='href' and value.startswith('#'):continue
            try:
                resolved=normalize(value,canonical)
                fragment=urlsplit(value).fragment
                node[attribute]=resolved+('#'+fragment if fragment and attribute=='href' else '')
            except (C0Error,ValueError):node.attrs.pop(attribute,None)
    def language(pre):
        for node in (pre,pre.find('code')):
            if node:
                for cls in node.get('class',[]):
                    match=re.fullmatch(r'(?:language|lang)-([A-Za-z0-9_+.-]{1,40})',cls)
                    if match:return match[1]
        return ''
    body=MarkdownConverter(heading_style='ATX',bullets='-',code_language_callback=language,
        table_infer_header=True,wrap=False,strip_pre=None).convert_soup(article)
    body=body.replace('\r\n','\n').replace('\r','\n').lstrip('\ufeff').strip()+'\n'
    if not body.strip() or '\0' in body:raise C0Error('website_empty_article')
    metadata={'source_type':'website','extractor':extractor or EXTRACTOR,'configuration_version':config['configuration_version'],
        **{key:config[key] for key in ('product','product_version','language','manual')},
        'path':[value for value in (config['manual'],*urlsplit(canonical).path.strip('/').split('/')) if value]}
    return title or canonical,body.encode(),canonical,links,metadata

