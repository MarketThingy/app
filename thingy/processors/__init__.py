import pathlib
import structlog
import thingy.processors.extract
import thingy.processors.html


def all(target: str, logger: structlog.stdlib.BoundLogger):

    target = pathlib.Path(target)
    count = 0

    for path in (target / 'sec_edgar_filings').glob('*/*/*.txt'):

        logger.info('Processing archive', path=path, count=count)

        with open(path) as fp:
            extractor = thingy.processors.extract.EDGAR_Archive(fp.read(), logger)
            extractor.process(path.with_suffix(''))

    thingy.processors.html.HTML_Index(target / 'sec_edgar_filings', logger).process()

    if not count:
        logger.warning('WARNING: No files processed')
