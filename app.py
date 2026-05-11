import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np

# Configuração da página
st.set_page_config(page_title="Inteligência de Compras Kowalski", layout="wide")

st.title("🛡️ Central de Comando de Suprimentos")
st.markdown("---")

def process_data(df):
    # Padronização de colunas e datas
    df['Data O.C.'] = pd.to_datetime(df['Data O.C.'])
    df['Ano'] = df['Data O.C.'].dt.year
    df['Mes'] = df['Data O.C.'].dt.month
    df['Comprador'] = df['Comprador'].fillna('Não Identificado')
    return df

def calcular_analytics(df_filtrado):
    # Agrupamento para Variação e Pareto
    df_sorted = df_filtrado.sort_values(['Cód. Produto', 'Data O.C.'])
    
    # Pegamos o primeiro preço, o último preço e o gasto total acumulado no período filtrado
    analise = df_sorted.groupby('Cód. Produto').agg({
        'Produto': 'first',
        'Vlr. Unitário': ['first', 'last', 'mean', 'min', 'max'],
        'Vlr. Total': 'sum',
        'Quantidade': 'sum',
        'Comprador': 'first'
    })
    
    analise.columns = ['Produto', 'Preço_Inicial', 'Preço_Atual', 'Preço_Medio', 'Preço_Min', 'Preço_Max', 'Gasto_Total', 'Quantidade_Total', 'Comprador_Princ']
    analise = analise.reset_index()
    
    # Cálculo da Variação Real
    analise['Variacao_Abs'] = analise['Preço_Atual'] - analise['Preço_Inicial']
    analise['Variacao_Perc'] = (analise['Preço_Atual'] - analise['Preço_Inicial']) / analise['Preço_Inicial']
    analise['Variacao_Perc'] = analise['Variacao_Perc'].replace([np.inf, -np.inf], 0).fillna(0)

    # Categorização solicitada
    def classificar(v):
        if v < 0: return "1. Redução"
        elif v == 0: return "2. Sem Alteração"
        elif v <= 0.10: return "3. Até 10%"
        elif v <= 0.20: return "4. Até 20%"
        elif v <= 0.30: return "5. Até 30%"
        else: return "6. Acima de 30%"
        
    analise['Categoria_Preco'] = analise['Variacao_Perc'].apply(classificar)
    
    # Pareto (ABC) - Baseado no impacto financeiro (Gasto Total)
    analise = analise.sort_values(by='Gasto_Total', ascending=False)
    analise['Gasto_Acumulado'] = analise['Gasto_Total'].cumsum()
    total = analise['Gasto_Total'].sum()
    analise['Perc_Acumulado'] = (analise['Gasto_Acumulado'] / total) * 100
    analise['Curva_ABC'] = analise['Perc_Acumulado'].apply(lambda x: 'A' if x <= 80 else ('B' if x <= 95 else 'C'))
    
    return analise, df_sorted

# --- Sidebar ---
st.sidebar.header("⚙️ Configurações de Filtro")
file = st.sidebar.file_uploader("Arquivo Excel/CSV", type=["xlsx", "xls", "csv"])

if file:
    try:
        if file.name.endswith(('.xlsx', '.xls')):
            df_raw = pd.read_excel(file, engine='openpyxl')
        else:
            df_raw = pd.read_csv(file)
            
        df_raw = process_data(df_raw)
        
        # Filtros laterais
        list_compradores = sorted(df_raw['Comprador'].unique())
        sel_compradores = st.sidebar.multiselect("Comprador", list_compradores, default=list_compradores)
        
        list_anos = sorted(df_raw['Ano'].unique())
        sel_anos = st.sidebar.multiselect("Ano", list_anos, default=list_anos)
        
        list_pareto = ['A', 'B', 'C']
        sel_pareto = st.sidebar.multiselect("Curva Pareto (ABC)", list_pareto, default=list_pareto)
        
        # Execução da filtragem base
        df_f = df_raw[(df_raw['Comprador'].isin(sel_compradores)) & (df_raw['Ano'].isin(sel_anos))]
        
        if not df_f.empty:
            df_resumo, df_hist = calcular_analytics(df_f)
            
            # Criando as Abas
            tab1, tab2 = st.tabs(["📊 Visão Executiva Estratégica", "🔍 Detalhado por Item"])

            # --- ABA 1: TUDO O QUE ESTAVA ANTES ---
            with tab1:
                # Filtro de Pareto aplicado apenas para os visuais desta aba
                df_resumo_tab1 = df_resumo[df_resumo['Curva_ABC'].isin(sel_pareto)]

                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Gasto Filtrado", f"R$ {df_resumo_tab1['Gasto_Total'].sum():,.2f}")
                col2.metric("Itens Críticos (>30%)", len(df_resumo_tab1[df_resumo_tab1['Categoria_Preco'] == "6. Acima de 30%"]))
                col3.metric("Itens Curva A", len(df_resumo_tab1[df_resumo_tab1['Curva_ABC'] == 'A']))
                col4.metric("Reduções Obtidas", len(df_resumo_tab1[df_resumo_tab1['Categoria_Preco'] == "1. Redução"]))

                st.markdown("---")
                
                c_left, c_right = st.columns(2)
                with c_left:
                    st.subheader("📊 Distribuição por Categoria de Preço")
                    dist_data = df_resumo_tab1['Categoria_Preco'].value_counts().reset_index()
                    dist_data.columns = ['Categoria', 'Quantidade']
                    dist_data = dist_data.sort_values('Categoria')
                    fig_bar = px.bar(dist_data, x='Categoria', y='Quantidade', color='Categoria',
                                     text_auto=True, color_discrete_sequence=px.colors.qualitative.Safe)
                    st.plotly_chart(fig_bar, use_container_width=True)

                with c_right:
                    st.subheader("🎯 Pareto: Top 15 Itens por Impacto")
                    fig_pareto = go.Figure()
                    fig_pareto.add_trace(go.Bar(x=df_resumo_tab1['Produto'][:15], y=df_resumo_tab1['Gasto_Total'][:15], name='Gasto R$'))
                    fig_pareto.add_trace(go.Scatter(x=df_resumo_tab1['Produto'][:15], y=df_resumo_tab1['Perc_Acumulado'][:15], 
                                                    name='% Acumulado', yaxis='y2', line=dict(color='red')))
                    fig_pareto.update_layout(yaxis2=dict(overlaying='y', side='right', range=[0, 100]), 
                                             xaxis=dict(tickangle=-45), showlegend=False, margin=dict(t=20))
                    st.plotly_chart(fig_pareto, use_container_width=True)

                st.subheader("🧠 Pontos Cegos e Oportunidades")
                risco_maximo = df_resumo_tab1[(df_resumo_tab1['Curva_ABC'] == 'A') & (df_resumo_tab1['Variacao_Perc'] > 0.10)]
                if not risco_maximo.empty:
                    st.error(f"🚨 **ALERTA CRÍTICO:** Identificamos {len(risco_maximo)} itens da **Curva A** com reajuste acima de 10%. Isso está drenando seu caixa diretamente.")
                    with st.expander("Ver itens de Risco Máximo"):
                        st.table(risco_maximo[['Produto', 'Preço_Inicial', 'Preço_Atual', 'Variacao_Perc', 'Gasto_Total']])
                
                sucessos = df_resumo_tab1[(df_resumo_tab1['Curva_ABC'] == 'A') & (df_resumo_tab1['Variacao_Perc'] < 0)]
                if not sucessos.empty:
                    st.success(f"✅ **BENCHMARK:** Você conseguiu redução em {len(sucessos)} itens estratégicos (Curva A). Verifique o que foi feito aqui para replicar nos outros itens.")

                st.subheader("📑 Tabela Analítica Detalhada")
                def styler(row):
                    if row['Curva_ABC'] == 'A' and row['Variacao_Perc'] > 0.10:
                        return ['background-color: #f8d7da'] * len(row)
                    if row['Curva_ABC'] == 'A' and row['Variacao_Perc'] < 0:
                        return ['background-color: #d4edda'] * len(row)
                    return [''] * len(row)

                st.dataframe(df_resumo_tab1[['Curva_ABC', 'Cód. Produto', 'Produto', 'Preço_Inicial', 'Preço_Atual', 'Variacao_Perc', 'Categoria_Preco', 'Gasto_Total', 'Comprador_Princ']]
                             .style.format({'Variacao_Perc': '{:.2%}', 'Gasto_Total': 'R$ {:,.2f}', 'Preço_Inicial': 'R$ {:,.2f}', 'Preço_Atual': 'R$ {:,.2f}'})
                             .apply(styler, axis=1), use_container_width=True)

            # --- ABA 2: MELHORIAS POR ITEM ---
            with tab2:
                st.subheader("🔍 Lupa sobre o Produto")
                
                # Filtro exclusivo de busca de item
                search_item = st.selectbox("Selecione ou digite o nome do produto:", 
                                           options=sorted(df_resumo['Produto'].unique()))
                
                # Dados isolados do item
                item_data = df_hist[df_hist['Produto'] == search_item].sort_values('Data O.C.')
                item_stats = df_resumo[df_resumo['Produto'] == search_item].iloc[0]

                # KPIs do Item
                ik1, ik2, ik3, ik4 = st.columns(4)
                ik1.metric("Preço Atual", f"R$ {item_stats['Preço_Atual']:,.2f}", 
                           delta=f"{item_stats['Variacao_Perc']:.2%}", delta_color="inverse")
                ik2.metric("Curva Pareto", f"Classe {item_stats['Curva_ABC']}")
                ik3.metric("Preço Médio Período", f"R$ {item_stats['Preço_Medio']:,.2f}")
                ik4.metric("Qtd Total Comprada", f"{int(item_stats['Quantidade_Total'])}")

                # Gráficos de Evolução
                g1, g2 = st.columns([2, 1])
                
                with g1:
                    st.markdown("**Evolução Histórica do Valor Unitário**")
                    fig_evol = px.line(item_data, x='Data O.C.', y='Vlr. Unitário', markers=True,
                                       hover_data=['Fornecedor', 'Quantidade', 'Vlr. Total'],
                                       labels={'Vlr. Unitário': 'Valor Unitário (R$)'})
                    fig_evol.update_layout(hovermode="x unified")
                    st.plotly_chart(fig_evol, use_container_width=True)
                
                with g2:
                    st.markdown("**Dispersão: Volume vs Preço**")
                    # Ajuda a ver se o preço cai quando a quantidade aumenta (ganho de escala)
                    fig_scatter = px.scatter(item_data, x='Quantidade', y='Vlr. Unitário', 
                                             color='Fornecedor', size='Vlr. Total',
                                             title="Escalabilidade e Fornecedores")
                    st.plotly_chart(fig_scatter, use_container_width=True)

                st.markdown("**Histórico de Compras Detalhado**")
                st.dataframe(item_data[['Data O.C.', 'Fornecedor', 'Quantidade', 'Und.', 'Vlr. Unitário', 'Vlr. Total', 'Comprador']]
                             .sort_values('Data O.C.', ascending=False), use_container_width=True)

    except Exception as e:
        st.error(f"Erro fatal: {e}")
else:
    st.info("Insira o arquivo para gerar a inteligência de compras.")
