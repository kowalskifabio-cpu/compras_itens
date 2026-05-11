import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np

# Configuração da página
st.set_page_config(page_title="Intelligence Compras Pro", layout="wide")

st.title("🚀 Inteligência Estratégica de Suprimentos")
st.markdown("---")

# --- FUNÇÕES DE MOTOR DE DADOS ---
def load_and_clean(file):
    if file.name.endswith(('.xlsx', '.xls')):
        df = pd.read_excel(file, engine='openpyxl')
    else:
        df = pd.read_csv(file)
    
    # Padronização de Colunas Críticas
    df['Data O.C.'] = pd.to_datetime(df['Data O.C.'])
    df['Ano'] = df['Data O.C.'].dt.year
    df['Mes'] = df['Data O.C.'].dt.month
    df['Comprador'] = df['Comprador'].fillna('N/I')
    return df

def get_analytics(df):
    # Agrupamento para Variação e Pareto
    df_sorted = df.sort_values(['Cód. Produto', 'Data O.C.'])
    
    analise = df_sorted.groupby('Cód. Produto').agg({
        'Produto': 'first',
        'Vlr. Unitário': ['first', 'last', 'mean', 'min', 'max'],
        'Vlr. Total': 'sum',
        'Quantidade': 'sum',
        'Comprador': 'first'
    })
    
    analise.columns = ['Produto', 'P_Inicial', 'P_Atual', 'P_Medio', 'P_Min', 'P_Max', 'Gasto_Total', 'Qtd_Total', 'Comprador']
    analise = analise.reset_index()
    
    # Variação e Pareto
    analise['Variacao_Perc'] = (analise['P_Atual'] - analise['P_Inicial']) / analise['P_Inicial']
    analise['Variacao_Perc'] = analise['Variacao_Perc'].replace([np.inf, -np.inf], 0).fillna(0)
    
    analise = analise.sort_values(by='Gasto_Total', ascending=False)
    analise['Perc_Acumulado'] = (analise['Gasto_Total'].cumsum() / analise['Gasto_Total'].sum()) * 100
    analise['Curva_ABC'] = analise['Perc_Acumulado'].apply(lambda x: 'A' if x <= 80 else ('B' if x <= 95 else 'C'))
    
    return analise, df_sorted

# --- SIDEBAR (FILTROS GLOBAIS) ---
st.sidebar.header("📂 Dados e Filtros")
uploaded_file = st.sidebar.file_uploader("Upload do arquivo", type=["xlsx", "xls", "csv"])

if uploaded_file:
    df_raw = load_and_clean(uploaded_file)
    
    # Filtros laterais que afetam o dashboard todo
    compradores = st.sidebar.multiselect("Filtrar Comprador", options=sorted(df_raw['Comprador'].unique()), default=df_raw['Comprador'].unique())
    anos = st.sidebar.multiselect("Anos", options=sorted(df_raw['Ano'].unique()), default=df_raw['Ano'].unique())
    
    df_f = df_raw[(df_raw['Comprador'].isin(compradores)) & (df_raw['Ano'].isin(anos))]
    df_resumo, df_hist = get_analytics(df_f)

    # --- CRIAÇÃO DAS ABAS ---
    aba_executiva, aba_item = st.tabs(["📊 Visão Executiva & Pareto", "🔍 Análise Detalhada por Item"])

    # --- ABA 1: VISÃO EXECUTIVA ---
    with aba_executiva:
        st.subheader("Painel de Controle de Reajustes")
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Gasto Total", f"R$ {df_resumo['Gasto_Total'].sum():,.2f}")
        c2.metric("Itens Críticos (Curva A + Aumento)", len(df_resumo[(df_resumo['Curva_ABC'] == 'A') & (df_resumo['Variacao_Perc'] > 0.05)]))
        c3.metric("Oportunidades (Reduções A)", len(df_resumo[(df_resumo['Curva_ABC'] == 'A') & (df_resumo['Variacao_Perc'] < 0)]))

        col_left, col_right = st.columns(2)
        
        with col_left:
            # Correção técnica do erro de 'index' no Plotly
            dist_data = df_resumo['Curva_ABC'].value_counts().reset_index()
            dist_data.columns = ['Curva', 'Qtd']
            fig_pie = px.pie(dist_data, values='Qtd', names='Curva', title="Distribuição Curva ABC (Itens)", hole=0.4)
            st.plotly_chart(fig_pie, use_container_width=True)

        with col_right:
            pareto_data = df_resumo.head(15)
            fig_pareto = go.Figure()
            fig_pareto.add_trace(go.Bar(x=pareto_data['Produto'], y=pareto_data['Gasto_Total'], name="Gasto"))
            fig_pareto.add_trace(go.Scatter(x=pareto_data['Produto'], y=pareto_data['Perc_Acumulado'], name="% Acumulado", yaxis="y2"))
            fig_pareto.update_layout(title="Top 15 Impacto Financeiro", yaxis2=dict(overlaying='y', side='right', range=[0,105]))
            st.plotly_chart(fig_pareto, use_container_width=True)

    # --- ABA 2: ANÁLISE POR ITEM (Diferencial) ---
    with aba_item:
        st.subheader("Exploração Individual de Itens")
        
        # Filtro de busca por produto ou código
        item_selecionado = st.selectbox("Selecione o Item para Analisar", options=df_resumo['Produto'].unique())
        
        # Dados específicos do item
        dados_item = df_hist[df_hist['Produto'] == item_selecionado].sort_values('Data O.C.')
        metrics_item = df_resumo[df_resumo['Produto'] == item_selecionado].iloc[0]

        # Painel de métricas do item selecionado
        mi1, mi2, mi3, mi4 = st.columns(4)
        mi1.metric("Preço Atual", f"R$ {metrics_item['P_Atual']:,.2f}", delta=f"{metrics_item['Variacao_Perc']:.2%}", delta_color="inverse")
        mi2.metric("Variação no Período", f"{metrics_item['Variacao_Perc']:.2%}")
        mi3.metric("Gasto Acumulado", f"R$ {metrics_item['Gasto_Total']:,.2f}")
        mi4.metric("Classificação", f"Curva {metrics_item['Curva_ABC']}")

        st.markdown("---")
        
        gi1, gi2 = st.columns([2, 1])
        
        with gi1:
            st.markdown("**📈 Evolução do Preço Unitário**")
            fig_evol = px.line(dados_item, x='Data O.C.', y='Vlr. Unitário', markers=True,
                               title=f"Histórico de Preços: {item_selecionado}",
                               labels={'Vlr. Unitário': 'R$ Unitário'})
            st.plotly_chart(fig_evol, use_container_width=True)
            
        with gi2:
            st.markdown("**💰 Comportamento de Compra**")
            # Gráfico de bolhas: Data vs Quantidade com tamanho do ponto sendo o Valor Total
            fig_bubble = px.scatter(dados_item, x='Data O.C.', y='Quantidade', size='Vlr. Total', color='Vlr. Unitário',
                                    title="Volume vs Preço Unitário",
                                    hover_data=['Fornecedor'])
            st.plotly_chart(fig_bubble, use_container_width=True)

        st.markdown("**📑 Histórico de Fornecedores para este Item**")
        st.dataframe(dados_item[['Data O.C.', 'Fornecedor', 'Quantidade', 'Vlr. Unitário', 'Vlr. Total', 'Comprador']].sort_values('Data O.C.', ascending=False), use_container_width=True)

else:
    st.info("Aguardando upload do arquivo para gerar inteligência...")
