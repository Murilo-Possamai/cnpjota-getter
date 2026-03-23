import argparse
import csv
import json
import os
import re
import sys
import threading
import time
import tkinter as tk
from tkinter import filedialog
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from tqdm import tqdm
from colorama import init, Fore, Style

init(autoreset=True)

MAX_WORKERS = 20
csv_lock = threading.Lock()
print_lock = threading.Lock() 

stop_animation = threading.Event()

def safe_print(*args, **kwargs):
    """Substitui o print padrão garantindo que não atropele a animação"""
    with print_lock:
        sys.stdout.write('\033[2K\r') 

        print(*args, **kwargs)
        sys.stdout.flush()

class SafeTqdm(tqdm):
    """Barra de progresso modificada para respeitar a trava de tela"""
    def display(self, msg=None, pos=None):
        with print_lock:
            sys.stdout.write('\033[2K\r')
            super().display(msg, pos)
            sys.stdout.flush()

def animate_chroma_logo():
    """Roda em 2º plano animando a logo com coordenadas fixas"""
    if os.name == 'nt':
        os.system('') 

    logo_lines = [
        " ▄████████ ███▄▄▄▄      ▄███████▄      ▄█  ▄██████▄      ███        ▄████████ ",
        "███    ███ ███▀▀▀██▄   ███    ███     ███ ███    ███ ▀█████████▄   ███    ███ ",
        "███    █▀  ███   ███   ███    ███     ███ ███    ███    ▀███▀▀██   ███    ███ ",
        "███        ███   ███   ███    ███     ███ ███    ███     ███   ▀   ███    ███ ",
        "███        ███   ███ ▀█████████▀      ███ ███    ███     ███      ▀███████████ ",
        "███    █▄  ███   ███   ███            ███ ███    ███     ███        ███    ███ ",
        "███    ███ ███   ███   ███            ███ ███    ███     ███        ███    ███ ",
        "████████▀   ▀█   █▀   ▄████▀      █▄ ▄███  ▀██████▀     ▄████▀      ███    █▀  ",
        "                                  ▀▀▀▀▀▀                                      "
    ]

    rainbow = ['\033[91m', '\033[93m', '\033[92m', '\033[96m', '\033[94m', '\033[95m']
    frame = 0

    while not stop_animation.is_set():
        with print_lock:
            sys.stdout.write('\033[s') 

            for r, line in enumerate(logo_lines):
                colored_line = ""
                for c, char in enumerate(line):
                    if char == ' ':
                        colored_line += char
                    else:
                        col_idx = ((c // 4) - frame) % len(rainbow)
                        colored_line += rainbow[col_idx] + char

                sys.stdout.write(f"\033[{r+1};1H\033[2K{colored_line}")

            sys.stdout.write('\033[0m') 

            sys.stdout.write('\033[u')  

            sys.stdout.flush()

        time.sleep(0.08)
        frame += 1

def clean_cnpj(cnpj):
    return re.sub(r'[^0-9]', '', str(cnpj))

def format_for_excel(value):
    if not value:
        return ""
    return f'="{value}"'

def format_telefones(telefones):
    if not isinstance(telefones, list):
        return ""

    numeros_formatados = []
    for tel in telefones:
        ddd = str(tel.get("ddd", "")).strip()
        numero = str(tel.get("numero", "")).strip()

        ddd_limpo = re.sub(r'\D', '', ddd)
        numero_limpo = re.sub(r'\D', '', numero)

        if ddd_limpo or numero_limpo:
            numeros_formatados.append(f"{ddd_limpo}{numero_limpo}")

    return ", ".join(numeros_formatados)

def format_qsa(qsa):
    if not isinstance(qsa, list):
        return ""

    socios_formatados = []
    for socio in qsa:
        nome = socio.get("nome_socio", "N/I")
        cargo = socio.get("qualificacao_socio", "N/I")
        documento = socio.get("cnpj_cpf_socio", "N/I")

        socios_formatados.append(f"{nome} ({cargo} - Doc: {documento})")

    return " | ".join(socios_formatados)

def fetch_cnpj_data(cnpj):
    url = f"https://api.opencnpj.org/{cnpj}"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return response.json(), None
        elif response.status_code == 404:
            return None, "Não Encontrado"
        elif response.status_code == 429:
            return None, "ERRO API: 429 (Rate Limit)"
        else:
            return None, f"ERRO API: {response.status_code}"
    except Exception as e:
        return None, f"ERRO: {str(e)}"

def process_cnpj(cnpj, headers):
    data, error = fetch_cnpj_data(cnpj)

    row = {h: "" for h in headers}
    row["cnpj"] = format_for_excel(cnpj)

    if error:
        row["erro"] = error
    else:
        for key in headers:
            if key in ["cnpj", "erro"]:
                continue
            if key in data and data[key] is not None:
                val = data[key]

                if key == "telefones":
                    row[key] = format_telefones(val)
                    continue
                elif key == "QSA":
                    row[key] = format_qsa(val)
                    continue

                if isinstance(val, (list, dict)):
                    val = json.dumps(val, ensure_ascii=False)

                if key in ["cep", "cnae_principal"]:
                    row[key] = format_for_excel(val)
                else:
                    row[key] = str(val)
    return row

def run_gui_selection():
    root = tk.Tk()
    root.withdraw()

    safe_print(Fore.CYAN + "[*] Aguardando seleção do arquivo de entrada na janela...")
    input_file = filedialog.askopenfilename(
        title="1. Selecione a lista de CNPJs (.txt)",
        filetypes=[("Arquivos de Texto", "*.txt"), ("Todos os Arquivos", "*.*")]
    )

    if not input_file:
        safe_print(Fore.RED + "[X] Operação cancelada: Nenhum arquivo de entrada foi selecionado.")
        sys.exit(1)

    safe_print(Fore.CYAN + "[*] Aguardando seleção da pasta de saída...")
    output_folder = filedialog.askdirectory(
        title="2. Selecione a pasta de saída (Cancele para usar 'Documentos')"
    )

    if not output_folder:
        output_folder = str(Path.home() / 'Documents')
        safe_print(Fore.YELLOW + f"[!] Aviso: Saída redirecionada para:\n-> {output_folder}")

    return input_file, output_folder

def main():
    help_text = """
=========================================================
  CNPJOTA - Consulta ultra-rápida de CNPJs em lote
=========================================================

Como usar:
  1. Modo Fácil (Interface Gráfica):
     cnpjota --select

  2. Modo Terminal (Comandos):
     cnpjota --listacnpj lista.txt --localsaida C:\\Caminho\\resultado.csv
=========================================================
"""

    parser = argparse.ArgumentParser(
        description=help_text, 
        formatter_class=argparse.RawTextHelpFormatter,
        usage="cnpjota [--select] [--listacnpj LISTA] [--localsaida SAIDA]"
    )

    parser.add_argument("--select", action="store_true", help="Abre janelas para escolher o arquivo e a pasta de saída.")
    parser.add_argument("--listacnpj", help="Caminho do arquivo .txt contendo os CNPJs")
    parser.add_argument("--localsaida", help="Caminho da pasta ou do arquivo .csv que será gerado")

    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(1)

    args = parser.parse_args()

    os.system('cls' if os.name == 'nt' else 'clear')
    sys.stdout.write('\033[?25l') 

    print("\n" * 10) 

    anim_thread = threading.Thread(target=animate_chroma_logo, daemon=True)
    anim_thread.start()

    try:
        time.sleep(0.2)
        safe_print(Fore.CYAN + Style.BRIGHT + " Iniciando o utilitário em lote...\n")

        if args.select:
            input_path, output_path = run_gui_selection()
        else:
            if not args.listacnpj or not args.localsaida:
                safe_print(Fore.RED + "Erro: Você deve usar '--select' OU fornecer '--listacnpj' e '--localsaida'.")
                sys.exit(1)
            input_path = args.listacnpj
            output_path = args.localsaida

        if not os.path.exists(input_path):
            safe_print(Fore.RED + f"[X] Erro: Arquivo não encontrado: {input_path}")
            sys.exit(1)

        with open(input_path, 'r', encoding='utf-8') as f:
            raw_cnpjs = f.read().splitlines()

        cnpjs = [clean_cnpj(c) for c in raw_cnpjs if clean_cnpj(c)]

        if not cnpjs:
            safe_print(Fore.RED + "[X] Nenhum CNPJ válido encontrado.")
            sys.exit(1)

        safe_print(Fore.GREEN + f"[+] {len(cnpjs)} CNPJs carregados com sucesso.")

        headers = [
            "cnpj", "razao_social", "nome_fantasia", "situacao_cadastral", "data_situacao_cadastral",
            "matriz_filial", "data_inicio_atividade", "cnae_principal", "cnaes_secundarios",
            "natureza_juridica", "logradouro", "numero", "complemento", "bairro", "cep", "uf",
            "municipio", "email", "telefones", "capital_social", "porte_empresa", "opcao_simples",
            "data_opcao_simples", "opcao_mei", "data_opcao_mei", "QSA", "erro"
        ]

        if os.path.isdir(output_path):
            output_path = os.path.join(output_path, "resultado_cnpjota.csv")
            safe_print(Fore.CYAN + f"[*] Gerando em: {output_path}")

        with open(output_path, 'w', encoding='utf-8-sig', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=headers, delimiter=';')
            writer.writeheader()

            safe_print(Fore.YELLOW + f"[*] Disparando motores: {MAX_WORKERS} requisições simultâneas...\n")

            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                future_to_cnpj = {executor.submit(process_cnpj, c, headers): c for c in cnpjs}

                for future in SafeTqdm(as_completed(future_to_cnpj), total=len(cnpjs), desc="Progresso", unit="cnpj", colour="green", file=sys.stdout):
                    row = future.result()
                    with csv_lock:
                        writer.writerow(row)

        safe_print(Fore.GREEN + Style.BRIGHT + f"\n[✓] Sucesso Absoluto! Relatório salvo em: {output_path}")

    except PermissionError:
        safe_print(Fore.RED + f"\n[X] Erro de Permissão: O arquivo '{output_path}' está aberto no Excel?")
    except Exception as e:
        safe_print(Fore.RED + f"\n[X] Ocorreu um erro inesperado: {str(e)}")

    finally:

        stop_animation.set()
        anim_thread.join(timeout=1.0)
        sys.stdout.write('\033[?25h') 

        sys.stdout.flush()
        print("\n")

if __name__ == "__main__":
    main()