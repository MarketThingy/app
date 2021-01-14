from __future__ import annotations
import structlog
import pathlib
import textwrap
import re
import codecs
import structlog
import collections
import wheezy.template
import wheezy.html.utils
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


class EDGAR_Document:
    DOCUMENT_RE = re.compile(r'<document>(.*?<text>.+?</text>.*?)</document>', re.IGNORECASE | re.DOTALL)
    ATTRS_RE = re.compile(r'^<(\w+)>(.+)$', re.IGNORECASE | re.MULTILINE)
    TEXT_RE = re.compile(r'<text>(.*)</text>', re.IGNORECASE | re.DOTALL)
    IS_UUENCODED = re.compile(r'^\s*begin \d+ .*end\s*$', re.DOTALL)

    def __init__(self, content: str, logger: structlog.stdlib.BoundLogger):
        self.logger = logger
        self.attrs = {key.upper(): value
                      for key, value in self.ATTRS_RE.findall(content)
                      if value}
        self.text = ''

        if (result := self.TEXT_RE.search(content)) is not None:
            self.text = result.groups()[0]

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

        if is_uuencoded := self.IS_UUENCODED.match(self.text):
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
    def find_all(cls, string: str, logger: structlog.stdlib.BoundLogger) -> List[EDGAR_Document]:
        return [
            cls(document, logger) for document in cls.DOCUMENT_RE.findall(string)
        ]


class EDGAR_Archive_10K:
    HEADER_RE = re.compile(r'<sec-header>(.*)</sec-header>', re.IGNORECASE | re.DOTALL)
    TEMPLATE_ENGINE = wheezy.template.engine.Engine(
        loader=wheezy.template.loader.DictLoader({
            'index': textwrap.dedent('''\
                    @require(target, header, file_hrefs)
                    <html>
                        <head>
                            <title>Expanded archive of @target.stem</title>
                        </head>
                        <body>
                            <h1>Expanded archive of @target.stem</h1>
                            <pre>@header</pre>

                            @for type, links in file_hrefs.items():
                                <p><b>Type: @type</b></p>
                                <ul>
                                @for link in links:
                                    <li>@link</li>
                                @end
                                </ul>
                            @end
                        </body>
                    </html>
                ''')}),
        extensions=[wheezy.template.ext.core.CoreExtension()]
    )

    def __init__(self, content: str, logger: structlog.stdlib.BoundLogger):
        self.logger = logger
        self.header = None
        self.documents = EDGAR_Document.find_all(content, self.logger)

        if (result := self.HEADER_RE.search(content)) is not None:
            self.header = result.groups()[0]

        if not self.header:
            raise RuntimeError('Unable to find header')
        if not self.documents:
            raise RuntimeError('Unable to find documents')

        self.logger.info('Loaded documents', doc_count=len(self.documents))

    def expand(self, target: pathlib.Path):
        target.mkdir(exist_ok=True)

        file_hrefs = collections.defaultdict(list)

        for doc in self.documents:
            doc.save(parent=target)
            file_hrefs[doc.attrs['TYPE']].append(doc.get_html_link())

        with open(target / 'index.html', 'w') as fp_index:
            index = self.TEMPLATE_ENGINE.get_template('index').render({
                'target': target,
                'header': wheezy.html.utils.html_escape(self.header),
                'file_hrefs': file_hrefs
            })
            fp_index.write(index)
            self.logger.debug('Wrote index', size=(len(index)))


def main(logger: structlog.stdlib.BoundLogger):
    for path in (pathlib.Path('archive') / 'sec_edgar_filings').glob('**/10-K/*.txt'):

        logger.info('Processing archive', path=path)

        with open(path) as fp:
            archive = EDGAR_Archive_10K(fp.read(), logger)
            archive.expand(path.with_suffix(''))


if __name__ == '__main__':
    main(structlog.get_logger())
