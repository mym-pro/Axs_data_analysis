import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import json
from datetime import datetime, timedelta
import io
import tempfile
import os

# 页面配置
st.set_page_config(
    page_title="AXS 海运数据分析平台",
    page_icon="🚢",
    layout="wide",
    initial_sidebar_state="expanded"
)

class DataManager:
    """数据管理器 - 处理用户上传的数据"""
    
    def __init__(self):
        """初始化数据管理器"""
        self.data = None
        self.commodity_hierarchy = None
        self.commodity_mapping = None
        
    def load_data_from_upload(self, uploaded_file):
        """从上传的文件加载数据"""
        try:
            # 根据文件类型读取数据
            if uploaded_file.name.endswith('.csv'):
                # 对于CSV文件，我们可以分块读取或直接读取
                df = pd.read_csv(uploaded_file)
            elif uploaded_file.name.endswith('.xlsx'):
                df = pd.read_excel(uploaded_file)
            elif uploaded_file.name.endswith('.parquet'):
                df = pd.read_parquet(uploaded_file)
            else:
                st.error(f"不支持的文件格式: {uploaded_file.name}")
                return None
            
            st.success(f"成功加载数据，共 {len(df):,} 条记录")
            return df
            
        except Exception as e:
            st.error(f"数据加载失败: {str(e)}")
            return None
    
    def load_default_commodity_hierarchy(self):
        """获取默认的商品分类结构"""
        return {
            "Major Bulks": {
                "Iron Ore": ["Iron Ore", "Iron Ore Pellets"],
                "Coal": ["Coal", "Steam Coal", "Coking Coal"],
                "Grain": ["Grain", "Wheat", "Corn", "Soybeans"]
            },
            "Minor Bulks": {
                "Steel Products": ["Steel", "Steel Coils", "Steel Billets"],
                "Fertilizers": ["Fertilizers", "Urea", "DAP", "MOP"]
            }
        }
    
    def save_commodity_hierarchy_to_file(self, commodity_hierarchy):
        """保存商品分类结构到临时文件"""
        try:
            # 创建临时文件
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
                json.dump(commodity_hierarchy, f, indent=2, ensure_ascii=False)
                temp_path = f.name
            
            # 提供下载
            with open(temp_path, 'r', encoding='utf-8') as f:
                json_content = f.read()
            
            # 清理临时文件
            os.unlink(temp_path)
            
            return json_content
            
        except Exception as e:
            st.error(f"保存商品分类结构失败: {str(e)}")
            return None

# 构建商品到层级的映射
def build_commodity_mapping(hierarchy):
    """构建商品到三个层级的映射字典"""
    mapping = {}
    
    def traverse(node, path):
        if isinstance(node, dict):
            for key, value in node.items():
                new_path = path + [key]
                traverse(value, new_path)
        elif isinstance(node, list):
            # 当前路径至少有1个元素（level1），可能有2个（level2），可能有3个（level3）
            for item in node:
                level1 = path[0] if len(path) > 0 else "Unknown"
                level2 = path[1] if len(path) > 1 else level1
                level3 = path[2] if len(path) > 2 else level2
                mapping[item] = (level1, level2, level3)
    
    traverse(hierarchy, [])
    return mapping

def check_and_generate_fields(df, commodity_mapping):
    """检查并生成缺失的字段"""
    modified = False
    
    # 1. 筛选voyage_type为laden的数据
    if 'voyage_type' in df.columns:
        laden_count = len(df[df['voyage_type'] == 'laden'])
        total_count = len(df)
        if laden_count < total_count:
            df = df[df['voyage_type'] == 'laden'].copy()
            modified = True
            st.info(f"已筛选voyage_type为laden的数据: {laden_count}/{total_count} 条记录")
    
    # 2. 生成vessel_dwt_type字段
    if 'vessel_dwt_type' not in df.columns and 'vsl_dwt' in df.columns:
        def get_dwt_type(dwt):
            if pd.isna(dwt):
                return "Unknown"
            if dwt >= 200000:
                return "VLOC"
            elif dwt >= 100000:
                return "Capesize"
            elif dwt >= 65000:
                return "Panamax/Kamsarmax"
            elif dwt >= 40000:
                return "Supramax/Ultramax"
            else:
                return "Handysize"
        
        df['vessel_dwt_type'] = df['vsl_dwt'].apply(get_dwt_type)
        modified = True
        st.info("已生成vessel_dwt_type字段")
    
    # 3. 生成日期相关字段
    date_fields_to_check = ['Year', 'Quarter', 'Month']
    missing_date_fields = [field for field in date_fields_to_check if field not in df.columns]
    
    if missing_date_fields and 'load_end_date' in df.columns:
        # 确保load_end_date是datetime类型
        df['load_end_date'] = pd.to_datetime(df['load_end_date'], errors='coerce')
        
        if 'Year' not in df.columns:
            df['Year'] = df['load_end_date'].dt.year
            modified = True
        
        if 'Quarter' not in df.columns:
            df['Quarter'] = 'Q' + df['load_end_date'].dt.quarter.astype(str)
            modified = True
        
        if 'Month' not in df.columns:
            df['Month'] = 'M' + df['load_end_date'].dt.month.astype(str)
            modified = True
        
        if modified:
            st.info("已生成日期相关字段 (Year, Quarter, Month)")
    
    # 4. 生成商品分类字段
    commodity_fields_to_check = ['commodity_type_1level', 'commodity_type_2level', 'commodity_type_3level']
    missing_commodity_fields = [field for field in commodity_fields_to_check if field not in df.columns]
    
    if missing_commodity_fields and 'commodity' in df.columns and commodity_mapping:
        def get_commodity_levels(commodity):
            if pd.isna(commodity):
                return ("Unknown", "Unknown", "Unknown")
            
            # 尝试精确匹配
            if commodity in commodity_mapping:
                return commodity_mapping[commodity]
            
            # 尝试部分匹配
            for key, value in commodity_mapping.items():
                if isinstance(key, str) and key.lower() in commodity.lower():
                    return value
            
            return ("Unknown", "Unknown", "Unknown")
        
        # 应用分类函数
        df[['commodity_type_1level', 'commodity_type_2level', 'commodity_type_3level']] = pd.DataFrame(
            df['commodity'].apply(get_commodity_levels).tolist(),
            index=df.index
        )
        modified = True
        st.info("已生成商品分类字段")
    
    return df, modified

@st.cache_data(ttl=86400)  # 缓存24小时
def process_uploaded_data(uploaded_file, commodity_mapping):
    """处理上传的数据"""
    try:
        # 初始化数据管理器
        data_manager = DataManager()
        
        # 加载数据
        with st.spinner("正在加载数据..."):
            df = data_manager.load_data_from_upload(uploaded_file)
        
        if df is None:
            return None
        
        # 检查并生成缺失字段
        with st.spinner("处理数据字段..."):
            df, modified = check_and_generate_fields(df, commodity_mapping)
        
        return df
    
    except Exception as e:
        st.error(f"数据处理错误: {str(e)}")
        return None

@st.cache_data(ttl=86400)  # 缓存24小时
def get_filtered_data(df, filters):
    """根据筛选条件获取数据（带缓存）"""
    filtered_df = df.copy()
    
    # 应用筛选条件
    if filters.get('vessel_type'):
        filtered_df = filtered_df[filtered_df['vessel_dwt_type'].isin(filters['vessel_type'])]
    
    if filters.get('commodity_level1'):
        filtered_df = filtered_df[filtered_df['commodity_type_1level'].isin(filters['commodity_level1'])]
    
    if filters.get('commodity_level2'):
        filtered_df = filtered_df[filtered_df['commodity_type_2level'].isin(filters['commodity_level2'])]
    
    if filters.get('commodity_level3'):
        filtered_df = filtered_df[filtered_df['commodity_type_3level'].isin(filters['commodity_level3'])]
    
    if filters.get('date_range') and len(filters['date_range']) == 2 and 'load_end_date' in filtered_df.columns:
        start_date, end_date = filters['date_range']
        filtered_df = filtered_df[(filtered_df['load_end_date'] >= pd.Timestamp(start_date)) & 
                                  (filtered_df['load_end_date'] <= pd.Timestamp(end_date))]
    
    return filtered_df

def create_trade_flow_charts(df, vessel_type=None, commodity_level1=None, 
                             commodity_level2=None, commodity_level3=None,
                             analysis_type="overall"):
    """创建贸易流柱状图"""
    
    # 准备筛选条件
    filters = {
        'vessel_type': vessel_type,
        'commodity_level1': commodity_level1,
        'commodity_level2': commodity_level2,
        'commodity_level3': commodity_level3
    }
    
    # 使用缓存的筛选函数
    filtered_df = get_filtered_data(df, filters)
    
    if filtered_df.empty:
        st.warning("筛选条件没有匹配的数据")
        return
    
    # 获取年份范围
    years = sorted(filtered_df['Year'].dropna().unique())
    
    if analysis_type == "overall":
        # 总体分析 - 每年生成2张图（load_zone和discharge_zone，load_country和discharge_country）
        
        # 1. 按区域分析
        st.subheader("按区域分析 - 年度排名前10")
        
        for year in years:
            year_df = filtered_df[filtered_df['Year'] == year]
            
            if not year_df.empty:
                # 装货区域排名
                load_zone_agg = year_df.groupby('load_zone')['voy_intake_mt'].sum().reset_index()
                load_zone_agg = load_zone_agg.sort_values('voy_intake_mt', ascending=False).head(10)
                
                # 卸货区域排名
                discharge_zone_agg = year_df.groupby('discharge_zone')['voy_intake_mt'].sum().reset_index()
                discharge_zone_agg = discharge_zone_agg.sort_values('voy_intake_mt', ascending=False).head(10)
                
                # 创建子图
                fig = make_subplots(
                    rows=1, cols=2,
                    subplot_titles=(f'{year}年 装货区域前10', f'{year}年 卸货区域前10'),
                    horizontal_spacing=0.2
                )
                
                # 装货区域柱状图
                fig.add_trace(
                    go.Bar(
                        x=load_zone_agg['voy_intake_mt'],
                        y=load_zone_agg['load_zone'],
                        orientation='h',
                        name='装货区域',
                        marker_color='steelblue'
                    ),
                    row=1, col=1
                )
                
                # 卸货区域柱状图
                fig.add_trace(
                    go.Bar(
                        x=discharge_zone_agg['voy_intake_mt'],
                        y=discharge_zone_agg['discharge_zone'],
                        orientation='h',
                        name='卸货区域',
                        marker_color='darkorange'
                    ),
                    row=1, col=2
                )
                
                fig.update_layout(
                    height=500,
                    showlegend=False,
                    title_text=f"{year}年 区域贸易流分析",
                    title_x=0.5
                )
                
                fig.update_xaxes(title_text="货运量 (MT)", row=1, col=1)
                fig.update_xaxes(title_text="货运量 (MT)", row=1, col=2)
                
                st.plotly_chart(fig, use_container_width=True)
        
        # 2. 按国家分析
        st.subheader("按国家分析 - 年度排名前10")
        
        for year in years:
            year_df = filtered_df[filtered_df['Year'] == year]
            
            if not year_df.empty:
                # 装货国家排名
                load_country_agg = year_df.groupby('load_country')['voy_intake_mt'].sum().reset_index()
                load_country_agg = load_country_agg.sort_values('voy_intake_mt', ascending=False).head(10)
                
                # 卸货国家排名
                discharge_country_agg = year_df.groupby('discharge_country')['voy_intake_mt'].sum().reset_index()
                discharge_country_agg = discharge_country_agg.sort_values('voy_intake_mt', ascending=False).head(10)
                
                # 创建子图
                fig = make_subplots(
                    rows=1, cols=2,
                    subplot_titles=(f'{year}年 装货国家前10', f'{year}年 卸货国家前10'),
                    horizontal_spacing=0.2
                )
                
                # 装货国家柱状图
                fig.add_trace(
                    go.Bar(
                        x=load_country_agg['voy_intake_mt'],
                        y=load_country_agg['load_country'],
                        orientation='h',
                        name='装货国家',
                        marker_color='seagreen'
                    ),
                    row=1, col=1
                )
                
                # 卸货国家柱状图
                fig.add_trace(
                    go.Bar(
                        x=discharge_country_agg['voy_intake_mt'],
                        y=discharge_country_agg['discharge_country'],
                        orientation='h',
                        name='卸货国家',
                        marker_color='mediumpurple'
                    ),
                    row=1, col=2
                )
                
                fig.update_layout(
                    height=500,
                    showlegend=False,
                    title_text=f"{year}年 国家贸易流分析",
                    title_x=0.5
                )
                
                fig.update_xaxes(title_text="货运量 (MT)", row=1, col=1)
                fig.update_xaxes(title_text="货运量 (MT)", row=1, col=2)
                
                st.plotly_chart(fig, use_container_width=True)
    
    elif analysis_type == "loading":
        # 装货分析
        
        st.subheader("装货分析 - 年度排名前10")
        
        for year in years:
            year_df = filtered_df[filtered_df['Year'] == year]
            
            if not year_df.empty:
                # 按卸货区域排名
                discharge_zone_agg = year_df.groupby('discharge_zone')['voy_intake_mt'].sum().reset_index()
                discharge_zone_agg = discharge_zone_agg.sort_values('voy_intake_mt', ascending=False).head(10)
                
                # 创建柱状图
                fig = go.Figure()
                
                fig.add_trace(go.Bar(
                    x=discharge_zone_agg['voy_intake_mt'],
                    y=discharge_zone_agg['discharge_zone'],
                    orientation='h',
                    marker_color='coral'
                ))
                
                fig.update_layout(
                    title=f"{year}年 卸货区域排名前10",
                    xaxis_title="货运量 (MT)",
                    yaxis_title="卸货区域",
                    height=500
                )
                
                st.plotly_chart(fig, use_container_width=True)
    
    elif analysis_type == "discharging":
        # 卸货分析
        
        st.subheader("卸货分析 - 年度排名前10")
        
        for year in years:
            year_df = filtered_df[filtered_df['Year'] == year]
            
            if not year_df.empty:
                # 按装货区域排名
                load_zone_agg = year_df.groupby('load_zone')['voy_intake_mt'].sum().reset_index()
                load_zone_agg = load_zone_agg.sort_values('voy_intake_mt', ascending=False).head(10)
                
                # 创建柱状图
                fig = go.Figure()
                
                fig.add_trace(go.Bar(
                    x=load_zone_agg['voy_intake_mt'],
                    y=load_zone_agg['load_zone'],
                    orientation='h',
                    marker_color='goldenrod'
                ))
                
                fig.update_layout(
                    title=f"{year}年 装货区域排名前10",
                    xaxis_title="货运量 (MT)",
                    yaxis_title="装货区域",
                    height=500
                )
                
                st.plotly_chart(fig, use_container_width=True)

@st.cache_data(ttl=3600)  # 缓存1小时
def create_time_series_charts(df, vessel_type=None, commodity_level1=None, 
                              commodity_level2=None, commodity_level3=None,
                              location_type="load_zone", selected_locations=None,
                              date_range=None):
    """创建时间序列图"""
    
    # 准备筛选条件
    filters = {
        'vessel_type': vessel_type,
        'commodity_level1': commodity_level1,
        'commodity_level2': commodity_level2,
        'commodity_level3': commodity_level3,
        'date_range': date_range
    }
    
    # 使用缓存的筛选函数
    filtered_df = get_filtered_data(df, filters)
    
    # 按位置筛选
    if selected_locations and location_type in filtered_df.columns:
        filtered_df = filtered_df[filtered_df[location_type].isin(selected_locations)]
    
    if filtered_df.empty:
        st.warning("筛选条件没有匹配的数据")
        return None
    
    # 按时间聚合（月度）
    filtered_df['Month_Year'] = filtered_df['load_end_date'].dt.to_period('M').astype(str)
    
    # 分组聚合
    if location_type in filtered_df.columns and selected_locations:
        # 如果选择了特定位置，按位置分组
        time_series = filtered_df.groupby([location_type, 'Month_Year'])['voy_intake_mt'].sum().reset_index()
        
        fig = go.Figure()
        
        for location in selected_locations:
            location_data = time_series[time_series[location_type] == location]
            fig.add_trace(go.Scatter(
                x=location_data['Month_Year'],
                y=location_data['voy_intake_mt'],
                mode='lines+markers',
                name=location,
                line=dict(width=2)
            ))
    else:
        # 如果没有选择特定位置，显示总量
        time_series = filtered_df.groupby('Month_Year')['voy_intake_mt'].sum().reset_index()
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=time_series['Month_Year'],
            y=time_series['voy_intake_mt'],
            mode='lines+markers',
            name='总货运量',
            line=dict(width=3, color='royalblue')
        ))
    
    fig.update_layout(
        title=f"{location_type.replace('_', ' ').title()} 货运量时间变化",
        xaxis_title="时间",
        yaxis_title="货运量 (MT)",
        height=500,
        hovermode='x unified'
    )
    
    return fig

@st.cache_data(ttl=3600)  # 缓存1小时
def create_seasonal_charts(df, vessel_type=None, commodity_level1=None, 
                           commodity_level2=None, commodity_level3=None,
                           location_type=None, selected_locations=None,
                           date_range=None):
    """创建季节性规律图表"""
    
    # 准备筛选条件
    filters = {
        'vessel_type': vessel_type,
        'commodity_level1': commodity_level1,
        'commodity_level2': commodity_level2,
        'commodity_level3': commodity_level3,
        'date_range': date_range
    }
    
    # 使用缓存的筛选函数
    filtered_df = get_filtered_data(df, filters)
    
    if filtered_df.empty:
        st.warning("筛选条件没有匹配的数据")
        return None
    
    # 提取月份
    filtered_df['Month_Num'] = filtered_df['load_end_date'].dt.month
    
    if location_type and selected_locations and location_type in filtered_df.columns:
        # 如果选择了特定位置，按位置和月份分组
        filtered_df = filtered_df[filtered_df[location_type].isin(selected_locations)]
        
        seasonal_data = filtered_df.groupby([location_type, 'Month_Num'])['voy_intake_mt'].sum().reset_index()
        
        fig = go.Figure()
        
        for location in selected_locations:
            location_data = seasonal_data[seasonal_data[location_type] == location]
            fig.add_trace(go.Scatter(
                x=location_data['Month_Num'],
                y=location_data['voy_intake_mt'],
                mode='lines+markers',
                name=location,
                line=dict(width=2)
            ))
        
        title = f"{location_type.replace('_', ' ').title()} 季节性规律"
    else:
        # 总体季节性规律
        seasonal_data = filtered_df.groupby('Month_Num')['voy_intake_mt'].sum().reset_index()
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=seasonal_data['Month_Num'],
            y=seasonal_data['voy_intake_mt'],
            mode='lines+markers',
            name='总货运量',
            line=dict(width=3, color='darkgreen')
        ))
        
        title = "货运量季节性规律"
    
    # 设置x轴标签为月份名称
    month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
                   'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    fig.update_xaxes(
        tickmode='array',
        tickvals=list(range(1, 13)),
        ticktext=month_names
    )
    
    fig.update_layout(
        title=title,
        xaxis_title="月份",
        yaxis_title="货运量 (MT)",
        height=500
    )
    
    return fig

def edit_commodity_hierarchy(commodity_hierarchy):
    """编辑商品分类层级结构"""
    st.header("📝 编辑商品分类层级结构")
    
    # 显示当前结构
    st.subheader("当前商品分类结构")
    st.json(commodity_hierarchy)
    
    # 编辑选项
    st.subheader("编辑选项")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # 提供JSON文件下载
        data_manager = DataManager()
        json_content = data_manager.save_commodity_hierarchy_to_file(commodity_hierarchy)
        if json_content:
            st.download_button(
                label="📥 下载当前结构",
                data=json_content,
                file_name="commodity_hierarchy.json",
                mime="application/json"
            )
    
    with col2:
        if st.button("🔄 重置为默认结构"):
            data_manager = DataManager()
            default_hierarchy = data_manager.load_default_commodity_hierarchy()
            st.session_state.commodity_hierarchy = default_hierarchy
            st.session_state.commodity_mapping = build_commodity_mapping(default_hierarchy)
            st.success("已重置为默认商品分类结构")
            st.rerun()
    
    with col3:
        # 上传新的JSON文件
        uploaded_file = st.file_uploader("上传新的JSON结构", type=['json'])
        if uploaded_file is not None:
            try:
                new_hierarchy = json.load(uploaded_file)
                st.success("JSON文件解析成功")
                st.write("新结构预览:")
                st.json(new_hierarchy)
                
                if st.button("💾 保存新结构"):
                    st.session_state.commodity_hierarchy = new_hierarchy
                    st.session_state.commodity_mapping = build_commodity_mapping(new_hierarchy)
                    st.success("商品分类结构已更新！")
                    st.rerun()
            except Exception as e:
                st.error(f"JSON文件解析失败: {str(e)}")
    
    return None

def main():
    """主函数"""
    
    st.title("🚢 AXS 海运数据分析平台")
    st.markdown("---")
    
    # 初始化session state
    if 'data_loaded' not in st.session_state:
        st.session_state.data_loaded = False
    if 'current_data' not in st.session_state:
        st.session_state.current_data = None
    
    # 创建标签页
    tab1, tab2 = st.tabs([
        "📊 数据分析仪表板", 
        "⚙️ 商品分类管理"
    ])
    
    with tab2:
        # 商品分类管理页面
        st.header("商品分类层级结构管理")
        
        # 初始化商品分类结构
        if 'commodity_hierarchy' not in st.session_state:
            data_manager = DataManager()
            default_hierarchy = data_manager.load_default_commodity_hierarchy()
            st.session_state.commodity_hierarchy = default_hierarchy
            st.session_state.commodity_mapping = build_commodity_mapping(default_hierarchy)
        
        # 编辑功能
        edit_commodity_hierarchy(st.session_state.commodity_hierarchy)
        
        # 显示映射统计信息
        st.subheader("商品映射统计")
        if st.session_state.commodity_mapping:
            st.write(f"已映射的商品数量: {len(st.session_state.commodity_mapping)}")
            
            # 显示映射示例
            with st.expander("查看商品映射示例"):
                sample_items = list(st.session_state.commodity_mapping.items())[:10]
                for commodity, levels in sample_items:
                    st.write(f"**{commodity}** → 一级: {levels[0]}, 二级: {levels[1]}, 三级: {levels[2]}")
    
    with tab1:
        # 数据分析页面
        st.header("数据分析仪表板")
        
        # 数据上传部分
        st.subheader("数据上传")
        col1, col2 = st.columns([2, 1])
        
        with col1:
            uploaded_file = st.file_uploader(
                "上传海运数据文件",
                type=['csv', 'xlsx', 'xls', 'parquet'],
                help="支持 CSV、Excel、Parquet 格式文件"
            )
        
        with col2:
            if uploaded_file is not None:
                if st.button("🚀 加载数据", type="primary", use_container_width=True):
                    with st.spinner("正在处理数据..."):
                        # 处理上传的数据
                        df = process_uploaded_data(
                            uploaded_file, 
                            st.session_state.commodity_mapping if 'commodity_mapping' in st.session_state else None
                        )
                        
                        if df is not None:
                            st.session_state.current_data = df
                            st.session_state.data_loaded = True
                            st.success("数据加载成功！")
                            st.rerun()
        
        # 如果没有加载数据，显示提示
        if not st.session_state.data_loaded or st.session_state.current_data is None:
            st.info("请先上传数据文件进行分析")
            return
        
        # 获取当前数据
        df = st.session_state.current_data
        
        # 侧边栏 - 数据筛选
        with st.sidebar:
            st.header("数据概览")
            st.write(f"总记录数: {len(df):,}")
            
            if 'load_end_date' in df.columns:
                min_date = df['load_end_date'].min()
                max_date = df['load_end_date'].max()
                st.write(f"数据时间范围: {min_date.date()} 至 {max_date.date()}")
            
            st.write(f"船舶类型数量: {df['vessel_dwt_type'].nunique()}")
            st.write(f"商品一级分类: {df['commodity_type_1level'].nunique()}")
            
            st.markdown("---")
            st.header("筛选条件")
            
            # 船舶类型选择
            vessel_options = sorted(df['vessel_dwt_type'].dropna().unique().tolist())
            selected_vessel_types = st.multiselect(
                "选择船舶类型",
                options=vessel_options,
                default=None,
                help="可多选"
            )
            
            # 商品分类选择（联动）
            st.subheader("商品分类筛选")
            
            commodity_level1_options = sorted(df['commodity_type_1level'].dropna().unique().tolist())
            selected_level1 = st.multiselect(
                "商品一级分类",
                options=commodity_level1_options,
                default=None
            )
            
            if selected_level1:
                level2_options = sorted(df[df['commodity_type_1level'].isin(selected_level1)]['commodity_type_2level'].dropna().unique().tolist())
                selected_level2 = st.multiselect(
                    "商品二级分类",
                    options=level2_options,
                    default=None
                )
            else:
                selected_level2 = None
            
            if selected_level2:
                level3_options = sorted(df[df['commodity_type_2level'].isin(selected_level2)]['commodity_type_3level'].dropna().unique().tolist())
                selected_level3 = st.multiselect(
                    "商品三级分类",
                    options=level3_options,
                    default=None
                )
            else:
                selected_level3 = None
            
            # 区域选择
            st.subheader("区域选择")
            
            load_zone_options = sorted(df['load_zone'].dropna().unique().tolist())
            discharge_zone_options = sorted(df['discharge_zone'].dropna().unique().tolist())
            load_country_options = sorted(df['load_country'].dropna().unique().tolist())
            discharge_country_options = sorted(df['discharge_country'].dropna().unique().tolist())
            
            selected_load_zones = st.multiselect(
                "装货区域",
                options=load_zone_options,
                default=None
            )
            
            selected_discharge_zones = st.multiselect(
                "卸货区域",
                options=discharge_zone_options,
                default=None
            )
            
            selected_load_countries = st.multiselect(
                "装货国家",
                options=load_country_options,
                default=None
            )
            
            selected_discharge_countries = st.multiselect(
                "卸货国家",
                options=discharge_country_options,
                default=None
            )
            
            # 时间范围选择
            st.subheader("时间范围")
            
            if 'load_end_date' in df.columns:
                min_date = df['load_end_date'].min()
                max_date = df['load_end_date'].max()
                
                date_range = st.date_input(
                    "选择时间范围",
                    value=[min_date, max_date],
                    min_value=min_date,
                    max_value=max_date
                )
            else:
                date_range = None
            
            st.markdown("---")
            
            # 手动刷新缓存按钮
            if st.button("🔄 清除缓存并重新加载"):
                st.cache_data.clear()
                st.session_state.data_loaded = False
                st.session_state.current_data = None
                st.rerun()
        
        # 创建分析标签页
        analysis_tab1, analysis_tab2, analysis_tab3 = st.tabs([
            "📊 贸易流分析", 
            "📈 时间序列分析", 
            "🌊 季节性分析"
        ])
        
        with analysis_tab1:
            st.header("贸易流分析")
            
            analysis_type = st.radio(
                "选择分析类型",
                ["总体分析", "装货分析", "卸货分析"],
                horizontal=True
            )
            
            if analysis_type == "总体分析":
                create_trade_flow_charts(
                    df,
                    vessel_type=selected_vessel_types,
                    commodity_level1=selected_level1,
                    commodity_level2=selected_level2,
                    commodity_level3=selected_level3,
                    analysis_type="overall"
                )
            elif analysis_type == "装货分析":
                # 选择装货区域
                st.subheader("选择装货区域进行分析")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    use_load_zone = st.checkbox("按装货区域分析", value=True)
                    if use_load_zone:
                        selected_for_analysis = selected_load_zones
                        location_type = "load_zone"
                
                with col2:
                    use_load_country = st.checkbox("按装货国家分析")
                    if use_load_country:
                        selected_for_analysis = selected_load_countries
                        location_type = "load_country"
                
                if (use_load_zone or use_load_country) and selected_for_analysis:
                    if use_load_zone:
                        create_trade_flow_charts(
                            df,
                            vessel_type=selected_vessel_types,
                            commodity_level1=selected_level1,
                            commodity_level2=selected_level2,
                            commodity_level3=selected_level3,
                            analysis_type="loading"
                        )
                    else:
                        st.info("按国家分析的实现与按区域分析类似")
                else:
                    st.warning("请先选择装货区域或国家")
            
            elif analysis_type == "卸货分析":
                # 选择卸货区域
                st.subheader("选择卸货区域进行分析")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    use_discharge_zone = st.checkbox("按卸货区域分析", value=True)
                    if use_discharge_zone:
                        selected_for_analysis = selected_discharge_zones
                        location_type = "discharge_zone"
                
                with col2:
                    use_discharge_country = st.checkbox("按卸货国家分析")
                    if use_discharge_country:
                        selected_for_analysis = selected_discharge_countries
                        location_type = "discharge_country"
                
                if (use_discharge_zone or use_discharge_country) and selected_for_analysis:
                    if use_discharge_zone:
                        create_trade_flow_charts(
                            df,
                            vessel_type=selected_vessel_types,
                            commodity_level1=selected_level1,
                            commodity_level2=selected_level2,
                            commodity_level3=selected_level3,
                            analysis_type="discharging"
                        )
                    else:
                        st.info("按国家分析的实现与按区域分析类似")
                else:
                    st.warning("请先选择卸货区域或国家")
        
        with analysis_tab2:
            st.header("海运量时间变化分析")
            
            analysis_type = st.radio(
                "选择分析维度",
                ["装货分析", "卸货分析"],
                horizontal=True
            )
            
            if analysis_type == "装货分析":
                location_type = st.selectbox(
                    "选择位置类型",
                    ["load_zone", "load_country"]
                )
                
                if location_type == "load_zone":
                    selected_locations = selected_load_zones
                else:
                    selected_locations = selected_load_countries
                
                fig = create_time_series_charts(
                    df,
                    vessel_type=selected_vessel_types,
                    commodity_level1=selected_level1,
                    commodity_level2=selected_level2,
                    commodity_level3=selected_level3,
                    location_type=location_type,
                    selected_locations=selected_locations,
                    date_range=date_range
                )
                
                if fig:
                    st.plotly_chart(fig, use_container_width=True)
            
            else:  # 卸货分析
                location_type = st.selectbox(
                    "选择位置类型",
                    ["discharge_zone", "discharge_country"]
                )
                
                if location_type == "discharge_zone":
                    selected_locations = selected_discharge_zones
                else:
                    selected_locations = selected_discharge_countries
                
                fig = create_time_series_charts(
                    df,
                    vessel_type=selected_vessel_types,
                    commodity_level1=selected_level1,
                    commodity_level2=selected_level2,
                    commodity_level3=selected_level3,
                    location_type=location_type,
                    selected_locations=selected_locations,
                    date_range=date_range
                )
                
                if fig:
                    st.plotly_chart(fig, use_container_width=True)
        
        with analysis_tab3:
            st.header("季节性规律分析")
            
            analysis_type = st.selectbox(
                "选择分析类型",
                ["总体季节性", "按装货国家", "按卸货国家"]
            )
            
            if analysis_type == "总体季节性":
                fig = create_seasonal_charts(
                    df,
                    vessel_type=selected_vessel_types,
                    commodity_level1=selected_level1,
                    commodity_level2=selected_level2,
                    commodity_level3=selected_level3,
                    date_range=date_range
                )
                
                if fig:
                    st.plotly_chart(fig, use_container_width=True)
            
            elif analysis_type == "按装货国家":
                if selected_load_countries:
                    fig = create_seasonal_charts(
                        df,
                        vessel_type=selected_vessel_types,
                        commodity_level1=selected_level1,
                        commodity_level2=selected_level2,
                        commodity_level3=selected_level3,
                        location_type="load_country",
                        selected_locations=selected_load_countries,
                        date_range=date_range
                    )
                    
                    if fig:
                        st.plotly_chart(fig, use_container_width=True)
                else:
                    st.warning("请先在侧边栏选择装货国家")
            
            else:  # 按卸货国家
                if selected_discharge_countries:
                    fig = create_seasonal_charts(
                        df,
                        vessel_type=selected_vessel_types,
                        commodity_level1=selected_level1,
                        commodity_level2=selected_level2,
                        commodity_level3=selected_level3,
                        location_type="discharge_country",
                        selected_locations=selected_discharge_countries,
                        date_range=date_range
                    )
                    
                    if fig:
                        st.plotly_chart(fig, use_container_width=True)
                else:
                    st.warning("请先在侧边栏选择卸货国家")

if __name__ == "__main__":
    main()
