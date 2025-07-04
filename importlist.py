import streamlit as st
import json
import os
import pandas as pd
import numpy as np
import sqlite3
from datetime import datetime
from itertools import product
from collections import defaultdict

#MAJOR.MINOR.PATCH[-LABEL]
#-alpha: versão bem inicial, instável -beta: quase pronta, mas precisa de feedback -rc.1: release candidate (quase final)
Versao = "V1.0.0-rc.1"

#Config da página
st.set_page_config(
    page_title="SISMATERIAL",
    page_icon="images/logo_elco_ajustado.png",
    layout="wide"
)

st.logo(
    "images/logo_elco.png",
    link=None,
    icon_image=None
)

#Funções de autenticação
def carregar_usuarios():
    if os.path.exists("dados_cadastrais.json"):
        with open("dados_cadastrais.json", "r", encoding='utf-8') as file:
            try:
                return json.load(file)
            except json.JSONDecodeError:
                return {}
    return {}

def salvar_usuarios(usuarios):
    with open("dados_cadastrais.json", "w", encoding='utf-8') as file:
        json.dump(usuarios, file, indent=4, ensure_ascii=False)

def cadastrar_usuario(email, nome, senha, usuarios):
    """Cadastra novo usuário usando e-mail como chave"""
    if email in usuarios:
        return False
    usuarios[email] = {
        "nome": nome,
        "senha": senha
    }
    salvar_usuarios(usuarios)
    return True

def autenticar_usuario(email, senha, usuarios):
    """Autentica usando e-mail e senha"""
    return email in usuarios and usuarios[email]["senha"] == senha

def carregar_regras():
    regras = {}

    conn = sqlite3.connect("dados.db")
    cursor = conn.cursor()

    # Pega todos os itens
    cursor.execute("SELECT id, nome_item, ordem FROM itens_padrao")
    itens = cursor.fetchall()

    for item_id, nome_item, ordem_str in itens:
        ordem = [o.strip() for o in ordem_str.split(",") if o.strip()]
        valores_comuns = defaultdict(list)

        # Pega todos os valores comuns para esse item
        cursor.execute("""
            SELECT parametro, valor FROM valores_comuns
            WHERE item_id = ?
        """, (item_id,))
        resultados = cursor.fetchall()

        for parametro, valor in resultados:
            if valor:
                valores_comuns[parametro].append(valor)

        regras[nome_item] = {
            "ordem": ordem,
            "valores_comuns": dict(valores_comuns)
        }

    conn.close()
    return regras

def carregar_codigos_erp():
    import sqlite3
    conn = sqlite3.connect("dados.db")
    cursor = conn.cursor()

    cursor.execute("SELECT descricao, codigo_erp FROM codigos_erp")
    resultado = cursor.fetchall()

    conn.close()
    return dict(resultado)

def salvar_codigo_erp(descricao, codigo):
    import sqlite3
    conn = sqlite3.connect("dados.db")
    cursor = conn.cursor()

    cursor.execute("""
        INSERT OR REPLACE INTO codigos_erp (descricao, codigo_erp)
        VALUES (?, ?)
    """, (descricao, codigo))

    conn.commit()
    conn.close()

def carregar_insumos_pendentes():
    conn = sqlite3.connect("dados.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT nome_item, ordem, parametro, valor, criado_por, nome_usuario,
               data, status, justificativa_admin, codigo_erp
        FROM insumos_pendentes
    """)

    rows = cursor.fetchall()
    conn.close()

    agrupado = defaultdict(lambda: {
        "ordem": [],
        "valores_comuns": defaultdict(list),
        "criado_por": "",
        "nome_usuario": "",
        "data": "",
        "status": "",
        "justificativa_admin": "",
        "codigo_erp": ""
    })

    for nome_item, ordem_str, parametro, valor, criado_por, nome_usuario, data, status, justificativa, codigo in rows:
        agrupado[nome_item]["ordem"] = [o.strip() for o in ordem_str.split(",")]
        agrupado[nome_item]["valores_comuns"][parametro].append(valor)
        agrupado[nome_item]["criado_por"] = criado_por
        agrupado[nome_item]["nome_usuario"] = nome_usuario
        agrupado[nome_item]["data"] = data
        agrupado[nome_item]["status"] = status
        agrupado[nome_item]["justificativa_admin"] = justificativa
        agrupado[nome_item]["codigo_erp"] = codigo

    return agrupado

###########################################################Interface das Páginas

def pagina_login_cadastro():
    st.title("Autenticação de Usuário")
    menu = st.sidebar.selectbox("Menu", ["Login", "Cadastro"])
    usuarios = carregar_usuarios()
    st.sidebar.text(Versao)
    st.sidebar.text("Versão de testes. Nenhum dos dados salvos aqui serão trabalhados como oficiais.")

    if menu == "Login":
        st.subheader("Login")
        with st.form("login_form"):
            email = st.text_input("E-mail").strip().lower()
            senha = st.text_input("Senha", type="password")
            submitted = st.form_submit_button("Entrar")
            
            if submitted:
                if autenticar_usuario(email, senha, usuarios):
                    st.session_state['logged_in'] = True
                    st.session_state['username'] = usuarios[email]["nome"]
                    st.session_state['email'] = email
                    st.rerun()
                else:
                    st.error("E-mail ou senha incorretos.")

    elif menu == "Cadastro":
        st.subheader("Cadastro")
        with st.form("cadastro_form"):
            nome = st.text_input("Nome completo do usuário").strip()
            email = st.text_input("E-mail").strip().lower()
            senha = st.text_input("Senha", type="password")
            confirmar_senha = st.text_input("Confirme a senha", type="password")
            submitted = st.form_submit_button("Cadastrar")

            if submitted:
                if not nome or not email or not senha or not confirmar_senha:
                    st.warning("Preencha todos os campos.")
                elif senha != confirmar_senha:
                    st.warning("As senhas não coincidem.")
                elif cadastrar_usuario(email, nome, senha, usuarios):
                    st.success("Usuário criado com sucesso! Faça login para continuar.")
                else:
                    st.error("Este e-mail já está cadastrado.")

def pagina_principal():
    """Exibe a aplicação principal após o login."""
    import sqlite3

    #Sidebar de navegação  
    from streamlit_option_menu import option_menu
    with st.sidebar:
        pagina_selecionada = option_menu(
            "Navegação",
            options=["Início", "Gerador de Premissas", "Cadastro/Edição de Itens", "Mensagens", "Usuários", "Suporte", "Terminar sessão"],
            icons=["house", "tools", "plus-circle", "chat-left-text", "people", "info-circle", "box-arrow-right"],
            menu_icon="cast",
            default_index=0,
            styles={
                "container": {"padding": "5!important", "background-color": "#f0f2f6"}, ##f0f2f6
                "icon": {"color": "black", "font-size": "18px"},
                "nav-link": {"font-size": "16px", "text-align": "left", "font-family": "inherit"},
                "nav-link-selected": {"background-color": "#FFD700", "color": "black", "font-family": "inherit"},
            }
        )

###########################################################Página Início
    if pagina_selecionada == "Início":

        insumos_dict = carregar_insumos_pendentes()
        insumos = []
        for nome_item, dados in insumos_dict.items():
            insumos.append({
                "nome_item": nome_item,
                "ordem": dados["ordem"],
                "valores_comuns": dict(dados["valores_comuns"]),
                "criado_por": dados["criado_por"],
                "nome_usuario": dados["nome_usuario"],
                "data": dados["data"],
                "status": dados["status"],
                "justificativa_admin": dados["justificativa_admin"],
                "codigo_erp": dados["codigo_erp"]
            })

        #Indicadores
        qtd_pendentes = sum(1 for i in insumos if i["status"] == "pendente")
        regras = carregar_regras()
        qtd_aprovados = len(regras)

        col_card1, col_card2 = st.columns(2)
        with col_card1:
            st.metric("ITENS AGUARDANDO APROVAÇÃO", qtd_pendentes)
        with col_card2:
            st.metric("TOTAL DE ITENS CADASTRADOS", qtd_aprovados)

        try:
            from streamlit_extras.metric_cards import style_metric_cards
            style_metric_cards()
        except:
            pass

        st.markdown(f"""
        #### Olá, **{st.session_state.get('username', '')}** 👋
        Este é o sistema interno para padronização de descrições técnicas da Elco Engenharia.

        ---
        """)

        if not insumos:
            st.info("Nenhum insumo aguardando aprovação.")
        else:
            st.markdown("### Insumos Cadastrados")
            #Filtros
            col_f1, col_f2 = st.columns([1, 2])
            with col_f1:
                filtro_status = st.selectbox(
                    "Filtro de Status:",
                    options=["Todos", "Pendente", "Aprovado", "Rejeitado"]
                )
            with col_f2:
                busca = st.text_input("Buscar por nome do insumo")

            insumos_filtrados = [
                i for i in insumos
                if (filtro_status == "Todos" or i["status"].lower() == filtro_status.lower())
                and (not busca or busca.lower() in i["nome_item"].lower())
            ]
            #Ordena por data mais recente no topo
            try:
                insumos_filtrados.sort(
                    key=lambda x: datetime.strptime(x["data"], "%Y-%m-%d %H:%M"),
                    reverse=True
                )
            except Exception as e:
                st.warning("Erro ao ordenar insumos por data.")

            if not insumos_filtrados:
                st.info("Nenhum insumo encontrado com os critérios selecionados.")
            else:
                for idx, item in enumerate(insumos_filtrados):
                    expandir = item["status"] == "pendente"
                    status = item["status"].lower()
                    emoji_status = {
                        "aprovado": "🟢",
                        "rejeitado": "🔴",
                        "pendente": "🟡"
                    }.get(status, "⚪")

                    with st.expander(f"{emoji_status} {item['nome_item']} ({status.capitalize()})", expanded=expandir):

                        col1, col2, col3 = st.columns(3)
                        col1.markdown(f"**Criado por:** {item['nome_usuario']} ({item['criado_por']})")
                        col2.markdown(f"**Data:** {item['data']}")
                        col3.markdown(f"**Status atual:** `{item['status'].capitalize()}`")
                        if item['status'] in ["aprovado", "rejeitado"] and item.get("justificativa_admin"):
                            st.markdown(f"**Justificativa do Administrador:** {item['justificativa_admin']}")


                        st.markdown("**Parâmetros:**")
                        for p in item['ordem']:
                            valores = item['valores_comuns'].get(p, [])
                            st.markdown(f"- **{p.upper()}**: {', '.join(valores) if valores else '—'}")

                        perfil_logado = carregar_usuarios().get(st.session_state.get("email", ""), {}).get("perfil", "usuario")

                        # Aprovação e rejeição
                        if perfil_logado in ["adm", "adm_master"] and item['status'] == "pendente":
                            # Campo obrigatório: justificativa + código do item (ERP)
                            perfil_logado = carregar_usuarios().get(st.session_state.get("email", ""), {}).get("perfil", "usuario")

                        if perfil_logado in ["adm", "adm_master"] and item['status'] == "pendente":
                            justificativa_admin = st.text_area("Justificativa:", key=f"justificativa_{idx}")

                            col1, col2 = st.columns(2)
                            if col1.button("✅ Aprovar", key=f"aprovar_{idx}"):
                                item['status'] = "aprovado"
                                item['justificativa_admin'] = justificativa_admin.strip()
                                # ➕ Salvando código ERP no banco (se preenchido)
                                descricao_final = f"{item['nome_item']} " + " ".join(
                                    v.strip() for p in item['ordem'] for v in item['valores_comuns'].get(p, [])
                                ).strip().upper()

                                codigo_erp = item.get("codigo_erp", "").strip()
                                if descricao_final and codigo_erp:
                                    salvar_codigo_erp(descricao_final, codigo_erp)

                                # Atualiza no banco
                                conn = sqlite3.connect("dados.db")
                                cursor = conn.cursor()
                                cursor.execute("""
                                    UPDATE insumos_pendentes
                                    SET status = ?, justificativa_admin = ?
                                    WHERE nome_item = ?
                                """, ("aprovado", item["justificativa_admin"], item["nome_item"]))
                                conn.commit()
                                conn.close()

                                # (Opcional) também salvar no banco final se ainda não estiver
                                regras = carregar_regras()
                                if item["nome_item"] not in regras:
                                    from collections import defaultdict
                                    import sqlite3

                                    conn = sqlite3.connect("dados.db")
                                    cursor = conn.cursor()

                                    ordem_str = ",".join(item["ordem"])
                                    cursor.execute("INSERT OR IGNORE INTO itens_padrao (nome_item, ordem) VALUES (?, ?)",
                                                (item["nome_item"], ordem_str))
                                    item_id = cursor.execute("SELECT id FROM itens_padrao WHERE nome_item = ?",
                                                            (item["nome_item"],)).fetchone()[0]

                                    for parametro, valores in item["valores_comuns"].items():
                                        for valor in valores:
                                            cursor.execute("INSERT INTO valores_comuns (item_id, parametro, valor) VALUES (?, ?, ?)",
                                                        (item_id, parametro, valor))
                                    conn.commit()
                                    conn.close()

                                st.success(f"Insumo '{item['nome_item']}' aprovado e atualizado no banco.")
                                st.rerun()

                            if col2.button("❌ Rejeitar", key=f"rejeitar_{idx}"):
                                item['status'] = "rejeitado"
                                item['justificativa_admin'] = justificativa_admin.strip()

                                conn = sqlite3.connect("dados.db")
                                cursor = conn.cursor()
                                cursor.execute("""
                                    UPDATE insumos_pendentes
                                    SET status = ?, justificativa_admin = ?
                                    WHERE nome_item = ?
                                """, ("rejeitado", item["justificativa_admin"], item["nome_item"]))
                                conn.commit()
                                conn.close()

                                st.warning(f"Insumo '{item['nome_item']}' foi rejeitado.")
                                st.rerun()

                        # --- Botão de excluir para itens aprovados ou rejeitados ---
                        if perfil_logado == "adm_master" and item['status'] in ["aprovado", "rejeitado"]:
                            if st.button("🗑️ Excluir da visualização", key=f"excluir_{idx}"):
                                import sqlite3
                                conn = sqlite3.connect("dados.db")
                                cursor = conn.cursor()

                                cursor.execute("DELETE FROM insumos_pendentes WHERE nome_item = ?", (item["nome_item"],))
                                conn.commit()
                                conn.close()

                                st.success(f"Insumo '{item['nome_item']}' removido da visualização.")
                                st.rerun()

###########################################################Página Gerador de Premissas
    if pagina_selecionada == "Gerador de Premissas":
        st.title("Padrão Descritivo de Materiais e Serviços")

        regras = carregar_regras()

        if not regras:
            st.info("⚠️ Nenhuma premissa cadastrada ainda.")

        if regras:
            #Adicionado index=None para não pré-selecionar
            item = st.selectbox(
                "Escolha o item:", 
                sorted(list(regras.keys())),
                index=None,
                placeholder="Selecione o tipo de item..."
            )
            #Só roda se um item for selecionado
            if item:
                descricao = [item]
                ordem = regras[item].get("ordem", [])
                valores = regras[item].get("valores_comuns", {})

                for campo in ordem:
                    opcoes = valores.get(campo, []) 
                    if not opcoes:
                        continue
                    
                    escolha = st.selectbox(
                        f"{campo.upper()}:", 
                        sorted(opcoes),
                        index=None,
                        placeholder=f"Escolha o valor para {campo.lower()}..."
                    )
                    
                    #Adiciona a escolha à descrição apenas se o usuário selecionar algo
                    if escolha:
                        descricao.append(escolha.upper())
                
                resultado = " ".join(descricao)

                #Só tenta buscar se todos os parâmetros foram preenchidos
                if len(descricao) == len(ordem) + 1:  # +1 por causa do nome do item na frente
                    codigos_erp = carregar_codigos_erp()

                    if resultado:
                        col_cod, col_desc = st.columns([1, 5])

                        codigos_erp = carregar_codigos_erp()

                        with col_cod:
                            if resultado in codigos_erp:
                                st.text_input("Código ERP:", value=codigos_erp[resultado], disabled=True, label_visibility="visible")
                            else:
                                novo_codigo = st.text_input("Código ERP (registrar):")
                                st.warning("Não cadastrado")
                                if novo_codigo:
                                    salvar_codigo_erp(resultado, novo_codigo)
                                    st.success("Código ERP salvo com sucesso.")
                                    st.rerun()

                        with col_desc:
                            st.text_area("Descrição final:", resultado, height=100)
        else:
            st.info("Não há premissas cadastradas.")

###Banco de Dados abaixo do gerador
        st.divider()
        ###Banco de Dados abaixo do gerador
        parametros = carregar_regras()


        codigos_erp = {}
        codigos_erp = carregar_codigos_erp()
        #Gerando todas as combinações
        linhas = []

        for nome_item, dados in parametros.items():
            ordem = dados.get("ordem", [])
            valores = dados.get("valores_comuns", {})
            combinacoes = list(product(*[valores.get(p, [""]) for p in ordem]))

            for combinacao in combinacoes:
                descricao = f"{nome_item} " + " ".join(combinacao).strip()
                codigo = codigos_erp.get(descricao, "")
                linhas.append((codigo, descricao))
        #Converte para dataframe
        df = pd.DataFrame(linhas, columns=["Código ERP", "Descrição"])
        #Filtros
        col1, col2 = st.columns([2, 2])

        with col1:
            filtro_status = st.selectbox("Filtros:", ["Todos", "Com código registrado", "Sem código registrado"])

        with col2:
            termo_busca = st.text_input("Buscar na descrição:")
        #Aplicação dos filtros
        if filtro_status == "Com código registrado":
            df = df[df["Código ERP"].astype(bool)]
        elif filtro_status == "Sem código registrado":
            df = df[~df["Código ERP"].astype(bool)]

        if termo_busca:
            df = df[df["Descrição"].str.lower().str.contains(termo_busca.strip().lower())]

        #Exibição final
        st.markdown("### Banco de Dados")
        df = df.sort_values(by="Código ERP", ascending=False, na_position='first')
        st.dataframe(df.reset_index(drop=True), use_container_width=True)

###########################################################Página Cadastro/Editar Itens
    elif pagina_selecionada == "Cadastro/Edição de Itens":
        st.title("Cadastro e Edição de Itens")

        regras = carregar_regras()
        modo = st.radio("Escolha a ação:", ["Solicitar Cadastro de Item", "Editar Item Existente", "Excluir Item"])

        if modo == "Solicitar Cadastro de Item":
            st.subheader("Solicitar cadastro de novo item")

            if "etapa_parametros" not in st.session_state:
                st.session_state.etapa_parametros = False

            #Etapa 1: Nome e Ordem
            with st.form("form_dados_iniciais"):
                nome_item = st.text_input("Nome do novo item (ex: JOELHO)").strip().upper()
                ordem_str = st.text_input("Ordem dos parâmetros (ex: ângulo,finalidade,material)").strip()
                continuar = st.form_submit_button("Continuar")

                if continuar:
                    parametros_existentes = carregar_regras()
                    if not nome_item or not ordem_str:
                        st.error("Preencha o nome do item e a ordem dos parâmetros.")
                    elif nome_item in parametros_existentes:
                        st.warning("Este insumo já existe. Edite seus parâmetros na aba 'Editar Item'.")
                    else:
                        st.session_state.nome_item_temp = nome_item
                        st.session_state.ordem_temp = [o.strip() for o in ordem_str.split(",") if o.strip()]
                        st.session_state.etapa_parametros = True
                        st.rerun()

            #Etapa 2: Parâmetros e Valores
            if st.session_state.etapa_parametros:
                st.markdown("### Defina os valores comuns (opcional)")
                valores_comuns = {}
                for param in st.session_state.ordem_temp:
                    entrada = st.text_area(f"Valores para '{param.upper()}' (separar por vírgula)", key=f"valores_{param}")
                    valores_comuns[param] = [v.strip() for v in entrada.split(",") if v.strip()]

                if st.button("Cadastrar Item"):
                    # Verifica se pelo menos um valor foi preenchido
                    preenchido = any(valores for valores in valores_comuns.values() if valores)

                    if not preenchido:
                        st.error("Preencha ao menos um valor em qualquer parâmetro para cadastrar o item.")
                    else:
                        novo_insumo = {
                            "nome_item": st.session_state.nome_item_temp,
                            "ordem": st.session_state.ordem_temp,
                            "valores_comuns": valores_comuns,
                            "criado_por": st.session_state.get("email", ""),
                            "nome_usuario": st.session_state.get("username", ""),
                            "data": datetime.now().strftime("%Y-%m-%d %H:%M"),
                            "status": "pendente"
                        }

                        import sqlite3

                        conn = sqlite3.connect("dados.db")
                        cursor = conn.cursor()

                        nome_item = novo_insumo["nome_item"]
                        ordem = ",".join(novo_insumo["ordem"])
                        criado_por = novo_insumo["criado_por"]
                        nome_usuario = novo_insumo["nome_usuario"]
                        data = novo_insumo["data"]
                        status = novo_insumo["status"]

                        for parametro, valores in novo_insumo["valores_comuns"].items():
                            for valor in valores:
                                if valor:  # ignora campos vazios
                                    cursor.execute("""
                                        INSERT INTO insumos_pendentes (
                                            nome_item, ordem, parametro, valor,
                                            criado_por, nome_usuario, data,
                                            status, justificativa_admin, codigo_erp
                                        )
                                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                    """, (
                                        nome_item, ordem, parametro, valor,
                                        criado_por, nome_usuario, data,
                                        status, "", ""  # justificativa_admin, codigo_erp
                                    ))

                        conn.commit()
                        conn.close()

                        st.success(f"Insumo '{novo_insumo['nome_item']}' enviado para aprovação.")

                        # Resetar estado temporário
                        st.session_state.etapa_parametros = False
                        del st.session_state.nome_item_temp
                        del st.session_state.ordem_temp
                        st.rerun()



        elif modo == "Editar Item Existente":
            st.subheader("Editar item existente")
            if not regras:
                st.warning("Nenhum item cadastrado ainda.")
            else:
                item_selecionado = st.selectbox("Selecione o item para editar:", sorted(list(regras.keys())))
                if item_selecionado:
                    item_data = regras[item_selecionado]
                    st.write(f"Parâmetros na ordem: `{'`, `'.join(item_data['ordem'])}`")
                    param_selecionado = st.selectbox("Selecione o parâmetro para solicitar novo valor:", item_data["ordem"])
                    with st.form("solicitar_valor_form"):
                        novo_valor = st.text_input(f"Novo valor para '{param_selecionado.upper()}'").strip()
                        submitted = st.form_submit_button("Solicitar adição")
                        if submitted:
                            if novo_valor:
                                # Verifica se o valor já existe (case insensitive)
                                if novo_valor.upper() in [v.upper() for v in item_data["valores_comuns"].get(param_selecionado, [])]:
                                    st.warning("Este valor já existe nesse parâmetro.")
                                else:
                                    solicitacao = {
                                        "tipo": "adicao_valor",
                                        "item": item_selecionado,
                                        "parametro": param_selecionado,
                                        "valor": novo_valor,
                                        "usuario": st.session_state.get("username", "Anônimo"),
                                        "email": st.session_state.get("email", ""),
                                        "data": datetime.now().strftime("%Y-%m-%d %H:%M"),
                                        "status": "Pendente"
                                    }

                                    caminho = "solicitacoes_parametros.json"
                                    todas = []
                                    if os.path.exists(caminho):
                                        with open(caminho, "r", encoding="utf-8") as f:
                                            try:
                                                todas = json.load(f)
                                            except:
                                                todas = []
                                    todas.append(solicitacao)
                                    with open(caminho, "w", encoding="utf-8") as f:
                                        json.dump(todas, f, indent=4, ensure_ascii=False)

                                    st.success("Solicitação enviada para aprovação.")
                            else:
                                st.error("Digite um valor válido para solicitar.")


        elif modo == "Excluir Item":
            st.subheader("Solicitar exclusão de item")
            if not regras:
                st.warning("Nenhum item cadastrado.")
            else:
                item_para_excluir = st.selectbox("Selecione o item:", sorted(list(regras.keys())))
                justificativa = st.text_area("Justificativa para a exclusão do item selecionado:")

                if st.button("📩 Solicitar Exclusão"): 
                    if not justificativa.strip():
                        st.warning("A justificativa é obrigatória.")
                    else:
                        ARQ_SOLICITACOES = "solicitacoes_exclusao.json"
                        solicitacoes = []
                        if os.path.exists(ARQ_SOLICITACOES):
                            with open(ARQ_SOLICITACOES, "r", encoding="utf-8") as f:
                                try:
                                    solicitacoes = json.load(f)
                                except:
                                    pass

                        nova_solicitacao = {
                            "item": item_para_excluir,
                            "justificativa": justificativa.strip(),
                            "solicitado_por": st.session_state.get("username", ""),
                            "email": st.session_state.get("email", ""),
                            "data": datetime.now().strftime("%Y-%m-%d %H:%M"),
                            "status": "pendente"
                        }

                        solicitacoes.append(nova_solicitacao)
                        with open(ARQ_SOLICITACOES, "w", encoding="utf-8") as f:
                            json.dump(solicitacoes, f, indent=4, ensure_ascii=False)

                        st.success(f"Solicitação de exclusão do item '{item_para_excluir}' enviada com sucesso.")
                        
###########################################################Página Mensagens
    elif pagina_selecionada == "Mensagens":
        st.title("Chat do Sistema")
        st.markdown("Sessão experimental.") ########################################################### REMOVER ###########################################################
        ARQ_CHAT = "notificacoes.json"
        mensagens = []

        if os.path.exists(ARQ_CHAT):
            with open(ARQ_CHAT, "r", encoding="utf-8") as f:
                try:
                    mensagens = json.load(f)
                except:
                    st.error("Erro ao carregar mensagens.")

        #Envio
        st.markdown("### Nova Mensagem")
        with st.form("form_chat"):
            conteudo = st.text_area("Digite sua mensagem:")
            enviar = st.form_submit_button("Enviar")
            if enviar and conteudo.strip():
                nova = {
                    "de": st.session_state.get("username", "Anônimo"),
                    "mensagem": conteudo.strip(),
                    "data": datetime.now().strftime("%Y-%m-%d %H:%M")
                }
                mensagens.append(nova)
                with open(ARQ_CHAT, "w", encoding="utf-8") as f:
                    json.dump(mensagens, f, indent=4, ensure_ascii=False)
                st.success("Mensagem enviada.")
                st.rerun()

        #Mensagens
        st.markdown("---")
        st.markdown("### Mensagens")

        if not mensagens:
            st.info("Nenhuma mensagem no chat ainda.")
        else:
            for msg in reversed(mensagens[-50:]):  # mostra as 50 últimas
                st.markdown(f"""
                    <div style='border:1px solid #ddd; border-radius:10px; padding:10px; margin-bottom:10px; background-color:#f9f9f9'>
                        <strong>{msg['de']}</strong> <span style='float:right; font-size: 0.8em;'>{msg['data']}</span><br>
                        {msg['mensagem']}
                    </div>
                """, unsafe_allow_html=True)

###########################################################Página Usuários
    elif pagina_selecionada == "Usuários":
        usuarios = carregar_usuarios()
        email_logado = st.session_state.get("email", "")
        perfil_logado = usuarios.get(email_logado, {}).get("perfil", "usuario")

        st.title("Gerenciamento de Usuários")

        if perfil_logado != "adm_master":
            st.warning("Apenas usuários com perfil 'Adm Master' podem gerenciar perfis de outros usuários.")
        else:
            st.success("Você está logado como *Adm Master*. Pode gerenciar os demais usuários.")

            for email, dados in usuarios.items():
                nome = dados.get("nome", "—")
                perfil = dados.get("perfil", "usuario")

                col1, col2, col3 = st.columns([3, 2, 2])
                with col1:
                    st.markdown(f"**{nome}** (`{email}`)")
                with col2:
                    st.markdown(f"Perfil atual: `{perfil}`")
                with col3:
                    if perfil == "adm_master":
                        st.markdown("*Não é possível alterar ou excluir perfil de Adm Master*")
                    else:
                        with st.expander("⚙️ Ações", expanded=False):
                            opcoes_perfil = ["usuario", "adm", "excluir conta"]
                            novo_perfil = st.selectbox(
                                "Alterar tipo de conta ou excluir:",
                                options=opcoes_perfil,
                                index=opcoes_perfil.index(perfil) if perfil in opcoes_perfil else 0,
                                key=f"select_{email}"
                            )

                            if st.button("💾 Salvar alterações", key=f"salvar_{email}"):
                                if novo_perfil == "excluir conta":
                                    st.session_state[f"confirm_excluir_{email}"] = True
                                elif novo_perfil != perfil:
                                    usuarios[email]["perfil"] = novo_perfil
                                    salvar_usuarios(usuarios)
                                    st.success(f"Perfil de {nome} atualizado para '{novo_perfil}'.")
                                    st.rerun()

                    #Pedir confirmação da ação (exclusão)
                    if st.session_state.get(f"confirm_excluir_{email}", False):
                        st.warning(f"Tem certeza que deseja excluir o usuário **{nome}** ({email})?")
                        col_confirma, col_cancela = st.columns(2)
                        with col_confirma:
                            if st.button("✅ Confirmar", key=f"confirma_{email}"):
                                del usuarios[email]
                                salvar_usuarios(usuarios)
                                st.success(f"Usuário '{nome}' excluído com sucesso.")
                                st.session_state[f"confirm_excluir_{email}"] = False
                                st.rerun()
                        with col_cancela:
                            if st.button("❌ Cancelar", key=f"cancela_{email}"):
                                st.session_state[f"confirm_excluir_{email}"] = False

        # Seção: Solicitações de Exclusão (visível apenas para administradores) / Mudar localização desta seção.!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
        if perfil_logado in ["adm", "adm_master"]:
            st.markdown("---")
            st.markdown("### Solicitações de Exclusão de Itens")

            ARQ_SOLICITACOES = "solicitacoes_exclusao.json"
            solicitacoes = []
            if os.path.exists(ARQ_SOLICITACOES):
                with open(ARQ_SOLICITACOES, "r", encoding="utf-8") as f:
                    try:
                        solicitacoes = json.load(f)
                    except:
                        pass

            pendentes = [s for s in solicitacoes if s["status"] == "pendente"]

            if not pendentes:
                st.info("Nenhuma solicitação de exclusão pendente.")
            else:
                for idx, s in enumerate(pendentes):
                    with st.expander(f"🗑️ {s['item']} — solicitado por {s['solicitado_por']}"):
                        st.markdown(f"**Justificativa:** {s['justificativa']}")
                        st.markdown(f"**Data:** {s['data']}")
                        col_aprova, col_recusa = st.columns(2)

                        if col_aprova.button("✅ Aprovar Exclusão", key=f"aprov_ex_{idx}"):
                            import sqlite3
                            nome_item = s["item"]

                            conn = sqlite3.connect("dados.db")
                            cursor = conn.cursor()

                            # Verifica se o item existe
                            cursor.execute("SELECT id FROM itens_padrao WHERE nome_item = ?", (nome_item,))
                            resultado = cursor.fetchone()

                            if resultado:
                                item_id = resultado[0]

                                cursor.execute("SELECT ordem FROM itens_padrao WHERE id = ?", (item_id,))
                                ordem_str = cursor.fetchone()[0]
                                # Remove os valores relacionados
                                cursor.execute("DELETE FROM valores_comuns WHERE item_id = ?", (item_id,))
                                # Remove o próprio item
                                cursor.execute("DELETE FROM itens_padrao WHERE id = ?", (item_id,))

                                # Também apagar todos os códigos ERP que comecem com o nome do item
                                nome_item_upper = nome_item.strip().upper()
                                cursor.execute("""
                                    DELETE FROM codigos_erp
                                    WHERE descricao LIKE ?
                                """, (f"{nome_item_upper} %",))

                                # Remove código ERP correspondente (se existir)
                                # Montar descrição completa com base na ordem original
                                nome_item_upper = nome_item.strip().upper()
                                cursor.execute("""
                                    DELETE FROM codigos_erp
                                    WHERE descricao LIKE ?
                                """, (f"{nome_item_upper} %",))

                                conn.commit()
                                st.success(f"Item '{nome_item}' excluído do banco de dados.")
                            else:
                                st.warning(f"Item '{nome_item}' não encontrado no banco.")

                            conn.close()

                            # Remove a solicitação do JSON
                            solicitacoes = [sol for sol in solicitacoes if not (sol["item"] == nome_item and sol["status"] == "pendente")]
                            with open(ARQ_SOLICITACOES, "w", encoding="utf-8") as f:
                                json.dump(solicitacoes, f, indent=4, ensure_ascii=False)

                            st.rerun()


                        if col_recusa.button("❌ Recusar Exclusão", key=f"recus_ex_{idx}"):
                            solicitacoes = [sol for sol in solicitacoes if not (sol["item"] == s["item"] and sol["status"] == "pendente")]
                            with open(ARQ_SOLICITACOES, "w", encoding="utf-8") as f:
                                json.dump(solicitacoes, f, indent=4, ensure_ascii=False)
                            st.info("Solicitação recusada.")
                            st.rerun()

            # Seção: Solicitações de Adição de Valores (visível apenas para administradores)
            st.markdown("### Solicitações de Adição de Valores a Parâmetros")

            ARQ_SOLIC_VALORES = "solicitacoes_parametros.json"
            solicitacoes_valores = []
            if os.path.exists(ARQ_SOLIC_VALORES):
                with open(ARQ_SOLIC_VALORES, "r", encoding="utf-8") as f:
                    try:
                        solicitacoes_valores = json.load(f)
                    except:
                        pass

            pendentes_valores = [s for s in solicitacoes_valores if s["status"] == "Pendente"]

            if not pendentes_valores:
                st.info("Nenhuma solicitação de adição pendente.")
            else:
                for idx, s in enumerate(pendentes_valores):
                    with st.expander(f"➕ {s['valor']} → {s['parametro']} do item {s['item']} — solicitado por {s['usuario']}"):
                        st.markdown(f"**Item:** {s['item']}")
                        st.markdown(f"**Parâmetro:** {s['parametro']}")
                        st.markdown(f"**Valor solicitado:** `{s['valor']}`")
                        st.markdown(f"**Data:** {s['data']}")
                        col_aprova, col_recusa = st.columns(2)

                        if col_aprova.button("✅ Aprovar Valor", key=f"aprovar_valor_{idx}"):
                            import sqlite3

                            nome_item = s["item"]
                            parametro = s["parametro"]
                            valor = s["valor"]

                            conn = sqlite3.connect("dados.db")
                            cursor = conn.cursor()

                            # Localiza o item no banco
                            cursor.execute("SELECT id FROM itens_padrao WHERE nome_item = ?", (nome_item,))
                            resultado = cursor.fetchone()

                            if resultado:
                                item_id = resultado[0]

                                # Verifica se o valor já existe
                                cursor.execute("""
                                    SELECT COUNT(*) FROM valores_comuns 
                                    WHERE item_id = ? AND parametro = ? AND valor = ?
                                """, (item_id, parametro, valor))
                                ja_existe = cursor.fetchone()[0] > 0

                                if ja_existe:
                                    st.warning(f"O valor '{valor}' já está cadastrado no parâmetro '{parametro}'.")
                                else:
                                    cursor.execute("""
                                        INSERT INTO valores_comuns (item_id, parametro, valor) 
                                        VALUES (?, ?, ?)
                                    """, (item_id, parametro, valor))
                                    conn.commit()
                                    st.success(f"Valor '{valor}' adicionado ao parâmetro '{parametro}' do item '{nome_item}'.")
                            else:
                                st.error(f"O item '{nome_item}' não foi encontrado no banco de dados.")

                            conn.close()

                            # Remove a solicitação do JSON
                            solicitacoes_valores = [v for v in solicitacoes_valores if not (
                                v["item"] == nome_item and v["parametro"] == parametro and v["valor"] == valor and v["status"] == "Pendente")]
                            with open(ARQ_SOLIC_VALORES, "w", encoding="utf-8") as f:
                                json.dump(solicitacoes_valores, f, indent=4, ensure_ascii=False)

                            st.rerun()


###########################################################Página Suporte
    if pagina_selecionada == "Suporte":
        st.title("Suporte do Sistema")
        st.divider()
        st.markdown("**Entrar em contato por email:**")
        st.markdown(
            '[Contato Nelluana Ribas](mailto:nelluana.ribas@elco.com.br)',
            unsafe_allow_html=True
        )
        st.markdown(
            '[Contato Eric Rosa](mailto:nelluana.ribas@elco.com.br)',
            unsafe_allow_html=True
        )
        st.divider()
        st.markdown("**Documentações disponíveis:**")
        st.markdown(
            '[Manual do Sistema](link do documento)',
            unsafe_allow_html=True
        )
        st.markdown(
            '[Manual PDMS](https://elcoeng-my.sharepoint.com/:b:/g/personal/eric_rosa_elco_com_br/EYYs1UgcJJlIsPyaB1GwvFMB59wAFMH2GjFK-mguX7Z2Zg?e=qElMFj)',
            unsafe_allow_html=True
        )
        st.divider()
        st.markdown("**Versão do Sistema:**")
        st.text(Versao)

    if pagina_selecionada == "Terminar sessão":
        st.session_state['logged_in'] = False
        st.session_state['username'] = ""
        st.rerun()

###########################################################Lógica Principal de Roteamento
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

if st.session_state['logged_in']:
    pagina_principal()
else:
    pagina_login_cadastro()

###########################################################Estilo do projeto (CSS) fora o config.toml
st.markdown(
f"""
    <style>
        :root {{
            --button-bg-light: #FFD700;
            --primary-color-light: #2e2e2e;
        }}
        .stButton > button {{
            background-color: {"var(--button-bg-light)"}; 
            color: {"var(--primary-color-light)"}; /* Cor do texto do botão */
            border: none;
            border-radius: 8px;
            padding: 10px 20px;
        }}
        .stButton > button:hover {{
            background-color: {'#FFCC00'};
            color: var(--primary-color-light);
        }}
    </style>
""",
    unsafe_allow_html=True
)