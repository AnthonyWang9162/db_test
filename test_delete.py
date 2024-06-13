import sqlite3
import streamlit as st
import os

# 获取数据库 URL
db_url = st.secrets["connections"]["pets_db"]["url"]
db_path = db_url.replace("sqlite:///", "")

# 连接到 SQLite 数据库
conn = sqlite3.connect(db_path)
c = conn.cursor()

# 创建一个简单的表单
st.title('Simple Form')

# 获取用户输入
name = st.text_input('Enter your name')
age = st.number_input('Enter your age', min_value=0)

# 按钮提交数据
if st.button('Submit'):
    c.execute("DELETE FROM pets  WHERE 種類 = ?, 編號 = ?)", (name, age))
    conn.commit()
    st.success('Data submitted successfully!')

# 显示数据库中的数据
st.write('Users in database:')
c.execute("SELECT * FROM pets")
rows = c.fetchall()
for row in rows:
    st.write(f'種類: {row[0]}, 編號: {row[1]}')

# 关闭数据库连接
conn.close()
