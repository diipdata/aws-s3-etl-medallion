# AWS S3 Medallion ETL Pipeline 🏅

Este projeto implementa um pipeline de Engenharia de Dados completo (ETL), movendo dados de um ambiente local para a nuvem AWS S3, seguindo a **Arquitetura Medalhão** (Bronze, Silver e Gold).

## 🏗 Arquitetura do Projeto

O fluxo de dados segue as seguintes etapas:

1.  **Ingestão (Local → Bronze):**
    - Upload de arquivos CSV brutos (Raw Data) para o bucket S3 na pasta `raw/`.
    - Garante backup e imutabilidade dos dados originais.

2.  **Processamento (Bronze → Silver):**
    - Leitura dos dados brutos.
    - Limpeza e padronização utilizando **Pandas**.
    - Adição de metadados (ex: data de ingestão).
    - Conversão para formato **Parquet** (colunar e comprimido) e upload para `silver/`.

3.  **Agregação (Silver → Gold):**
    - Leitura dos dados refinados (Parquet).
    - Aplicação de regras de negócio e agregações.
    - Criação de uma visão analítica pronta para consumo e upload para `gold/`.

4.  **Verificação:**
    - Validação dos dados diretamente na nuvem utilizando leitura via `s3fs` sem necessidade de download físico.

## 🛠 Tecnologias Utilizadas

- **Linguagem:** Python 3.11.12
- **Cloud:** AWS S3 (Simple Storage Service)
- **Manipulação de Dados:** Pandas
- **Formatos de Arquivo:** CSV, Parquet
- **Bibliotecas:** `boto3`, `s3fs`, `python-dotenv`, `pandas`

## 🚀 Como Executar

1. Clone o repositório.
2. Crie um arquivo `.env` com suas credenciais AWS:
   ```env
   AWS_ACCESS_KEY_ID=sua_chave
   AWS_SECRET_ACCESS_KEY=sua_senha
   AWS_REGION=us-east-1
   BUCKET_NAME=nome-do-seu-bucket
3. Coloque seus arquivos CSV na pasta downloads/.
4. Execute o pipeline:

    ``python main.py``

----


**Criado por [Diego](https://github.com/diipdata)**  
diegop.freitas@gmail.com | [LinkedIn](https://linkedin.com/in/diegop-freitas) | [X/Twitter](https://x.com/diipdata)

*Feito com ☕ e muitas linhas de código (e alguns erros pelo caminho).*