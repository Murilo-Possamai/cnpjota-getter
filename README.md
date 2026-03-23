```text

 ▄████████ ███▄▄▄▄      ▄███████▄      ▄█  ▄██████▄      ███        ▄████████ 
███    ███ ███▀▀▀██▄   ███    ███     ███ ███    ███ ▀█████████▄   ███    ███ 
███    █▀  ███   ███   ███    ███     ███ ███    ███    ▀███▀▀██   ███    ███ 
███        ███   ███   ███    ███     ███ ███    ███     ███   ▀   ███    ███ 
███        ███   ███ ▀█████████▀      ███ ███    ███     ███     ▀███████████ 
███    █▄  ███   ███   ███            ███ ███    ███     ███       ███    ███ 
███    ███ ███   ███   ███            ███ ███    ███     ███       ███    ███ 
████████▀   ▀█   █▀   ▄████▀      █▄ ▄███  ▀██████▀     ▄████▀     ███    █▀  
                                  ▀▀▀▀▀▀
```

O **CNPJOTA** é um utilitário de linha de comando (CLI) desenvolvido em Python para consultar dados de Cadastro Nacional da Pessoa Jurídica (CNPJ) em massa utilizando a API pública do **[OpenCNPJ](https://opencnpj.org/)**. 

## 📦 Compilar para `.exe` (Windows)

2. Pyinstaller:
   ```cmd
   pyinstaller --onefile --name cnpjota cnpjota.py
   ```

## 🛠️ Como Usar

O CNPJOTA requer um arquivo de texto (`.txt`) contendo um CNPJ por linha. Ele ignora pontuações automaticamente, então os CNPJs podem estar formatados (`00.000.000/0001-00`) ou não (`00000000000100`).

Você pode rodar o programa de duas maneiras:

### 1. Modo Interface Gráfica (Fácil)
Abre janelas nativas do sistema para você escolher o arquivo `.txt` de entrada e a pasta onde deseja salvar o `.csv` de saída.
```cmd
cnpjota.exe --select
```
*(No Python: `python cnpjota.py --select`)*

### 2. Modo Terminal (Automação)
Ideal para rodar em scripts em lote (Batch/Bash) sem interação humana.
```cmd
cnpjota.exe --listacnpj lista_de_cnpjs.txt --localsaida C:\MeusRelatorios\resultado.csv
```
> **Nota:** Se você passar apenas uma pasta no argumento `--localsaida`, o arquivo será salvo automaticamente com o nome `resultado_cnpjota.csv` dentro dela.

## ⚠️ Tratamento de Erros e Limites da API
Por utilizar uma API pública, o CNPJOTA está sujeito a limites de requisição (*Rate Limit*). Se o servidor bloquear o excesso de velocidade, o script não irá "quebrar". Ele registrará a falha na coluna `erro` do CSV gerado com o status correspondente (Ex: `ERRO API: 429`), permitindo que você filtre e consulte os que faltaram posteriormente.

## 💻 Dependências (Para quem for rodar via Código-Fonte)

Se você não for usar o `.exe` compilado, precisará ter o Python instalado e as seguintes bibliotecas:
```bash
pip install requests tqdm colorama
```
