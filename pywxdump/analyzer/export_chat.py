# -*- coding: utf-8 -*-#
# -------------------------------------------------------------------------------
# Name:         export_chat.py
# Description:  
# Author:       xaoyaoo
# Date:         2023/12/03
# -------------------------------------------------------------------------------
# -*- coding: utf-8 -*-#
# -------------------------------------------------------------------------------
# Name:         GUI.py
# Description:
# Author:       xaoyaoo
# Date:         2023/11/10
# -------------------------------------------------------------------------------
import re
import sqlite3
import os
import json
import time
from functools import wraps

from .utils import get_md5, attach_databases, execute_sql, get_type_name, match_BytesExtra
from .db_parsing import parse_xml_string, decompress_CompressContent, read_BytesExtra


def get_contact_list(MicroMsg_db_path):
    """
    获取联系人列表
    :param MicroMsg_db_path: MicroMsg.db 文件路径
    :return: 联系人列表
    """
    users = []
    # 连接 MicroMsg.db 数据库，并执行查询
    db = sqlite3.connect(MicroMsg_db_path)
    cursor = db.cursor()
    sql = ("SELECT A.UserName, A.NickName, A.Remark,A.Alias,A.Reserved6,B.bigHeadImgUrl "
           "FROM Contact A,ContactHeadImgUrl B "
           "where UserName==usrName "
           "ORDER BY NickName ASC;")
    cursor.execute(sql)
    result = cursor.fetchall()

    for row in result:
        # 获取用户名、昵称、备注和聊天记录数量
        username, nickname, remark, Alias, describe, headImgUrl = row
        users.append(
            {"username": username, "nickname": nickname, "remark": remark, "account": Alias, "describe": describe,
             "headImgUrl": headImgUrl})
    cursor.close()
    db.close()
    return users


def get_chatroom_list(MicroMsg_db_path):
    """
    获取群聊列表
    :param MicroMsg_db_path: MicroMsg.db 文件路径
    :return: 群聊列表
    """
    rooms = []
    # 连接 MicroMsg.db 数据库，并执行查询
    db = sqlite3.connect(MicroMsg_db_path)

    sql = ("SELECT A.ChatRoomName,A.UserNameList, A.DisplayNameList, B.Announcement,B.AnnouncementEditor "
           "FROM ChatRoom A,ChatRoomInfo B "
           "where A.ChatRoomName==B.ChatRoomName "
           "ORDER BY A.ChatRoomName ASC;")

    result = execute_sql(db, sql)
    db.close()
    for row in result:
        # 获取用户名、昵称、备注和聊天记录数量
        ChatRoomName, UserNameList, DisplayNameList, Announcement, AnnouncementEditor = row
        UserNameList = UserNameList.split("^G")
        DisplayNameList = DisplayNameList.split("^G")
        rooms.append(
            {"ChatRoomName": ChatRoomName, "UserNameList": UserNameList, "DisplayNameList": DisplayNameList,
             "Announcement": Announcement, "AnnouncementEditor": AnnouncementEditor})
    return rooms


def get_msg_list(MSG_db_path, selected_talker="", start_index=0, page_size=500):
    """
    获取聊天记录列表
    :param MSG_db_path: MSG.db 文件路径
    :param selected_talker: 选中的聊天对象 wxid
    :param start_index: 开始索引
    :param page_size: 每页数量
    :return: 聊天记录列表
    """

    # 连接 MSG_ALL.db 数据库，并执行查询
    db1 = sqlite3.connect(MSG_db_path)
    cursor1 = db1.cursor()
    if selected_talker:
        sql = (
            "SELECT localId, IsSender, StrContent, StrTalker, Sequence, Type, SubType,CreateTime,MsgSvrID,DisplayContent,CompressContent,BytesExtra "
            "FROM MSG WHERE StrTalker=? "
            "ORDER BY CreateTime ASC LIMIT ?,?")
        cursor1.execute(sql, (selected_talker, start_index, page_size))
    else:
        sql = (
            "SELECT localId, IsSender, StrContent, StrTalker, Sequence, Type, SubType,CreateTime,MsgSvrID,DisplayContent,CompressContent,BytesExtra "
            "FROM MSG ORDER BY CreateTime ASC LIMIT ?,?")
        cursor1.execute(sql, (start_index, page_size))
    result1 = cursor1.fetchall()
    cursor1.close()
    db1.close()

    data = []
    for row in result1:
        localId, IsSender, StrContent, StrTalker, Sequence, Type, SubType, CreateTime, MsgSvrID, DisplayContent, CompressContent, BytesExtra = row
        CreateTime = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(CreateTime))

        type_id = (Type, SubType)
        type_name = get_type_name(type_id)

        content = {"src": "", "msg": StrContent}

        if type_id == (1, 0):  # 文本
            content["msg"] = StrContent

        elif type_id == (3, 0):  # 图片
            BytesExtra = read_BytesExtra(BytesExtra)
            BytesExtra = str(BytesExtra)
            match = re.search(r"FileStorage(.*?)'", BytesExtra)
            if match:
                img_path = match.group(0).replace("'", "")
                img_path = [i for i in img_path.split("\\") if i]
                img_path = os.path.join(*img_path)
                content["src"] = img_path
            else:
                content["src"] = ""
            content["msg"] = "图片"
        elif type_id == (34, 0):
            tmp_c = parse_xml_string(StrContent)
            voicelength = tmp_c.get("voicemsg", {}).get("voicelength", "")
            transtext = tmp_c.get("voicetrans", {}).get("transtext", "")
            if voicelength.isdigit():
                voicelength = int(voicelength) / 1000
                voicelength = f"{voicelength:.2f}"
            content["msg"] = f"语音时长：{voicelength}秒\n翻译结果：{transtext}" if transtext else f"语音时长：{voicelength}秒"
            content["src"] = os.path.join("audio", f"{StrTalker}", f"{CreateTime}_{MsgSvrID}.wav")
        elif type_id == (43, 0):  # 视频
            BytesExtra = read_BytesExtra(BytesExtra)
            BytesExtra = str(BytesExtra)
            match = re.search(r"FileStorage(.*?)'", BytesExtra)
            if match:
                video_path = match.group(0).replace("'", "")
                content["src"] = video_path
            else:
                content["src"] = ""
            content["msg"] = "视频"

        elif type_id == (47, 0):  # 动画表情
            content_tmp = parse_xml_string(StrContent)
            cdnurl = content_tmp.get("emoji", {}).get("cdnurl", "")
            # md5 = content_tmp.get("emoji", {}).get("md5", "")
            if cdnurl:
                content = {"src": cdnurl, "msg": "表情"}

        elif type_id[0] == 49:
            BytesExtra = read_BytesExtra(BytesExtra)
            url = match_BytesExtra(BytesExtra)
            content["src"] = url
            content["msg"] = type_name

        elif type_id == (50, 0):  # 语音通话
            BytesExtra = read_BytesExtra(BytesExtra)

        # elif type_id == (10000, 0):
        #     content["msg"] = StrContent
        # elif type_id == (10000, 4):
        #     content["msg"] = StrContent
        # elif type_id == (10000, 8000):
        #     content["msg"] = StrContent

        talker = "未知"
        if IsSender == 1:
            talker = "我"
        else:
            if StrTalker.endswith("@chatroom"):
                bytes_extra = read_BytesExtra(BytesExtra)
                if bytes_extra:
                    try:
                        talker = bytes_extra['3'][0]['2'].decode('utf-8', errors='ignore')
                    except:
                        pass
            else:
                talker = StrTalker

        row_data = {"MsgSvrID": MsgSvrID, "type_name": type_name, "is_sender": IsSender, "talker": talker,
                    "room_name": StrTalker, "content": content, "CreateTime": CreateTime}
        data.append(row_data)
    return data


def get_chat_count(MSG_db_path: [str, list], username: str = ""):
    """
    获取聊天记录数量
    :param MSG_db_path: MSG.db 文件路径
    :return: 聊天记录数量列表
    """
    if username:
        sql = f"SELECT StrTalker,COUNT(*) FROM MSG WHERE StrTalker='{username}';"
    else:
        sql = f"SELECT StrTalker, COUNT(*) FROM MSG GROUP BY StrTalker ORDER BY COUNT(*) DESC;"
    db1 = sqlite3.connect(MSG_db_path)
    result = execute_sql(db1, sql)

    chat_counts = {}
    for row in result:
        username, chat_count = row
        chat_counts[username] = chat_count
    return chat_counts


def export_csv(username, outpath, MSG_ALL_db_path, page_size=5000):
    if not os.path.exists(outpath):
        outpath = os.path.join(os.getcwd(), "export" + os.sep + username)
        if not os.path.exists(outpath):
            os.makedirs(outpath)
    count = get_chat_count(MSG_ALL_db_path, username)
    chatCount = count.get(username, 0)
    if chatCount == 0:
        return False, "没有聊天记录"
    for i in range(0, chatCount, page_size):
        start_index = i
        data = get_msg_list(MSG_ALL_db_path, username, start_index, page_size)
        if len(data) == 0:
            break
        save_path = os.path.join(outpath, f"{username}_{int(i / page_size)}.csv")
        with open(save_path, "w", encoding="utf-8") as f:
            f.write("MsgSvrID,type_name,is_sender,talker,room_name,content,CreateTime\n")
            for row in data:
                MsgSvrID = row.get("MsgSvrID", "")
                type_name = row.get("type_name", "")
                is_sender = row.get("is_sender", "")
                talker = row.get("talker", "")
                room_name = row.get("room_name", "")
                content = row.get("content", "")
                CreateTime = row.get("CreateTime", "")

                content = json.dumps(content, ensure_ascii=False)

                f.write(f"{MsgSvrID},{type_name},{is_sender},{talker},{room_name},{content},{CreateTime}\n")
    return True, f"导出成功: {outpath}"


def export_html(user, outpath, MSG_ALL_db_path, MediaMSG_all_db_path, FileStorage_path, page_size=500):
    name_save = user.get("remark", user.get("nickname", user.get("username", "")))
    username = user.get("username", "")

    chatCount = user.get("chat_count", 0)
    if chatCount == 0:
        return False, "没有聊天记录"

    for i in range(0, chatCount, page_size):
        start_index = i
        data = load_chat_records(username, start_index, page_size, user, MSG_ALL_db_path, MediaMSG_all_db_path,
                                 FileStorage_path)
        if len(data) == 0:
            break
        save_path = os.path.join(outpath, f"{name_save}_{int(i / page_size)}.html")
        with open(save_path, "w", encoding="utf-8") as f:
            f.write(render_template("chat.html", msgs=data))
    return True, f"导出成功{outpath}"


def export(username, outpath, MSG_ALL_db_path, MicroMsg_db_path, MediaMSG_all_db_path, FileStorage_path):
    if not os.path.exists(outpath):
        outpath = os.path.join(os.getcwd(), "export" + os.sep + username)
        if not os.path.exists(outpath):
            os.makedirs(outpath)

    USER_LIST = get_user_list(MSG_ALL_db_path, MicroMsg_db_path)
    user = list(filter(lambda x: x["username"] == username, USER_LIST))

    if username and len(user) > 0:
        user = user[0]
        return export_html(user, outpath, MSG_ALL_db_path, MediaMSG_all_db_path, FileStorage_path)
