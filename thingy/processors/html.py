import json
import yaml
import datetime
import collections
from pathlib import Path
from wheezy.template.engine import Engine
from wheezy.template.ext.core import CoreExtension
from wheezy.template.loader import FileLoader
from typing import Iterator
import structlog


class HTML_Index:
    def __init__(self, root: Path, logger: structlog.stdlib.BoundLogger):
        self.logger = logger
        self.root = root
        self.engine = Engine(
            loader=FileLoader([Path(__file__).parent / 'html_templates']),
            extensions=[CoreExtension()]
        )

    def process(self):
        self._create_symbol_index(self.root)

        for symbol in self._dirs(self.root):
            self._create_filing_index(symbol)

            for filing in self._dirs(symbol):
                self._create_archive_index(symbol, filing)

                for archive in self._dirs(filing):
                    self._create_document_index(symbol, filing, archive)

    def _dirs(self, path: Path) -> Iterator[Path]:
        return (item for item in path.iterdir() if item.is_dir())

    def _render(self, template: str, target: Path, **kwargs):
        kwargs['today'] = datetime.datetime.now().isoformat()
        with open(target, 'w') as fp:
            fp.write(
                self.engine.get_template(template).render(kwargs)
            )

    def _create_symbol_index(self, root: Path):
        self.logger.debug('creating symbol index', root=root)
        self._render(
            'symbol_index.html',
            root / 'index.html',
            symbols=[path.stem for path in self._dirs(root)])

    def _create_filing_index(self, symbol: Path):
        self.logger.debug('creating filing index', symbol=symbol)
        self._render(
            'filings_index.html',
            symbol / 'index.html',
            symbol=symbol.stem,
            filings=[path.stem for path in self._dirs(symbol)])

    def _create_archive_index(self, symbol: Path, filing: Path):
        self.logger.debug('creating archive index', symbol=symbol, filing=filing)
        archives = dict()

        for path in self._dirs(filing):
            with open(path / 'meta.json') as fp_json:
                meta = json.load(fp_json)
                filing_date_str = str(meta['header']['FILED AS OF DATE'])
                filing_date_obj = datetime.datetime.strptime(filing_date_str, '%Y%m%d')
                archives[path.stem] = filing_date_obj.strftime('%Y %B %d')

        self._render(
            'archives_index.html',
            filing / 'index.html',
            symbol=symbol.stem,
            filing=filing.stem,
            archives=archives)

    def _create_document_index(self, symbol: Path, filing: Path, archive: Path):
        self.logger.debug('creating document index', symbol=symbol, filing=filing, archive=archive)
        documents = collections.defaultdict(dict)

        with open(archive / 'meta.json') as fp_json:
            meta = json.load(fp_json)

            for filename, doc_meta in meta['documents'].items():
                documents[filename.partition('.')[-1].upper()][filename] = doc_meta.get('DESCRIPTION', doc_meta['TYPE'])

            self._render(
                'documents_index.html',
                archive / 'index.html',
                symbol=symbol.stem,
                filing=filing.stem,
                archive=archive.stem,
                headers=yaml.dump(meta['header']),
                documents=documents)
