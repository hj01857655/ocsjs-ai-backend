# -*- coding: utf-8 -*-
"""
数据表管理接口
提供数据表的查看、管理、查询等功能
"""
from flask import Blueprint, request, jsonify
from sqlalchemy import text, inspect
# from utils.auth import token_required  # 暂时移除认证
from utils.response_handler import success_response, error_response, handle_exception
from utils.logger import get_logger
from models.models import db
import json
from datetime import datetime

logger = get_logger(__name__)

table_management_bp = Blueprint('table_management', __name__, url_prefix='/api/table-management')

@table_management_bp.route('/tables', methods=['GET'])
def get_tables():
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
            'user_id': None
        })

@table_management_bp.route('/tables/<table_name>/structure', methods=['GET'])
def get_table_structure(table_name):
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
            'user_id': None
        })

@table_management_bp.route('/tables/<table_name>/data', methods=['GET'])
def get_table_data(table_name):
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
            'user_id': None
        })

@table_management_bp.route('/query', methods=['POST'])
def execute_query():
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
        
        logger.info(f"执行查询: {sql[:100]}...")
        
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
            'user_id': None
        })

@table_management_bp.route('/tables/<table_name>/export', methods=['GET'])
def export_table_data(table_name):
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
            'user_id': None
        })

@table_management_bp.route('/tables/<table_name>/analyze', methods=['GET'])
def analyze_table(table_name):
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
            'user_id': None
        })

@table_management_bp.route('/tables/<table_name>/columns', methods=['GET'])
def get_table_columns(table_name):
    """获取表的列信息"""
    try:
        inspector = inspect(db.engine)

        # 检查表是否存在
        if table_name not in inspector.get_table_names():
            return error_response(f'表 {table_name} 不存在', status_code=404)

        # 获取列信息
        columns = inspector.get_columns(table_name)
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
                'primary_key': col['name'] in primary_keys.get('constrained_columns', []),
                'comment': col.get('comment', '')
            })

        return success_response(
            data={
                'table_name': table_name,
                'columns': formatted_columns,
                'total_columns': len(formatted_columns)
            },
            message=f'获取表 {table_name} 列信息成功'
        )

    except Exception as e:
        return handle_exception(e, context={
            'function': 'get_table_columns',
            'table_name': table_name,
            'user_id': None
        })

@table_management_bp.route('/tables/<table_name>/indexes', methods=['GET'])
def get_table_indexes(table_name):
    """获取表的索引信息"""
    try:
        inspector = inspect(db.engine)

        # 检查表是否存在
        if table_name not in inspector.get_table_names():
            return error_response(f'表 {table_name} 不存在', status_code=404)

        # 获取索引信息
        indexes = inspector.get_indexes(table_name)
        primary_key = inspector.get_pk_constraint(table_name)

        # 格式化索引信息
        formatted_indexes = []

        # 添加主键信息
        if primary_key and primary_key.get('constrained_columns'):
            formatted_indexes.append({
                'name': primary_key.get('name', 'PRIMARY'),
                'type': 'PRIMARY KEY',
                'columns': primary_key['constrained_columns'],
                'unique': True,
                'comment': '主键索引'
            })

        # 添加其他索引
        for idx in indexes:
            formatted_indexes.append({
                'name': idx['name'],
                'type': 'UNIQUE' if idx['unique'] else 'INDEX',
                'columns': idx['column_names'],
                'unique': idx['unique'],
                'comment': '唯一索引' if idx['unique'] else '普通索引'
            })

        return success_response(
            data={
                'table_name': table_name,
                'indexes': formatted_indexes,
                'total_indexes': len(formatted_indexes)
            },
            message=f'获取表 {table_name} 索引信息成功'
        )

    except Exception as e:
        return handle_exception(e, context={
            'function': 'get_table_indexes',
            'table_name': table_name,
            'user_id': None
        })

@table_management_bp.route('/execute-sql', methods=['POST'])
def execute_sql():
    """执行SQL语句（兼容旧接口名称）"""
    try:
        data = request.get_json()
        if not data or 'sql' not in data:
            return error_response('请提供SQL查询语句', status_code=400)

        # 重定向到新的查询接口
        return execute_query()

    except Exception as e:
        return handle_exception(e, context={
            'function': 'execute_sql',
            'user_id': None
        })

@table_management_bp.route('/tables/<table_name>/optimize', methods=['POST'])
def optimize_table(table_name):
    """优化表"""
    try:
        inspector = inspect(db.engine)

        # 检查表是否存在
        if table_name not in inspector.get_table_names():
            return error_response(f'表 {table_name} 不存在', status_code=404)

        with db.engine.connect() as conn:
            # 执行表优化
            result = conn.execute(text(f"OPTIMIZE TABLE `{table_name}`"))
            optimize_result = result.fetchall()

            # 格式化结果
            formatted_result = []
            for row in optimize_result:
                formatted_result.append({
                    'table': row[0] if len(row) > 0 else table_name,
                    'op': row[1] if len(row) > 1 else 'optimize',
                    'msg_type': row[2] if len(row) > 2 else 'status',
                    'msg_text': row[3] if len(row) > 3 else 'OK'
                })

        logger.info(f"用户 {anonymous} 优化了表 {table_name}")

        return success_response(
            data={
                'table_name': table_name,
                'operation': 'optimize',
                'results': formatted_result
            },
            message=f'表 {table_name} 优化完成'
        )

    except Exception as e:
        return handle_exception(e, context={
            'function': 'optimize_table',
            'table_name': table_name,
            'user_id': None
        })

@table_management_bp.route('/tables/<table_name>/repair', methods=['POST'])
def repair_table(table_name):
    """修复表"""
    try:
        inspector = inspect(db.engine)

        # 检查表是否存在
        if table_name not in inspector.get_table_names():
            return error_response(f'表 {table_name} 不存在', status_code=404)

        with db.engine.connect() as conn:
            # 执行表修复
            result = conn.execute(text(f"REPAIR TABLE `{table_name}`"))
            repair_result = result.fetchall()

            # 格式化结果
            formatted_result = []
            for row in repair_result:
                formatted_result.append({
                    'table': row[0] if len(row) > 0 else table_name,
                    'op': row[1] if len(row) > 1 else 'repair',
                    'msg_type': row[2] if len(row) > 2 else 'status',
                    'msg_text': row[3] if len(row) > 3 else 'OK'
                })

        logger.info(f"用户 {anonymous} 修复了表 {table_name}")

        return success_response(
            data={
                'table_name': table_name,
                'operation': 'repair',
                'results': formatted_result
            },
            message=f'表 {table_name} 修复完成'
        )

    except Exception as e:
        return handle_exception(e, context={
            'function': 'repair_table',
            'table_name': table_name,
            'user_id': None
        })

@table_management_bp.route('/tables/<table_name>/check', methods=['POST'])
def check_table(table_name):
    """检查表完整性"""
    try:
        inspector = inspect(db.engine)

        # 检查表是否存在
        if table_name not in inspector.get_table_names():
            return error_response(f'表 {table_name} 不存在', status_code=404)

        with db.engine.connect() as conn:
            # 执行表检查
            result = conn.execute(text(f"CHECK TABLE `{table_name}`"))
            check_result = result.fetchall()

            # 格式化结果
            formatted_result = []
            for row in check_result:
                formatted_result.append({
                    'table': row[0] if len(row) > 0 else table_name,
                    'op': row[1] if len(row) > 1 else 'check',
                    'msg_type': row[2] if len(row) > 2 else 'status',
                    'msg_text': row[3] if len(row) > 3 else 'OK'
                })

        logger.info(f"用户 {anonymous} 检查了表 {table_name}")

        return success_response(
            data={
                'table_name': table_name,
                'operation': 'check',
                'results': formatted_result
            },
            message=f'表 {table_name} 检查完成'
        )

    except Exception as e:
        return handle_exception(e, context={
            'function': 'check_table',
            'table_name': table_name,
            'user_id': None
        })

@table_management_bp.route('/tables/<table_name>/truncate', methods=['POST'])
def truncate_table(table_name):
    """清空表数据（危险操作）"""
    try:
        # 安全检查：只有管理员可以执行
        if not True:
            return error_response('只有管理员可以执行清空表操作', status_code=403)

        inspector = inspect(db.engine)

        # 检查表是否存在
        if table_name not in inspector.get_table_names():
            return error_response(f'表 {table_name} 不存在', status_code=404)

        # 获取确认参数
        data = request.get_json() or {}
        confirm = data.get('confirm', False)

        if not confirm:
            return error_response('请确认要清空表数据，设置 confirm: true', status_code=400)

        # 获取清空前的行数
        with db.engine.connect() as conn:
            count_result = conn.execute(text(f"SELECT COUNT(*) as count FROM `{table_name}`"))
            original_count = count_result.fetchone()[0]

            # 执行清空操作
            conn.execute(text(f"TRUNCATE TABLE `{table_name}`"))
            conn.commit()

        logger.warning(f"管理员 {anonymous} 清空了表 {table_name}，原有 {original_count} 行数据")

        return success_response(
            data={
                'table_name': table_name,
                'operation': 'truncate',
                'original_rows': original_count,
                'current_rows': 0
            },
            message=f'表 {table_name} 已清空，删除了 {original_count} 行数据'
        )

    except Exception as e:
        return handle_exception(e, context={
            'function': 'truncate_table',
            'table_name': table_name,
            'user_id': None
        })

@table_management_bp.route('/tables/<table_name>/size', methods=['GET'])
def get_table_size(table_name):
    """获取表大小信息"""
    try:
        inspector = inspect(db.engine)

        # 检查表是否存在
        if table_name not in inspector.get_table_names():
            return error_response(f'表 {table_name} 不存在', status_code=404)

        with db.engine.connect() as conn:
            # 获取表大小信息
            size_query = text("""
                SELECT
                    table_name,
                    table_rows,
                    data_length,
                    index_length,
                    (data_length + index_length) as total_length,
                    avg_row_length,
                    auto_increment
                FROM information_schema.tables
                WHERE table_schema = DATABASE()
                AND table_name = :table_name
            """)

            result = conn.execute(size_query, {'table_name': table_name})
            row = result.fetchone()

            if not row:
                return error_response(f'无法获取表 {table_name} 的大小信息', status_code=404)

            # 格式化大小信息
            def format_bytes(bytes_value):
                if bytes_value is None:
                    return "0 B"

                for unit in ['B', 'KB', 'MB', 'GB']:
                    if bytes_value < 1024.0:
                        return f"{bytes_value:.2f} {unit}"
                    bytes_value /= 1024.0
                return f"{bytes_value:.2f} TB"

            size_info = {
                'table_name': row[0],
                'rows': row[1] or 0,
                'data_size': row[2] or 0,
                'index_size': row[3] or 0,
                'total_size': row[4] or 0,
                'avg_row_length': row[5] or 0,
                'auto_increment': row[6],
                'formatted': {
                    'data_size': format_bytes(row[2] or 0),
                    'index_size': format_bytes(row[3] or 0),
                    'total_size': format_bytes(row[4] or 0),
                    'avg_row_length': format_bytes(row[5] or 0)
                }
            }

        return success_response(
            data=size_info,
            message=f'获取表 {table_name} 大小信息成功'
        )

    except Exception as e:
        return handle_exception(e, context={
            'function': 'get_table_size',
            'table_name': table_name,
            'user_id': None
        })

@table_management_bp.route('/database/info', methods=['GET'])
def get_database_info():
    """获取数据库整体信息"""
    try:
        with db.engine.connect() as conn:
            # 获取数据库基本信息
            db_info_query = text("""
                SELECT
                    SCHEMA_NAME as database_name,
                    DEFAULT_CHARACTER_SET_NAME as charset,
                    DEFAULT_COLLATION_NAME as collation
                FROM information_schema.SCHEMATA
                WHERE SCHEMA_NAME = DATABASE()
            """)

            db_result = conn.execute(db_info_query)
            db_row = db_result.fetchone()

            # 获取表统计信息
            tables_query = text("""
                SELECT
                    COUNT(*) as table_count,
                    SUM(table_rows) as total_rows,
                    SUM(data_length) as total_data_size,
                    SUM(index_length) as total_index_size,
                    SUM(data_length + index_length) as total_size
                FROM information_schema.tables
                WHERE table_schema = DATABASE()
            """)

            tables_result = conn.execute(tables_query)
            tables_row = tables_result.fetchone()

            # 获取数据库版本
            version_result = conn.execute(text("SELECT VERSION() as version"))
            version = version_result.fetchone()[0]

            # 格式化大小
            def format_bytes(bytes_value):
                if bytes_value is None:
                    return "0 B"

                for unit in ['B', 'KB', 'MB', 'GB']:
                    if bytes_value < 1024.0:
                        return f"{bytes_value:.2f} {unit}"
                    bytes_value /= 1024.0
                return f"{bytes_value:.2f} TB"

            database_info = {
                'database_name': db_row[0] if db_row else 'Unknown',
                'charset': db_row[1] if db_row else 'Unknown',
                'collation': db_row[2] if db_row else 'Unknown',
                'version': version,
                'statistics': {
                    'table_count': tables_row[0] or 0,
                    'total_rows': tables_row[1] or 0,
                    'total_data_size': tables_row[2] or 0,
                    'total_index_size': tables_row[3] or 0,
                    'total_size': tables_row[4] or 0,
                    'formatted': {
                        'total_data_size': format_bytes(tables_row[2] or 0),
                        'total_index_size': format_bytes(tables_row[3] or 0),
                        'total_size': format_bytes(tables_row[4] or 0)
                    }
                }
            }

        return success_response(
            data=database_info,
            message='获取数据库信息成功'
        )

    except Exception as e:
        return handle_exception(e, context={
            'function': 'get_database_info',
            'user_id': None
        })

# 注册错误处理器
@table_management_bp.errorhandler(Exception)
def handle_table_management_error(error):
    """处理表管理相关错误"""
    logger.error(f"表管理API错误: {str(error)}")
    return error_response('表管理服务异常', status_code=500)
