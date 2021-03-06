import click
import thingy.processors
import sec_edgar_downloader
import structlog
from typing import Tuple


@click.group()
def cli():
    pass


@cli.command()
@click.argument('symbol',
                nargs=-1,
                required=True)
@click.option('--target',
              type=click.Path(exists=True),
              required=True,
              help='Parent directory for downloaded files')
@click.option('--filing',
              type=click.Choice(['10-K', '10-Q'], case_sensitive=False),
              required=True,
              multiple=True,
              help='Type of SEC filing to download')
def download(symbol: Tuple[str], target: str, filing: Tuple[str]):
    '''Download SYMBOL [SYMBOL] ...

    Where SYMBOLs are stock ticker symbol
    '''

    logger = structlog.get_logger()

    downloader = sec_edgar_downloader.Downloader(target)
    for _symbol in symbol:
        for _filing in filing:
            logger.info('Downloading SEC documents', symbol=_symbol, filing=_filing)
            downloader.get(_filing, _symbol)


@cli.command()
@click.option('--source',
              type=click.Path(exists=True),
              required=True,
              help='Parent directory that houses downloaded files')
@click.option('--target',
              type=click.Path(exists=False),
              help=('Directory to write the output files. Defaults to SOURCE.'
                    ' Will be created if it does not exit'))
def process(source, target):
    '''Process files that have been downloaded.'''

    thingy.processors.all(source=source, target=target, logger=structlog.get_logger())


if __name__ == '__main__':
    cli()
