from sec_edgar_downloader import Downloader

dl = Downloader('./archive')
symbols = ['CDEV', 'MTDR', 'QEP', 'SM', 'NR']

for symbol in symbols:
    print(f'Downloading 10-K for: {symbol}')
    dl.get('10-K', symbol)
