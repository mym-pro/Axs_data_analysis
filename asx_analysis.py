import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import json
from datetime import datetime, timedelta
import io
from pathlib import Path
import sys
from github import Github, GithubException
import base64
import tempfile
import os

# 页面配置
st.set_page_config(
    page_title="AXS 海运数据分析平台",
    page_icon="🚢",
    layout="wide",
    initial_sidebar_state="expanded"
)

class GitHubDataManager:
    """GitHub数据管理器"""
    
    def __init__(self):
        """初始化GitHub连接"""
        try:
            # 从Streamlit secrets获取GitHub配置
            self.github_token = st.secrets["github"]["token"]
            self.repo_owner = st.secrets["github"]["repo_owner"]
            self.repo_name = st.secrets["github"]["repo_name"]
            
            # 数据文件路径（从secrets获取，如果没有则使用默认值）
            self.data_path = st.secrets["github"].get("data_path", "data/axs_data.csv")
            self.commodity_hierarchy_path = st.secrets["github"].get(
                "commodity_hierarchy_path", 
                "data/commodity_hierarchy.json"
            )
            
            # 初始化GitHub客户端
            self.g = Github(self.github_token)
            self.repo = self.g.get_repo(f"{self.repo_owner}/{self.repo_name}")
            
            st.success(f"成功连接到GitHub仓库: {self.repo_owner}/{self.repo_name}")
            
        except Exception as e:
            st.error(f"GitHub连接失败: {str(e)}")
            st.info("请确保在Streamlit secrets中正确配置了GitHub凭据")
            raise
    
    def download_json_file(self, file_path):
        """从GitHub下载JSON文件"""
        try:
            # 获取文件内容
            file_content = self.repo.get_contents(file_path)
            
            # 解码内容
            content = base64.b64decode(file_content.content).decode('utf-8')
            
            # 解析JSON
            json_data = json.loads(content)
            
            return json_data
            
        except Exception as e:
            st.error(f"下载JSON文件失败 {file_path}: {str(e)}")
            return None
    
    def upload_json_file(self, json_data, file_path, commit_message="更新JSON文件"):
        """上传JSON文件到GitHub"""
        try:
            # 将JSON数据转换为字符串
            json_content = json.dumps(json_data, indent=2, ensure_ascii=False)
            
            # 编码内容
            encoded_content = base64.b64encode(json_content.encode()).decode()
            
            # 检查文件是否已存在
            try:
                # 尝试获取现有文件
                file_content = self.repo.get_contents(file_path)
                
                # 更新现有文件
                self.repo.update_file(
                    path=file_path,
                    message=commit_message,
                    content=encoded_content,
                    sha=file_content.sha
                )
                st.success(f"已更新GitHub上的文件: {file_path}")
                
            except GithubException as e:
                if e.status == 404:
                    # 文件不存在，创建新文件
                    self.repo.create_file(
                        path=file_path,
                        message=commit_message,
                        content=encoded_content
                    )
                    st.success(f"已在GitHub上创建文件: {file_path}")
                else:
                    raise
            
            return True
            
        except Exception as e:
            st.error(f"上传JSON文件到GitHub失败: {str(e)}")
            return False
    
    def download_data(self):
        """从GitHub下载数据"""
        try:
            # 获取文件内容
            file_content = self.repo.get_contents(self.data_path)
            
            # 如果是CSV文件
            if self.data_path.endswith('.csv'):
                # 解码内容
                content = base64.b64decode(file_content.content).decode('utf-8')
                # 创建临时文件
                with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8') as f:
                    f.write(content)
                    temp_path = f.name
                
                # 读取CSV
                df = pd.read_csv(temp_path)
                
                # 清理临时文件
                os.unlink(temp_path)
                
                return df
            
            # 如果是Excel文件
            elif self.data_path.endswith('.xlsx'):
                # 解码内容
                content = base64.b64decode(file_content.content)
                # 创建临时文件
                with tempfile.NamedTemporaryFile(mode='wb', suffix='.xlsx', delete=False) as f:
                    f.write(content)
                    temp_path = f.name
                
                # 读取Excel
                df = pd.read_excel(temp_path)
                
                # 清理临时文件
                os.unlink(temp_path)
                
                return df
            else:
                st.error(f"不支持的文件格式: {self.data_path}")
                return None
                
        except Exception as e:
            st.error(f"下载数据失败: {str(e)}")
            return None
    
    def upload_data(self, df, commit_message="更新数据"):
        """上传数据到GitHub"""
        try:
            # 将DataFrame转换为CSV字符串
            csv_content = df.to_csv(index=False)
            
            # 编码内容
            encoded_content = base64.b64encode(csv_content.encode()).decode()
            
            # 检查文件是否已存在
            try:
                # 尝试获取现有文件
                file_content = self.repo.get_contents(self.data_path)
                
                # 更新现有文件
                self.repo.update_file(
                    path=self.data_path,
                    message=commit_message,
                    content=encoded_content,
                    sha=file_content.sha
                )
                st.success(f"已更新GitHub上的数据文件: {self.data_path}")
                
            except GithubException as e:
                if e.status == 404:
                    # 文件不存在，创建新文件
                    self.repo.create_file(
                        path=self.data_path,
                        message=commit_message,
                        content=encoded_content
                    )
                    st.success(f"已在GitHub上创建数据文件: {self.data_path}")
                else:
                    raise
            
            return True
            
        except Exception as e:
            st.error(f"上传数据到GitHub失败: {str(e)}")
            return False
    
    def load_commodity_hierarchy(self):
        """从GitHub加载商品分类层级结构"""
        try:
            # 尝试从GitHub加载商品分类
            with st.spinner("正在加载商品分类结构..."):
                commodity_hierarchy = self.download_json_file(self.commodity_hierarchy_path)
            
            if commodity_hierarchy:
                st.success("商品分类结构加载成功")
                return commodity_hierarchy
            else:
                # 如果GitHub加载失败，使用默认结构
                st.warning("从GitHub加载商品分类失败，使用默认分类结构")
                return self.get_default_commodity_hierarchy()
                
        except Exception as e:
            st.error(f"加载商品分类结构失败: {str(e)}")
            # 使用默认结构作为后备
            return self.get_default_commodity_hierarchy()
    
    def get_default_commodity_hierarchy(self):
        """获取默认的商品分类结构（作为后备方案）"""
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
    
    def save_commodity_hierarchy(self, commodity_hierarchy, commit_message="更新商品分类结构"):
        """保存商品分类结构到GitHub"""
        try:
            success = self.upload_json_file(
                commodity_hierarchy, 
                self.commodity_hierarchy_path, 
                commit_message
            )
            return success
        except Exception as e:
            st.error(f"保存商品分类结构失败: {str(e)}")
            return False

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

@st.cache_data(ttl=3600)
def load_and_process_data(github_manager, commodity_mapping):
    """从GitHub加载并处理数据"""
    try:
        # 从GitHub下载数据
        with st.spinner("正在从GitHub下载数据..."):
            df = github_manager.download_data()
        
        if df is None:
            st.error("无法从GitHub下载数据")
            return None
        
        st.success(f"成功加载数据，共 {len(df):,} 条记录")
        
        # 检查并生成缺失字段
        with st.spinner("检查并生成数据字段..."):
            df, modified = check_and_generate_fields(df, commodity_mapping)
        
        # 如果需要，保存回GitHub
        if modified:
            with st.spinner("保存更新到GitHub..."):
                if github_manager.upload_data(df, "自动生成缺失字段"):
                    st.success("数据已保存回GitHub")
                else:
                    st.warning("数据已处理，但保存到GitHub失败")
        
        return df
    
    except Exception as e:
        st.error(f"数据处理错误: {str(e)}")
        return None

def create_trade_flow_charts(df, vessel_type=None, commodity_level1=None, 
                             commodity_level2=None, commodity_level3=None,
                             analysis_type="overall"):
    """创建贸易流柱状图"""
    
    # 筛选数据
    filtered_df = df.copy()
    
    if vessel_type:
        filtered_df = filtered_df[filtered_df['vessel_dwt_type'].isin(vessel_type)]
    
    if commodity_level1:
        filtered_df = filtered_df[filtered_df['commodity_type_1level'].isin(commodity_level1)]
    
    if commodity_level2:
        filtered_df = filtered_df[filtered_df['commodity_type_2level'].isin(commodity_level2)]
    
    if commodity_level3:
        filtered_df = filtered_df[filtered_df['commodity_type_3level'].isin(commodity_level3)]
    
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

def create_time_series_charts(df, vessel_type=None, commodity_level1=None, 
                              commodity_level2=None, commodity_level3=None,
                              location_type="load_zone", selected_locations=None,
                              date_range=None):
    """创建时间序列图"""
    
    # 筛选数据
    filtered_df = df.copy()
    
    if vessel_type:
        filtered_df = filtered_df[filtered_df['vessel_dwt_type'].isin(vessel_type)]
    
    if commodity_level1:
        filtered_df = filtered_df[filtered_df['commodity_type_1level'].isin(commodity_level1)]
    
    if commodity_level2:
        filtered_df = filtered_df[filtered_df['commodity_type_2level'].isin(commodity_level2)]
    
    if commodity_level3:
        filtered_df = filtered_df[filtered_df['commodity_type_3level'].isin(commodity_level3)]
    
    # 按日期筛选
    if date_range and len(date_range) == 2:
        start_date, end_date = date_range
        filtered_df = filtered_df[(filtered_df['load_end_date'] >= start_date) & 
                                  (filtered_df['load_end_date'] <= end_date)]
    
    if filtered_df.empty:
        st.warning("筛选条件没有匹配的数据")
        return
    
    # 按位置筛选
    if selected_locations and location_type in filtered_df.columns:
        filtered_df = filtered_df[filtered_df[location_type].isin(selected_locations)]
    
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
    
    st.plotly_chart(fig, use_container_width=True)

def create_seasonal_charts(df, vessel_type=None, commodity_level1=None, 
                           commodity_level2=None, commodity_level3=None,
                           location_type=None, selected_locations=None,
                           date_range=None):
    """创建季节性规律图表"""
    
    # 筛选数据
    filtered_df = df.copy()
    
    if vessel_type:
        filtered_df = filtered_df[filtered_df['vessel_dwt_type'].isin(vessel_type)]
    
    if commodity_level1:
        filtered_df = filtered_df[filtered_df['commodity_type_1level'].isin(commodity_level1)]
    
    if commodity_level2:
        filtered_df = filtered_df[filtered_df['commodity_type_2level'].isin(commodity_level2)]
    
    if commodity_level3:
        filtered_df = filtered_df[filtered_df['commodity_type_3level'].isin(commodity_level3)]
    
    # 按日期筛选
    if date_range and len(date_range) == 2:
        start_date, end_date = date_range
        filtered_df = filtered_df[(filtered_df['load_end_date'] >= start_date) & 
                                  (filtered_df['load_end_date'] <= end_date)]
    
    if filtered_df.empty:
        st.warning("筛选条件没有匹配的数据")
        return
    
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
    
    st.plotly_chart(fig, use_container_width=True)

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
        if st.button("📥 下载当前结构为JSON"):
            # 提供JSON文件下载
            json_str = json.dumps(commodity_hierarchy, indent=2, ensure_ascii=False)
            st.download_button(
                label="下载JSON文件",
                data=json_str,
                file_name="commodity_hierarchy.json",
                mime="application/json"
            )
    
    with col2:
        if st.button("🔄 重新加载结构"):
            st.cache_data.clear()
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
                
                if st.button("💾 保存新结构到GitHub"):
                    return new_hierarchy
            except Exception as e:
                st.error(f"JSON文件解析失败: {str(e)}")
    
    return None

def main():
    """主函数"""
    
    st.title("🚢 AXS 海运数据分析平台")
    st.markdown("---")
    
    # 检查是否配置了GitHub secrets
    if "github" not in st.secrets:
        st.error("请在Streamlit Cloud secrets中配置GitHub凭据")
        st.info("""
        请添加以下配置到Streamlit Cloud secrets:
        
        [github]
        token = "your_github_token"
        repo_owner = "your_username"
        repo_name = "your_repository"
        data_path = "path/to/your/data.csv"  # 可选，默认为data/axs_data.csv
        commodity_hierarchy_path = "path/to/commodity_hierarchy.json"  # 可选，默认为data/commodity_hierarchy.json
        """)
        return
    
    try:
        # 初始化GitHub数据管理器
        github_manager = GitHubDataManager()
        
        # 创建标签页
        tab1, tab2 = st.tabs([
            "📊 数据分析仪表板", 
            "⚙️ 商品分类管理"
        ])
        
        with tab2:
            # 商品分类管理页面
            st.header("商品分类层级结构管理")
            
            # 从GitHub加载商品分类结构
            commodity_hierarchy = github_manager.load_commodity_hierarchy()
            
            # 构建商品映射
            commodity_mapping = build_commodity_mapping(commodity_hierarchy)
            
            # 编辑功能
            new_hierarchy = edit_commodity_hierarchy(commodity_hierarchy)
            
            if new_hierarchy:
                # 保存新结构到GitHub
                if github_manager.save_commodity_hierarchy(new_hierarchy, "更新商品分类结构"):
                    st.success("商品分类结构已更新！")
                    st.cache_data.clear()
                    st.rerun()
            
            # 显示映射统计信息
            st.subheader("商品映射统计")
            st.write(f"已映射的商品数量: {len(commodity_mapping)}")
            
            # 显示映射示例
            with st.expander("查看商品映射示例"):
                sample_items = list(commodity_mapping.items())[:10]
                for commodity, levels in sample_items:
                    st.write(f"**{commodity}** → 一级: {levels[0]}, 二级: {levels[1]}, 三级: {levels[2]}")
        
        with tab1:
            # 数据分析页面
            st.header("数据分析仪表板")
            
            # 从GitHub加载商品分类结构（如果还没加载）
            if 'commodity_hierarchy' not in st.session_state:
                with st.spinner("正在加载商品分类结构..."):
                    commodity_hierarchy = github_manager.load_commodity_hierarchy()
                    commodity_mapping = build_commodity_mapping(commodity_hierarchy)
                    st.session_state.commodity_hierarchy = commodity_hierarchy
                    st.session_state.commodity_mapping = commodity_mapping
            else:
                commodity_hierarchy = st.session_state.commodity_hierarchy
                commodity_mapping = st.session_state.commodity_mapping
            
            # 加载数据
            df = load_and_process_data(github_manager, commodity_mapping)
            
            if df is None:
                return
            
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
                
                # 手动刷新数据按钮
                if st.button("🔄 重新加载数据"):
                    st.cache_data.clear()
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
                    
                    create_time_series_charts(
                        df,
                        vessel_type=selected_vessel_types,
                        commodity_level1=selected_level1,
                        commodity_level2=selected_level2,
                        commodity_level3=selected_level3,
                        location_type=location_type,
                        selected_locations=selected_locations,
                        date_range=date_range
                    )
                
                else:  # 卸货分析
                    location_type = st.selectbox(
                        "选择位置类型",
                        ["discharge_zone", "discharge_country"]
                    )
                    
                    if location_type == "discharge_zone":
                        selected_locations = selected_discharge_zones
                    else:
                        selected_locations = selected_discharge_countries
                    
                    create_time_series_charts(
                        df,
                        vessel_type=selected_vessel_types,
                        commodity_level1=selected_level1,
                        commodity_level2=selected_level2,
                        commodity_level3=selected_level3,
                        location_type=location_type,
                        selected_locations=selected_locations,
                        date_range=date_range
                    )
            
            with analysis_tab3:
                st.header("季节性规律分析")
                
                analysis_type = st.selectbox(
                    "选择分析类型",
                    ["总体季节性", "按装货国家", "按卸货国家"]
                )
                
                if analysis_type == "总体季节性":
                    create_seasonal_charts(
                        df,
                        vessel_type=selected_vessel_types,
                        commodity_level1=selected_level1,
                        commodity_level2=selected_level2,
                        commodity_level3=selected_level3,
                        date_range=date_range
                    )
                
                elif analysis_type == "按装货国家":
                    if selected_load_countries:
                        create_seasonal_charts(
                            df,
                            vessel_type=selected_vessel_types,
                            commodity_level1=selected_level1,
                            commodity_level2=selected_level2,
                            commodity_level3=selected_level3,
                            location_type="load_country",
                            selected_locations=selected_load_countries,
                            date_range=date_range
                        )
                    else:
                        st.warning("请先在侧边栏选择装货国家")
                
                else:  # 按卸货国家
                    if selected_discharge_countries:
                        create_seasonal_charts(
                            df,
                            vessel_type=selected_vessel_types,
                            commodity_level1=selected_level1,
                            commodity_level2=selected_level2,
                            commodity_level3=selected_level3,
                            location_type="discharge_country",
                            selected_locations=selected_discharge_countries,
                            date_range=date_range
                        )
                    else:
                        st.warning("请先在侧边栏选择卸货国家")
    
    except Exception as e:
        st.error(f"应用初始化失败: {str(e)}")

if __name__ == "__main__":
    main()