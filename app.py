import os
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


class Conversor:

    def __init__(self, arquivo=None):
        self.arquivo = arquivo

    def encontrar_csv(self):
        if self.arquivo and os.path.isfile(self.arquivo):
            log.info(f"Usando arquivo informado: {self.arquivo}")
            return self.arquivo

        caminho = os.path.join(PATH_DOWNLOAD, "SCN009P.csv")
        if not os.path.isfile(caminho):
            raise FileNotFoundError(
                f"Arquivo SCN009P.csv não encontrado em '{PATH_DOWNLOAD}/'"
            )
        log.info(f"Arquivo encontrado: {caminho}")
        return caminho

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
            log.info("FASE 1 - Localizar CSV")
            arquivo = self.encontrar_csv()

            log.info("FASE 2 - Leitura e tratamento")
            df = pd.read_csv(arquivo, sep=";", encoding="latin-1")
            log.info(f"Linhas encontradas: {len(df)}")

            df = self.tratar_dados(df)
            log.info(f"Linhas após tratamento: {len(df)}")

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