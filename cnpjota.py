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

#Quantidade de threads simult, recomendado 5.
MAX_WORKERS = 5
csv_lock = threading.Lock()
print_lock = threading.Lock() 

stop_animation = threading.Event()
api_pause_lock = threading.Lock()
api_pause_event = threading.Event()
api_pause_event.set() 

def safe_print(*args, **kwargs):
    with print_lock:
        sys.stdout.write('\033[2K\r') 
        print(*args, **kwargs)
        sys.stdout.flush()

class SafeTqdm(tqdm):
    def display(self, msg=None, pos=None):
        with print_lock:
            sys.stdout.write('\033[2K\r')
            super().display(msg, pos)
            sys.stdout.flush()

def animate_chroma_logo():
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

# =====================================================================
# BRASILAPI (EXCLUSIVO para consulta única via CMD)
# =====================================================================
def fetch_cnpj_data_brasilapi(cnpj):
    url = f"https://brasilapi.com.br/api/cnpj/v1/{cnpj}"
    headers = {"User-Agent": "CNPJota-CLI/1.0"}

    try:
        response = requests.get(url, headers=headers, timeout=15)
        
        if response.status_code == 200:
            br_data = response.json()
            
            data = {
                "cnpj": br_data.get("cnpj"),
                "razao_social": br_data.get("razao_social"),
                "nome_fantasia": br_data.get("nome_fantasia"),
                "situacao_cadastral": br_data.get("descricao_situacao_cadastral"),
                "data_situacao_cadastral": br_data.get("data_situacao_cadastral"),
                "matriz_filial": br_data.get("descricao_identificador_matriz_filial"),
                "data_inicio_atividade": br_data.get("data_inicio_atividade"),
                "cnae_principal": f"{br_data.get('cnae_fiscal', '')} - {br_data.get('cnae_fiscal_descricao', '')}",
                "cnaes_secundarios": br_data.get("cnaes_secundarios", []),
                "natureza_juridica": br_data.get("natureza_juridica"),
                "logradouro": br_data.get("logradouro"),
                "numero": br_data.get("numero"),
                "complemento": br_data.get("complemento"),
                "bairro": br_data.get("bairro"),
                "cep": br_data.get("cep"),
                "uf": br_data.get("uf"),
                "municipio": br_data.get("municipio"),
                "email": br_data.get("email"),
                "capital_social": br_data.get("capital_social"),
                "porte_empresa": br_data.get("descricao_porte"),
                "opcao_simples": "Sim" if br_data.get("opcao_pelo_simples") else "Não",
                "data_opcao_simples": br_data.get("data_opcao_pelo_simples"),
                "opcao_mei": "Sim" if br_data.get("opcao_pelo_mei") else "Não",
                "data_opcao_mei": br_data.get("data_opcao_pelo_mei"),
                "QSA": []
            }
            
            tels = []
            tel1 = str(br_data.get("ddd_telefone_1") or "").strip()
            tel2 = str(br_data.get("ddd_telefone_2") or "").strip()
            if tel1 and len(tel1) > 2:
                tels.append({"ddd": tel1[:2], "numero": tel1[2:]})
            if tel2 and len(tel2) > 2:
                tels.append({"ddd": tel2[:2], "numero": tel2[2:]})
            data["telefones"] = tels
            
            for socio in br_data.get("qsa", []):
                data["QSA"].append({
                    "nome_socio": socio.get("nome_socio"),
                    "qualificacao_socio": socio.get("qualificacao_socio"),
                    "cnpj_cpf_socio": socio.get("cnpj_cpf_do_socio")
                })
                
            return data, None

        elif response.status_code == 404:
            return None, "Não Encontrado"
        else:
            return None, f"ERRO API: {response.status_code}"
            
    except Exception as e:
        return None, f"ERRO: {str(e)}"

# =====================================================================
# OPENCNPJ ( EXCLUSIVAMENTE para a lista em lote / CSV)
# =====================================================================
def fetch_cnpj_data_opencnpj(cnpj):
    url = f"https://api.opencnpj.org/{cnpj}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "application/json"
    }

    while True:
        api_pause_event.wait()
        
        try:
            response = requests.get(url, headers=headers, timeout=15)
            
            if response.status_code == 200:
                return response.json(), None
            elif response.status_code == 404:
                return None, "Não Encontrado"
            elif response.status_code in [429, 403]:
                with api_pause_lock:
                    if api_pause_event.is_set():
                        api_pause_event.clear()
                        is_lead_thread = True
                    else:
                        is_lead_thread = False
                
                if is_lead_thread:
                    safe_print(Fore.RED + Style.BRIGHT + f"\n[!] Bloqueio OpenCNPJ (Erro {response.status_code}).")
                    for remaining in range(180, 0, -1):
                        safe_print(Fore.YELLOW + f"[*] Pausa de segurança... Retomando em {remaining} segundos.  ", end='')
                        time.sleep(1)
                        
                    safe_print(Fore.GREEN + Style.BRIGHT + "\n[!] Pausa concluída. Retomando requisições automáticas...     ")
                    api_pause_event.set()
                else:
                    api_pause_event.wait()
                
                continue
            else:
                return None, f"ERRO API: {response.status_code}"
                
        except Exception as e:
            return None, f"ERRO: {str(e)}"

# =====================================================================
# Terminal
# =====================================================================
def display_single_cnpj_terminal(cnpj_raw):
    """Consulta rápida usando a BRASILAPI"""
    cnpj_clean = clean_cnpj(cnpj_raw)
    
    if len(cnpj_clean) != 14:
        safe_print(Fore.RED + f"[X] O CNPJ informado ('{cnpj_raw}') é inválido. Ele deve conter 14 dígitos numéricos.")
        return

    safe_print(Fore.YELLOW + Style.BRIGHT + f"[*] Consultando CNPJ: {cnpj_clean} (BrasilAPI)...\n")
    data, error = fetch_cnpj_data_brasilapi(cnpj_clean)

    if error:
        safe_print(Fore.RED + f"[X] Ocorreu um erro na consulta: {error}")
        return

    def show_field(label, value):
        if value and str(value).lower() != "none":
            safe_print(Fore.CYAN + f"{label}: " + Fore.WHITE + str(value))

    safe_print(Fore.MAGENTA + Style.BRIGHT + "="*60)
    safe_print(Fore.GREEN + Style.BRIGHT + " 🏢 DADOS DA EMPRESA")
    safe_print(Fore.MAGENTA + Style.BRIGHT + "="*60)

    show_field("Razão Social", data.get("razao_social"))
    show_field("Nome Fantasia", data.get("nome_fantasia"))
    show_field("CNPJ", data.get("cnpj"))
    show_field("Situação Cadastral", f"{data.get('situacao_cadastral')} (Desde: {data.get('data_situacao_cadastral')})")
    show_field("Tipo", data.get("matriz_filial"))
    show_field("Data de Abertura", data.get("data_inicio_atividade"))
    show_field("CNAE Principal", data.get("cnae_principal"))
    show_field("Natureza Jurídica", data.get("natureza_juridica"))

    endereco = f"{data.get('logradouro', '')}, {data.get('numero', '')}"
    if data.get('complemento'):
        endereco += f" - {data.get('complemento')}"
    endereco += f" - {data.get('bairro', '')} - {data.get('municipio', '')}/{data.get('uf', '')} - CEP: {data.get('cep', '')}"
    show_field("Endereço", endereco)

    show_field("Email", data.get("email"))
    show_field("Telefones", format_telefones(data.get("telefones")))

    if data.get('capital_social'):
        show_field("Capital Social", f"R$ {data.get('capital_social')}")
    show_field("Porte da Empresa", data.get("porte_empresa"))
    show_field("Opção pelo Simples", f"{data.get('opcao_simples')} (Adesão: {data.get('data_opcao_simples', 'N/A')})")
    show_field("Opção pelo MEI", f"{data.get('opcao_mei')} (Adesão: {data.get('data_opcao_mei', 'N/A')})")

    qsa_raw = data.get("QSA")
    if qsa_raw and isinstance(qsa_raw, list):
        safe_print(Fore.MAGENTA + Style.BRIGHT + "\n" + "="*60)
        safe_print(Fore.GREEN + Style.BRIGHT + " 👥 QUADRO DE SÓCIOS E ADMINISTRADORES (QSA)")
        safe_print(Fore.MAGENTA + Style.BRIGHT + "="*60)
        
        for socio in qsa_raw:
            nome = socio.get("nome_socio", "N/I")
            cargo = socio.get("qualificacao_socio", "N/I")
            doc = socio.get("cnpj_cpf_socio", "N/I")
            safe_print(Fore.YELLOW + f" • {nome} " + Fore.WHITE + f"({cargo} | Doc: {doc})")

    safe_print(Fore.MAGENTA + Style.BRIGHT + "="*60 + "\n")

def process_cnpj(cnpj, headers):
    """Consulta em massa usando o OPENCNPJ"""
    data, error = fetch_cnpj_data_opencnpj(cnpj)
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
  CNPJOTA - Consulta ultra-rápida de CNPJs
=========================================================

Como usar:
  1. Consulta Única no Terminal:
     cnpjota 87.921.849/0001-86

  2. Modo Lote (Interface Gráfica):
     cnpjota --select

  3. Modo Lote (Comandos via Terminal):
     cnpjota --listacnpj lista.txt --localsaida C:\\saida.csv
=========================================================
"""

    parser = argparse.ArgumentParser(
        description=help_text, 
        formatter_class=argparse.RawTextHelpFormatter,
        usage="cnpjota [CNPJ_UNICO] [--select] [--listacnpj LISTA] [--localsaida SAIDA]"
    )

    parser.add_argument("cnpj_unico", nargs="?", help="Consulte um único CNPJ diretamente no terminal")
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
        
        safe_print(Fore.RED + Style.BRIGHT + "⚠️  AVISO: As informações retornadas podem estar desatualizadas.")
        safe_print(Fore.YELLOW + "Caso seja importante, realize sempre a pesquisa pelo site oficial da Receita Federal.\n")
        
        # MODO ÚNICO -> BRASIL API
        if args.cnpj_unico:
            display_single_cnpj_terminal(args.cnpj_unico)
            
            stop_animation.set()
            anim_thread.join(timeout=1.0)
            
            sys.stdout.write('\033[?25h')
            sys.stdout.flush()
            
            input(Fore.YELLOW + Style.BRIGHT + "Pressione [ENTER] para sair...")
            return 

        # MODO LOTE -> OPENCNPJ
        safe_print(Fore.CYAN + Style.BRIGHT + " Iniciando o utilitário em lote (Via OpenCNPJ)...\n")

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
