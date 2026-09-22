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


COL_CONTRATO = "cod_cotc"
COL_ANO = "ano_cotc"
COL_INICIO = "dt_inic_vig"
COL_SITU = "cod_situ_cotc_atu"


def _texto(valor):
    """Normaliza celula do pandas em str limpa ou None."""
    if valor is None or pd.isna(valor):
        return None
    texto = str(valor).strip()
    return texto or None


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

        if COL_SITU not in df.columns:
            df[COL_SITU] = None

        df = df[[COL_INICIO, COL_SITU, COL_CONTRATO, COL_ANO]].copy()

        # guarda o valor bruto para distinguir data ausente de data invalida
        bruta = df[COL_INICIO].map(_texto)

        # data de inicio da vigencia (descarta hora)
        df[COL_INICIO] = pd.to_datetime(
            df[COL_INICIO], errors="coerce", dayfirst=True
        ).dt.date

        invalidas = bruta.notna() & df[COL_INICIO].isna()
        if invalidas.any():
            exemplos = bruta[invalidas].head(5).tolist()
            log.warning(
                f"{int(invalidas.sum())} linhas com {COL_INICIO} em formato "
                f"nao reconhecido (serao gravadas sem data): {exemplos}"
            )

        # ano como inteiro
        df[COL_ANO] = pd.to_numeric(df[COL_ANO], errors="coerce").astype("Int64")

        # contrato e situacao como texto limpo (None quando vazio)
        df[COL_CONTRATO] = df[COL_CONTRATO].map(_texto)
        df[COL_SITU] = df[COL_SITU].map(_texto)

        antes = len(df)
        df = df.dropna(subset=[COL_ANO, COL_CONTRATO])
        if len(df) < antes:
            log.warning(f"{antes - len(df)} linhas descartadas por falta de chave.")

        sem_data = int(df[COL_INICIO].isna().sum())
        if sem_data:
            log.info(
                f"{sem_data} linhas sem inicio de vigencia: "
                f"apenas a situacao sera gravada."
            )

        return df

    def atualizar_no_banco(self, df):
        valores = [
            (
                row[COL_INICIO] if not pd.isna(row[COL_INICIO]) else None,
                row[COL_SITU],
                row[COL_CONTRATO],
                int(row[COL_ANO]),
            )
            for _, row in df.iterrows()
        ]

        if not valores:
            log.warning("Nenhuma linha valida para atualizar.")
            return

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

            query = """
                UPDATE tb_contratos AS t
                   SET inicio_vigencia = COALESCE(v.inicio_vigencia, t.inicio_vigencia),
                       cod_situ        = COALESCE(v.cod_situ, t.cod_situ)
                  FROM (VALUES %s) AS v(inicio_vigencia, cod_situ, cod_contrato, ano_contrato)
                 WHERE t.cod_contrato = v.cod_contrato
                   AND t.ano_contrato = v.ano_contrato
                RETURNING t.cod_contrato, t.ano_contrato
            """

            atualizadas = execute_values(
                cur,
                query,
                valores,

                template="(%s::date, %s::text, %s::text, %s::int)",
                page_size=500,
                fetch=True,
            )

            log.info(f"Linhas atualizadas: {len(atualizadas)} de {len(valores)}")

            if len(atualizadas) < len(valores):
                cur.execute(
                    """
                    SELECT v.cod, v.ano
                      FROM (VALUES %s) AS v(cod, ano)
                     WHERE NOT EXISTS (
                           SELECT 1 FROM tb_contratos t
                            WHERE t.cod_contrato = v.cod
                              AND t.ano_contrato = v.ano)
                    """ % ",".join(
                        cur.mogrify("(%s::text,%s::int)", (cod, ano)).decode()
                        for _, _, cod, ano in valores
                    )
                )
                faltantes = cur.fetchall()
                log.warning(
                    f"{len(faltantes)} contratos do CSV nao existem em tb_contratos. "
                    f"Primeiros: {[f'{c}/{a}' for c, a in faltantes[:10]]}"
                )

            conn.commit()
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

            df = pd.read_csv(arquivo, sep=";", encoding="latin-1", dtype=str)
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