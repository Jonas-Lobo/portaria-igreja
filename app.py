import time
import random
import streamlit as st
import gspread
from gspread.exceptions import APIError
from oauth2client.service_account import ServiceAccountCredentials
 
# 1. Configuração da Página para ocupar a tela toda
st.set_page_config(page_title="Portaria de Ingressos", layout="wide")
 
# ---------------------------------------------------------------------------
# 2. Conexão com o Google Sheets
# ---------------------------------------------------------------------------
@st.cache_resource
def init_connection():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = st.secrets["gcp_service_account"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    return gspread.authorize(creds)
 
client = init_connection()
 
# ⚠️ OBRIGATÓRIO: Substitua pelo link da sua planilha
URL_PLANILHA = "https://docs.google.com/spreadsheets/d/1iUkxg-f0KN_VAGdSl-hIMcPz_-U3jzjfWpFdc66sG6o/edit?gid=0#gid=0"
 
@st.cache_resource
def get_worksheet():
    return client.open_by_url(URL_PLANILHA).worksheet("Base")
 
sheet = get_worksheet()
 
# ---------------------------------------------------------------------------
# 3. Retry com backoff exponencial para qualquer chamada à API do Sheets
#    (evita que um "quota exceeded" momentâneo derrube o app)
# ---------------------------------------------------------------------------
def chamar_com_retry(func, *args, max_tentativas=5, **kwargs):
    for tentativa in range(max_tentativas):
        try:
            return func(*args, **kwargs)
        except APIError as e:
            # 429 = quota exceeded, 5xx = erro temporário do lado do Google
            codigo = getattr(e.response, "status_code", None)
            if codigo in (429, 500, 502, 503) and tentativa < max_tentativas - 1:
                espera = (2 ** tentativa) + random.uniform(0, 1)  # backoff exponencial + jitter
                time.sleep(espera)
                continue
            raise
    return None
 
# ---------------------------------------------------------------------------
# 4. Cache local dos códigos (evita 1 leitura da planilha inteira por bipagem)
#    ttl curto só para sincronizar entre leitores/dispositivos diferentes
# ---------------------------------------------------------------------------
@st.cache_data(ttl=15, show_spinner=False)
def carregar_base():
    """Lê a planilha inteira UMA vez a cada 15s (compartilhado entre todos os usuários),
    em vez de 1 vez por bipagem."""
    registros = chamar_com_retry(sheet.get_all_values)
    # dict: codigo -> (linha_na_planilha, status)
    base = {}
    for i, row in enumerate(registros):
        if i == 0:
            continue
        codigo = row[0].strip()
        status = row[1].strip().upper() if len(row) > 1 else ""
        base[codigo] = {"linha": i + 1, "status": status}
    return base
 
# Guardamos também, em memória de processo (não só no cache_data), os códigos
# já marcados nesta sessão do app inteiro, para que uma bipagem duplicada
# rápida (antes do próximo refresh do cache) nunca precise ir à planilha.
if "usados_localmente" not in st.session_state:
    st.session_state.usados_localmente = set()
 
# ---------------------------------------------------------------------------
# 5. Função de Estilo Visual (Responsiva - Ajusta ao celular e PC)
# ---------------------------------------------------------------------------
def mostrar_alerta(icone, titulo, subtitulo, cor_fundo, cor_texto):
    st.markdown(f"""
        <style>
        .stApp {{
            background-color: {cor_fundo} !important;
        }}
        header {{visibility: hidden;}}
        .alerta-box {{
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            text-align: center;
            margin-top: 10px;
        }}
        .alerta-titulo {{
            font-size: clamp(40px, 12vw, 100px);
            color: {cor_texto};
            font-weight: 900;
            line-height: 1.1;
            margin-bottom: 20px;
        }}
        .alerta-subtitulo {{
            font-size: clamp(25px, 6vw, 45px);
            color: {cor_texto};
            font-weight: bold;
            background-color: rgba(0, 0, 0, 0.15);
            padding: 10px 25px;
            border-radius: 15px;
        }}
        </style>
 
        <div class="alerta-box">
            <div class="alerta-titulo">{icone}<br>{titulo}</div>
            <div class="alerta-subtitulo">{subtitulo}</div>
        </div>
        """, unsafe_allow_html=True)
 
# ---------------------------------------------------------------------------
# 6. Lógica de Validação (agora batendo no cache local, não na planilha)
# ---------------------------------------------------------------------------
def validar_ingresso(codigo):
    codigo = str(codigo).strip()
    base = carregar_base()
    info = base.get(codigo)
 
    if info is None:
        mostrar_alerta("❌", "NÃO IDENTIFICADO", f"Código: {codigo}", "#b71c1c", "white")
        return
 
    ja_usado = info["status"] == "OK" or codigo in st.session_state.usados_localmente
 
    if ja_usado:
        mostrar_alerta("⚠️", "DUPLICADO", f"Código: {codigo}", "#ffeb3b", "black")
    else:
        try:
            chamar_com_retry(sheet.update_cell, info["linha"], 2, "OK")
            st.session_state.usados_localmente.add(codigo)
            mostrar_alerta("✅", "LIBERADO", f"Código: {codigo}", "#1b5e20", "white")
        except APIError:
            # Mesmo com retry, se ainda falhar, avisa sem quebrar o app
            mostrar_alerta(
                "⏳", "TENTE NOVAMENTE",
                f"Código: {codigo} (sistema ocupado)", "#ff9800", "black"
            )
 
# ---------------------------------------------------------------------------
# 7. Interface Otimizada para o Leitor Físico e Celular
# ---------------------------------------------------------------------------
st.title("🎫 Validação de Ingressos")
 
if "ultimo_codigo" not in st.session_state:
    st.session_state.ultimo_codigo = ""
 
def processar_leitura():
    st.session_state.ultimo_codigo = st.session_state.campo_leitor
    st.session_state.campo_leitor = ""
 
st.text_input("Mantenha o cursor piscando aqui e passe o ingresso no leitor:",
              key="campo_leitor",
              on_change=processar_leitura)
 
if st.session_state.ultimo_codigo:
    validar_ingresso(st.session_state.ultimo_codigo)
