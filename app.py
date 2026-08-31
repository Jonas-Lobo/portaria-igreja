import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# 1. Configuração da Página para ocupar a tela toda
st.set_page_config(page_title="Portaria de Ingressos", layout="wide")

# 2. Conexão com o Google Sheets
@st.cache_resource
def init_connection():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = st.secrets["gcp_service_account"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    return gspread.authorize(creds)

client = init_connection()

# ⚠️ OBRIGATÓRIO: Substitua pelo link da sua planilha
URL_PLANILHA = "https://docs.google.com/spreadsheets/d/1iUkxg-f0KN_VAGdSl-hIMcPz_-U3jzjfWpFdc66sG6o/edit?gid=0#gid=0"
sheet = client.open_by_url(URL_PLANILHA).worksheet("Base")

# 3. Função de Estilo Visual (Responsiva - Ajusta ao celular e PC)
def mostrar_alerta(icone, titulo, subtitulo, cor_fundo, cor_texto):
    st.markdown(f"""
        <style>
        /* Pinta o fundo da tela inteira */
        .stApp {{
            background-color: {cor_fundo} !important;
        }}
        /* Esconde barra superior para ficar mais limpo */
        header {{visibility: hidden;}}
        
        /* Formatação das letras usando CLAMP (cresce e diminui sozinho) */
        .alerta-box {{
            display: flex; 
            flex-direction: column; 
            justify-content: center; 
            align-items: center; 
            text-align: center;
            margin-top: 10px;
        }}
        .alerta-titulo {{
            /* Tamanho fluido: min 40px, ideal 12vw, max 100px */
            font-size: clamp(40px, 12vw, 100px); 
            color: {cor_texto}; 
            font-weight: 900; 
            line-height: 1.1;
            margin-bottom: 20px;
        }}
        .alerta-subtitulo {{
            /* Tamanho fluido para a caixinha do número */
            font-size: clamp(25px, 6vw, 45px);
            color: {cor_texto};
            font-weight: bold;
            background-color: rgba(0, 0, 0, 0.15); /* Fundo sutil */
            padding: 10px 25px;
            border-radius: 15px;
        }}
        </style>
        
        <div class="alerta-box">
            <div class="alerta-titulo">{icone}<br>{titulo}</div>
            <div class="alerta-subtitulo">{subtitulo}</div>
        </div>
        """, unsafe_allow_html=True)

# 4. Lógica de Validação
def validar_ingresso(codigo):
    records = sheet.get_all_values() 
    linha_encontrada = -1
    status_atual = ""
    
    for i, row in enumerate(records):
        if i == 0: continue 
        
        if row[0].strip() == str(codigo).strip():
            linha_encontrada = i + 1 
            status_atual = row[1].strip().upper() if len(row) > 1 else ""
            break
            
    if linha_encontrada == -1:
        # Fundo Vermelho
        mostrar_alerta("❌", "NÃO IDENTIFICADO", f"Código: {codigo}", "#b71c1c", "white")
    else:
        if status_atual == "OK":
            # Fundo Amarelo
            mostrar_alerta("⚠️", "DUPLICADO", f"Código: {codigo}", "#ffeb3b", "black")
        else:
            # Fundo Verde
            sheet.update_cell(linha_encontrada, 2, "OK")
            mostrar_alerta("✅", "LIBERADO", f"Código: {codigo}", "#1b5e20", "white")

# 5. Interface Otimizada para o Leitor Físico e Celular
st.title("🎫 Validação de Ingressos")

# Cria variáveis na memória para não perder o fluxo quando a tela atualizar
if "ultimo_codigo" not in st.session_state:
    st.session_state.ultimo_codigo = ""

# Esta função roda instantaneamente assim que o enter é disparado
def processar_leitura():
    st.session_state.ultimo_codigo = st.session_state.campo_leitor
    # Apaga o campo instantaneamente
    st.session_state.campo_leitor = ""

# O campo de texto agora reage automaticamente ao Enter (on_change)
st.text_input("Mantenha o cursor piscando aqui e passe o ingresso no leitor:", 
              key="campo_leitor", 
              on_change=processar_leitura)

# Roda a validação visual baseada no código lido
if st.session_state.ultimo_codigo:
    validar_ingresso(st.session_state.ultimo_codigo)
