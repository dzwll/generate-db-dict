SELECT
  a.TABLE_NAME 表名,
  b.TABLE_COMMENT 表备注,
  a.COLUMN_NAME 列名,
  a.COLUMN_TYPE 数据类型,
  a.DATA_TYPE 字段类型,
  a.CHARACTER_MAXIMUM_LENGTH 长度,
  a.IS_NULLABLE 是否为空,
  a.COLUMN_DEFAULT 默认值,
  a.COLUMN_COMMENT 备注 
FROM
INFORMATION_SCHEMA.COLUMNS a,information_schema.TABLES b
where
a.table_schema ='库名'  and   a.TABLE_NAME='表名'
and a.TABLE_NAME=b.TABLE_NAME
order by a.TABLE_NAME;
