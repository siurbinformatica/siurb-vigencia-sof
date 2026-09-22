import csv
import os
from datetime import datetime
from pathlib import Path

import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv

load_dotenv(Path(__file__).with_name('.env'))

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
    """Converte a string em date. Devolve None se vazia ou irreconhecivel."""
    value = (value or '').strip()
    if not value or value.upper() in ('NULL', 'NONE'):
        return None
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def parse_int(value):
    value = (value or '').strip()
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def ler_csv(path):
    rows = []
    ignoradas = []
    sem_data = 0

    with open(path, newline='', encoding='latin-1') as f:
        sample = f.read(2048)
        f.seek(0)
        delimiter = ';' if sample.count(';') > sample.count(',') else ','
        reader = csv.DictReader(f, delimiter=delimiter)

        for num, r in enumerate(reader, start=2):
            contrato = (r.get(COL_CONTRATO) or '').strip()
            ano = parse_int(r.get(COL_ANO))

            # sem chave nao ha como casar com o banco
            if not contrato or ano is None:
                ignoradas.append((num, contrato, r.get(COL_ANO)))
                continue

            bruta = (r.get(COL_INICIO) or '').strip()
            inicio = parse_date(bruta)
            if bruta and inicio is None:
                ignoradas.append((num, contrato, bruta))
                continue
            if inicio is None:
                sem_data += 1

            situ = (r.get(COL_SITU) or '').strip() or None

            # linha entra mesmo sem data: a situacao ainda vale
            rows.append((inicio, situ, contrato, ano))

    return rows, sem_data, ignoradas


def main():
    rows, sem_data, ignoradas = ler_csv(CSV_PATH)

    print(f'{len(rows)} linhas lidas do CSV '
          f'({sem_data} sem inicio de vigencia, so a situacao sera gravada).')
    for num, contrato, valor in ignoradas:
        print(f'  linha {num} ignorada: contrato={contrato!r} valor invalido={valor!r}')

    if not rows:
        print('Nada a atualizar.')
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

            # COALESCE: valor vazio no CSV nao apaga o que ja existe no banco.
            # RETURNING + fetch=True: o execute_values pagina a execucao, e o
            # cur.rowcount so reflete a ultima pagina. O fetch junta todas.
            atualizadas = execute_values(
                cur,
                """
                UPDATE tb_contratos AS t
                   SET inicio_vigencia = COALESCE(v.inicio, t.inicio_vigencia),
                       cod_situ        = COALESCE(v.situ, t.cod_situ)
                  FROM (VALUES %s) AS v (inicio, situ, cod, ano)
                 WHERE t.cod_contrato = v.cod
                   AND t.ano_contrato = v.ano
                RETURNING t.cod_contrato, t.ano_contrato
                """,
                rows,
                template='(%s::date, %s::text, %s::text, %s::int)',
                page_size=500,
                fetch=True,
            )
            print(f'{len(atualizadas)} de {len(rows)} linhas atualizadas.')

            # quais chaves do CSV nao existem na tabela
            cur.execute(
                """
                SELECT v.cod, v.ano
                  FROM (VALUES %s) AS v (cod, ano)
                 WHERE NOT EXISTS (
                       SELECT 1 FROM tb_contratos t
                        WHERE t.cod_contrato = v.cod
                          AND t.ano_contrato = v.ano)
                """ % ','.join(
                    cur.mogrify('(%s::text,%s::int)', (c, a)).decode()
                    for _, _, c, a in rows
                )
            )
            faltantes = cur.fetchall()
            print(f'{len(faltantes)} contratos do CSV nao existem em tb_contratos:')
            for cod, ano in faltantes[:20]:
                print(f'  {cod}/{ano}')
            if len(faltantes) > 20:
                print(f'  ... e mais {len(faltantes) - 20}')
    finally:
        conn.close()


if __name__ == '__main__':
    main()