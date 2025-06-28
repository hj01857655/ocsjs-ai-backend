# -*- coding: utf-8 -*-
"""
数据表管理接口
提供数据表的查看、管理、查询等功能
"""
from flask import Blueprint, request, jsonify
from sqlalchemy import text, inspect
from utils.auth import token_required
from utils.response import success_response, error_response, handle_exception
from utils.logger import get_logger
from models.models import db
import json
from datetime import datetime

logger = get_logger(__name__)

table_management_bp = Blueprint('table_management', __name__, url_prefix='/api/table-management')

@table_management_bp.route('/tables', methods=['GET'])
@token_required
def get_tables(current_user):
    """获取所有数据表列表"""
    try:
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        
        table_info = []
        for table_name in tables:
            try:
                # 获取表的基本信息
                columns = inspector.get_columns(table_name)
                indexes = inspector.get_indexes(table_name)
                foreign_keys = inspector.get_foreign_keys(table_name)
                
                # 获取表的行数
                with db.engine.connect() as conn:
                    result = conn.execute(text(f"SELECT COUNT(*) as count FROM `{table_name}`"))
                    row_count = result.fetchone()[0]
                
                table_info.append({
                    'name': table_name,
                    'columns': len(columns),
                    'rows': row_count,
                    'indexes': len(indexes),
                    'foreign_keys': len(foreign_keys)
                })
                
            except Exception as e:
                logger.warning(f"获取表 {table_name} 信息失败: {str(e)}")
                table_info.append({
                    'name': table_name,
                    'columns': 0,
                    'rows': 0,
                    'indexes': 0,
                    'foreign_keys': 0,
                    'error': str(e)
                })
        
        return success_response(
            data={'tables': table_info, 'total': len(table_info)},
            message='获取数据表列表成功'
        )
        
    except Exception as e:
        return handle_exception(e, context={
            'function': 'get_tables',
            'user_id': current_user.id if current_user else None
        })

@table_management_bp.route('/tables/<table_name>/structure', methods=['GET'])
@token_required
def get_table_structure(current_user, table_name):
    """获取指定表的结构信息"""
    try:
        inspector = inspect(db.engine)
        
        # 检查表是否存在
        if table_name not in inspector.get_table_names():
            return error_response(f'表 {table_name} 不存在', status_code=404)
        
        # 获取列信息
        columns = inspector.get_columns(table_name)
        
        # 获取索引信息
        indexes = inspector.get_indexes(table_name)
        
        # 获取外键信息
        foreign_keys = inspector.get_foreign_keys(table_name)
        
        # 获取主键信息
        primary_keys = inspector.get_pk_constraint(table_name)
        
        # 格式化列信息
        formatted_columns = []
        for col in columns:
            formatted_columns.append({
                'name': col['name'],
                'type': str(col['type']),
                'nullable': col['nullable'],
                'default': str(col['default']) if col['default'] is not None else None,
                'autoincrement': col.get('autoincrement', False),
                'primary_key': col['name'] in primary_keys.get('constrained_columns', [])
            })
        
        # 格式化索引信息
        formatted_indexes = []
        for idx in indexes:
            formatted_indexes.append({
                'name': idx['name'],
                'columns': idx['column_names'],
                'unique': idx['unique']
            })
        
        # 格式化外键信息
        formatted_foreign_keys = []
        for fk in foreign_keys:
            formatted_foreign_keys.append({
                'name': fk['name'],
                'constrained_columns': fk['constrained_columns'],
                'referred_table': fk['referred_table'],
                'referred_columns': fk['referred_columns']
            })
        
        return success_response(
            data={
                'table_name': table_name,
                'columns': formatted_columns,
                'indexes': formatted_indexes,
                'foreign_keys': formatted_foreign_keys,
                'primary_key': primary_keys
            },
            message=f'获取表 {table_name} 结构成功'
        )
        
    except Exception as e:
        return handle_exception(e, context={
            'function': 'get_table_structure',
            'table_name': table_name,
            'user_id': current_user.id if current_user else None
        })

@table_management_bp.route('/tables/<table_name>/data', methods=['GET'])
@token_required
def get_table_data(current_user, table_name):
    """获取指定表的数据"""
    try:
        inspector = inspect(db.engine)
        
        # 检查表是否存在
        if table_name not in inspector.get_table_names():
            return error_response(f'表 {table_name} 不存在', status_code=404)
        
        # 获取分页参数
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        per_page = min(per_page, 100)  # 限制最大每页数量
        
        # 获取排序参数
        order_by = request.args.get('order_by', '')
        order_direction = request.args.get('order_direction', 'ASC')
        
        # 构建查询
        offset = (page - 1) * per_page
        
        # 基础查询
        base_query = f"SELECT * FROM `{table_name}`"
        count_query = f"SELECT COUNT(*) as total FROM `{table_name}`"
        
        # 添加排序
        if order_by:
            base_query += f" ORDER BY `{order_by}` {order_direction}"
        
        # 添加分页
        base_query += f" LIMIT {per_page} OFFSET {offset}"
        
        with db.engine.connect() as conn:
            # 获取总数
            total_result = conn.execute(text(count_query))
            total = total_result.fetchone()[0]
            
            # 获取数据
            data_result = conn.execute(text(base_query))
            rows = data_result.fetchall()
            
            # 获取列名
            columns = [col for col in data_result.keys()]
            
            # 格式化数据
            formatted_data = []
            for row in rows:
                row_dict = {}
                for i, col in enumerate(columns):
                    value = row[i]
                    # 处理特殊类型
                    if isinstance(value, datetime):
                        value = value.isoformat()
                    elif value is None:
                        value = None
                    else:
                        value = str(value)
                    row_dict[col] = value
                formatted_data.append(row_dict)
        
        return success_response(
            data={
                'table_name': table_name,
                'columns': columns,
                'data': formatted_data,
                'pagination': {
                    'page': page,
                    'per_page': per_page,
                    'total': total,
                    'pages': (total + per_page - 1) // per_page
                }
            },
            message=f'获取表 {table_name} 数据成功'
        )
        
    except Exception as e:
        return handle_exception(e, context={
            'function': 'get_table_data',
            'table_name': table_name,
            'user_id': current_user.id if current_user else None
        })

@table_management_bp.route('/query', methods=['POST'])
@token_required
def execute_query(current_user):
    """执行自定义SQL查询"""
    try:
        data = request.get_json()
        if not data or 'sql' not in data:
            return error_response('请提供SQL查询语句', status_code=400)
        
        sql = data['sql'].strip()
        if not sql:
            return error_response('SQL查询语句不能为空', status_code=400)
        
        # 安全检查：只允许SELECT语句
        sql_upper = sql.upper().strip()
        if not sql_upper.startswith('SELECT'):
            return error_response('出于安全考虑，只允许执行SELECT查询', status_code=400)
        
        # 检查危险关键词
        dangerous_keywords = ['DROP', 'DELETE', 'UPDATE', 'INSERT', 'ALTER', 'CREATE', 'TRUNCATE']
        for keyword in dangerous_keywords:
            if keyword in sql_upper:
                return error_response(f'查询中包含危险关键词: {keyword}', status_code=400)
        
        # 限制查询结果数量
        limit = data.get('limit', 100)
        limit = min(limit, 1000)  # 最大1000条
        
        # 如果SQL中没有LIMIT，自动添加
        if 'LIMIT' not in sql_upper:
            sql += f' LIMIT {limit}'
        
        with db.engine.connect() as conn:
            result = conn.execute(text(sql))
            rows = result.fetchall()
            columns = [col for col in result.keys()]
            
            # 格式化数据
            formatted_data = []
            for row in rows:
                row_dict = {}
                for i, col in enumerate(columns):
                    value = row[i]
                    if isinstance(value, datetime):
                        value = value.isoformat()
                    elif value is None:
                        value = None
                    else:
                        value = str(value)
                    row_dict[col] = value
                formatted_data.append(row_dict)
        
        logger.info(f"用户 {current_user.username} 执行查询: {sql[:100]}...")
        
        return success_response(
            data={
                'sql': sql,
                'columns': columns,
                'data': formatted_data,
                'row_count': len(formatted_data)
            },
            message='查询执行成功'
        )
        
    except Exception as e:
        logger.error(f"查询执行失败: {str(e)}")
        return handle_exception(e, context={
            'function': 'execute_query',
            'sql': data.get('sql', '') if 'data' in locals() else '',
            'user_id': current_user.id if current_user else None
        })

@table_management_bp.route('/tables/<table_name>/export', methods=['GET'])
@token_required
def export_table_data(current_user, table_name):
    """导出表数据为CSV格式"""
    try:
        inspector = inspect(db.engine)

        # 检查表是否存在
        if table_name not in inspector.get_table_names():
            return error_response(f'表 {table_name} 不存在', status_code=404)

        # 获取导出格式
        format_type = request.args.get('format', 'csv').lower()
        if format_type not in ['csv', 'json']:
            return error_response('支持的导出格式: csv, json', status_code=400)

        # 获取限制参数
        limit = request.args.get('limit', 1000, type=int)
        limit = min(limit, 10000)  # 最大10000条

        with db.engine.connect() as conn:
            # 获取数据
            query = f"SELECT * FROM `{table_name}` LIMIT {limit}"
            result = conn.execute(text(query))
            rows = result.fetchall()
            columns = [col for col in result.keys()]

            if format_type == 'csv':
                import io
                import csv

                output = io.StringIO()
                writer = csv.writer(output)

                # 写入列名
                writer.writerow(columns)

                # 写入数据
                for row in rows:
                    formatted_row = []
                    for value in row:
                        if isinstance(value, datetime):
                            formatted_row.append(value.isoformat())
                        elif value is None:
                            formatted_row.append('')
                        else:
                            formatted_row.append(str(value))
                    writer.writerow(formatted_row)

                csv_data = output.getvalue()
                output.close()

                return success_response(
                    data={
                        'format': 'csv',
                        'content': csv_data,
                        'filename': f'{table_name}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv',
                        'row_count': len(rows)
                    },
                    message=f'导出表 {table_name} 数据成功'
                )

            elif format_type == 'json':
                # 格式化数据为JSON
                formatted_data = []
                for row in rows:
                    row_dict = {}
                    for i, col in enumerate(columns):
                        value = row[i]
                        if isinstance(value, datetime):
                            value = value.isoformat()
                        row_dict[col] = value
                    formatted_data.append(row_dict)

                return success_response(
                    data={
                        'format': 'json',
                        'content': json.dumps(formatted_data, indent=2, ensure_ascii=False),
                        'filename': f'{table_name}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json',
                        'row_count': len(rows)
                    },
                    message=f'导出表 {table_name} 数据成功'
                )

    except Exception as e:
        return handle_exception(e, context={
            'function': 'export_table_data',
            'table_name': table_name,
            'user_id': current_user.id if current_user else None
        })

@table_management_bp.route('/tables/<table_name>/analyze', methods=['GET'])
@token_required
def analyze_table(current_user, table_name):
    """分析表的数据分布和统计信息"""
    try:
        inspector = inspect(db.engine)

        # 检查表是否存在
        if table_name not in inspector.get_table_names():
            return error_response(f'表 {table_name} 不存在', status_code=404)

        # 获取表结构
        columns = inspector.get_columns(table_name)

        analysis_result = {
            'table_name': table_name,
            'total_rows': 0,
            'columns_analysis': []
        }

        with db.engine.connect() as conn:
            # 获取总行数
            total_result = conn.execute(text(f"SELECT COUNT(*) as total FROM `{table_name}`"))
            analysis_result['total_rows'] = total_result.fetchone()[0]

            # 分析每个列
            for col in columns:
                col_name = col['name']
                col_type = str(col['type'])

                col_analysis = {
                    'name': col_name,
                    'type': col_type,
                    'nullable': col['nullable'],
                    'null_count': 0,
                    'unique_count': 0,
                    'sample_values': []
                }

                try:
                    # 获取NULL值数量
                    null_result = conn.execute(text(f"SELECT COUNT(*) as null_count FROM `{table_name}` WHERE `{col_name}` IS NULL"))
                    col_analysis['null_count'] = null_result.fetchone()[0]

                    # 获取唯一值数量
                    unique_result = conn.execute(text(f"SELECT COUNT(DISTINCT `{col_name}`) as unique_count FROM `{table_name}`"))
                    col_analysis['unique_count'] = unique_result.fetchone()[0]

                    # 获取样本值
                    sample_result = conn.execute(text(f"SELECT DISTINCT `{col_name}` FROM `{table_name}` WHERE `{col_name}` IS NOT NULL LIMIT 5"))
                    sample_values = [str(row[0]) for row in sample_result.fetchall()]
                    col_analysis['sample_values'] = sample_values

                    # 数值类型的额外分析
                    if 'INT' in col_type.upper() or 'DECIMAL' in col_type.upper() or 'FLOAT' in col_type.upper():
                        stats_result = conn.execute(text(f"""
                            SELECT
                                MIN(`{col_name}`) as min_val,
                                MAX(`{col_name}`) as max_val,
                                AVG(`{col_name}`) as avg_val
                            FROM `{table_name}`
                            WHERE `{col_name}` IS NOT NULL
                        """))
                        stats = stats_result.fetchone()
                        if stats:
                            col_analysis['min_value'] = str(stats[0]) if stats[0] is not None else None
                            col_analysis['max_value'] = str(stats[1]) if stats[1] is not None else None
                            col_analysis['avg_value'] = f"{float(stats[2]):.2f}" if stats[2] is not None else None

                except Exception as e:
                    logger.warning(f"分析列 {col_name} 时出错: {str(e)}")
                    col_analysis['error'] = str(e)

                analysis_result['columns_analysis'].append(col_analysis)

        return success_response(
            data=analysis_result,
            message=f'分析表 {table_name} 完成'
        )

    except Exception as e:
        return handle_exception(e, context={
            'function': 'analyze_table',
            'table_name': table_name,
            'user_id': current_user.id if current_user else None
        })

# 注册错误处理器
@table_management_bp.errorhandler(Exception)
def handle_table_management_error(error):
    """处理表管理相关错误"""
    logger.error(f"表管理API错误: {str(error)}")
    return error_response('表管理服务异常', status_code=500)
