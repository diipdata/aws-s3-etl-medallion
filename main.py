## IMPORTS

import os
import boto3
import pandas as pd
from typing import List
from dotenv import load_dotenv
from botocore.exceptions import NoCredentialsError, ClientError

# Carrega variáveis de ambiente
load_dotenv()

# --- CONFIGURAÇÕES ---
try:
    AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
    AWS_REGION = os.getenv('AWS_REGION')
    BUCKET_NAME = os.getenv('BUCKET_NAME')
    PASTA_ENTRADA = 'data'

    # Configuração do Cliente S3
    s3_client = boto3.client(
        's3',
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        region_name=AWS_REGION
    )
except Exception as e:
    print(f"Erro fatal ao configurar AWS ou carregar variáveis: {e}")
    exit()

## LE OS ARQUIVOS NO SISTEMA LOCAL
def listar_arquivos(pasta: str) -> List[str]:
    """Lista todos os arquivos em uma pasta local"""
    arquivo: List[str] =[]
    try:
        if not os.path.exists(pasta):
             print(f"Erro: A pasta '{pasta}' não foi encontrada.")
             return []
             
        for nome_arquivo in os.listdir(pasta):
            caminho_completo = os.path.join(pasta, nome_arquivo)
            if os.path.isfile(caminho_completo):
                arquivo.append(caminho_completo)
    except Exception as e:
        print(f"Erro ao listar arquivos: {e}")
        
    return arquivo

## --- CAMADAS MEDALHÃO (BRONZE -> SILVER -> GOLD) ---

# --- CAMADA 1: BRONZE (RAW) ---
def ingestao_bronze_s3(arquivo_caminho: str, nome_arquivo: str) -> None:
    """Faz upload do arquivo bruto para o S3"""
    try:
        # CORREÇÃO: Removido o 'for loop' que iterava sobre a string
        s3_client.upload_file(arquivo_caminho, BUCKET_NAME, f"raw/{nome_arquivo}")
        print(f'-> [Bronze] {nome_arquivo} enviado com sucesso.')
        
    except FileNotFoundError:
        print(f"Erro Bronze: Arquivo local não encontrado: {arquivo_caminho}")
        raise # Para o processo deste arquivo
    except ClientError as e:
        print(f"Erro Bronze: Falha de conexão/permissão AWS: {e}")
        raise
    except Exception as e:
        print(f"Erro genérico na Ingestão Bronze: {e}")
        raise

# --- CAMADA 2: SILVER (REFINED) ---
def processar_silver(arquivo: str) -> str:
    try:
        # Leitura
        print(f"-> [Silver] Iniciando transformação de {os.path.basename(arquivo)}")
        df = pd.read_csv(arquivo, delimiter=',')

        # --- Transformações ---
        # 1. Adiciona metadados
        df['dt_processamento'] = pd.Timestamp.now()
        
        # 2. Garantindo tipagem 
        df = df.astype(str)

        # 3. Alterando NaN
        # Obs: Como convertemos para string antes, o NaN virou string 'nan'. 
        # O fillna pode não funcionar como esperado em strings, mas mantive a lógica.
        cols_fillna = {'email': 'Sem Registro', 'state': 'Ausente', 
                       'street': 'Nao informado', 'number': 'Sem numero', 
                       'additionals': 'Sem complemento'}
        
        for col, valor in cols_fillna.items():
            if col in df.columns:
                df[col] = df[col].replace('nan', valor).fillna(valor)

        # Salva Parquet localmente
        nome_parquet = os.path.basename(arquivo).replace('.csv', '.parquet')
        caminho_parquet_local = os.path.join(os.path.dirname(arquivo), nome_parquet)
        
        df.to_parquet(caminho_parquet_local, index=False, compression='snappy')

        # Upload S3
        caminho_s3 = f"silver/{nome_parquet}"
        s3_client.upload_file(caminho_parquet_local, BUCKET_NAME, caminho_s3)
        print(f"-> [Silver] Sucesso: Salvo em s3://{BUCKET_NAME}/{caminho_s3}")

        return caminho_parquet_local

    except pd.errors.EmptyDataError:
        print(f"Erro Silver: O arquivo CSV está vazio: {arquivo}")
        raise
    except Exception as e:
        print(f"Erro na etapa Silver: {e}")
        raise

# --- CAMADA 3: GOLD (AGGREGATED) ---
def processar_gold(caminho_parquet_local: str) -> str:
    try:
        print(f"-> [Gold] Criando agregação...")
        df = pd.read_parquet(caminho_parquet_local)

        # Verificação de segurança se a coluna existe
        if 'state' not in df.columns:
            print("Aviso: Coluna 'state' não encontrada para agregação.")
            # Cria dataframe vazio ou trata conforme regra de negócio
            df_gold = pd.DataFrame({'total_registros': [len(df)]}) 
        else:
            # --- Agregação ---
            df_gold = df.groupby(['state']).size().reset_index(name='total_registros')

        nome_gold = os.path.basename(caminho_parquet_local).replace('.parquet', '_gold.parquet')
        caminho_gold_local = os.path.join(os.path.dirname(caminho_parquet_local), nome_gold)

        df_gold.to_parquet(caminho_gold_local, index=False)

        # Upload S3
        caminho_s3 = f"gold/{nome_gold}"
        s3_client.upload_file(caminho_gold_local, BUCKET_NAME, caminho_s3)
        print(f"-> [Gold] Sucesso: Salvo em s3://{BUCKET_NAME}/{caminho_s3}")
        
        # CORREÇÃO: Adicionado retorno para não quebrar a validação
        return caminho_gold_local

    except Exception as e:
        print(f"Erro na etapa Gold: {e}")
        raise

# --- VALIDAÇÃO (LEITURA DIRETA DO S3) ---
def validar_dados_nuvem(caminho_s3_gold: str):
    print(f"\n> [4/4] Verificação final (Lendo direto da Nuvem)...")
    try:
        url_s3 = f"s3://{BUCKET_NAME}/{caminho_s3_gold}"
        
        df_remoto = pd.read_parquet(
            url_s3,
            storage_options={
                'key': AWS_ACCESS_KEY_ID,
                'secret': AWS_SECRET_ACCESS_KEY
            }
        )
        print(f"   Leitura S3 OK! O arquivo Gold contem {len(df_remoto)} linhas.")
        print("   Amostra dos dados:")
        print(df_remoto.head())
    except Exception as e:
        print(f"   Erro ao validar leitura do S3: {e}")

## --- PIPELINE EXECUÇÃO ---

# --- PIPELINE PRINCIPAL ---
def executar_pipeline():
    print(f"--- INICIANDO PIPELINE ETL MEDALLION ---")
    arquivos = listar_arquivos(PASTA_ENTRADA)
    
    if not arquivos:
        print(f"Nenhum arquivo CSV encontrado na pasta '{PASTA_ENTRADA}'.")
        return

    for arquivo in arquivos:
        nome_arquivo = os.path.basename(arquivo)
        lixo_para_limpar = []
        
        try:
            print(f"\n=== PROCESSANDO ARQUIVO: {nome_arquivo} ===")
            
            # 1. Bronze
            ingestao_bronze_s3(arquivo, nome_arquivo)
            
            # 2. Silver
            path_silver = processar_silver(arquivo)
            if path_silver: 
                lixo_para_limpar.append(path_silver)
            
            # 3. Gold
            path_gold = processar_gold(path_silver)
            if path_gold:
                lixo_para_limpar.append(path_gold)
            
            # 4. Validação
            if path_gold:
                nome_gold_s3 = f"gold/{os.path.basename(path_gold)}"
                validar_dados_nuvem(nome_gold_s3)
            
            # 5. Limpeza (Opcional - descomentar se quiser deletar os parquets locais)
            # for item in lixo_para_limpar:
            #     if os.path.exists(item): os.remove(item)
            
        except Exception as e:
            print(f"!!! Falha crítica no pipeline do arquivo {nome_arquivo}: {e}")

if __name__ == "__main__":
    executar_pipeline()