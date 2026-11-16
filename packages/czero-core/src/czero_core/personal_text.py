# Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
"""Local HTML-to-text extraction; never performs network requests."""
from html.parser import HTMLParser


class _Text(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.hidden=[]
        self.parts=[]

    def handle_starttag(self, tag, attrs):
        if tag in {'script','style','template','iframe','object','svg','head'}:
            self.hidden.append(tag)
        if not self.hidden and tag in {'p','br','div','li','tr','h1','h2','h3','blockquote'}:
            self.parts.append('\n')

    def handle_endtag(self, tag):
        if self.hidden and self.hidden[-1]==tag:
            self.hidden.pop()
        if not self.hidden and tag in {'p','div','li','tr','blockquote'}:
            self.parts.append('\n')

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def html_text(value):
    if not isinstance(value,str) or len(value.encode('utf-8'))>2*1024*1024 or '\0' in value:
        raise ValueError('invalid_mail_body')
    parser=_Text()
    parser.feed(value)
    parser.close()
    return '\n'.join(line.strip() for line in ''.join(parser.parts).splitlines() if line.strip())
