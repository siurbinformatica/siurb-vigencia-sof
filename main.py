import os
import glob
import json
import logging

import boto3
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values

from config.settings import PATH_DOWNLOAD

# LOGGING
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler()],
)
log = logging.getLogger("conversor_vigencia")


# SECRETS MANAGER
def get_db_secret():
    client = boto3.session.Session().client("secretsmanager", region_name="sa-east-1")
    response = client.get_secret_value(SecretId="prod/rds/siurbcofi")
    return json.loads(response["SecretString"])


# mapeamento coluna no CSV -> coluna no banco
COL_CONTRATO = "cod_cotc"
COL_ANO = "ano_cotc"
COL_INICIO = "dt_inic_vig"
COL_SITU = "cod_situ_cotc_atu"

PADRAO_ARQUIVO = "SCN009P*.csv"


class Conversor:

    def __init__(self, arquivos=None):
        self.arquivos = arquivos

    def encontrar_csvs(self):
        if self.arquivos:
            encontrados = [a for a in self.arquivos if os.path.isfile(a)]
            log.info(f"Usando {len(encontrados)} arquivo(s) informado(s)")
            return encontrados

        padrao = os.path.join(PATH_DOWNLOAD, PADRAO_ARQUIVO)
        encontrados = sorted(glob.glob(padrao))
        if not encontrados:
            raise FileNotFoundError(
                f"Nenhum arquivo '{PADRAO_ARQUIVO}' encontrado em '{PATH_DOWNLOAD}/'"
            )
        log.info(f"{len(encontrados)} arquivo(s) encontrado(s):")
        for a in encontrados:
            log.info(f"  - {os.path.basename(a)}")
        return encontrados

    def ler_arquivos(self, arquivos):
        dfs = []
        for arquivo in arquivos:
            df = pd.read_csv(arquivo, sep=";", encoding="latin-1")
            log.info(f"  {os.path.basename(arquivo)}: {len(df)} linhas")
            dfs.append(df)
        return pd.concat(dfs, ignore_index=True)

    def tratar_dados(self, df):
        df.columns = [col.strip().lower() for col in df.columns]

        obrigatorias = [COL_CONTRATO, COL_ANO, COL_INICIO]
        faltando = [c for c in obrigatorias if c not in df.columns]
        if faltando:
            raise ValueError(f"Colunas obrigatórias ausentes no CSV: {faltando}")

        colunas = [COL_INICIO, COL_SITU, COL_CONTRATO, COL_ANO]
        colunas = [c for c in colunas if c in df.columns]
        df = df[colunas].copy()

        # data de início da vigência (descarta hora)
        df[COL_INICIO] = pd.to_datetime(
            df[COL_INICIO], errors="coerce", dayfirst=True
        ).dt.date

        # ano como inteiro
        df[COL_ANO] = pd.to_numeric(df[COL_ANO], errors="coerce").astype("Int64")

        # contrato e situação como texto limpo
        df[COL_CONTRATO] = df[COL_CONTRATO].astype(str).str.strip()
        if COL_SITU in df.columns:
            df[COL_SITU] = df[COL_SITU].astype(str).str.strip()
        else:
            df[COL_SITU] = None

        # descarta linhas sem início de vigência ou sem chave
        df = df.dropna(subset=[COL_INICIO, COL_ANO])
        df = df[df[COL_CONTRATO] != ""]

        # remove duplicatas de (contrato, ano) — mantém a última ocorrência
        df = df.drop_duplicates(subset=[COL_CONTRATO, COL_ANO], keep="last")

        df = df.where(pd.notnull(df), None)
        return df

    def atualizar_no_banco(self, df):
        log.info("Obtendo credenciais do Secrets Manager...")
        db_secret = get_db_secret()

        conn = psycopg2.connect(
            host=db_secret["host"],
            dbname=db_secret["dbname"],
            user=db_secret["username"],
            password=db_secret["password"],
            port=db_secret["port"],
        )
        cur = conn.cursor()

        try:
            cur.execute(
                "ALTER TABLE tb_contratos ADD COLUMN IF NOT EXISTS inicio_vigencia date"
            )
            cur.execute(
                "ALTER TABLE tb_contratos ADD COLUMN IF NOT EXISTS cod_situ text"
            )

            # UPDATE em massa via tabela temporária de valores
            query = """
                UPDATE tb_contratos AS t
                   SET inicio_vigencia = v.inicio_vigencia,
                       cod_situ = v.cod_situ
                  FROM (VALUES %s) AS v(inicio_vigencia, cod_situ, cod_contrato, ano_contrato)
                 WHERE t.cod_contrato = v.cod_contrato
                   AND t.ano_contrato = v.ano_contrato
            """

            valores = [
                (
                    row[COL_INICIO],
                    row[COL_SITU],
                    row[COL_CONTRATO],
                    int(row[COL_ANO]),
                )
                for _, row in df.iterrows()
            ]

            execute_values(
                cur,
                query,
                valores,
                template="(%s, %s, %s, %s)",
                page_size=500,
            )
            conn.commit()
            log.info(f"Linhas atualizadas: {cur.rowcount} de {len(valores)}")
        except Exception as e:
            conn.rollback()
            log.error(f"Erro ao atualizar: {e}", exc_info=True)
            raise
        finally:
            cur.close()
            conn.close()

    def executar(self):
        log.info("=" * 60)
        log.info("INICIO - conversor_vigencia (PROD)")
        log.info("=" * 60)

        try:
            log.info("FASE 1 - Localizar CSVs")
            arquivos = self.encontrar_csvs()

            log.info("FASE 2 - Leitura e tratamento")
            df = self.ler_arquivos(arquivos)
            log.info(f"Total de linhas (todos os arquivos): {len(df)}")

            df = self.tratar_dados(df)
            log.info(f"Linhas após tratamento e deduplicação: {len(df)}")

            log.info("FASE 3 - Update no banco")
            self.atualizar_no_banco(df)

            log.info("=" * 60)
            log.info("CONCLUIDO")
            log.info("=" * 60)

        except Exception as e:
            log.error(f"ERRO GERAL: {e}", exc_info=True)
            raise


if __name__ == "__main__":
    Conversor().executar()