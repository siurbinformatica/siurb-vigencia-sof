# Relatório Vigência

Script que lê um CSV de contratos (relatório SCN009P) e atualiza a tabela
`tb_contratos` no banco `siurb-sof`, gravando o início de vigência e o código
de situação atual de cada contrato.

## O que ele faz

1. Lê o CSV (encoding `latin-1`, delimitador detectado automaticamente).
2. Cria as colunas `inicio_vigencia` (date) e `cod_situ` (text) na tabela
   `tb_contratos`, caso ainda não existam.
3. Atualiza cada contrato casando por `cod_contrato` + `ano_contrato`,
   gravando `DT_INIC_VIG` em `inicio_vigencia` e `COD_SITU_COTC_ATU` em `cod_situ`.

Apenas contratos que já existem na tabela são atualizados — linhas do CSV sem
correspondência no banco são ignoradas. Ao final, o script imprime quantas
linhas foram efetivamente atualizadas.

## Pré-requisitos

- Python 3.9+
- Acesso de rede ao banco PostgreSQL
- O arquivo CSV na pasta do projeto (ou caminho definido em `CSV_PATH`)

## Instalação

```bash
pip install -r requirements.txt
```


## Mapeamento de colunas (CSV → banco)

| Coluna no CSV       | Destino no banco   |
|---------------------|--------------------|
| `COD_COTC`          | `cod_contrato` (chave) |
| `ANO_COTC`          | `ano_contrato` (chave) |
| `DT_INIC_VIG`       | `inicio_vigencia`  |
| `COD_SITU_COTC_ATU` | `cod_situ`         |

Se o relatório mudar os nomes dessas colunas, ajuste as constantes no topo do
`app.py`.

## Observações

- `cod_situ` foi criada como `text` para aceitar qualquer formato de código de
  situação. Se for sempre numérico, dá para trocar para `integer`.
