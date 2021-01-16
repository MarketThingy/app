import pathlib
import structlog
import thingy.processors.extract
import thingy.processors.html


def all(source: str, target: str, logger: structlog.stdlib.BoundLogger):

    target = pathlib.Path(target)
    source = pathlib.Path(source)
    count = 0

    for path in (source / 'sec_edgar_filings').glob('*/*/*.txt'):
        count += 1
        logger.info('Processing archive', path=path, count=count)

        symbol, filing = path.parts[-3:-1]
        archive_target = target / symbol / filing
        archive_target.mkdir(parents=True, exist_ok=True)

        with open(path) as fp:
            extractor = thingy.processors.extract.EDGAR_Archive(fp.read(), logger)
            extractor.process(archive_target / path.stem)

    thingy.processors.html.HTML_Index(target, logger).process()

    if not count:
        logger.warning('WARNING: No files processed')
