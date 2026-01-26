import polars as pl

def csv_trf(data):
    df = pl.read_csv(
        data,
        separator=';',
        encoding='utf8',
        has_header=True,
        try_parse_dates=False
    )
    return df

