import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np

# Configuração da página
st.set_page_config(page_title="Analytics de Compras - Inteligência de Suprimentos", layout="wide")

st.title("📊 Dashboard de Análise de Compras e Preços")
st.markdown("---")

# Funções de Processamento
def process_data(df):
    # Tratamento de datas - Garante que o formato seja reconhecido
    df['Data O.C.'] = pd.to_datetime(df['Data O.C.'])
    
    # 1. Análise de Variação de Preços
    # Agrupamos por produto para pegar o primeiro e último preço cronológico
    df_sorted = df.sort_values(['Cód. Produto', 'Data O.C.'])
    
    analise_precos = df_sorted.groupby('Cód. Produto').agg({
        'Produto': 'first',
        'Vlr. Unitário': ['first', 'last'],
        'Vlr. Total': 'sum',
        'Data O.C.': ['min', 'max']
    })
    
    analise_precos.columns = ['Produto', 'Preço_Inicial', 'Preço_Atual', 'Gasto_Total', 'Data_Ini', 'Data_Fim']
    analise_precos = analise_precos.reset_index()
    
    # Cálculo da Variação Percentual
    analise_precos['Variacao_Perc'] = (analise_precos['Preço_Atual'] - analise_precos['Preço_Inicial']) / analise_precos['Preço_Inicial']
    
    def classificar_reajuste(v):
        if v < 0: return "Redução"
        elif v == 0: return "Sem Alteração"
        elif v <= 0.10: return "Até 10%"
        elif v <= 0.20: return "Até 20%"
        elif v <= 0.30: return "Até 30%"
        else: return "Acima de 30%"
        
    analise_precos['Categoria_Reajuste'] = analise_precos['Variacao_Perc'].apply(classificar_reajuste)
    
    # 2. Análise de Pareto (Curva ABC baseada no Gasto Total)
    analise_precos = analise_precos.sort_values(by='Gasto_Total', ascending=False)
    analise_precos['Gasto_Acumulado'] = analise_precos['Gasto_Total'].cumsum()
    total_gasto = analise_precos['Gasto_Total'].sum()
    analise_precos['Perc_Acumulado'] = (analise_precos['Gasto_Acumulado'] / total_gasto) * 100
    
    def curva_abc(perc):
        if perc <= 80: return 'A'
        elif perc <= 95: return 'B'
        else: return 'C'
        
    analise_precos['Curva_ABC'] = analise_precos['Perc_Acumulado'].apply(curva_abc)
    
    return analise_precos, df_sorted

# Upload do Arquivo - Atualizado para aceitar Excel
uploaded_file = st.file_uploader("Arraste o arquivo EXCEL ou CSV de compras aqui", type=["xlsx", "xls", "csv"])

if uploaded_file is not None:
    try:
        # Lógica para identificar se é Excel ou CSV
        if uploaded_file.name.endswith(('.xlsx', '.xls')):
            df_raw = pd.read_excel(uploaded_file, engine='openpyxl')
        else:
            df_raw = pd.read_csv(uploaded_file)
            
        df_analise, df_timeline = process_data(df_raw)

        # --- KPI's Principais ---
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total de Itens", len(df_analise))
        with col2:
            reajustes_criticos = len(df_analise[df_analise['Variacao_Perc'] > 0.10])
            st.metric("Reajustes > 10%", reajustes_criticos, delta_color="inverse")
        with col3:
            reducoes = len(df_analise[df_analise['Variacao_Perc'] < 0])
            st.metric("Itens com Redução", reducoes)
        with col4:
            gasto_total_periodo = df_analise['Gasto_Total'].sum()
            st.metric("Gasto Total (R$)", f"{gasto_total_periodo:,.2f}")

        # --- GRÁFICO 1: COMPORTAMENTO NO TEMPO (ÍNDICE) ---
        st.subheader("📈 Evolução dos Preços (Índice Base 100)")
        df_timeline['Preco_Indexado'] = df_timeline.groupby('Cód. Produto')['Vlr. Unitário'].transform(lambda x: (x / x.iloc[0]) * 100 if x.iloc[0] != 0 else 100)
        df_tendencia = df_timeline.groupby('Data O.C.')['Preco_Indexado'].mean().reset_index()
        
        fig_line = px.line(df_tendencia, x='Data O.C.', y='Preco_Indexado', 
                          title="Tendência de Preço Média (Base 100)",
                          labels={'Preco_Indexado': 'Índice de Preço'})
        st.plotly_chart(fig_line, use_container_width=True)

        # --- GRÁFICO 2: DISTRIBUIÇÃO DE REAJUSTES ---
        st.subheader("📊 Distribuição de Reajustes por Categoria")
        contagem_cat = df_analise['Categoria_Reajuste'].value_counts().reindex([
            "Redução", "Sem Alteração", "Até 10%", "Até 20%", "Até 30%", "Acima de 30%"
        ]).fillna(0).reset_index()
        
        fig_bar = px.bar(contagem_cat, x='index', y='Categoria_Reajuste', 
                        color='index', title="Quantidade de Itens por Faixa de Reajuste",
                        labels={'index': 'Categoria', 'Categoria_Reajuste': 'Qtd Itens'})
        st.plotly_chart(fig_bar, use_container_width=True)

        # --- GRÁFICO 3: PARETO (CURVA ABC) ---
        st.subheader("🎯 Análise de Pareto (Curva ABC de Gasto)")
        fig_pareto = go.Figure()
        fig_pareto.add_trace(go.Bar(
            x=df_analise['Produto'][:30],
            y=df_analise['Gasto_Total'][:30],
            name='Gasto Total por Item',
            marker_color='blue'
        ))
        fig_pareto.add_trace(go.Scatter(
            x=df_analise['Produto'][:30],
            y=df_analise['Perc_Acumulado'][:30],
            name='% Acumulado',
            yaxis='y2',
            line=dict(color='red', width=3)
        ))
        fig_pareto.update_layout(
            title="Top 30 Itens por Gasto (Impacto Financeiro)",
            yaxis=dict(title='Gasto Total (R$)'),
            yaxis2=dict(title='% Acumulado', overlaying='y', side='right', range=[0, 100]),
            xaxis=dict(tickangle=-45)
        )
        st.plotly_chart(fig_pareto, use_container_width=True)

        # --- TABELA DETALHADA ---
        st.subheader("🔍 Detalhamento por Item (Foco na Curva A)")
        colunas_finais = ['Curva_ABC', 'Cód. Produto', 'Produto', 'Preço_Inicial', 'Preço_Atual', 'Variacao_Perc', 'Categoria_Reajuste', 'Gasto_Total']
        
        # Estilização para destacar riscos na Curva A
        def highlight_risks(row):
            color = ''
            if row['Curva_ABC'] == 'A' and row['Variacao_Perc'] > 0.10:
                color = 'background-color: #ffcccc' # Vermelho claro para Curva A com aumento > 10%
            return [color] * len(row)

        st.dataframe(df_analise[colunas_finais].style.format({
            'Variacao_Perc': '{:.2%}',
            'Gasto_Total': 'R$ {:,.2f}',
            'Preço_Inicial': 'R$ {:,.2f}',
            'Preço_Atual': 'R$ {:,.2f}'
        }).apply(highlight_risks, axis=1))

    except Exception as e:
        st.error(f"Erro ao processar o arquivo: {e}")
        st.info("Certifique-se de que as colunas 'Cód. Produto', 'Vlr. Unitário', 'Vlr. Total' e 'Data O.C.' existem no seu Excel.")

else:
    st.info("Aguardando upload do arquivo Excel para processar os indicadores...")
