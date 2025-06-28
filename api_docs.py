# -*- coding: utf-8 -*-
"""
API 文档系统 - 类似 Swagger
提供完整的 API 文档和测试界面
"""
from flask import Flask, render_template_string
from flask_restx import Api, Resource, fields
import json

def create_api_docs(app):
    """创建 API 文档"""
    
    # 创建 API 文档实例
    api = Api(
        app,
        version='1.0',
        title='EduBrain AI 数据库管理 API',
        description='完整的数据库管理和监控 API 文档',
        doc='/api/docs/',  # Swagger UI 路径
        prefix='/api'
    )
    
    # 定义命名空间
    db_monitor_ns = api.namespace('db-monitor', description='数据库监控接口')
    table_mgmt_ns = api.namespace('table-management', description='数据表管理接口')
    
    # 定义数据模型
    db_stats_model = api.model('DatabaseStats', {
        'pool_stats': fields.Raw(description='连接池统计'),
        'query_stats': fields.Raw(description='查询统计'),
        'performance_metrics': fields.Raw(description='性能指标')
    })
    
    connection_test_model = api.model('ConnectionTest', {
        'database_info': fields.Raw(description='数据库信息'),
        'connection_time': fields.Float(description='连接时间(毫秒)'),
        'database_version': fields.String(description='数据库版本'),
        'connection_status': fields.String(description='连接状态')
    })
    
    table_list_model = api.model('TableList', {
        'tables': fields.List(fields.Raw, description='表列表'),
        'total': fields.Integer(description='表总数')
    })
    
    table_structure_model = api.model('TableStructure', {
        'table_name': fields.String(description='表名'),
        'columns': fields.List(fields.Raw, description='列信息'),
        'indexes': fields.List(fields.Raw, description='索引信息'),
        'foreign_keys': fields.List(fields.Raw, description='外键信息')
    })
    
    query_request_model = api.model('QueryRequest', {
        'sql': fields.String(required=True, description='SQL查询语句'),
        'limit': fields.Integer(description='结果限制数量', default=100)
    })
    
    query_result_model = api.model('QueryResult', {
        'sql': fields.String(description='执行的SQL'),
        'columns': fields.List(fields.String, description='列名'),
        'data': fields.List(fields.Raw, description='查询结果'),
        'row_count': fields.Integer(description='结果行数')
    })
    
    # 数据库监控接口
    @db_monitor_ns.route('/stats')
    class DatabaseStats(Resource):
        @db_monitor_ns.doc('get_database_stats')
        @db_monitor_ns.marshal_with(db_stats_model)
        def get(self):
            """获取数据库统计信息"""
            return {
                'pool_stats': {
                    'pool_size': 10,
                    'active_connections': 3,
                    'overflow_connections': 0
                },
                'query_stats': {
                    'total_queries': 1250,
                    'slow_queries': 5,
                    'avg_query_time': 45.2
                }
            }
    
    @db_monitor_ns.route('/test-connection')
    class ConnectionTest(Resource):
        @db_monitor_ns.doc('test_database_connection')
        @db_monitor_ns.marshal_with(connection_test_model)
        def post(self):
            """测试数据库连接"""
            return {
                'database_info': {
                    'host': 'interchange.proxy.rlwy.net',
                    'port': 49225,
                    'database': 'railway'
                },
                'connection_time': 45.67,
                'database_version': '8.0.35',
                'connection_status': 'success'
            }
    
    @db_monitor_ns.route('/health')
    class DatabaseHealth(Resource):
        @db_monitor_ns.doc('get_database_health')
        def get(self):
            """获取数据库健康状态"""
            return {
                'status': 'healthy',
                'uptime': '7 days, 14:32:15',
                'connections': {
                    'active': 3,
                    'max': 100,
                    'usage_percent': 3.0
                }
            }
    
    @db_monitor_ns.route('/optimize')
    class OptimizationRecommendations(Resource):
        @db_monitor_ns.doc('get_optimization_recommendations')
        def get(self):
            """获取数据库优化建议"""
            return {
                'recommendations': [
                    '数据库状态良好，建议定期监控性能指标',
                    '考虑定期备份重要数据'
                ],
                'optimization_score': 85,
                'database_analysis': {
                    'large_tables': [],
                    'total_fragmentation_mb': 0
                }
            }
    
    # 表管理接口
    @table_mgmt_ns.route('/tables')
    class TableList(Resource):
        @table_mgmt_ns.doc('get_table_list')
        @table_mgmt_ns.marshal_with(table_list_model)
        def get(self):
            """获取所有数据表列表"""
            return {
                'tables': [
                    {'name': 'users', 'columns': 8, 'rows': 1250},
                    {'name': 'orders', 'columns': 12, 'rows': 5680}
                ],
                'total': 2
            }
    
    @table_mgmt_ns.route('/tables/<string:table_name>/structure')
    class TableStructure(Resource):
        @table_mgmt_ns.doc('get_table_structure')
        @table_mgmt_ns.marshal_with(table_structure_model)
        def get(self, table_name):
            """获取表结构信息"""
            return {
                'table_name': table_name,
                'columns': [
                    {
                        'name': 'id',
                        'type': 'INT',
                        'nullable': False,
                        'primary_key': True
                    }
                ],
                'indexes': [],
                'foreign_keys': []
            }
    
    @table_mgmt_ns.route('/tables/<string:table_name>/data')
    class TableData(Resource):
        @table_mgmt_ns.doc('get_table_data')
        @table_mgmt_ns.param('page', '页码', type='integer', default=1)
        @table_mgmt_ns.param('per_page', '每页数量', type='integer', default=20)
        @table_mgmt_ns.param('order_by', '排序字段', type='string')
        @table_mgmt_ns.param('order_direction', '排序方向', type='string', enum=['ASC', 'DESC'])
        def get(self, table_name):
            """获取表数据（分页）"""
            return {
                'table_name': table_name,
                'columns': ['id', 'name', 'email'],
                'data': [
                    {'id': 1, 'name': 'John', 'email': 'john@example.com'}
                ],
                'pagination': {
                    'page': 1,
                    'per_page': 20,
                    'total': 1,
                    'pages': 1
                }
            }
    
    @table_mgmt_ns.route('/query')
    class QueryExecution(Resource):
        @table_mgmt_ns.doc('execute_query')
        @table_mgmt_ns.expect(query_request_model)
        @table_mgmt_ns.marshal_with(query_result_model)
        def post(self):
            """执行自定义SQL查询"""
            return {
                'sql': 'SELECT * FROM users LIMIT 10',
                'columns': ['id', 'name', 'email'],
                'data': [
                    {'id': 1, 'name': 'John', 'email': 'john@example.com'}
                ],
                'row_count': 1
            }
    
    @table_mgmt_ns.route('/tables/<string:table_name>/optimize')
    class TableOptimize(Resource):
        @table_mgmt_ns.doc('optimize_table')
        def post(self, table_name):
            """优化表"""
            return {
                'table_name': table_name,
                'operation': 'optimize',
                'results': [
                    {
                        'table': table_name,
                        'op': 'optimize',
                        'msg_type': 'status',
                        'msg_text': 'OK'
                    }
                ]
            }
    
    return api

def create_custom_api_docs():
    """创建自定义 API 文档页面"""
    
    api_docs_html = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>EduBrain AI 数据库管理 API 文档</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }
        .container { max-width: 1200px; margin: 0 auto; background: white; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 8px 8px 0 0; }
        .content { padding: 30px; }
        .endpoint { margin-bottom: 30px; border: 1px solid #e1e5e9; border-radius: 6px; overflow: hidden; }
        .endpoint-header { background: #f8f9fa; padding: 15px; border-bottom: 1px solid #e1e5e9; }
        .method { display: inline-block; padding: 4px 8px; border-radius: 4px; font-weight: bold; margin-right: 10px; }
        .get { background: #61affe; color: white; }
        .post { background: #49cc90; color: white; }
        .endpoint-body { padding: 20px; }
        .params { margin-top: 15px; }
        .param { margin-bottom: 10px; padding: 10px; background: #f8f9fa; border-radius: 4px; }
        .response { margin-top: 15px; }
        .code { background: #f4f4f4; padding: 15px; border-radius: 4px; overflow-x: auto; }
        .nav { background: #f8f9fa; padding: 20px; border-bottom: 1px solid #e1e5e9; }
        .nav a { margin-right: 20px; text-decoration: none; color: #495057; font-weight: 500; }
        .nav a:hover { color: #007bff; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🗄️ EduBrain AI 数据库管理 API</h1>
            <p>完整的数据库管理和监控 API 文档 - 所有接口无需认证</p>
        </div>
        
        <div class="nav">
            <a href="#db-monitor">数据库监控</a>
            <a href="#table-management">表管理</a>
            <a href="/api/docs/">Swagger UI</a>
        </div>
        
        <div class="content">
            <h2 id="db-monitor">📊 数据库监控接口</h2>
            
            <div class="endpoint">
                <div class="endpoint-header">
                    <span class="method post">POST</span>
                    <strong>/api/db-monitor/test-connection</strong>
                    <span style="color: #6c757d;">测试数据库连接</span>
                </div>
                <div class="endpoint-body">
                    <p>测试数据库连接状态，获取连接信息和性能指标。</p>
                    <div class="response">
                        <strong>响应示例：</strong>
                        <div class="code">
{
  "success": true,
  "data": {
    "database_info": {
      "host": "interchange.proxy.rlwy.net",
      "port": 49225,
      "database": "railway"
    },
    "connection_time": 45.67,
    "database_version": "8.0.35",
    "connection_status": "success"
  }
}
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="endpoint">
                <div class="endpoint-header">
                    <span class="method get">GET</span>
                    <strong>/api/db-monitor/stats</strong>
                    <span style="color: #6c757d;">获取数据库统计</span>
                </div>
                <div class="endpoint-body">
                    <p>获取数据库连接池统计、查询统计和性能指标。</p>
                </div>
            </div>
            
            <h2 id="table-management">🗄️ 表管理接口</h2>
            
            <div class="endpoint">
                <div class="endpoint-header">
                    <span class="method get">GET</span>
                    <strong>/api/table-management/tables</strong>
                    <span style="color: #6c757d;">获取所有表</span>
                </div>
                <div class="endpoint-body">
                    <p>获取数据库中所有表的列表和基本信息。</p>
                </div>
            </div>
            
            <div class="endpoint">
                <div class="endpoint-header">
                    <span class="method post">POST</span>
                    <strong>/api/table-management/query</strong>
                    <span style="color: #6c757d;">执行SQL查询</span>
                </div>
                <div class="endpoint-body">
                    <p>执行自定义的SELECT查询语句。</p>
                    <div class="params">
                        <strong>请求参数：</strong>
                        <div class="param">
                            <strong>sql</strong> (string, required): SQL查询语句
                        </div>
                        <div class="param">
                            <strong>limit</strong> (integer, optional): 结果限制数量，默认100
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</body>
</html>
    """
    
    return api_docs_html
