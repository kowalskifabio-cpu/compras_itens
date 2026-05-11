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
        'Vlr. Unitário': ['first', 'last'],
        'Vlr. Total': 'sum',
        'Comprador': 'first'
    })
    
    analise.columns = ['Produto', 'Preço_Inicial', 'Preço_Atual', 'Gasto_Total', 'Comprador_Princ']
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
        # Carregamento resiliente
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
        
        # Execução da filtragem
        df_f = df_raw[(df_raw['Comprador'].isin(sel_compradores)) & (df_raw['Ano'].isin(sel_anos))]
        
        if not df_f.empty:
            df_resumo, df_hist = calcular_analytics(df_f)
            # Filtro de Pareto aplicado após o cálculo
            df_resumo = df_resumo[df_resumo['Curva_ABC'].isin(sel_pareto)]

            # --- DASHBOARD - VISÃO ESTRATÉGICA ---
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Gasto Filtrado", f"R$ {df_resumo['Gasto_Total'].sum():,.2f}")
            col2.metric("Itens Críticos (>30%)", len(df_resumo[df_resumo['Categoria_Preco'] == "6. Acima de 30%"]))
            col3.metric("Itens Curva A", len(df_resumo[df_resumo['Curva_ABC'] == 'A']))
            col4.metric("Reduções Obtidas", len(df_resumo[df_resumo['Categoria_Preco'] == "1. Redução"]))

            st.markdown("---")
            
            # Gráficos em colunas
            c_left, c_right = st.columns(2)
            
            with c_left:
                st.subheader("📊 Distribuição por Categoria de Preço")
                # Correção do erro de 'index' - reset_index com nome explícito
                dist_data = df_resumo['Categoria_Preco'].value_counts().reset_index()
                dist_data.columns = ['Categoria', 'Quantidade']
                dist_data = dist_data.sort_values('Categoria')
                
                fig_bar = px.bar(dist_data, x='Categoria', y='Quantidade', color='Categoria',
                                 text_auto=True, color_discrete_sequence=px.colors.qualitative.Safe)
                st.plotly_chart(fig_bar, use_container_width=True)

            with c_right:
                st.subheader("🎯 Pareto: Top 15 Itens por Impacto")
                fig_pareto = go.Figure()
                fig_pareto.add_trace(go.Bar(x=df_resumo['Produto'][:15], y=df_resumo['Gasto_Total'][:15], name='Gasto R$'))
                fig_pareto.add_trace(go.Scatter(x=df_resumo['Produto'][:15], y=df_resumo['Perc_Acumulado'][:15], 
                                                name='% Acumulado', yaxis='y2', line=dict(color='red')))
                fig_pareto.update_layout(yaxis2=dict(overlaying='y', side='right', range=[0, 100]), 
                                         xaxis=dict(tickangle=-45), showlegend=False, margin=dict(t=20))
                st.plotly_chart(fig_pareto, use_container_width=True)

            # --- PAINEL DE INSIGHTS (O CORAÇÃO DA ANÁLISE) ---
            st.subheader("🧠 Pontos Cegos e Oportunidades")
            
            # 1. Alerta de Risco Máximo
            risco_maximo = df_resumo[(df_resumo['Curva_ABC'] == 'A') & (df_resumo['Variacao_Perc'] > 0.10)]
            if not risco_maximo.empty:
                st.error(f"🚨 **ALERTA CRÍTICO:** Identificamos {len(risco_maximo)} itens da **Curva A** com reajuste acima de 10%. Isso está drenando seu caixa diretamente.")
                with st.expander("Ver itens de Risco Máximo"):
                    st.table(risco_maximo[['Produto', 'Preço_Inicial', 'Preço_Atual', 'Variacao_Perc', 'Gasto_Total']])
            
            # 2. Benchmark de Redução
            sucessos = df_resumo[(df_resumo['Curva_ABC'] == 'A') & (df_resumo['Variacao_Perc'] < 0)]
            if not sucessos.empty:
                st.success(f"✅ **BENCHMARK:** Você conseguiu redução em {len(sucessos)} itens estratégicos (Curva A). Verifique o que foi feito aqui para replicar nos outros itens.")

            # --- TABELA DE DADOS COMPLETA ---
            st.subheader("📑 Tabela Analítica Detalhada")
            
            def styler(row):
                # Vermelho para itens caros que subiram muito
                if row['Curva_ABC'] == 'A' and row['Variacao_Perc'] > 0.10:
                    return ['background-color: #f8d7da'] * len(row)
                # Verde para itens estratégicos com redução
                if row['Curva_ABC'] == 'A' and row['Variacao_Perc'] < 0:
                    return ['background-color: #d4edda'] * len(row)
                return [''] * len(row)

            st.dataframe(df_resumo[['Curva_ABC', 'Cód. Produto', 'Produto', 'Preço_Inicial', 'Preço_Atual', 'Variacao_Perc', 'Categoria_Preco', 'Gasto_Total', 'Comprador_Princ']]
                         .style.format({'Variacao_Perc': '{:.2%}', 'Gasto_Total': 'R$ {:,.2f}', 'Preço_Inicial': 'R$ {:,.2f}', 'Preço_Atual': 'R$ {:,.2f}'})
                         .apply(styler, axis=1), use_container_width=True)

        else:
            st.warning("Filtros resultaram em dados vazios.")
    except Exception as e:
        st.error(f"Erro fatal: {e}")
else:
    st.info("Insira o arquivo para gerar a inteligência de compras.")
