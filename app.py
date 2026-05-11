import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np

# Configuração da página
st.set_page_config(page_title="Gestão Estratégica de Compras", layout="wide")

st.title("🚀 Painel de Inteligência em Suprimentos")
st.markdown("---")

def process_data(df):
    # Tratamento de dados e datas
    df['Data O.C.'] = pd.to_datetime(df['Data O.C.'])
    df['Ano'] = df['Data O.C.'].dt.year
    df['Mes'] = df['Data O.C.'].dt.month
    
    return df

def calcular_indicadores(df_filtrado):
    # Agrupamento por produto para análise de variação e Pareto
    df_sorted = df_filtrado.sort_values(['Cód. Produto', 'Data O.C.'])
    
    analise = df_sorted.groupby('Cód. Produto').agg({
        'Produto': 'first',
        'Vlr. Unitário': ['first', 'last'],
        'Vlr. Total': 'sum',
        'Comprador': 'first'
    })
    
    analise.columns = ['Produto', 'Preço_Inicial', 'Preço_Atual', 'Gasto_Total', 'Comprador']
    analise = analise.reset_index()
    
    # Cálculo de Variação
    analise['Variacao_Perc'] = (analise['Preço_Atual'] - analise['Preço_Inicial']) / analise['Preço_Inicial']
    analise['Variacao_Perc'] = analise['Variacao_Perc'].replace([np.inf, -np.inf], 0).fillna(0)

    def classificar(v):
        if v < 0: return "Redução de Preço"
        elif v == 0: return "Sem Alteração"
        elif v <= 0.10: return "Aumento até 10%"
        elif v <= 0.20: return "Aumento até 20%"
        elif v <= 0.30: return "Aumento até 30%"
        else: return "Aumento acima de 30%"
        
    analise['Categoria_Variacao'] = analise['Variacao_Perc'].apply(classificar)
    
    # Pareto (ABC)
    analise = analise.sort_values(by='Gasto_Total', ascending=False)
    analise['Gasto_Acumulado'] = analise['Gasto_Total'].cumsum()
    total = analise['Gasto_Total'].sum()
    analise['Perc_Acumulado'] = (analise['Gasto_Acumulado'] / total) * 100
    analise['Curva_ABC'] = analise['Perc_Acumulado'].apply(lambda x: 'A' if x <= 80 else ('B' if x <= 95 else 'C'))
    
    return analise, df_sorted

# --- Sidebar / Filtros ---
st.sidebar.header("Filtros de Análise")
uploaded_file = st.sidebar.file_uploader("Upload do Excel/CSV", type=["xlsx", "xls", "csv"])

if uploaded_file:
    try:
        if uploaded_file.name.endswith(('.xlsx', '.xls')):
            df_raw = pd.read_excel(uploaded_file, engine='openpyxl')
        else:
            df_raw = pd.read_csv(uploaded_file)
        
        df_raw = process_data(df_raw)
        
        # Filtros Dinâmicos
        compradores = st.sidebar.multiselect("Comprador", options=df_raw['Comprador'].unique(), default=df_raw['Comprador'].unique())
        anos = st.sidebar.multiselect("Ano", options=sorted(df_raw['Ano'].unique()), default=sorted(df_raw['Ano'].unique()))
        meses = st.sidebar.multiselect("Mês", options=list(range(1, 13)), default=list(range(1, 13)))
        
        # Aplicar Filtros
        df_f = df_raw[
            (df_raw['Comprador'].isin(compradores)) & 
            (df_raw['Ano'].isin(anos)) & 
            (df_raw['Mes'].isin(meses))
        ]
        
        if not df_f.empty:
            df_analise, df_timeline = calcular_indicadores(df_f)

            # --- Painel de Pontos Cegos (Visão Estratégica) ---
            st.subheader("⚠️ Painel de Alerta: Pontos Cegos")
            c1, c2 = st.columns(2)
            
            with c1:
                # Alerta de Itens Críticos: Curva A com aumento > 10%
                criticos = df_analise[(df_analise['Curva_ABC'] == 'A') & (df_analise['Variacao_Perc'] > 0.10)]
                st.error(f"**Itens Curva A com Reajuste > 10%:** {len(criticos)}")
                if not criticos.empty:
                    st.caption("Estes itens estão corroendo sua margem principal.")
            
            with c2:
                # Oportunidade: Reduções na Curva A
                oportunidades = df_analise[(df_analise['Curva_ABC'] == 'A') & (df_analise['Variacao_Perc'] < 0)]
                st.success(f"**Oportunidades Replicáveis (Reduções em Curva A):** {len(oportunidades)}")

            # --- Gráficos ---
            col_a, col_b = st.columns(2)
            
            with col_a:
                st.markdown("### Distribuição de Reajustes")
                contagem = df_analise['Categoria_Variacao'].value_counts().reindex([
                    "Redução de Preço", "Sem Alteração", "Aumento até 10%", "Aumento até 20%", "Aumento até 30%", "Aumento acima de 30%"
                ]).fillna(0).reset_index()
                fig_bar = px.bar(contagem, x='index', y='Categoria_Variacao', color='index', 
                                 labels={'index': 'Categoria', 'Categoria_Variacao': 'Qtd Itens'})
                st.plotly_chart(fig_bar, use_container_width=True)
                
            with col_b:
                st.markdown("### Pareto: Concentração de Gasto")
                fig_pareto = go.Figure()
                fig_pareto.add_trace(go.Bar(x=df_analise['Produto'][:15], y=df_analise['Gasto_Total'][:15], name='Gasto (R$)'))
                fig_pareto.add_trace(go.Scatter(x=df_analise['Produto'][:15], y=df_analise['Perc_Acumulado'][:15], name='% Acumulado', yaxis='y2'))
                fig_pareto.update_layout(yaxis2=dict(overlaying='y', side='right', range=[0, 100]), showlegend=False)
                st.plotly_chart(fig_pareto, use_container_width=True)

            # --- Tabela Final ---
            st.subheader("🔍 Detalhamento Estratégico (Pareto x Reajuste)")
            
            def colorir_linhas(row):
                if row['Curva_ABC'] == 'A' and row['Variacao_Perc'] > 0.10:
                    return ['background-color: #ffcccc'] * len(row) # Vermelho: Perigo
                if row['Variacao_Perc'] < 0:
                    return ['background-color: #ccffcc'] * len(row) # Verde: Sucesso
                return [''] * len(row)

            st.dataframe(df_analise[['Curva_ABC', 'Produto', 'Preço_Inicial', 'Preço_Atual', 'Variacao_Perc', 'Gasto_Total', 'Comprador']]
                         .style.format({'Variacao_Perc': '{:.2%}', 'Gasto_Total': 'R$ {:,.2f}', 'Preço_Inicial': 'R$ {:,.2f}', 'Preço_Atual': 'R$ {:,.2f}'})
                         .apply(colorir_linhas, axis=1))

        else:
            st.warning("Nenhum dado encontrado para os filtros selecionados.")
            
    except Exception as e:
        st.error(f"Erro ao processar o arquivo: {e}")
else:
    st.info("Faça o upload do arquivo Excel para iniciar.")
