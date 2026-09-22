import os
import csv
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


COL_CONTRATO = "cod_cotc"
COL_ANO = "ano_cotc"
COL_INICIO = "dt_inic_vig"
COL_SITU = "cod_situ_cotc_atu"

PADRAO_ARQUIVOS = "*.csv"


def _texto(valor):
    """Normaliza celula do pandas em str limpa ou None."""
    if valor is None or pd.isna(valor):
        return None
    texto = str(valor).strip()
    return texto or None


def _detectar_separador(caminho):
    """Le o inicio do arquivo e decide entre ';' e ','."""
    with open(caminho, newline="", encoding="latin-1") as f:
        amostra = f.read(4096)
    return ";" if amostra.count(";") > amostra.count(",") else ","


class Conversor:

    def __init__(self, arquivo=None):
        # aceita um arquivo, uma pasta, ou None (usa PATH_DOWNLOAD)
        self.arquivo = arquivo

    def encontrar_csvs(self):
        if self.arquivo and os.path.isfile(self.arquivo):
            log.info(f"Usando arquivo informado: {self.arquivo}")
            return [self.arquivo]

        pasta = self.arquivo if self.arquivo else PATH_DOWNLOAD
        if not os.path.isdir(pasta):
            raise FileNotFoundError(f"Pasta não encontrada: '{pasta}'")

        # ordem cronologica: o arquivo mais novo tem a ultima palavra
        arquivos = sorted(
            glob.glob(os.path.join(pasta, PADRAO_ARQUIVOS)),
            key=lambda p: (os.path.getmtime(p), os.path.basename(p)),
        )
        if not arquivos:
            raise FileNotFoundError(
                f"Nenhum arquivo '{PADRAO_ARQUIVOS}' encontrado em '{pasta}/'"
            )

        log.info(f"{len(arquivos)} arquivo(s) encontrado(s) em '{pasta}/':")
        for caminho in arquivos:
            log.info(f"  - {os.path.basename(caminho)}")
        return arquivos

    def ler_arquivos(self, arquivos):
        """Le todos os CSVs e devolve um unico DataFrame."""
        partes = []
        obrigatorias = [COL_CONTRATO, COL_ANO, COL_INICIO]

        for ordem, caminho in enumerate(arquivos):
            nome = os.path.basename(caminho)
            try:
                # dtype=str: impede o pandas de inferir int/float nas chaves.
                # Uma coluna com celula vazia viraria float e o codigo do
                # contrato sairia como '14943.0', que nunca casa com a tabela.
                df = pd.read_csv(
                    caminho,
                    sep=_detectar_separador(caminho),
                    encoding="latin-1",
                    dtype=str,
                )
            except Exception as e:
                log.warning(f"  {nome}: falha na leitura, arquivo ignorado ({e})")
                continue

            df.columns = [col.strip().lower() for col in df.columns]

            faltando = [c for c in obrigatorias if c not in df.columns]
            if faltando:
                log.warning(
                    f"  {nome}: ignorado, colunas obrigatórias ausentes {faltando}"
                )
                continue

            if COL_SITU not in df.columns:
                df[COL_SITU] = None

            df = df[[COL_INICIO, COL_SITU, COL_CONTRATO, COL_ANO]].copy()
            df["_ordem"] = ordem
            df["_arquivo"] = nome
            partes.append(df)
            log.info(f"  {nome}: {len(df)} linhas")

        if not partes:
            raise ValueError("Nenhum arquivo válido para processar.")

        return pd.concat(partes, ignore_index=True)

    def tratar_dados(self, df):
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

        # descarta apenas linhas sem chave: sem chave nao ha como casar no banco.
        # linha sem inicio de vigencia PERMANECE, para gravar a situacao.
        antes = len(df)
        df = df.dropna(subset=[COL_ANO, COL_CONTRATO])
        if len(df) < antes:
            log.warning(f"{antes - len(df)} linhas descartadas por falta de chave.")

        return df

    def consolidar(self, df):
        """Um contrato pode aparecer em varios arquivos. Mantem, para cada
        campo, o valor preenchido mais recente (groupby.last ignora nulos)."""
        antes = len(df)
        df = df.sort_values("_ordem")

        consolidado = (
            df.groupby([COL_CONTRATO, COL_ANO], as_index=False, sort=False)
              .last()[[COL_INICIO, COL_SITU, COL_CONTRATO, COL_ANO]]
        )

        if len(consolidado) < antes:
            log.info(
                f"{antes} linhas consolidadas em {len(consolidado)} contratos "
                f"({antes - len(consolidado)} repetidos entre arquivos)."
            )

        anos = sorted(consolidado[COL_ANO].dropna().unique().tolist())
        log.info(f"Anos presentes: {anos}")

        sem_data = int(consolidado[COL_INICIO].isna().sum())
        if sem_data:
            log.info(
                f"{sem_data} contratos sem inicio de vigencia: "
                f"apenas a situacao sera gravada."
            )

        return consolidado

    def _contratos_ausentes(self, cur, valores):
        """Chaves do CSV que nao existem em tb_contratos, em lotes."""
        faltantes = []
        lote = 1000
        for i in range(0, len(valores), lote):
            bloco = valores[i:i + lote]
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
                    for _, _, cod, ano in bloco
                )
            )
            faltantes.extend(cur.fetchall())
        return faltantes

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

            # COALESCE: valor ausente no CSV nao apaga o que ja existe na tabela.
            # RETURNING + fetch=True: o execute_values pagina a execucao e o
            # cur.rowcount reflete apenas a ultima pagina; o fetch junta todas.
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
                # casts explicitos: sem eles o Postgres nao infere o tipo
                # de uma coluna do VALUES cujo primeiro valor seja NULL
                template="(%s::date, %s::text, %s::text, %s::int)",
                page_size=500,
                fetch=True,
            )

            log.info(f"Linhas atualizadas: {len(atualizadas)} de {len(valores)}")

            if len(atualizadas) < len(valores):
                faltantes = self._contratos_ausentes(cur, valores)
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
            log.info("FASE 1 - Localizar CSVs")
            arquivos = self.encontrar_csvs()

            log.info("FASE 2 - Leitura e tratamento")
            df = self.ler_arquivos(arquivos)
            log.info(f"Linhas encontradas: {len(df)}")

            df = self.tratar_dados(df)
            df = self.consolidar(df)
            log.info(f"Contratos após tratamento: {len(df)}")

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