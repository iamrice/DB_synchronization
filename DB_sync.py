from binlog2sql import Binlog2sql
from mysql_operator import mysql_operator, Exit, check_binlog_update
import time
from postgresql_operator import postgresql_operator,sync_to_target_db
from pymysqlreplication.row_event import (
    WriteRowsEvent,
    UpdateRowsEvent,
    DeleteRowsEvent,
)

def get_binlog_parser(host='localhost',port=3306,user='root',password='root',database=[],table=[],log_file='mysql-bin.000001'):
	'''
		TODO:
			1. 查找最新的一个 binlog 文件
			2. 根据 binlog 文件名，以及其他参数，创建 binlog 解析器对象
		Args:
			1. 服务器名称、服务器端口、用户名、密码、数据库名、数据表
		Return:
			1. parser
	'''
	args = {'host':host, 'user':user, 'password':password, 'port':port, 
	'start_file':log_file, 'start_pos':4, 'end_file':'', 'end_pos':0, 
	'start_time':'', 'stop_time':'', 'stop_never':False, 'help':False, 
	'databases':database, 'tables':table, 'only_dml':False, 
	'sql_type':['INSERT', 'UPDATE', 'DELETE'], 
	'no_pk':False, 'flashback':False, 'back_interval':1.0}

	conn_setting = {'host': args['host'], 'port': args['port'], 'user': args['user'], 'passwd': args['password'], 'charset': 'utf8'}

	binlog2sql = Binlog2sql(connection_settings=conn_setting, start_file=args['start_file'], start_pos=args['start_pos'],
	                    end_file=args['end_file'], end_pos=args['end_pos'], start_time=args['start_time'],
	                    stop_time=args['stop_time'], only_schemas=args['databases'], only_tables=args['tables'],
	                    no_pk=args['no_pk'], flashback=args['flashback'], stop_never=args['stop_never'],
	                    back_interval=args['back_interval'], only_dml=args['only_dml'], sql_type=args['sql_type'])
	return binlog2sql;


def parse_binlog(parser, start_pos, log_file):
	'''
		TODO:
			1. 使用 parser 获取数据库更新的内容
			注：binlog 解析器只能解析出命令，并不能解析出整个表项，所以需要对那个项目进行改造。
			改造方法是，在 binlog2sql_util.py 文件117行的 if 条件下，读取 row 的内容
			对于 insert 操作，读取 row.values
			对于 update 操作，读取 row.before_values 和 row.after_values
			对于 delete 操作，读取 row.values
			
		Args:
			1. 解析器，起始解析位置，终止解析位置
		Return:
			一个数组，数组的成员是 modify_unit
			modify_unit定义为 {'modify_type': INSERT/DELETE/UPDATE, 'content': [...#该表项的所有内容]}
	'''
	# parser.start_pos=start_pos
	#parser.end_pos=end_pos
	modify_units = []
	events = parser.process_binlog(log_file=log_file,log_pos=start_pos)
	for binlog_event,row in events:
		print(binlog_event.table,row)
		#input()
		if isinstance(binlog_event, WriteRowsEvent):
			modify_units.append({'table':binlog_event.table,'modify_type':'INSERT','after_values':row['values']})
		if isinstance(binlog_event, DeleteRowsEvent):
			modify_units.append({'table':binlog_event.table,'modify_type':'DELETE','before_values':row['values']})
		if isinstance(binlog_event, UpdateRowsEvent):
			modify_units.append({'table':binlog_event.table,'modify_type':'UPDATE','before_values':row['before_values'],'after_values':row['after_values']})

	return modify_units


def filter_sync_content(rule, modify_unit, target_db):
	'''
		TODO:
			1. 根据源端修改的表项，以及 rule 中的 search_title, 找到目标端中需要修改的表项的主键
			2. 根据源端修改的表项，以及 rule 中的 update_title, 过滤出需要修改的内容
		Args:
			1. rule
			2. modify_unit 
			3. target_db
		Return:
			1. 一个字典：{type:'', update_items:[],update_content:{}}，字典中的两个成员分别对应 TODO 中的两部分
			e.g.{type:'update',update_items:['001','008'],update_content:{'course':'math','time':'monday'}} 注：course和time应当是目标端的属性名，不是源端的。
			e.g.{type:'insert',update_items:[],update_content:{'course':'math','time':'monday'}}
			e.g.{type:'delete',update_items:['001','008'],update_content:{}}
	'''
	if(rule['sourse_table']!=modify_unit['table']):
		return 0
	if(modify_unit['modify_type'] not in rule['action']):
		return 0

	update_items = []
	update_content = {}

	if modify_unit['table']=='course':
		if modify_unit['modify_type']=='DELETE' or modify_unit['modify_type']=='UPDATE':
			search_query = 'select ' + target_db.primary_key + ' from ' + target_db.table
			first_item = True
			for source_key,target_key in rule['search_keys'].items():
				if first_item==True:
					search_query += ' where '
					first_item = False
				else:
					search_query += ' and '
				# print(modify_unit)
				search_query += target_key + ' = ' + str(modify_unit['before_values'][source_key])
			update_items = target_db.pgsSelect(search_query)

		if modify_unit['modify_type']=='INSERT' or modify_unit['modify_type']=='UPDATE':
			for source_key,target_key in rule['update_keys'].items():
				update_content[target_key] = modify_unit['after_values'][source_key]

		return {'type':modify_unit['modify_type'],'update_items':update_items,'update_content':update_content}

	elif modify_unit['table']=='teacher':
		search_query = 'select ' + target_db.primary_key + ' from ' + target_db.table + ' where teacher_id=' + str(modify_unit['after_values']['id'] )
		update_items = target_db.pgsSelect(search_query)
		# print(search_query,update_items)

		for source_key,target_key in rule['update_keys'].items():
			update_content[target_key] = modify_unit['after_values'][source_key]

		return {'type':'UPDATE','update_items':update_items,'update_content':update_content}


def main():
	# 初始化解析器、操作器
	target_db = postgresql_operator(password='Aa15816601051')
	source_db = mysql_operator(passwd='root',database='db01')

	[file,length] = check_binlog_update(source_db)
	print(file,length)
	parser = get_binlog_parser('localhost',3306,'root','root',['db01'],['course','teacher'],file)

	# 初始化同步规则(在1.0 版本只考虑一个规则，后续视情况拓展)
	# e.g. {'search_keys':[{'course':'myCourse'}],update_keys:[{'time':'course_time'}]} 每一个键值对的键代表源端的key，值代表目标端的key
	sync_rule = [{
				'sourse_table':'course',
				'target_table':'senior_course',
				'action':['UPDATE',	'INSERT','DELETE'],
				'search_keys':{'id':'course_id'},
				'update_keys':{'id':'course_id','name':'course_name','start_time':'course_start_time','end_time':'course_end_time','teacher_id':'teacher_id'}
				},{				
				'sourse_table':'teacher',
				'target_table':'senior_course',
				'action':['UPDATE','INSERT'],
				'search_keys':{'id':'teacher_id'},
				'update_keys':{'id':'teacher_id','name':'teacher_name','introduction':'teacher_introduction','photo':'teacher_photo'}				
				}]

	
	# 初始化读取位置
	start_pos = 0
	end_pos = 4
	# 初始化同步间隔(ms)
	sync_interval = 600

	print("\n")
	print("WELCOME TO THE DATABASE SYNCHRONIZATION TOOL!")
	print("You can enter 'help' to get the usage of all the commands.\n")
	while(True):
		com = input("DB Sync tool@SCUT:")
		if com == "help":
			print("Commands:")
			print("help   ---   show help menu ")
			print("run    ---   run the synchronization ") 
			print("exit   ---   exit the tool ")

		elif com == "run":
			[file,length] = check_binlog_update(source_db)
			if(length > end_pos):
				# 解析更新内容
				start_pos = end_pos
				end_pos = length
				# print('file_pos',start_pos,end_pos)
				modify_units = parse_binlog(parser, start_pos, file)
				# print('modify_units',modify_units)
				# 过滤,同步
				for unit in modify_units:
					for rule in sync_rule:
						update_unit = filter_sync_content(rule,unit,target_db)
						if update_unit!=0:
							print('update_unit',update_unit)
							sync_to_target_db(update_unit,target_db)
		else:
			break;
	
	Exit(source_db)


if __name__ == '__main__':
	main()
