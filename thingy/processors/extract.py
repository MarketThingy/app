from __future__ import annotations
import structlog
import pathlib
import textwrap
import regex
import codecs
import structlog
import collections
import json
import yaml
from typing import List

#
# ALL YE WHO ENTER HERE ...
#
# Yes, we're parsing XML with regular expressions
# Yes, we're aware this is a terrible idea
#
# But the SEC format sucks and includes many tags (in it's specification, mind you)
#   that have open, but no closing tags which causes XML parsers
#   (including BeautifulSoup) to parse the content incorrectly
#
# In addition, there are files that are uuencoded and BeautifulSoup completely mangles
#    the whitespace, making decoding those files impossible
#


class REGEXPS:
    HEADER = regex.compile(r'<sec-header>(.*)</sec-header>', regex.IGNORECASE | regex.DOTALL)
    DOCUMENT = regex.compile(r'<document>(.*?<text>.+?</text>.*?)</document>', regex.IGNORECASE | regex.DOTALL)
    ATTRS = regex.compile(r'^<(.+?)>(.+)$', regex.IGNORECASE | regex.MULTILINE)
    TEXT = regex.compile(r'<text>(.*)</text>', regex.IGNORECASE | regex.DOTALL)
    IS_UUENCODED = regex.compile(r'^\s*begin \d+ .*end\s*$', regex.DOTALL)


class _EDGAR_Document:

    def __init__(self, content: str, logger: structlog.stdlib.BoundLogger):
        self.logger = logger
        self.attrs = dict()
        self.text = ''

        if (result := REGEXPS.TEXT.search(content)) is not None:
            self.text = result.groups()[0]

            # Strip text so avoid REGEXPS.ATTRS picking up text attributes
            content = content[:result.start()] + content[result.end():]

        self.attrs = {key.upper(): value
                      for key, value in REGEXPS.ATTRS.findall(content)
                      if value}

        self.logger.debug('Loaded document', text_len=len(self.text), attrs=list(self.attrs.keys()))

        if not self.attrs:
            raise RuntimeError('Unable to find attrs')
        elif not self.text:
            raise RuntimeError('Unable to find text')

    @property
    def filename(self) -> str:
        if 'FILENAME' in self.attrs:
            return self.attrs['FILENAME']
        elif 'DESCRIPTION' in self.attrs:
            return f'{self.attrs["DESCRIPTION"].strip(".").replace("/","-")}.html'
        return f'{self.attrs["TYPE"]}.{self.attrs["SEQUENCE"]}'

    def save(self, parent: pathlib.Path):
        content = self.text
        target = parent / self.filename
        mode = 'w'

        if is_uuencoded := REGEXPS.IS_UUENCODED.match(self.text):
            content = codecs.decode(self.text.encode('utf-8'), 'uu')
            mode = 'wb'

        self.logger.debug(
            'Saving document',
            target=target,
            content_len=len(content),
            is_uuencoded=bool(is_uuencoded),
            mode=mode)

        with open(target, mode) as fp_doc:
            fp_doc.write(content)

    def get_html_link(self):
        filename = self.filename
        description = self.attrs.get("DESCRIPTION", filename)
        return f'<a href="./{filename}"><b>{description}</b> ({filename})</a>'

    @classmethod
    def find_all(cls,
                 string: str,
                 logger: structlog.stdlib.BoundLogger) -> List[_EDGAR_Document]:
        return [
            cls(document, logger) for document in REGEXPS.DOCUMENT.findall(string)
        ]


class EDGAR_Archive:

    def __init__(self, content: str, logger: structlog.stdlib.BoundLogger):
        self.logger = logger
        self.header = None
        self.documents = _EDGAR_Document.find_all(content, self.logger)

        if (result := REGEXPS.HEADER.search(content)) is not None:
            header_txt = REGEXPS.ATTRS.sub(r'\1: \2', result.groups()[0]).replace('\t', ' ' * 4)
            self.header = yaml.load(header_txt)

        if not self.header:
            raise RuntimeError('Unable to find header')
        if not self.documents:
            raise RuntimeError('Unable to find documents')

        self.logger.info('Loaded documents', doc_count=len(self.documents))

    def process(self, target: pathlib.Path):
        self._expand(target)
        self._save_metadata(target)

    def _expand(self, target: pathlib.Path):
        target.mkdir(exist_ok=True)

        for doc in self.documents:
            doc.save(parent=target)

    def _save_metadata(self, parent: pathlib.Path):
        with open(parent / 'meta.json', 'w') as fp_meta:
            self.logger.info('Saved metadata', path=fp_meta.name)
            json.dump({
                'header': self.header,
                'documents': {
                    document.filename: document.attrs for document in self.documents
                }
            }, fp_meta)
