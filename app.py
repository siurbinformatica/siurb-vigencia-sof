import csv
import os
from datetime import datetime

import psycopg2
from dotenv import load_dotenv

load_dotenv()

db_config = {
    'host': os.getenv('DB_HOST'),
    'dbname': os.getenv('DB_NAME'),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'port': os.getenv('DB_PORT'),
}

CSV_PATH = os.path.join('archives', 'SCN009P.csv')

# nomes das colunas no CSV
COL_CONTRATO = 'COD_COTC'
COL_ANO = 'ANO_COTC'
COL_INICIO = 'DT_INIC_VIG'
COL_SITU = 'COD_SITU_COTC_ATU'

DATE_FORMATS = ['%d/%m/%Y %H:%M:%S', '%d/%m/%Y %H:%M', '%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y']


def parse_date(value):
    value = (value or '').strip()
    if not value:
        return None
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    raise ValueError(f'Data em formato não reconhecido: {value!r}')


def main():
    rows = []
    with open(CSV_PATH, newline='', encoding='latin-1') as f:
        sample = f.read(2048)
        f.seek(0)
        delimiter = ';' if sample.count(';') > sample.count(',') else ','
        reader = csv.DictReader(f, delimiter=delimiter)
        for r in reader:
            inicio = parse_date(r.get(COL_INICIO))
            if inicio is None:
                continue
            situ = (r.get(COL_SITU) or '').strip() or None
            rows.append((
                inicio,
                situ,
                r[COL_CONTRATO].strip(),
                int(r[COL_ANO]),
            ))

    if not rows:
        print('Nenhuma linha com início de vigência válido encontrada.')
        return

    conn = psycopg2.connect(**db_config)
    try:
        with conn, conn.cursor() as cur:
            cur.execute(
                'ALTER TABLE tb_contratos ADD COLUMN IF NOT EXISTS inicio_vigencia date'
            )
            cur.execute(
                'ALTER TABLE tb_contratos ADD COLUMN IF NOT EXISTS cod_situ text'
            )
            cur.executemany(
                """
                UPDATE tb_contratos
                   SET inicio_vigencia = %s,
                       cod_situ = %s
                 WHERE cod_contrato = %s
                   AND ano_contrato = %s
                """,
                rows,
            )
            print(f'{cur.rowcount} de {len(rows)} linhas atualizadas.')
    finally:
        conn.close()


if __name__ == '__main__':
    main()
