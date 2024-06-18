import streamlit as st
import sqlite3
import os
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload
import io

# 设置 Google Drive API 凭据
creds = Credentials.from_service_account_info(st.secrets["google_drive"])

# 连接到 Google Drive API
service = build('drive', 'v3', credentials=creds)

# 下载和上传 SQLite 数据库文件的函数
def download_db(file_id, destination):
    request = service.files().get_media(fileId=file_id)
    fh = io.FileIO(destination, 'wb')
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while done is False:
        status, done = downloader.next_chunk()

def upload_db(source, file_id):
    file_metadata = {'name': 'test.db'}
    media = MediaFileUpload(source, mimetype='application/x-sqlite3')
    updated_file = service.files().update(
        fileId=file_id,
        media_body=media
    ).execute()

# Google Drive 文件 ID（你需要手动获取）
db_file_id = '1uZ7_ccqZN7UMWwaYzXYYxCRptYsxegFV'
local_db_path = '/tmp/test.db'

# 下载数据库文件到本地
download_db(db_file_id, local_db_path)

# 连接到本地 SQLite 数据库
conn = sqlite3.connect(local_db_path)
c = conn.cursor()

# 创建一个简单的表单
st.title('Simple Form')

# 获取用户输入
name = st.text_input('Enter your name')
age = st.text_input('Enter your age')

# 按钮提交数据
if st.button('Submit'):
    # 插入数据到数据库
    c.execute("INSERT INTO pets (種類, 編號) VALUES (?, ?)", (name, age))
    conn.commit()
    # 上传数据库文件到 Google Drive
    upload_db(local_db_path, db_file_id)
    st.success('Data submitted successfully!')

# 显示数据库中的数据
st.write('Users in database:')
c.execute("SELECT * FROM pets")
rows = c.fetchall()
for row in rows:
    st.write(f'種類: {row[0]}, 編號: {row[1]}')

# 关闭数据库连接
conn.close()
