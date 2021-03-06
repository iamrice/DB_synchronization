import pymysql
from pymysql import cursors

class mysql_operator:
	'''
		TODO:
			实现两个函数
			1. 构造函数：创建数据库连接
			2. flush binlog
	'''
	def __init__(self,host = 'localhost',user = 'root',passwd='6002920.Qy',port = 3306,database = 'test_db'):
		self.conn=pymysql.connect(host =host,user =user,passwd=passwd,port =port,database = database)

	def flush_binlog(self):
		cursor = self.conn.cursor()
		#sql = "insert into student values(1003,'name3') "
		#print(cursor.execute(sql))
		sql3 = "flush logs"
		try:
			cursor.execute(sql3)
			self.conn.commit()
		except:
			self.conn.rollback()
		
		#self.conn.commit()
		#sql2 = "show master logs"
		#cursor.fetchall(sql2)
	
	def _del_(self):
		self.conn.close()
    

def Exit(source_db):
	'''
		TODO:
			通过 flush log 命令刷新 binlog，使得下一次访问时 binlog 是一个全新的日志文件。
		Args:
			none
		Return:
			none
	'''
	source_db.flush_binlog()
    

    

def check_binlog_update(mysql_operator):
	'''
		TODO:
			1. 检查 binlog 文件大小是否大于 end_pos
		Args:
			1. parser: binlog 解析器
			2. end_pos
		Return:
			1. 如果文件相比上一次有所变动，则返回当前文件大小
			2. 如果没有变动，则返回 0
	'''
	sql = "show master status"
	cursor = mysql_operator.conn.cursor()
	#cursor = parser.conn.cursor()
	cursor.execute(sql)
	binlog_tuple = cursor.fetchall()
	file_size = binlog_tuple[0][1]
	return [binlog_tuple[0][0],binlog_tuple[0][1]]
	# print(binlog_tuple,file_size)
	# if file_size > end_pos:
	# 	return file_size
	# else:
	# 	return 0



#src_db = mysql_operator()
#src_db.flush_binlog()
#print(check_binlog_update(src_db,3))
