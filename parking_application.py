import streamlit as st
import sqlite3
import os
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload
import io
import re
from datetime import datetime
from filelock import FileLock
import time
# 设置 Google Drive API 凭据
creds = Credentials.from_service_account_info(st.secrets["google_drive"])

# 连接到 Google Drive API
service = build('drive', 'v3', credentials=creds)

lockfile_path = "/tmp/operation.lock"
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


def get_quarter(year, month):
    if 1 <= month <= 3:
        quarter = 2
    elif 4 <= month <= 6:
        quarter = 3
    elif 7 <= month <= 9:
        quarter = 4
    elif 10 <= month <= 12:
        year = year + 1
        quarter = 1
    else:
        raise ValueError("Month must be between 1 and 12")
    return year, quarter

def previous_quarters(year, quarter):
    # 計算前兩個季度
    if quarter == 1:
        previous1_year, previous1_quarter = year - 1, 4
        previous2_year, previous2_quarter = year - 1, 3
    elif quarter == 2:
        previous1_year, previous1_quarter = year, 1
        previous2_year, previous2_quarter = year -1 , 4
    elif quarter == 3:
        previous1_year, previous1_quarter = year, 2
        previous2_year, previous2_quarter = year, 1
    elif quarter == 4:
        previous1_year, previous1_quarter = year, 3
        previous2_year, previous2_quarter = year, 2
    return (f"{previous1_year}{previous1_quarter:02}", f"{previous2_year}{previous2_quarter:02}")
def perform_operation(conn, cursor, unit, name, car_number, employee_id, special_needs, contact_info, previous1, previous2, current, local_db_path, db_file_id):
    lock = FileLock(lockfile_path)
    try:
        lock.acquire(timeout=1)
        st.write("資料驗證判斷中，請稍後!")
        time.sleep(3)
        submit_application(conn, cursor, unit, name, car_number, employee_id, special_needs, contact_info, previous1, previous2, current, local_db_path, db_file_id)

        return True
    except TimeoutError:
        st.warning("有操作正在進行，請稍後再試，或聯絡秘書處大樓管理組(6395)。")
        return False
    finally:
        if lock.is_locked:
            lock.release()

# 建立Streamlit表單
def main():
    # 獲取今天的日期
    today = datetime.today()
    year, quarter = get_quarter(today.year, today.month)
    Taiwan_year = year - 1911
    current = f"{Taiwan_year}{quarter:02}"
    # 計算前兩個季度
    previous1, previous2 = previous_quarters(Taiwan_year, quarter)
    st.title('停車抽籤申請表單')
    # Google Drive 文件 ID（你需要手动获取）
    db_file_id = '1AK_T7f_Zr3rhDemyXkwO-Lnk3eTjKlT0'
    local_db_path = '/tmp/test.db'

    # 下载数据库文件到本地
    download_db(db_file_id, local_db_path)

    # 连接到本地 SQLite 数据库
    conn = sqlite3.connect(local_db_path)
    cursor = conn.cursor()

    # 1. 單位
    unit = st.selectbox('(1)請問您所屬單位?', ['秘書處', '公眾服務處'])

    # 2. 大名
    name = st.text_input('(2)請問您的大名?')

    # 3. 愛車車號
    st.write('(3)請問您的愛車車號?')
    col1, col2, col3 = st.columns([1, 0.1, 1])
    with col1:
        car_number_prefix = st.text_input('前半段').upper()
    with col2:
        st.markdown('<h1 style="text-align: center;">-</h1>', unsafe_allow_html=True)
    with col3:
        car_number_suffix = st.text_input('後半段').upper()

    car_number = car_number_prefix +car_number_suffix  # 合併車號

    # 4. 員工編號
    employee_id = st.text_input('(4)請問您的員工編號?')  

    # 5. 特殊需求
    special_needs = st.selectbox('(5)請問是否有特殊需求？', ['一般', '孕婦', '身心障礙'])

    # 6. 公務聯絡方式
    contact_info = st.text_input('(7)請問您的公務聯絡方式?')
    
    st.warning("請確認填寫資料完全無誤後，再點擊'提交'")

    if st.button('提交'):
        perform_operation(conn, cursor, unit, name, car_number, employee_id, special_needs, contact_info, previous1, previous2, current, local_db_path, db_file_id)
    # 關閉cursor和連線
    cursor.close()
    conn.close()

def submit_application(conn, cursor, unit, name, car_number, employee_id, special_needs, contact_info, previous1, previous2, current,local_db_path, db_file_id):
    # 檢查表單是否填寫完整
    try:
        if not unit or not name or not car_number or not employee_id or not special_needs or not contact_info:
            st.error('請填寫完整表單！')
        elif not re.match(r'^[A-Z0-9]+$', car_number):
            st.error('您填寫的車號欄位有誤，請重新填寫')
        else:
            if special_needs == '孕婦':
                status = get_pregnant_record_status(cursor, employee_id, previous1, previous2)  
                if status == 'none':
                    insert_apply(conn, cursor, unit, name, car_number, employee_id, special_needs, contact_info, False, current, local_db_path, db_file_id)
                    st.error('您為第一次孕婦申請，請將相關證明文件(如 :孕婦手冊、行照、駕照)電郵至example@taipower.com.tw')
                elif status == 'only_last_period':
                    if has_approved_car_record(cursor, employee_id, car_number):
                        insert_apply(conn, cursor, unit, name, car_number, employee_id, special_needs, contact_info, True, current, local_db_path, db_file_id)
                        st.success('本期"孕婦"身分停車申請成功')
                    else:
                        insert_apply(conn, cursor, unit, name, car_number, employee_id, special_needs, contact_info, False, current, local_db_path, db_file_id)
                        st.error('這輛車為第一次申請，請將相關證明文件電郵至example@taipower.com.tw')
                else:
                    st.error('您已經過了孕婦申請期限，請將特殊需求改成"一般"後重新申請')
            elif special_needs == '身心障礙':
                cursor.execute("SELECT * FROM 申請紀錄 WHERE 姓名代號 = ? AND 身分註記 = ?", (employee_id, '身心障礙'))
                disable_data = cursor.fetchone()
                if disable_data:
                    if has_approved_car_record(cursor, employee_id, car_number):
                        insert_apply(conn, cursor, unit, name, car_number, employee_id, special_needs, contact_info, True, current, local_db_path, db_file_id)
                        st.success('本期"身心障礙"身分停車申請成功')
                    else:
                        insert_apply(conn, cursor, unit, name, car_number, employee_id, special_needs, contact_info, False, current, local_db_path, db_file_id)
                        st.error('這輛車為第一次申請，請將相關證明文件電郵至example@taipower.com.tw')
                else:
                    insert_apply(conn, cursor, unit, name, car_number, employee_id, special_needs, contact_info, False, current, local_db_path, db_file_id)
                    st.error('您為第一次身心障礙申請，請將相關證明文件(如 :身心障礙證明、行照、駕照)電郵至example@taipower.com.tw')
            else:
                cursor.execute("SELECT * FROM 繳費紀錄 WHERE 姓名代號 = ? AND 期別 = ?", (employee_id, previous1))
                existing_data = cursor.fetchone()
                cursor.execute("SELECT * FROM 申請紀錄 WHERE 姓名代號 = ? AND 身分註記 = ? AND 期別 = ?", (employee_id, '一般', previous1))
                existing_application_data = cursor.fetchone()
                # 在上一期繳費紀錄且申請一般身分代表上期有確定停車
                if existing_data and existing_application_data:
                    st.error('您上期已確認停車，請您下期再來申請停車位!')
                # 代表上期沒有停車
                else:
                    if check_user_eligibility(employee_id, conn, cursor, previous1, previous2):
                        if has_approved_car_record(cursor, employee_id, car_number):
                            insert_apply(conn, cursor, unit, name, car_number, employee_id, '保障', contact_info, True, current, local_db_path, db_file_id)
                            st.success('由於您前兩期申請停車都未抽籤，本期獲得保障資格!')
                        else:
                            insert_apply(conn, cursor, unit, name, car_number, employee_id, '保障', contact_info, False, current, local_db_path, db_file_id)
                            st.error('本期獲得保障資格，但是此車輛為第一次申請，請將相關證明文件電郵至example@taipower.com.tw!')
                    else:
                        status = get_pregnant_record_status(cursor, employee_id, previous1, previous2)  
                        if status == 'only_last_period':
                            if has_approved_car_record(cursor, employee_id, car_number):
                                insert_apply(conn, cursor, unit, name, car_number, employee_id, '孕婦', contact_info, True, current, local_db_path, db_file_id)
                                st.success('由於您上期申請孕婦資格成功，本期將自動替換為孕婦身分申請!')
                            else:
                                insert_apply(conn, cursor, unit, name, car_number, employee_id, '孕婦', contact_info, False, current, local_db_path, db_file_id)
                                st.error('由於您上期已通過孕婦資格申請，這期申請身分資格已改為"孕婦"，另請附車輛證明文件電郵至example@taipower.com.tw')
                        else:
                            if has_approved_car_record(cursor, employee_id, car_number):
                                insert_apply(conn, cursor, unit, name, car_number, employee_id, special_needs, contact_info, True, current, local_db_path, db_file_id)
                                st.success('本期一般車位申請成功!')
                            else:
                                insert_apply(conn, cursor, unit, name, car_number, employee_id, special_needs, contact_info, False , current,local_db_path, db_file_id)
                                st.error('此輛車為第一次申請，請將相關證明文件寄送至example@taipower.com.tw')
    except:
        st.warning("有操作正在進行，請稍後再試，或聯絡秘書處大樓管理組(6395)。")

# 將填寫的資料插入到資料庫
def insert_apply(conn, cursor, unit, name, car_number, employee_id, special_needs, contact_info, car_bind, current, local_db_path, db_file_id):
    # 檢查是否已經存在相同的 (期別, 姓名代號) 記錄
    cursor.execute('''
    SELECT 1 FROM 申請紀錄 WHERE 期別 = ? AND 姓名代號 = ?
    ''', (current, employee_id))
    existing_record = cursor.fetchone()

    if existing_record:
        st.error('您已經在本期提交過申請，請勿重複提交，，如需修正申請資料請聯繫秘書處大樓管理組(分機:6395)!')
        break
    else:
        # 獲取當前日期
        current_date = datetime.now().strftime('%Y-%m-%d')
        cursor.execute('''
        INSERT INTO 申請紀錄 (日期,期別,姓名代號,姓名,單位,車牌號碼,聯絡電話,身分註記,車牌綁定)
        VALUES (?,?,?,?,?,?,?,?,?)
        ''', (current_date, current, employee_id, name, unit, car_number, contact_info, special_needs, car_bind))
        conn.commit()
        upload_db(local_db_path, db_file_id)

def check_user_eligibility(employee_id, conn, cursor,previous1,previous2):
    # 檢查申請紀錄表中是否有前二期別的紀錄
    cursor.execute('''
        SELECT COUNT(*)
        FROM 申請紀錄
        WHERE 姓名代號 = ? AND 期別 IN (?,?)
    ''', (employee_id,previous1,previous2))
    application_periods_count = cursor.fetchone()[0]

    if application_periods_count < 2:
        return False

    # 檢查抽籤繳費表中前二期別的紀錄繳費狀態是否為未繳費
    cursor.execute('''
        SELECT COUNT(*)
        FROM 抽籤繳費
        WHERE 姓名代號 = ? AND 期別 = ? AND 繳費狀態 = '未繳費'
    ''', (employee_id,previous2))
    unpaid_before_last_period = cursor.fetchone()[0]

    cursor.execute('''
        SELECT COUNT(*)
        FROM 抽籤繳費
        WHERE 姓名代號 = ? AND 期別 = ? AND 繳費狀態 = '未繳費'
    ''', (employee_id,previous1))
    unpaid_last_period = cursor.fetchone()[0]

    return unpaid_before_last_period > 0 and unpaid_last_period > 0

def has_approved_car_record(cursor, employee_id, car_number):
    cursor.execute("SELECT * FROM 使用者車牌 WHERE 姓名代號 = ? AND 車牌號碼 = ?", (employee_id, car_number))
    return cursor.fetchone() is not None

def get_pregnant_record_status(cursor, employee_id,last_period,before_last_period):
    cursor.execute('''
        SELECT 期別 FROM 申請紀錄 WHERE 姓名代號 = ? AND 期別 IN (?, ?) AND 身分註記 = ?
    ''', (employee_id, last_period, before_last_period, '孕婦'))
    records = cursor.fetchall()
    periods = [record[0] for record in records]
    
    if last_period in periods and before_last_period in periods:
        return "both"
    elif last_period in periods:
        return "only_last_period"
    elif before_last_period in periods:
        return "only_before_last_period"
    else:
        return "none"

if __name__ == '__main__':
    main()
